#!/usr/bin/env python3
"""Private source-install services and diagnostics. Never installs packages.

Only child processes started here are stopped here. Existing configured remote
services and pre-existing CodecServer configuration files are not overwritten.
"""
import argparse
from contextlib import ExitStack, contextmanager
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit


def config_value(config, key):
    try:
        return config[key] or ""
    except KeyError:
        return ""


def private_directory(path):
    """Do not follow an attacker-created runtime directory symlink."""
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise RuntimeError(f"Unsafe runtime directory: {path}")
    path.chmod(0o700)


def socket_listening(path):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.2)
        try:
            connection.connect(str(path))
            return True
        except OSError:
            return False


def whisper_health(inference_url):
    url = urlsplit(inference_url)
    if url.scheme not in ("http", "https"):
        return False
    path = url.path.rsplit("/", 1)[0] + "/health"
    health_url = urlunsplit((url.scheme, url.netloc, path, "", ""))
    # Loopback must not be sent through a user's HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if url.hostname in ("127.0.0.1", "::1", "localhost") else urllib.request.build_opener()
    try:
        with opener.open(health_url, timeout=1) as response:
            return response.status == 200 and json.load(response).get("status") == "ok"
    except (OSError, ValueError, urllib.error.URLError):
        return False


class Services:
    def __init__(self, args, config):
        self.args = args
        self.config = config
        self.prefix = Path(args.prefix).resolve()
        self.logs = Path(args.logs)
        self.run_dir = self.prefix / "var/run/openwebrx-source"
        self.codec_socket = self.run_dir / "codecserver.sock"
        self.codec_config = self.run_dir / "codecserver.conf"
        self.children = []
        self.errors = []
        self.local_speech_ready = None

    def warn(self, message):
        self.errors.append(message)
        print(f"[WARN] {message}", file=sys.stderr)

    def configure(self):
        """Populate only empty application settings, never a user's remote URL."""
        changed = False
        module = self.prefix / "lib/codecserver/libmbelib.so"
        binary = self.prefix / "bin/codecserver"
        if module.is_file() and os.access(binary, os.X_OK):
            private_directory(self.run_dir)
            if len(os.fsencode(self.codec_socket)) >= 108:
                raise RuntimeError("Private CodecServer socket path exceeds Linux's Unix socket limit; choose a shorter prefix")
            self.codec_config.write_text(
                "# Managed by OpenWebRX source build; not the user's codecserver.conf.\n"
                "[server:unixdomainsockets]\n"
                f"socket={self.codec_socket}\n\n"
                "[device:mbelib]\ndriver=mbelib\nunvoiced_quality=3\n"
            )
            if not config_value(self.config, "digital_voice_codecserver"):
                self.config["digital_voice_codecserver"] = str(self.codec_socket)
                changed = True
        model = Path(self.args.model)
        if (self.args.model_name != "none" and model.is_file() and model.stat().st_size > 0
                and os.access(self.prefix / "bin/whisper-server", os.X_OK)
                and not config_value(self.config, "speech_url")):
            self.config["speech_url"] = self.args.speech_url
            changed = True
        if changed:
            self.config.store()

    def spawn(self, name, command):
        self.logs.mkdir(parents=True, exist_ok=True)
        with (self.logs / f"{name}-runtime.log").open("w") as log:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
                                       stderr=subprocess.STDOUT)
        self.children.append(process)
        return process

    @contextmanager
    def startup_lock(self):
        private_directory(self.run_dir)
        with (self.run_dir / "startup.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def start_codec(self):
        with self.startup_lock():
            self._start_codec()

    def _start_codec(self):
        configured = config_value(self.config, "digital_voice_codecserver")
        if configured != str(self.codec_socket):
            if not configured:
                self.warn("AMBE is not configured: build mbelib and codecserver-mbelib first")
            # An explicitly configured server belongs to the user, not this runner.
            return
        if socket_listening(self.codec_socket):
            return
        if os.path.lexists(self.codec_socket):
            info = self.codec_socket.lstat()
            if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
                raise RuntimeError(f"Refusing to replace {self.codec_socket}")
            self.codec_socket.unlink()  # stale, owned socket inside our 0700 directory
        child = self.spawn("codecserver", [str(self.prefix / "bin/codecserver"), "-c", str(self.codec_config)])
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and child.poll() is None:
            if socket_listening(self.codec_socket):
                return
            time.sleep(0.1)
        self.warn(f"Private CodecServer did not become ready; see {self.logs / 'codecserver-runtime.log'}")

    def start_whisper(self):
        with self.startup_lock():
            self._start_whisper()

    def _start_whisper(self):
        configured = config_value(self.config, "speech_url")
        if configured != self.args.speech_url:
            if not configured:
                self.warn("Speech is not configured: no local model, or OWRX_WHISPER_MODEL=none; a remote speech_url is also supported")
            return
        self.local_speech_ready = whisper_health(configured)
        if self.local_speech_ready:
            return
        model = Path(self.args.model)
        binary = self.prefix / "bin/whisper-server"
        if not os.access(binary, os.X_OK) or not model.is_file():
            self.warn("Local Whisper needs both whisper-server and its model file")
            return
        address = urlsplit(configured)
        if address.hostname != "127.0.0.1" or address.port is None:
            raise RuntimeError("Managed Whisper must bind explicitly to 127.0.0.1")
        # A random open TCP port is not evidence of a ready Whisper model.
        with socket.socket() as test:
            test.settimeout(0.2)
            occupied = test.connect_ex(("127.0.0.1", address.port)) == 0
        if occupied:
            self.warn("Whisper port is occupied but /health is not ready; not replacing the existing service")
            return
        child = self.spawn("whisper", [str(binary), "-m", str(model), "-t", str(min(self.args.jobs, 4)),
                                      "-l", "auto", "--host", "127.0.0.1", "--port", str(address.port)])
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and child.poll() is None:
            if whisper_health(configured):
                self.local_speech_ready = True
                return
            time.sleep(0.2)
        self.warn(f"Whisper model did not become ready; see {self.logs / 'whisper-runtime.log'}")

    def start(self):
        self.configure()
        self.start_codec()
        self.start_whisper()

    def close(self):
        # No pkill, global /tmp socket deletion, or stopping another invocation.
        for child in reversed(self.children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
        self.children.clear()


def print_skips(state):
    files = sorted(Path(state).glob("*.skip"))
    if files:
        print("\nExternal/platform prerequisites (not successful builds):")
        for path in files:
            print(f"  {path.stem:24} {path.read_text().strip()}")


def report(args, services):
    from owrx.feature import FeatureCache, FeatureDetector
    FeatureCache.sharedInstance = None
    result = FeatureDetector().feature_report()
    # Core's speech probe traditionally checks configuration only. The source
    # report additionally refuses PASS for our local server unless /health is OK.
    if services.local_speech_ready is False:
        result["speech"]["available"] = False
        result["speech"]["requirements"]["whisper"]["available"] = False
        result["speech"]["requirements"]["whisper"]["enabled"] = False
    for name, entry in sorted(result.items()):
        missing = [key for key, value in entry["requirements"].items() if not value["available"]]
        print(f"{name:28} {'PASS' if entry['available'] else 'MISS'}" +
              ("  missing: " + ", ".join(missing) if missing else ""))
    Path(args.logs).mkdir(parents=True, exist_ok=True)
    (Path(args.logs) / "feature-report.json").write_text(json.dumps(result, indent=2) + "\n")
    print_skips(args.state)
    return result


def diagnostics(args, services):
    from owrx.feature_probes import run_probe
    outputs = []
    for command in [("SoapySDRUtil", "--info"), ("soapy_connector", "--version"), ("acarsdec", "-h")]:
        result = run_probe(command)
        outputs.append(f"===== {' '.join(command)} (exit={result.returncode}) =====\n{result.error}\n{result.output}")
    for name in ("codecserver", "whisper"):
        path = Path(args.logs) / f"{name}-runtime.log"
        if path.is_file():
            outputs.append(f"===== {name} runtime (last 60 lines) =====\n" +
                           "\n".join(path.read_text(errors="replace").splitlines()[-60:]))
    text = "\n".join(outputs) + "\n"
    print(text)
    (Path(args.logs) / "optional-diagnostics.txt").write_text(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("configure", "report", "diagnostics", "run"))
    for key in ("root", "prefix", "venv", "config", "logs", "state", "model", "model-name", "speech-url"):
        parser.add_argument("--" + key, required=True)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args(argv)
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    sys.path.insert(0, args.root)
    from owrx.config.core import CoreConfig
    CoreConfig.load(Path(args.config))
    from owrx.config import Config
    services = Services(args, Config.get())
    with ExitStack() as stack:
        stack.callback(services.close)
        def interrupted(*_):
            raise KeyboardInterrupt()
        previous = signal.signal(signal.SIGTERM, interrupted)
        stack.callback(signal.signal, signal.SIGTERM, previous)
        if args.action == "configure":
            services.configure()
            return 0
        services.start()
        if args.action == "run":
            child = subprocess.Popen([str(Path(args.venv) / "bin/openwebrx"), "-c", args.config, "--debug"], cwd=args.root)
            services.children.append(child)
            return child.wait()
        report(args, services)
        if args.action == "diagnostics":
            diagnostics(args, services)
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"[FAIL] runtime integration: {exc}", file=sys.stderr)
        raise SystemExit(1)
