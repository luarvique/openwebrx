"""Offline source-build cache, install-artifact, and runtime regressions."""
import importlib.util
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from owrx import feature_probes as probes


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


component = load_script("installed_components", "build/check-component.py")
runtime = load_script("runtime_validation", "build/source_runtime.py")


class InstallTests(unittest.TestCase):
    def test_empty_factory_explanation_is_not_an_identifier(self):
        self.assertEqual(probes.parse_soapy_factories("Available factories... No factories found!\n"), set())

    @patch.object(component, "cli_output")
    def test_acars_version_requirement(self, output):
        for banner, accepted in (("Acarsdec 4.4.1+git.dfd62e2", True),
                                 ("Acarsdec 3.0", False), ("Acarsdec dfd62e2", False)):
            output.return_value = banner
            if accepted:
                component.validate("acarsdec", Path("/unused"))
            else:
                with self.assertRaises(RuntimeError):
                    component.validate("acarsdec", Path("/unused"))

    def test_absent_binary_is_not_success(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                component.validate("tetrarx", Path(d))

    def test_loader_error_is_not_success(self):
        with tempfile.TemporaryDirectory() as d:
            binary = Path(d) / "loader"
            binary.write_text("#!/bin/sh\necho loader-error\nexit 127\n")
            binary.chmod(0o755)
            with self.assertRaises(RuntimeError):
                component.cli_output(binary)

    @patch.object(component, "run_probe")
    def test_mbelib_plugin_must_load(self, run):
        run.return_value = probes.ProbeResult((), 127, "undefined symbol")
        with self.assertRaises(RuntimeError):
            component.validate("codecserver-mbelib", Path("/prefix"))
        self.assertEqual(run.call_args.args[0][-1], "/prefix/lib/codecserver/libmbelib.so")
        run.return_value = probes.ProbeResult((), 0, "")
        component.validate("codecserver-mbelib", Path("/prefix"))

    @patch.object(component, "cli_output", return_value="whisper-server help")
    def test_missing_whisper_model_invalidates_stamp(self, output):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                component.validate("whisper", Path(d), "tiny")
            component.validate("whisper", Path(d), "none")


def factory_test(name, factory):
    def test(self):
        text = "Available factories... " + factory + "\n"
        result = probes.ProbeResult(("SoapySDRUtil", "--info"), 0, text)
        with patch.object(component, "soapy_registry", return_value=(probes.parse_soapy_factories(text), result)):
            component.validate(name, Path("/unused"))
        with patch.object(component, "soapy_registry", return_value=(set(), result)):
            with self.assertRaises(RuntimeError):
                component.validate(name, Path("/unused"))
    return test


for _name, _factory in component.FACTORIES.items():
    setattr(InstallTests, "test_installed_" + _name, factory_test(_name, _factory))


class BuildStateTests(unittest.TestCase):
    def shell(self, body):
        with tempfile.TemporaryDirectory() as d:
            script = '''source "$1/build-linux.sh"
STATE="$2/state"; LOG="$2/logs"; mkdir -p "$STATE" "$LOG"
validate_component(){ return 0; }
''' + body
            return subprocess.run(["bash", "-c", script, "tests", str(ROOT), d], text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15)

    def check(self, body):
        result = self.shell(body)
        self.assertEqual(result.returncode, 0, result.stdout)
        return result.stdout

    def test_recipe_failure_does_not_continue_or_leave_stamp(self):
        self.check('''echo old >"$STATE/test.ok"
recipe(){ false; echo wrong >"$STATE/reached"; }
step test 0 recipe
[[ ! -f "$STATE/test.ok" && ! -f "$STATE/reached" ]]
grep -qx test "$STATE/optional-failures.txt"
''')

    def test_skip_report_visible_without_failures(self):
        output = self.check('''step skipped 0 skip_component skipped "missing vendor SDK"
[[ ! -f "$STATE/skipped.ok" ]]
failure_report
''')
        self.assertIn("none recorded", output)
        self.assertIn("missing vendor SDK", output)

    def test_success_clears_only_its_own_prior_failure(self):
        self.check('''printf 'test\\nother\\n' >"$STATE/optional-failures.txt"
step test 0 true
[[ "$(cat "$STATE/optional-failures.txt")" == other ]]
[[ -s "$STATE/test.ok" ]]
''')

    def test_missing_artifact_invalidates_success_stamp(self):
        self.check('''stamp test >"$STATE/test.ok"
validate_component(){ [[ -f "$STATE/artifact" ]]; }
repair(){ touch "$STATE/artifact"; }
step test 0 repair
[[ -f "$STATE/artifact" && -f "$STATE/test.ok" ]]
''')

    def test_post_install_validation_records_failure(self):
        self.check('''validate_component(){ echo "not installed"; return 1; }
step test 0 true
[[ ! -f "$STATE/test.ok" ]]
grep -qx test "$STATE/optional-failures.txt"
''')

    def test_strict_failure_recorded_before_exit(self):
        result = self.shell('''STRICT=1
trap 'grep -qx test "$STATE/optional-failures.txt" && echo RECORDED' EXIT
step test 0 false
''')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("RECORDED", result.stdout)

    def test_changed_patch_invalidates_stamp(self):
        self.check('''ROOT="$2/fixture"; mkdir -p "$ROOT/build/patches/test"
echo first >"$ROOT/build/patches/test/fix.patch"
a="$(stamp test)"
echo second >"$ROOT/build/patches/test/fix.patch"
[[ "$a" != "$(stamp test)" ]]
''')

    def test_runtime_and_reports_do_not_install_python_packages(self):
        script = (ROOT / "build-linux.sh").read_text()
        env_function = script.split("activate_env(){", 1)[1].split("\n}", 1)[0]
        self.assertNotIn("pip install", env_function)
        self.assertNotIn(': >"$STATE/optional-failures.txt"', script)


class RuntimeValidationTests(unittest.TestCase):
    def test_malformed_or_oversized_health_response_is_not_ready(self):
        response = Mock()
        response.status = 200
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = Mock()
        opener.open.return_value = response
        with patch.object(runtime.urllib.request, "build_opener", return_value=opener):
            for body in (b"[]", b"null", b'"not-an-object"', b'<html>another service</html>'):
                response.read.return_value = body
                self.assertFalse(runtime.whisper_health("http://127.0.0.1:8074/inference"))
            response.read.assert_called_with(4096)

    def test_explicit_no_model_does_not_start_a_local_server(self):
        with tempfile.TemporaryDirectory() as d:
            prefix = Path(d)
            args = SimpleNamespace(prefix=d, logs=d, model=str(prefix / "model"), model_name="none",
                                   speech_url="http://127.0.0.1:8074/inference", jobs=2)
            service = runtime.Services(args, {"speech_url": args.speech_url})
            with patch.object(runtime, "whisper_health", return_value=False), patch.object(service, "spawn") as spawn:
                service.start_whisper()
                spawn.assert_not_called()
                self.assertFalse(service.local_speech_ready)


class DependencyPatchTests(unittest.TestCase):
    def test_sddc_requires_soapy_instead_of_silent_skip(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "SoapySDDC/CMakeLists.txt"
            source.parent.mkdir()
            source.write_text('# SoapySDR Lib\n\nfind_package(SoapySDR CONFIG)\n\nif (SoapySDR_FOUND)\n\n    include_directories("." "../Core")\n')
            patch_file = ROOT / "build/patches/extio_sddc/0001-require-soapy-for-source-build.patch"
            subprocess.run(["git", "apply", "--check", str(patch_file)], cwd=d, check=True)
            subprocess.run(["git", "apply", str(patch_file)], cwd=d, check=True)
            self.assertIn("find_package(SoapySDR CONFIG REQUIRED)", source.read_text())
            subprocess.run(["git", "apply", "--reverse", "--check", str(patch_file)], cwd=d, check=True)

class NativeSocketTests(unittest.TestCase):
    def apply(self, directory, patch_path):
        result = subprocess.run(["git", "apply", "--check", str(ROOT / patch_path)], cwd=directory,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        subprocess.run(["git", "apply", str(ROOT / patch_path)], cwd=directory, check=True)
        subprocess.run(["git", "apply", "--reverse", "--check", str(ROOT / patch_path)], cwd=directory, check=True)

    @unittest.skipUnless(shutil.which("g++"), "C++ compiler not installed")
    def test_patched_native_unix_connection_uses_requested_socket(self):
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d)
            source = directory / "src/mbe_synthesizer/mbe_synthesizer.cpp"
            source.parent.mkdir(parents=True)
            source.write_text((ROOT / "test/source_build/fixtures/digiham-connect.cpp").read_text())
            self.apply(directory, "build/patches/digiham/0001-honor-codecserver-socket-path.patch")
            program = directory / "test.cpp"
            program.write_text('''#include <sys/un.h>
#include <sys/socket.h>
#include <unistd.h>
#include <cstring>
#include <cerrno>
#include <stdexcept>
#include <string>
using ConnectionError = std::runtime_error;
struct MbeSynthesizer { static int connect(const std::string& path); };
''' + source.read_text() + '''
int main(int argc, char** argv) {
    try { int fd = MbeSynthesizer::connect(argv[1]); ::close(fd); return 0; }
    catch (const ConnectionError&) { return 2; }
}
''')
            binary = directory / "test"
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", str(program), "-o", str(binary)], check=True, capture_output=True)
            path = str(directory / "private.sock")
            with socket.socket(socket.AF_UNIX) as server:
                server.bind(path)
                server.listen(1)
                self.assertEqual(subprocess.run([str(binary), path], timeout=5).returncode, 0)
            self.assertEqual(subprocess.run([str(binary), "x" * 108], timeout=5).returncode, 2)
            self.assertEqual(subprocess.run([str(binary), str(directory / "missing")], timeout=5).returncode, 2)


if __name__ == "__main__":
    unittest.main()
