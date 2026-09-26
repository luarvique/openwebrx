"""No radio, native extensions or network required."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("native_probes", ROOT / "owrx/feature_probes.py")
p = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = p
spec.loader.exec_module(p)


class SoapyTests(unittest.TestCase):
    def test_registry(self):
        text = "Module found: /prefix/libSDDCSupport.so\nAvailable factories... SDDC, airspy, soapyMiri, rtlsdr\nAvailable converters...\n"
        self.assertEqual(p.parse_soapy_factories(text), {"sddc", "airspy", "soapymiri", "rtlsdr"})

    def test_ansi_and_crlf(self):
        self.assertEqual(p.parse_soapy_factories("\x1b[32m  Available factories... lime, uhd\x1b[0m\r\n"), {"lime", "uhd"})

    def test_empty_registry(self):
        self.assertEqual(p.parse_soapy_factories("Available factories...\nAvailable converters...\n"), set())

    def test_module_is_not_a_factory(self):
        self.assertIsNone(p.parse_soapy_factories("Module found: /prefix/librtlsdrSupport.so\n"))
        text = "Module found: /prefix/librtlsdrSupport.so\nLoader error: bad ABI\nAvailable factories... airspy\n"
        self.assertNotIn("rtlsdr", p.parse_soapy_factories(text))

    def test_nonzero_exit_rejected(self):
        with patch.object(p, "run_probe", return_value=p.ProbeResult(("SoapySDRUtil", "--info"), 127, "Available factories... rtlsdr\n")):
            self.assertEqual(p.soapy_registry()[0], set())

    def test_no_hardware_probe(self):
        with patch.object(p, "run_probe", return_value=p.ProbeResult(("SoapySDRUtil", "--info"), 0, "Available factories... rtlsdr\n")) as run:
            self.assertIn("rtlsdr", p.soapy_registry()[0])
            run.assert_called_once_with(("SoapySDRUtil", "--info"))

    def test_missing_binary(self):
        with patch.object(p.subprocess, "run", side_effect=FileNotFoundError("not found")):
            result = p.run_probe(("missing",))
            self.assertIsNone(result.returncode)
            self.assertIn("not found", result.error)

    def test_timeout_bytes(self):
        exc = subprocess.TimeoutExpired("probe", 15, output=b"partial")
        with patch.object(p.subprocess, "run", side_effect=exc):
            self.assertEqual(p.run_probe(("probe",)).output, "partial")


class AcarsTests(unittest.TestCase):
    def test_versions(self):
        for banner, expected in [("Acarsdec 4.4.1 Copyright", "4.4.1"),
                                 ("Acarsdec v4.4.1-3-gabcdef\n", "4.4.1"),
                                 ("ACARSDEC 4.4.1+git.dfd62e2 Copyright", "4.4.1"),
                                 ("Acarsdec 4 Copyright", "4")]:
            with self.subTest(banner=banner):
                self.assertEqual(p.acars_version(banner), expected)

    def test_hash_not_version(self):
        for banner in ["Acarsdec dfd62e2 Copyright", "Acarsdec 123dead Copyright", "libacars 4.4.1", "usage: acarsdec -h"]:
            self.assertIsNone(p.acars_version(banner))

    def test_help_exit_one(self):
        with patch.object(p, "run_probe", return_value=p.ProbeResult(("acarsdec", "-h"), 1, "Acarsdec 4.4.1 Copyright")):
            self.assertEqual(p.acars_probe()[0], "4.4.1")

    def test_loader_failure(self):
        with patch.object(p, "run_probe", return_value=p.ProbeResult(("acarsdec", "-h"), 127, "Acarsdec 4.4.1 Copyright")):
            self.assertIsNone(p.acars_probe()[0])


if __name__ == "__main__":
    unittest.main()
