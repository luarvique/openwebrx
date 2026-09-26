import importlib.util
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("source_runtime", ROOT / "build/source_runtime.py")
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


class Config(dict):
    stored = False
    def store(self):
        self.stored = True


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.prefix = Path(self.tmp.name)
        self.args = SimpleNamespace(prefix=str(self.prefix), logs=str(self.prefix / "logs"),
                                    model=str(self.prefix / "model.bin"), model_name="tiny",
                                    speech_url="http://127.0.0.1:8074/inference", jobs=2)
        self.cfg = Config(digital_voice_codecserver="", speech_url="")
        self.services = r.Services(self.args, self.cfg)
        self.addCleanup(self.services.close)

    def make_inputs(self):
        (self.prefix / "lib/codecserver").mkdir(parents=True)
        (self.prefix / "lib/codecserver/libmbelib.so").write_text("fixture")
        (self.prefix / "bin").mkdir()
        for name in ("codecserver", "whisper-server"):
            p = self.prefix / "bin" / name
            p.write_text("#!/bin/sh\nexit 0\n")
            p.chmod(0o755)
        Path(self.args.model).write_bytes(b"test model data")

    def test_configure_empty_settings(self):
        self.make_inputs()
        self.services.configure()
        self.assertEqual(self.cfg["digital_voice_codecserver"], str(self.services.codec_socket))
        self.assertEqual(self.cfg["speech_url"], self.args.speech_url)
        self.assertTrue(self.cfg.stored)
        self.assertEqual(self.services.run_dir.stat().st_mode & 0o777, 0o700)
        self.assertIn("driver=mbelib", self.services.codec_config.read_text())

    def test_preserve_user_settings(self):
        self.make_inputs()
        self.cfg.update(digital_voice_codecserver="radio.example:1073", speech_url="https://speech.example/inference")
        self.services.configure()
        self.assertEqual(self.cfg["digital_voice_codecserver"], "radio.example:1073")
        self.assertEqual(self.cfg["speech_url"], "https://speech.example/inference")
        self.assertFalse(self.cfg.stored)

    def test_no_model_does_not_enable_speech(self):
        self.services.configure()
        self.assertEqual(self.cfg["speech_url"], "")

    def test_explicit_none_does_not_enable_local_speech(self):
        self.make_inputs()
        self.args.model_name = "none"
        self.services.configure()
        self.assertEqual(self.cfg["speech_url"], "")

    def test_remote_does_not_need_local_binary(self):
        self.cfg.update(digital_voice_codecserver="remote", speech_url="https://remote/inference")
        self.services.start()
        self.assertEqual(self.services.children, [])
        self.assertEqual(self.services.errors, [])

    def test_non_socket_refused(self):
        self.make_inputs()
        self.services.configure()
        self.services.codec_socket.write_text("do not delete")
        with self.assertRaises(RuntimeError):
            self.services.start_codec()
        self.assertEqual(self.services.codec_socket.read_text(), "do not delete")

    def test_existing_listener_not_owned(self):
        self.make_inputs()
        self.services.configure()
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(self.services.codec_socket))
            server.listen()
            self.services.start_codec()
            self.services.close()
            self.assertEqual(self.services.children, [])
            self.assertTrue(self.services.codec_socket.exists())

    def test_symlink_runtime_directory_rejected(self):
        target = self.prefix / "target"
        target.mkdir()
        link = self.prefix / "link"
        link.symlink_to(target)
        with self.assertRaises(RuntimeError):
            r.private_directory(link)

    def test_close_only_owned_process(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        self.services.children.append(child)
        self.services.close()
        self.assertIsNotNone(child.poll())
        self.assertEqual(self.services.children, [])

    def test_health_is_http_model_readiness(self):
        response = Mock()
        response.status = 200
        response.read.return_value = b'{"status":"ok"}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = Mock()
        opener.open.return_value = response
        with patch.object(r.urllib.request, "build_opener", return_value=opener):
            self.assertTrue(r.whisper_health("http://127.0.0.1:8074/inference"))
            opener.open.assert_called_once_with("http://127.0.0.1:8074/health", timeout=1)

    def test_wrong_service_is_not_whisper(self):
        response = Mock()
        response.status = 200
        response.read.return_value = b'{"status":"loading"}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = Mock()
        opener.open.return_value = response
        with patch.object(r.urllib.request, "build_opener", return_value=opener):
            self.assertFalse(r.whisper_health("http://127.0.0.1:8074/inference"))


if __name__ == "__main__":
    unittest.main()
