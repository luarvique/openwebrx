import subprocess
from functools import reduce
from operator import and_
import re
from distutils.version import LooseVersion, StrictVersion
import inspect
from owrx.config.core import CoreConfig
from owrx.config import Config
import shlex
import os
from datetime import datetime, timedelta

import logging

logger = logging.getLogger(__name__)


class UnknownFeatureException(Exception):
    pass


class FeatureCache(object):
    sharedInstance = None

    @staticmethod
    def getSharedInstance():
        if FeatureCache.sharedInstance is None:
            FeatureCache.sharedInstance = FeatureCache()
        return FeatureCache.sharedInstance

    def __init__(self):
        self.cache = {}
        self.cachetime = timedelta(hours=2)

    def has(self, feature):
        if feature not in self.cache:
            return False
        now = datetime.now()
        if self.cache[feature]["valid_to"] < now:
            return False
        return True

    def get(self, feature):
        return self.cache[feature]["value"]

    def set(self, feature, value):
        valid_to = datetime.now() + self.cachetime
        self.cache[feature] = {"value": value, "valid_to": valid_to}


class FeatureDetector(object):
    features = {
        # core features; we won't start without these
        "core": ["csdr"],
        # different types of sdrs and their requirements
        "rtl_sdr": ["rtl_connector"],
        "rtl_sdr_soapy": ["soapy_connector", "soapy_rtl_sdr"],
        "rtl_tcp": ["rtl_tcp_connector"],
        "sdrplay": ["soapy_connector", "soapy_sdrplay"],
        "mirics": ["soapy_connector", "soapy_mirics"],
        "malahit_rr": ["soapy_connector", "soapy_malahit_rr"],
        "hackrf": ["soapy_connector", "soapy_hackrf"],
        "perseussdr": ["perseustest", "nmux"],
        "airspy": ["soapy_connector", "soapy_airspy"],
        "airspyhf": ["soapy_connector", "soapy_airspyhf"],
        "hydrasdr": ["soapy_connector", "soapy_hydrasdr"],
        "afedri": ["soapy_connector", "soapy_afedri"],
        "lime_sdr": ["soapy_connector", "soapy_lime_sdr"],
        "fifi_sdr": ["alsa", "rockprog", "nmux"],
        "pluto_sdr": ["soapy_connector", "soapy_pluto_sdr"],
        "soapy_remote": ["soapy_connector", "soapy_remote"],
        "uhd": ["soapy_connector", "soapy_uhd"],
        "radioberry": ["soapy_connector", "soapy_radioberry"],
        "fcdpp": ["soapy_connector", "soapy_fcdpp"],
        "bladerf": ["soapy_connector", "soapy_bladerf"],
        "sddc": ["sddc_connector"],
        "sddc_soapy": ["soapy_connector", "soapy_sddc"],
        "hpsdr": ["hpsdr_connector"],
        "runds": ["runds_connector"],
        # optional features and their requirements
        "digital_voice_digiham": ["digiham", "codecserver_ambe"],
        "digital_voice_freedv": ["freedv_rx"],
        "digital_voice_m17": ["m17_demod"],
        "wsjt-x": ["wsjtx"],
        "wsjt-x-2-3": ["wsjtx_2_3"],
        "wsjt-x-2-4": ["wsjtx_2_4"],
        "msk144": ["msk144decoder"],
        "packet": ["direwolf", "aprs_symbols"],
        "pocsag": ["digiham"],
        "js8call": ["js8", "js8py"],
        "drm": ["dream"],
        "dream-2-2": ["dream_2_2"],
        "adsb": ["dump1090"],
        "uat": ["dump978"],
        "ism": ["rtl_433"],
        "hfdl": ["dumphfdl"],
        "vdl2": ["dumpvdl2"],
        "acars": ["acarsdec"],
        "page": ["multimon"],
        "selcall": ["multimon"],
        "eas": ["multimon"],
        "wxsat": ["satdump"],
        "png": ["imagemagick"],
        "rds": ["redsea"],
        "dab": ["csdreti", "dablin"],
        "mqtt": ["paho_mqtt"],
        "hdradio": ["nrsc5"],
        "rigcontrol": ["hamlib"],
        "skimmer": ["csdr_skimmer"],
        "sonde": ["sonde_rs"],
        "mp3": ["lame"],
    }

    def feature_availability(self):
        return {name: self.is_available(name) for name in FeatureDetector.features}

    def feature_report(self):
        def requirement_details(name):
            available = self.has_requirement(name)
            return {
                "available": available,
                # as of now, features are always enabled as soon as they are available. this may change in the future.
                "enabled": available,
                "description": self.get_requirement_description(name),
            }

        def feature_details(name):
            return {
                "available": self.is_available(name),
                "requirements": {name: requirement_details(name) for name in self.get_requirements(name)},
            }

        return {name: feature_details(name) for name in FeatureDetector.features}

    def is_available(self, feature):
        return self.has_requirements(self.get_requirements(feature))

    def get_failed_requirements(self, feature):
        return [req for req in self.get_requirements(feature) if not self.has_requirement(req)]

    def get_requirements(self, feature):
        try:
            return FeatureDetector.features[feature]
        except KeyError:
            raise UnknownFeatureException('Feature "{0}" is not known.'.format(feature))

    def has_requirements(self, requirements):
        passed = True
        for requirement in requirements:
            passed = passed and self.has_requirement(requirement)
        return passed

    def _get_requirement_method(self, requirement):
        methodname = "has_" + requirement
        if hasattr(self, methodname) and callable(getattr(self, methodname)):
            return getattr(self, methodname)
        return None

    def has_requirement(self, requirement):
        cache = FeatureCache.getSharedInstance()
        if cache.has(requirement):
            return cache.get(requirement)

        method = self._get_requirement_method(requirement)
        result = False
        if method is not None:
            result = method()
        else:
            logger.error("detection of requirement {0} not implement. please fix in code!".format(requirement))

        cache.set(requirement, result)
        return result

    def get_requirement_description(self, requirement):
        return inspect.getdoc(self._get_requirement_method(requirement))

    def command_is_runnable(self, command, expected_result=None):
        tmp_dir = CoreConfig().get_temporary_directory()
        cmd = shlex.split(command)
        env = os.environ.copy()
        # prevent X11 programs from opening windows if called from a GUI shell
        env.pop("DISPLAY", None)
        try:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=tmp_dir,
                env=env,
            )
            while True:
                try:
                    rc = process.wait(10)
                    break
                except subprocess.TimeoutExpired:
                    logger.warning("feature check command \"%s\" did not return after 10 seconds!", command)
                    process.kill()

            if expected_result is None:
                return rc != 32512
            else:
                return rc == expected_result
        except FileNotFoundError:
            return False

    def has_csdr(self):
        """
        OpenWebRX uses the demodulator and pipeline tools provided by the
        [CSDR](https://github.com/jketterl/csdr) project. In addition, the
        [PyCSDR](https://github.com/jketterl/pycsdr) must be installed to
        provide CSDR Python bindings. The `python3-csdr` package, found in
        the OpenWebRX repositories, should be all you need. Do not forget
        to restart OpenWebRX after installing this package.
        """
        required_version = LooseVersion("0.18.0")

        try:
            from pycsdr.modules import csdr_version
            from pycsdr.modules import version as pycsdr_version

            return (
                LooseVersion(csdr_version) >= required_version and
                LooseVersion(pycsdr_version) >= required_version
            )
        except ImportError:
            return False

    def has_nmux(self):
        """
        Nmux is a tool provided by the
        [CSDR](https://github.com/jketterl/csdr) project and used for
        the internal multiplexing of IQ data streams. You can install
        the `nmux` package from the OpenWebRX repositories.
        """
        return self.command_is_runnable("nmux --help")

    def has_perseustest(self):
        """
        To use the Microtelecom Perseus HF receiver,
        [download](https://github.com/Microtelecom/libperseus-sdr/releases/download/v0.8.2/libperseus_sdr-0.8.2.tar.gz),
        compile and install the `libperseus-sdr` library and tools:
        ```
         sudo apt install libusb-1.0-0-dev
         tar -zxvf libperseus_sdr-0.8.2.tar.gz
         cd libperseus_sdr-0.8.2/
         ./configure
         make
         sudo make install
         sudo ldconfig
         perseustest
        ```
        """
        return self.command_is_runnable("perseustest -h")

    def has_digiham(self):
        """
        OpenWebRX uses the [DigiHAM](https://github.com/jketterl/digiham)
        library for the digital voice modes. In addition, the
        [PyDigiHAM](https://github.com/jketterl/pydigiham) must
        be installed to provide DigiHAM Python bindings. The
        `python3-digiham` package, found in the OpenWebRX
        repositories, should be all you need. Do not forget to
        restart OpenWebRX after installing this package.
        """
        required_version = LooseVersion("0.6")

        try:
            from digiham.modules import digiham_version as digiham_version
            from digiham.modules import version as pydigiham_version

            return (
                LooseVersion(digiham_version) >= required_version
                and LooseVersion(pydigiham_version) >= required_version
            )
        except ImportError:
            return False

    def _check_connector(self, command, required_version):
        owrx_connector_version_regex = re.compile("^{} version (.*)$".format(re.escape(command)))

        try:
            process = subprocess.Popen([command, "--version"], stdout=subprocess.PIPE)
            matches = owrx_connector_version_regex.match(process.stdout.readline().decode())
            if matches is None:
                return False
            version = LooseVersion(matches.group(1))
            process.wait(1)
            return version >= required_version
        except FileNotFoundError:
            return False

    def _check_owrx_connector(self, command):
        return self._check_connector(command, LooseVersion("0.5"))

    def has_rtl_connector(self):
        """
        The [OWRX Connector](https://github.com/jketterl/owrx_connector)
        provides direct interfacing between RTL-SDR hardware and OpenWebRX.
        You can install the `owrx-connector` package from the OpenWebRX
        repositories.
        """
        return self._check_owrx_connector("rtl_connector")

    def has_rtl_tcp_connector(self):
        """
        The [OWRX Connector](https://github.com/jketterl/owrx_connector)
        provides direct interfacing between networked RTL-SDR hardware and
        OpenWebRX. You can install the `owrx-connector` package from the
        OpenWebRX repositories.
        """
        return self._check_owrx_connector("rtl_tcp_connector")

    def has_soapy_connector(self):
        """
        The [OWRX Connector](https://github.com/jketterl/owrx_connector)
        provides direct interfacing between Soapy SDR API and OpenWebRX.
        You can install the `owrx-connector` package from the OpenWebRX
        repositories.
        """
        return self._check_owrx_connector("soapy_connector")

    def _has_soapy_driver(self, driver):
        try:
            process = subprocess.Popen(["soapy_connector", "--listdrivers"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

            drivers = [line.decode().strip() for line in process.stdout]
            process.wait(1)

            return driver in drivers
        except FileNotFoundError:
            return False

    def has_soapy_rtl_sdr(self):
        """
        The [SoapySDR module for RTL-SDR](https://github.com/pothosware/SoapyRTLSDR/wiki)
        devices can be used as an alternative to the rtl_connector. It
        provides additional support for the direct sampling mode. The
        `soapysdr-module-rtlsdr` package is available in most Linux
        distributions.
        """
        return self._has_soapy_driver("rtlsdr")

    def has_soapy_sdrplay(self):
        """
        The [SoapySDR module for SDRPlay](https://github.com/SDRplay/SoapySDRPlay)
        devices is required for interfacing with SDRPlay devices (RSP1*, RSP2*,
        RSPdx, RSPduo, etc). You can install the `soapysdr-module-sdrplay3`
        package from the OpenWebRX+ repositories. You will also need to
        manually install the latest
        [SDRPlay APIv3 library](https://www.sdrplay.com/api/)
        from the manufacturer.
        """
        return self._has_soapy_driver("sdrplay")

    def has_soapy_mirics(self):
        """
        The [SoapySDR module for Mirics](https://github.com/ericek111/SoapyMiri)
        devices is required for interfacing with Mirics-based hardware
        (MSi001 + MSi2500). You will also need to install the
        [libmirisdr-5](https://github.com/ericek111/libmirisdr-5)
        library.
        """
        return self._has_soapy_driver("soapyMiri")

    def has_soapy_malahit_rr(self):
        """
        The [SoapySDR module for Malahit Remote Radio](https://github.com/luarvique/SoapyMalahitR1)
        is required for interfacing with Malahit-R1 devices. You can install the
        `soapysdr-module-malahit-rr` package from the OpenWebRX+ repositories.
        """
        return self._has_soapy_driver("malahitrr")

    def has_soapy_airspy(self):
        """
        The [SoapySDR module for Airspy](https://github.com/pothosware/SoapyAirspy/wiki)
        devices is required for interfacing with Airspy devices (Airspy
        R2, Airspy Mini, etc). The `soapysdr-module-airspy` package is
        available in most Linux distributions.
        """
        return self._has_soapy_driver("airspy")

    def has_soapy_airspyhf(self):
        """
        The [SoapySDR module for AirspyHF](https://github.com/pothosware/SoapyAirspyHF/wiki)
        devices is required for interfacing with Airspy HF devices
        (Airspy HF+, Airspy HF Discovery, etc).
        """
        return self._has_soapy_driver("airspyhf")

    def has_soapy_hydrasdr(self):
        """
        The [SoapySDR module for RFOne](https://github.com/hydrasdr/SoapyHydraSDR)
        device is required for interfacing with HydraSDR RFOne devices.
        """
        return self._has_soapy_driver("hydrasdr")

    def has_soapy_afedri(self):
        """
        The [SoapyAfedri](https://github.com/alexander-sholohov/SoapyAfedri)
        module allows using Afedri SDR-Net devices with SoapySDR.
        """
        return self._has_soapy_driver("afedri")

    def has_soapy_lime_sdr(self):
        """
        The [Lime Suite](https://github.com/myriadrf/LimeSuite)
        installs, among other things, a SoapySDR driver for the
        LimeSDR device series.
        """
        return self._has_soapy_driver("lime")

    def has_soapy_pluto_sdr(self):
        """
        The [SoapySDR module for PlutoSDR](https://github.com/pothosware/SoapyPlutoSDR)
        devices is required for interfacing with PlutoSDR devices.
        """
        return self._has_soapy_driver("plutosdr")

    def has_soapy_remote(self):
        """
        The [SoapyRemote](https://github.com/pothosware/SoapyRemote/wiki)
        allows the usage of remote SDR devices using the SoapySDRServer.
        """
        return self._has_soapy_driver("remote")

    def has_soapy_uhd(self):
        """
        The [SoapyUHD](https://github.com/pothosware/SoapyUHD/wiki)
        module allows using UHD / USRP devices with SoapySDR. The
        `soapysdr-module-uhd` package is available in most Linux
        distributions.
        """
        return self._has_soapy_driver("uhd")

    def has_soapy_radioberry(self):
        """
        The Radioberry is an SDR extension board for the Raspberry Pi.
        More information, along with a SoapySDR module, is available
        at the
        [Radioberry GitHub page](https://github.com/pa3gsb/Radioberry-2.x).
        """
        return self._has_soapy_driver("radioberry")

    def has_soapy_hackrf(self):
        """
        The [SoapyHackRF](https://github.com/pothosware/SoapyHackRF/wiki)
        module allows HackRF to be used with SoapySDR. The
        `soapysdr-module-hackrf` package is available in most
        Linux distributions.
        """
        return self._has_soapy_driver("hackrf")

    def has_soapy_fcdpp(self):
        """
        The [SoapyFCDPP](https://github.com/pothosware/SoapyFCDPP)
        module allows to use Funcube Dongle Pro+ with SoapySDR.
        """
        return self._has_soapy_driver("fcdpp")

    def has_soapy_bladerf(self):
        """
        The [SoapyBladeRF](https://github.com/pothosware/SoapyBladeRF)
        module allows to use BladeRF devices with SoapySDR. The
        `soapysdr-module-bladerf` package is available in most
        Linux distributions.
        """
        return self._has_soapy_driver("bladerf")

    def has_m17_demod(self):
        """
        OpenWebRX uses the [M17 Demodulator](https://github.com/mobilinkd/m17-cxx-demod)
        to demodulate M17 digital voice signals. You can install the
        `m17-demod` package from the OpenWebRX repositories.
        """
        return self.command_is_runnable("m17-demod", 0)

    def has_direwolf(self):
        """
        OpenWebRX uses the [Direwolf](https://github.com/wb2osz/direwolf)
        software modem to decode Packet Radio and report data back to APRS-IS.
        The same software is also used to decode maritime AIS transmissions.
        The `direwolf` package is available in most Linux distributions.
        """
        return self.command_is_runnable("direwolf --help")

    def has_airspy_rx(self):
        """
        The [Airspy Host](https://github.com/airspy/airspyone_host)
        software is required to interface with the Airspy devices.
        You can find instructions on how to build and install it
        [here](https://github.com/airspy/airspyone_host).
        """
        return self.command_is_runnable("airspy_rx --help")

    def has_wsjtx(self):
        """
        OpenWebRX uses the [WSJT-X](https://wsjt.sourceforge.io/) software
        suite to decode FT8 and other digital modes. The `wsjtx` package is
        available in most Linux distributions.
        """
        return reduce(and_, map(self.command_is_runnable, ["jt9", "wsprd"]), True)

    def _has_wsjtx_version(self, required_version):
        wsjt_version_regex = re.compile("^WSJT-X (.*)$")

        try:
            process = subprocess.Popen(["wsjtx_app_version", "--version"], stdout=subprocess.PIPE)
            matches = wsjt_version_regex.match(process.stdout.readline().decode())
            if matches is None:
                return False
            version = LooseVersion(matches.group(1))
            process.wait(1)
            return version >= required_version
        except FileNotFoundError:
            return False

    def has_wsjtx_2_3(self):
        """
        Newer digital modes (e.g. FST4, FST4) require
        [WSJT-X](https://wsjt.sourceforge.io/) version 2.3 or higher.
        Use the latest `wsjtx` package available in your Linux distribution.
        """
        return self.has_wsjtx() and self._has_wsjtx_version(LooseVersion("2.3"))

    def has_wsjtx_2_4(self):
        """
        The Q65 digital mode requires
        [WSJT-X](https://wsjt.sourceforge.io/) version 2.4 or higher.
        Use the latest `wsjtx` package available in your Linux distribution.
        """
        return self.has_wsjtx() and self._has_wsjtx_version(LooseVersion("2.4"))

    def has_msk144decoder(self):
        """
        OpenWebRX uses the
        [MSK144 Decoder](https://github.com/alexander-sholohov/msk144decoder)
        to decode the MSK144 digital mode. You can install the
        `msk144decoder` package from the OpenWebRX repositories.
        """
        return self.command_is_runnable("msk144decoder")

    def has_js8(self):
        """
        OpenWebRX uses the [JS8Call](http://js8call.com/) software
        to decode JS8 communications. The `js8call` package is
        available in most Linux distributions.

        Please note that the `js8` command line decoder is not added
        to the $PATH variable by some JS8Call package builds. You may
        have to make a link to it from the `/usr/bin` folder or add
        its location to the $PATH variable.
        """
        return self.command_is_runnable("js8")

    def has_js8py(self):
        """
        OpenWebRX uses the [JS8Py](https://github.com/jketterl/js8py)
        library to decode binary JS8 messages into readable text. You
        can install the `python3-js8py` package from the OpenWebRX
        repositories. Do not forget to restart OpenWebRX after
        installing this package.
        """
        required_version = StrictVersion("0.1")
        try:
            from js8py.version import strictversion

            return strictversion >= required_version
        except ImportError:
            return False

    def has_alsa(self):
        """
        Some SDR receivers identify themselves as sound cards. OpenWebRX relies
        on the ALSA library to access such receivers. It can be obtained by
        installing the `alsa-utils` package in most Linux distributions.
        """
        return self.command_is_runnable("arecord --help")

    def has_rockprog(self):
        """
        The `rockprog` executable is required to interface with FiFiSDR
        devices. You can download and install it from
        [here](https://o28.sischa.net/fifisdr/trac/wiki/De%3Arockprog).
        """
        return self.command_is_runnable("rockprog")

    def has_freedv_rx(self):
        """
        The `freedv_rx` executable is required to demodulate FreeDV digital
        transmissions. It comes as part of the `codec2` library build, but is
        not installed by default or contained inside the `codec2` packages.

        To obtain it, you will have to compile 'codec2' from the sources and
        then manually install `freedv_rx`. The detailed installation
        instructions are available from the
        [OpenWebRX Wiki](https://github.com/jketterl/openwebrx/wiki/FreeDV-demodulator-notes).
        """
        return self.command_is_runnable("freedv_rx")

    def has_dream(self):
        """
        OpenWebRX uses the [Dream](https://sourceforge.net/projects/drm/)
        software to decode DRM broadcasts. The default version of Dream,
        supplied in most Linux distributions, so you will have to install
        the specially built `dream` package from the OpenWebRX+
        repositories.
        """
        return self.command_is_runnable("dream --help", 0)

    def has_dream_2_2(self):
        """
        [Dream 2.2](https://github.com/wwek/dream) has some extended
        features, such as status reporting. With Dream 2.2 installed,
        you will be able to observe what the DRM decoder is doing and
        what radio programs are available from the data stream. You can
        install the `dream` package from the OpenWebRX+ repositories.
        """
        # Will be looking for the --status-socket option
        dream_status_regex = re.compile(".*--status-socket.*")
        # Look through the --help output
        try:
            process = subprocess.Popen(["dream", "--help"], stderr=subprocess.PIPE)
            while process.poll() is None:
                line = process.stderr.readline()
                if line is None:
                    # Output ended, old Dream
                    return False
                else:
                    matches = dream_status_regex.match(line.decode())
                    if matches is not None:
                        # --status-socket option supported, new Dream!
                        return True
        except Exception as e:
            # Something bad happens, probably no Dream
            return False
        # Process ended, old Dream
        return False

    def has_sddc_connector(self):
        """
        The [SDDC Connector](https://github.com/jketterl/sddc_connector)
        allows connectivity with SDR devices powered by the `libsddc`
        library, such as RX666, RX888, HF103, etc.
        """
        return self._check_connector("sddc_connector", LooseVersion("0.1"))

    def has_soapy_sddc(self):
        """
        The [SoapySDR module for SDDC](https://github.com/ik1xpv/ExtIO_sddc)
        devices can be used as an alternative to the `sddc_connector`, enabling
        connectivity with SDR devices such as the RX666, RX888, HF103, etc.
        Unlike the `sddc_connector`, the SoapySDR module relies solely on the CPU
        and does not require an NVIDIA GPU.
        You will need to compile SoapySDDC from source. Detailed installation
        instructions are available on the [OpenWebRX Wiki](https://github.com/jketterl/openwebrx/wiki/SDDC-device-notes).
        """
        return self._has_soapy_driver("SDDC")

    def has_hpsdr_connector(self):
        """
        The [HPSDR Connector](https://github.com/jancona/hpsdrconnector)
        is required to interface OpenWebRX with Hermes Lite 2, Red Pitaya,
        and similar networked SDR devices. You can install the
        `hpsdrconnector` package from the OpenWebRX repositories.
        """
        return self.command_is_runnable("hpsdrconnector -h")

    def has_runds_connector(self):
        """
        The [RunDS Connector](https://github.com/jketterl/runds_connector)
        allows using R&S radios via EB200 or Ammos.
        """
        return self._check_connector("runds_connector", LooseVersion("0.2"))

    def has_codecserver_ambe(self):
        """
        The [CodecServer](https://github.com/jketterl/codecserver) is used to decode
        audio data from digital voice modes using the AMBE codec. This feature checks
        for both the `codecserver` executable and the configured AMBE codec. The
        `codecserver` package can be found in the OpenWebRX repositories.
        """
        config = Config.get()
        server = ""
        if "digital_voice_codecserver" in config:
            server = config["digital_voice_codecserver"]
        try:
            from digiham.modules import MbeSynthesizer

            return MbeSynthesizer.hasAmbe(server)
        except ImportError:
            return False
        except ConnectionError:
            return False
        except RuntimeError as e:
            logger.exception("Codecserver error while checking for AMBE support:")
            return False

    def has_dump1090(self):
        """
        OpenWebRX supports decoding Mode-S and ADS-B airplane communications by using the
        [Dump1090](https://github.com/flightaware/dump1090) decoder. You can install the
        `dump1090-fa-minimal` package from the OpenWebRX repositories.

        While there exist many Dump1090 forks, any version that supports `--ifile` and
        `--iformat` arguments will work. We recommend using the
        [Dump1090 by FlightAware](https://github.com/flightaware/dump1090).
        If you are using a different fork, please make sure that the `dump1090` command
        (without suffixes) runs the desired version. You can use symbolic links or the
        [Debian alternatives system](https://wiki.debian.org/DebianAlternatives) to
        achieve this.
        """
        return self.command_is_runnable("dump1090 --version")

    def has_dump978(self):
        """
        OpenWebRX supports decoding UAT airplane communications by using the
        [Dump978](https://github.com/flightaware/dump978) decoder. You can install the
        `dump978-fa-minimal` package from the OpenWebRX+ repositories.
        """
        return self.command_is_runnable("dump978 --version")

    def has_rtl_433(self):
        """
        OpenWebRX supports decoding ISM signals from various sensors
        by using the [RTL-433](https://github.com/merbanan/rtl_433)
        decoder suite. The `rtl-433` package is available in most Linux
        distributions.
        """
        return self.command_is_runnable("rtl_433 -h")

    def has_dumphfdl(self):
        """
        OpenWebRX supports decoding HFDL airplane communications by using the
        [DumpHFDL](https://github.com/szpajder/dumphfdl) decoder. You can
        install the `dumphfdl` package from the OpenWebRX repositories.
        """
        return self.command_is_runnable("dumphfdl --version")

    def has_dumpvdl2(self):
        """
        OpenWebRX supports decoding VDL Mode 2 airplane communications by using the
        [DumpVDL2](https://github.com/szpajder/dumpvdl2) decoder. You can
        install the `dumpvdl2` package from the OpenWebRX repositories.
        """
        return self.command_is_runnable("dumpvdl2 --version")

    def has_redsea(self):
        """
        OpenWebRX uses the [RedSea](https://github.com/windytan/redsea)
        decoder to obtain the RDS information from WFM broadcasts. You can
        install the `redsea` package from the OpenWebRX repositories.
        """
        return self.command_is_runnable("redsea --version")

    def has_csdreti(self):
        """
        To decode DAB broadcast signals, OpenWebRX needs the ETI decoder from the
        [`csdr-eti`](https://github.com/jketterl/csdr-eti) project, together with
        the associated Python bindings from [`pycsdr-eti`](https://github.com/jketterl/pycsdr-eti).
        The `python3-csdr-eti` package, found in the OpenWebRX repositories,
        should be all you need. Do not forget to restart OpenWebRX after
        installing this package.
        """
        required_version = LooseVersion("0.0.11")

        try:
            from csdreti.modules import csdreti_version
            from csdreti.modules import version as pycsdreti_version

            return (
                LooseVersion(csdreti_version) >= required_version
                and LooseVersion(pycsdreti_version) >= required_version
            )
        except ImportError:
            return False

    def has_dablin(self):
        """
        OpenWebRX uses the [Dablin](https://github.com/Opendigitalradio/dablin)
        software to decode DAB broadcast signals. The `dablin` package is
        available in most Linux distributions.
        """
        return self.command_is_runnable("dablin -h")

    def has_paho_mqtt(self):
        """
        OpenWebRX uses the [paho-mqtt](https://pypi.org/project/paho-mqtt/)
        library to send decoded signal data to an MQTT broker for further
        processing by third-party applications. The `python3-paho-mqtt`
        package is available in most Linux distributions. Do not forget
        to restart OpenWebRX after installing this package.
        """
        try:
            from paho.mqtt import __version__
            return True
        except ImportError:
            return False

    def _has_acarsdec_version(self, required_version):
        acarsdec_version_regex = re.compile(r"^Acarsdec\s+v?(\S+)\s+")
        try:
            process = subprocess.Popen(["acarsdec"], stderr=subprocess.PIPE)
            matches = None
            for x in range(3):
                matches = acarsdec_version_regex.match(process.stderr.readline().decode())
                if matches is not None:
                    break
            process.wait(1)
            if matches is None:
                return False
            else:
                version = LooseVersion(matches.group(1))
                return version >= required_version
        except Exception as e:
            return False

    def has_acarsdec(self):
        """
        OpenWebRX supports decoding ACARS airplane communications by using the
        [AcarsDec](https://github.com/TLeconte/acarsdec) decoder. You can
        install the `acarsdec` package from the OpenWebRX repositories.
        """
        return self._has_acarsdec_version(LooseVersion("4"))

    def has_imagemagick(self):
        """
        OpenWebRX converts received images to the PNG format with the
        [ImageMagick](https://www.imagemagick.org/) tool. The
        `imagemagick` package is available in most Linux distributions.
        """
        return self.command_is_runnable("convert -version")

    def has_multimon(self):
        """
        OpenWebRX supports decoding FLEX, POCSAG, and several other digital modes
        by using the [MultiMon-NG](https://github.com/EliasOenal/multimon-ng)
        decoder suite. The `multimon-ng` package is available in most Linux
        distributions.
        """
        return self.command_is_runnable("multimon-ng --help")

    def has_satdump(self):
        """
        OpenWebRX uses [SatDump](https://github.com/SatDump/SatDump) software
        suite to receive weather satellite transmissions. The `satdump`
        packages are available from its
        [homepage](https://github.com/SatDump/SatDump).
        """
        return self.command_is_runnable("satdump --help")

    def has_nrsc5(self):
        """
        OpenWebRX uses the [Nrsc5](https://github.com/theori-io/nrsc5) tool
        to decode HDRadio broadcasts. You can install the `nrsc5` package
        from the OpenWebRX+ repositories.
        """
        return self.command_is_runnable("nrsc5 -v")

    def has_hamlib(self):
        """
        OpenWebRX uses the [Hamlib](https://github.com/Hamlib/Hamlib) `rigctl`
        tool to synchronize frequency and modulation with external transceivers.
        The `hamlib` package is available in most Linux distributions.
        """
        return self.command_is_runnable("rigctl -V")

    def has_csdr_skimmer(self):
        """
        OpenWebRX uses the [CSDR Skimmer](https://github.com/luarvique/csdr-skimmer)
        to decode multiple CW and RTTY signals at once. You can install
        the `csdr-skimmer` package from the OpenWebRX+ repositories.
        """
        return self.command_is_runnable("csdr-rttyskimmer -h")

    def has_sonde_rs(self):
        """
        OpenWebRX uses Zilog decoders in [Project Horus](https://github.com/projecthorus/radiosonde_auto_rx)
        to decode radiosonde data. This software has to be built and
        installed manually.
        """
        return self.command_is_runnable("rs41mod -h")

    def has_lame(self):
        """
        OpenWebRX uses the [LAME](https://lame.sourceforge.io/) tool
        to compress recorded audio into MP3 format. The `lame` package
        is available in most Linux distributions.
        """
        return self.command_is_runnable("lame --help")

    def has_aprs_symbols(self):
        """
        OpenWebRX uses a collection of APRS symbol icons to show APRS
        traffic at the map. You can install the `aprs-symbols` package
        from the OpenWebRX repositories.
        """
        return os.path.isdir("/usr/share/aprs-symbols")
