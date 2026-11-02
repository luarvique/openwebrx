from types import ModuleType
from unittest import TestCase
from unittest.mock import patch
import sys

from owrx.feature import FeatureDetector
from owrx.modes import Modes


class NativeFeatureTest(TestCase):
    def testOldPycsdrHidesOnlyModbus(self):
        module = ModuleType("pycsdr.modules")
        with patch.dict(sys.modules, {"pycsdr.modules": module}):
            self.assertFalse(FeatureDetector().has_csdr_fsk_uart())
            mode = next(m for m in Modes.getModes() if m.modulation == "modbus")
            self.assertEqual(mode.requirements, ["modbus"])
            self.assertNotIn("csdr_fsk_uart", FeatureDetector.features["core"])

    def testNativeDecoderCapability(self):
        module = ModuleType("pycsdr.modules")
        module.FskUartDecoder = object
        with patch.dict(sys.modules, {"pycsdr.modules": module}):
            self.assertTrue(FeatureDetector().has_csdr_fsk_uart())
