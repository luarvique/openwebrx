"""OpenWebRX feature detector with tested native source-install probes.

The unchanged feature catalogue and other probes live in feature_base. Keeping
these command-output parsers separate permits regression tests without SDR
hardware or the native DSP Python extensions.
"""
from distutils.version import LooseVersion
import logging
import sys

from owrx.feature_base import (
    FeatureCache,
    FeatureDetector as _FeatureDetector,
    UnknownFeatureException,
)
from owrx.config import Config
from owrx.feature_probes import acars_probe, soapy_registry, run_probe

logger = logging.getLogger(__name__)


class FeatureDetector(_FeatureDetector):
    def _has_soapy_driver(self, driver):
        # Share a single registry snapshot across this detector's feature report.
        if not hasattr(self, "_native_soapy_registry"):
            self._native_soapy_registry, result = soapy_registry()
            if result.error or result.returncode != 0:
                logger.warning("Soapy factory discovery failed: %s\n%s",
                               result.error or result.returncode, result.output)
        return driver.casefold() in self._native_soapy_registry

    def _has_acarsdec_version(self, required_version):
        version, result = acars_probe()
        if version is None:
            logger.debug("Unable to identify AcarsDec version: %s\n%s",
                         result.error or result.returncode, result.output)
            return False
        return LooseVersion(version) >= required_version

    def has_codecserver_ambe(self):
        # The native client can throw C++ exceptions. Isolate it from the HTTP
        # server and enforce a wall-clock timeout on the AMBE protocol check.
        config = Config.get()
        server = config["digital_voice_codecserver"] if "digital_voice_codecserver" in config else ""
        result = run_probe((sys.executable, "-c",
            "import sys; from digiham.modules import MbeSynthesizer; "
            "sys.exit(0 if MbeSynthesizer.hasAmbe(sys.argv[1]) else 1)",
            server or ""), timeout=15)
        if result.returncode != 0:
            logger.debug("AMBE probe failed: %s\n%s", result.error or result.returncode, result.output)
        return result.returncode == 0

    has_codecserver_ambe.__doc__ = _FeatureDetector.has_codecserver_ambe.__doc__
