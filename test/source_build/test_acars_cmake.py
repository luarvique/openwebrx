from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which("cmake") and shutil.which("git"), "requires cmake and git")
class ProvenanceTests(unittest.TestCase):
    def test_version_comes_from_dependency_not_callers_cwd(self):
        patch = (ROOT / "build/patches/acarsdec/0001-source-version-provenance.patch").read_text()
        added = "\n".join(line[1:] for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++"))
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            src, other = base / "acarsdec", base / "unrelated-repo"
            src.mkdir(); other.mkdir()
            for directory in (src, other):
                subprocess.run(["git", "init", "-q", str(directory)], check=True)
                (directory / "fixture").write_text(str(directory))
                subprocess.run(["git", "-C", str(directory), "add", "fixture"], check=True)
                subprocess.run(["git", "-C", str(directory), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"], check=True)
            expected = subprocess.check_output(["git", "-C", str(src), "rev-parse", "--short=12", "HEAD"], text=True).strip()
            (src / "acarsdec.h").write_text('#define ACARSDEC_VERSION "4.4.1"\n#define ACARSDEC_VERSION VERSION\n')
            script = src / "test.cmake"
            script.write_text('set(CMAKE_CURRENT_SOURCE_DIR "'+str(src)+'")\n'+added+'\nmessage(STATUS "CHECK=${VERSION}")\n')
            result = subprocess.run(["cmake", "-P", str(script)], cwd=other, check=True, capture_output=True, text=True)
            self.assertIn("CHECK=4.4.1+git." + expected, result.stdout)


if __name__ == "__main__":
    unittest.main()
