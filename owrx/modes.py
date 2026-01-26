from owrx.feature import FeatureDetector
from owrx.audio import ProfileSource
from functools import reduce
from abc import ABCMeta, abstractmethod


class Bandpass(object):
    def __init__(self, low_cut, high_cut):
        self.low_cut = low_cut
        self.high_cut = high_cut


class Mode:
    def __init__(self, modulation: str, name: str, bandpass: Bandpass = None, ifRate=None, requirements=None, service=False, squelch=True):
        self.modulation = modulation
        self.name = name
        self.requirements = requirements if requirements is not None else []
        self.service = service
        self.bandpass = bandpass
        self.ifRate = ifRate
        self.squelch = squelch

    def is_available(self):
        fd = FeatureDetector()
        return reduce(lambda a, b: a and b, [fd.is_available(r) for r in self.requirements], True)

    def is_service(self):
        return self.service

    def get_bandpass(self):
        return self.bandpass

    def get_modulation(self):
        return self.modulation

    def get_bandwidth(self):
        bandwidth = 0
        if self.bandpass is not None:
            bandwidth = 2 * max(abs(self.bandpass.low_cut), abs(self.bandpass.high_cut))
        if self.ifRate is not None:
            bandwidth = max(bandwidth, self.ifRate)
        return bandwidth


EmptyMode = Mode("empty", "Empty")


class AnalogMode(Mode):
    pass


class DigitalMode(Mode):
    def __init__(
        self,
        modulation,
        name,
        underlying,
        bandpass: Bandpass = None,
        ifRate=None,
        requirements=None,
        service=False,
        squelch=True,
        secondaryFft=True
    ):
        super().__init__(modulation, name, bandpass, ifRate, requirements, service, squelch)
        self.underlying = underlying
        self.secondaryFft = secondaryFft

    def get_underlying_mode(self):
        mode = Modes.findByModulation(self.underlying[0])
        if mode is None:
            mode = EmptyMode
        return mode

    def get_bandpass(self):
        if self.bandpass is not None:
            return self.bandpass
        return self.get_underlying_mode().get_bandpass()

    def get_bandwidth(self):
        bandwidth = super().get_bandwidth()
        if bandwidth > 0:
            return bandwidth
        return self.get_underlying_mode().get_bandwidth()

    def get_modulation(self):
        return self.get_underlying_mode().get_modulation()

    def for_underlying(self, underlying: str):
        if underlying not in self.underlying:
            raise ValueError("{} is not a valid underlying mode for {}".format(underlying, self.modulation))
        return DigitalMode(
            self.modulation, self.name, [underlying], self.bandpass, self.ifRate, self.requirements, self.service, self.squelch
        )


class ServiceOnlyMode(DigitalMode):
    pass


class AudioChopperMode(DigitalMode, metaclass=ABCMeta):
    def __init__(self, modulation, name, bandpass=None, requirements=None):
        if bandpass is None:
            bandpass = Bandpass(0, 3000)
        super().__init__(modulation, name, ["usb"], bandpass=bandpass, requirements=requirements, service=True)

    @abstractmethod
    def get_profile_source(self) -> ProfileSource:
        pass


class WsjtMode(AudioChopperMode):
    def __init__(self, modulation, name, bandpass=None, requirements=None):
        if requirements is None:
            requirements = ["wsjt-x"]
        super().__init__(modulation, name, bandpass=bandpass, requirements=requirements)

    def get_profile_source(self) -> ProfileSource:
        # inline import due to circular dependencies
        from owrx.wsjt import WsjtProfiles
        return WsjtProfiles.getSource(self.modulation)


class Js8Mode(AudioChopperMode):
    def __init__(self, modulation, name, bandpass=None, requirements=None):
        if requirements is None:
            requirements = ["js8call"]
        super().__init__(modulation, name, bandpass, requirements)

    def get_profile_source(self) -> ProfileSource:
        # inline import due to circular dependencies
        from owrx.js8 import Js8ProfileSource
        return Js8ProfileSource()


class Modes(object):
    mappings = [
        AnalogMode("nfm", "FM", bandpass=Bandpass(-4000, 4000)),
        AnalogMode("wfm", "WFM", bandpass=Bandpass(-75000, 75000)),
        AnalogMode("bcfm", "BCFM", bandpass=None, ifRate=192000),
        AnalogMode("am", "AM", bandpass=Bandpass(-4000, 4000)),
        AnalogMode("lsb", "LSB", bandpass=Bandpass(-2750, -150)),
        AnalogMode("usb", "USB", bandpass=Bandpass(150, 2750)),
        AnalogMode("cw", "CW", bandpass=Bandpass(700, 900)),
        AnalogMode("sam", "SAM", bandpass=Bandpass(-4000, 4000)),
        AnalogMode("usbd", "DATA", bandpass=Bandpass(0, 24000)),
        AnalogMode("dmr", "DMR", bandpass=Bandpass(-6250, 6250), requirements=["digital_voice_digiham"], squelch=False),
        AnalogMode(
            "dstar", "D-Star", bandpass=Bandpass(-3250, 3250), requirements=["digital_voice_digiham"], squelch=False
        ),
        AnalogMode("nxdn", "NXDN", bandpass=Bandpass(-3250, 3250), requirements=["digital_voice_digiham"], squelch=False),
        AnalogMode("ysf", "YSF", bandpass=Bandpass(-6250, 6250), requirements=["digital_voice_digiham"], squelch=False),
        AnalogMode("m17", "M17", bandpass=Bandpass(-6250, 6250), requirements=["digital_voice_m17"], squelch=False),
        AnalogMode(
            "freedv", "FreeDV", bandpass=Bandpass(300, 3000), requirements=["digital_voice_freedv"], squelch=False
        ),
        AnalogMode("drm", "DRM", bandpass=Bandpass(-5000, 5000), requirements=["drm"], squelch=False),
        AnalogMode("dab", "DAB", bandpass=None, ifRate=2048000, requirements=["dab"], squelch=False),
        AnalogMode("hdr", "HDR", bandpass=Bandpass(-200000, 200000), requirements=["hdradio"], squelch=False),
        DigitalMode("bpsk31", "BPSK31", underlying=["usb"]),
        DigitalMode("bpsk63", "BPSK63", underlying=["usb"]),
        DigitalMode("rtty170", "RTTY-170 (45)", underlying=["usb", "lsb"]),
        DigitalMode("rtty450", "RTTY-450 (50N)", underlying=["usb", "lsb"]),
        DigitalMode("rtty85", "RTTY-85 (50N)", underlying=["usb", "lsb"]),
        DigitalMode("sitorb", "SITOR-B", underlying=["usb"]),
        DigitalMode("navtex", "NAVTEX", underlying=["usb"], service=True),
        DigitalMode("dsc", "DSC", underlying=["usb"], service=True),
        WsjtMode("ft8", "FT8"),
        WsjtMode("ft4", "FT4"),
        WsjtMode("jt65", "JT65"),
        WsjtMode("jt9", "JT9"),
        WsjtMode("wspr", "WSPR", bandpass=Bandpass(1350, 1650)),
        WsjtMode("fst4", "FST4", requirements=["wsjt-x-2-3"]),
        WsjtMode("fst4w", "FST4W", bandpass=Bandpass(1350, 1650), requirements=["wsjt-x-2-3"]),
        WsjtMode("q65", "Q65", requirements=["wsjt-x-2-4"]),
        DigitalMode("msk144", "MSK144", requirements=["msk144"], underlying=["usb"], service=True),
        Js8Mode("js8", "JS8Call"),
        DigitalMode(
            "packet",
            "Packet",
            underlying=["empty"], #["nfm", "usb", "lsb"],
            bandpass=Bandpass(-6250, 6250),
            requirements=["packet"],
            service=True,
            squelch=False,
        ),
        DigitalMode(
            "ais",
            "AIS",
            underlying=["empty"], #["nfm"],
            bandpass=Bandpass(-6250, 6250),
            requirements=["packet"],
            service=True,
            squelch=False,
        ),
# Replaced by Jakob's RTTY decoder
#        DigitalMode("mfrtty170", "RTTY-170", underlying=["usb"]),
#        DigitalMode("mfrtty450", "RTTY-450", underlying=["usb"]),
# Replaced by the general paging decoder (both POCSAG and FLEX)
#        DigitalMode(
#            "pocsag",
#            "Pocsag",
#            underlying=["nfm"],
#            bandpass=Bandpass(-6000, 6000),
#            requirements=["pocsag"],
#            service=True,
#            squelch=False,
#        ),
        DigitalMode(
            "page",
            "Page",
            underlying=["empty"], #["nfm"],
            bandpass=Bandpass(-6000, 6000),
            requirements=["page"],
            service=True,
            squelch=False,
        ),
        DigitalMode("cwdecoder", "CW Decoder", underlying=["usb", "lsb"]),
        DigitalMode(
            "cwskimmer",
            "CW Skimmer",
            underlying=["empty"],
            bandpass=Bandpass(0, 48000),
            requirements=["skimmer"],
            service=True,
            squelch=False,
        ),
        DigitalMode(
            "rttyskimmer",
            "RTTY Skimmer",
            underlying=["empty"],
            bandpass=Bandpass(0, 48000),
            requirements=["skimmer"],
            service=True,
            squelch=False,
        ),
        DigitalMode(
            "sstv",
            "SSTV",
            underlying=["usb", "lsb", "nfm"],
            service=True,
            squelch=True,
        ),
        DigitalMode(
            "fax",
            "Fax",
            underlying=["usb"],
            service=True,
            squelch=True,
        ),
        DigitalMode(
            "selcall",
            "SelCall",
            underlying=["nfm"],
            requirements=["selcall"],
            squelch=True
        ),
        DigitalMode(
            "zvei",
            "Zvei",
            underlying=["nfm"],
            requirements=["selcall"],
            squelch=True
        ),
        DigitalMode(
            "eas",
            "EAS",
            underlying=["nfm"],
            requirements=["eas"],
            service=True,
            squelch=True
        ),
        DigitalMode(
            "ism",
            "ISM",
            underlying=["empty"],
            bandpass=None,
            ifRate=250000,
            requirements=["ism"],
            service=True,
            squelch=False
        ),
        DigitalMode(
            "wmbus",
            "WMBus",
            underlying=["empty"],
            bandpass=Bandpass(-125000, 125000),
            requirements=["ism"],
            service=True,
            squelch=False
        ),
        DigitalMode(
            "hfdl",
            "HFDL",
            underlying=["empty"],
            bandpass=Bandpass(0, 3000),
            requirements=["hfdl"],
            service=True,
            squelch=False
        ),
        DigitalMode(
            "vdl2",
            "VDL2",
            underlying=["empty"],
            bandpass=Bandpass(-12500, 12500),
            requirements=["vdl2"],
            service=True,
            squelch=False
        ),
        DigitalMode(
            "acars",
            "ACARS",
            underlying=["am"],
            bandpass=Bandpass(-6000, 6000),
            requirements=["acars"],
            service=True,
            squelch=False
        ),
        DigitalMode(
            "adsb",
            "ADSB",
            underlying=["empty"],
            bandpass=None,
            ifRate=2400000,
            requirements=["adsb"],
            service=True,
            squelch=False,
            secondaryFft=False
        ),
        DigitalMode(
            "uat",
            "UAT",
            underlying=["empty"],
            bandpass=None,
            ifRate=2083334,
            requirements=["uat"],
            service=True,
            squelch=False,
            secondaryFft=False
        ),
        # Radiosonde modes
        DigitalMode(
            "sonde-rs41",
            "Sonde RS41",
            underlying=["empty"],
            bandpass=Bandpass(-6250, 6250),
            requirements=["sonde"],
            service=True,
            squelch=False
        ),
        DigitalMode(
            "sonde-dfm9",
            "Sonde DFM9",
            underlying=["empty"],
            bandpass=Bandpass(-6250, 6250),
            requirements=["sonde"],
            service=True,
            squelch=False
        ),
        DigitalMode(
            "sonde-dfm17",
            "Sonde DFM17",
            underlying=["empty"],
            bandpass=Bandpass(-6250, 6250),
            requirements=["sonde"],
            service=True,
            squelch=False
        ),
        DigitalMode(
            "sonde-mts01",
            "Sonde MTS01",
            underlying=["empty"],
            bandpass=Bandpass(-6250, 6250),
            requirements=["sonde"],
            service=True,
            squelch=False
        ),
        DigitalMode(
            "sonde-m10",
            "Sonde M10",
            underlying=["empty"],
            bandpass=Bandpass(-12500, 12500),
            requirements=["sonde"],
            service=True,
            squelch=False
        ),
        DigitalMode(
            "sonde-m20",
            "Sonde M20",
            underlying=["empty"],
            bandpass=Bandpass(-12500, 12500),
            requirements=["sonde"],
            service=True,
            squelch=False
        ),
        # Server-side audio recording is a background service only.
        # See JavaScript code for client-side audio recording.
        ServiceOnlyMode(
            "audio",
            "Audio Recorder",
            underlying=["am", "usb", "lsb", "nfm", "sam", "cw"],
            requirements=["mp3"],
            service=True,
            squelch=True
        ),
        # SatDump-based weather satellite reception is not real-time
        # and thus only works as background services.
        ServiceOnlyMode(
            "meteor-lrpt",
            "Meteor-M2 LRPT",
            underlying=["empty"],
            bandpass=Bandpass(-75000, 75000),
            requirements=["wxsat"],
            service=True,
            squelch=False,
            secondaryFft=False
        ),
        ServiceOnlyMode(
            "elektro-lrit",
            "Elektro-L LRIT",
            underlying=["empty"],
            bandpass=Bandpass(-200000, 200000),
            requirements=["wxsat"],
            service=True,
            squelch=False,
            secondaryFft=False
        ),
        # NOAA-15 satellite has been retired, not operational
        #ServiceOnlyMode(
        #    "noaa-apt-15",
        #    "NOAA-15 APT",
        #    underlying=["empty"],
        #    bandpass=Bandpass(-25000, 25000),
        #    requirements=["wxsat"],
        #    service=True,
        #    squelch=False,
        #    secondaryFft=False
        #),
        # NOAA-19 satellite has been retired, not operational
        #ServiceOnlyMode(
        #    "noaa-apt-19",
        #    "NOAA-19 APT",
        #    underlying=["empty"],
        #    bandpass=Bandpass(-25000, 25000),
        #    requirements=["wxsat"],
        #    service=True,
        #    squelch=False,
        #    secondaryFft=False
        #),
    ]

    @staticmethod
    def getModes():
        return Modes.mappings

    @staticmethod
    def getAvailableModes():
        return [m for m in Modes.getModes() if m.is_available()]

    @staticmethod
    def getAvailableClientModes():
        return [m for m in Modes.getAvailableModes() if not isinstance(m, ServiceOnlyMode)]

    @staticmethod
    def getAvailableServices():
        return [m for m in Modes.getAvailableModes() if m.is_service()]

    @staticmethod
    def findByModulation(modulation):
        modes = [m for m in Modes.getAvailableModes() if m.modulation == modulation]
        if modes:
            return modes[0]
