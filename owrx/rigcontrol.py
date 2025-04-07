from owrx.feature import FeatureDetector
from owrx.property import PropertyStack
from owrx.config import Config
from subprocess import Popen, PIPE, STDOUT, TimeoutExpired

import threading
import select
import os

import logging

logger = logging.getLogger(__name__)

class RigControl():
    # Mapping from rig names to Rigctl rig types
    RIGS = {
#       "Hamlib Dummy"        : 1,
        "Hamlib"              : 2,
        "FLRig"               : 4,
        "TRXManager 5.7.630+" : 5,
#       "Hamlib Dummy No VFO" : 6,

        "ADAT ADT-200A"   : 29001,
        "AE9RB Si570 Peaberry V1" : 25016,
        "AE9RB Si570 Peaberry V2" : 25017,
        "Alinco DX-77"    : 17001,
        "Alinco DX-SR8"   : 17002,
        "AmQRP DDS-60"    : 25006,
        "AMSAT-UK FUNcube Dongle" : 25013,
        "AMSAT-UK FUNcube Dongle Pro+" : 25018,
        "ANAN Thetis"     : 2048,

        "AOR AR3000A"     : 5006,
        "AOR AR3030"      : 5005,
        "AOR AR5000"      : 5004,
        "AOR AR2700"      : 5008,
        "AOR AR8600"      : 5013,
        "AOR AR5000A"     : 5014,
        "AOR AR7030"      : 5003,
        "AOR AR7030 Plus" : 5015,
        "AOR AR8000"      : 5002,
        "AOR AR8200"      : 5001,
        "AOR SR2200"      : 5016,

        "Barrett 2050"    : 32001,
        "Barrett 950"     : 32002,
        "Coding Technologies Digital World Traveller" : 25003,
        "Dorji DRA818V"   : 31001,
        "Dorji DRA818U"   : 31002,
        "Drake R-8A"      : 9002,
        "Drake R-8B"      : 9003,
        "DTTS Microwave Society DttSP IPC" : 23003,
        "DTTS Microwave Society DttSP UDP" : 23004,
        "ELAD FDM-DUO"    : 33001,

        "Elecraft K2"     : 2021,
        "Elecraft K3"     : 2029,
        "Elecraft K3S"    : 2043,
        "Elecraft K4"     : 2047,
        "Elecraft KX2"    : 2044,
        "Elecraft KX3"    : 2045,
        "Elecraft XG3"    : 2038,

        "Elektor SDR-USB"     : 25007,
        "Elektor 3/04"        : 25001,
        "FiFi FiFi-SDR"       : 25012,
        "FlexRadio 6xxx"      : 2036,
        "FlexRadio PowerSDR"  : 2048,
        "FlexRadio SDR-1000"  : 23001,
        "Funkamateur FA-SDR"  : 25015,
        "Hilberling PT-8000A" : 2046,
        "HobbyPCB RS-HFIQ"    : 25019,

        "Icom IC-92D"  : 3065,
        "Icom IC-271"  : 3003,
        "Icom IC-275"  : 3004,
        "Icom IC-471"  : 3006,
        "Icom IC-475"  : 3007,
        "Icom IC-575"  : 3008,
        "Icom IC-703"  : 3055,
        "Icom IC-706"  : 3009,
        "Icom IC-706MkII" : 3010,
        "Icom IC-706MkIIG" : 3011,
        "Icom IC-705"  : 3085,
        "Icom IC-707"  : 3012,
        "Icom IC-718"  : 3013,
        "Icom IC-725"  : 3014,
        "Icom IC-726"  : 3015,
        "Icom IC-728"  : 3016,
        "Icom IC-729"  : 3017,
        "Icom IC-735"  : 3019,
        "Icom IC-736"  : 3020,
        "Icom IC-737"  : 3021,
        "Icom IC-738"  : 3022,
        "Icom IC-746"  : 3023,
        "Icom IC-746PRO" : 3046,
        "Icom IC-751"  : 3024,
        "Icom IC-756"  : 3026,
        "Icom IC-756PRO" : 3027,
        "Icom IC-756PROII" : 3047,
        "Icom IC-756PROIII" : 3057,
        "Icom IC-761"  : 3028,
        "Icom IC-765"  : 3029,
        "Icom IC-775"  : 3030,
        "Icom IC-78"   : 3045,
        "Icom IC-781"  : 3031,
        "Icom IC-820H" : 3032,
        "Icom IC-821H" : 3034,
        "Icom IC-910"  : 3044,
        "Icom IC-970"  : 3035,
        "Icom IC-1275" : 3002,
        "Icom IC-2730" : 3072,
        "Icom IC-7000" : 3060,
        "Icom IC-7100" : 3070,
        "Icom IC-7300" : 3073,
        "Icom IC-7200" : 3061,
        "Icom IC-7410" : 3067,
        "Icom IC-7700" : 3062,
        "Icom IC-7600" : 3063,
        "Icom IC-7610" : 3078,
        "Icom IC-7800" : 3056,
        "Icom IC-785x" : 3075,
        "Icom IC-9100" : 3068,
        "Icom IC-9700" : 3081,

        "Icom IC-M700PRO" : 30001,
        "Icom IC-M710"    : 30003,
        "Icom IC-M802"    : 30002,
        "Icom IC-M803"    : 30004,

        "Icom IC-R6"      : 3077,
        "Icom IC-R10"     : 3036,
        "Icom IC-R20"     : 3058,
        "Icom IC-R30"     : 3080,
        "Icom IC-R71"     : 3037,
        "Icom IC-R72"     : 3038,
        "Icom IC-R75"     : 3039,
        "Icom IC-R7000"   : 3040,
        "Icom IC-R7100"   : 3041,
        "Icom IC-R8500"   : 3042,
        "Icom IC-R8600"   : 3079,
        "Icom IC-R9000"   : 3043,
        "Icom IC-R9500"   : 3066,
        "Icom IC-RX7"     : 3069,

        "Icom IC-PCR1000" : 4001,
        "Icom IC-PCR100"  : 4002,
        "Icom IC-PCR1500" : 4003,
        "Icom IC-PCR2500" : 4004,

        "Icom ID-1"       : 3054,
        "Icom ID-31"      : 3083,
        "Icom ID-51"      : 3084,
        "Icom ID-4100"    : 3082,
        "Icom ID-5100"    : 3071,

        "JRC NRD-525"     : 6005,
        "JRC NRD-535D"    : 6006,
        "JRC NRD-545 DSP" : 6007,
        "Kachina 505DSP"  : 18001,

        "Kenwood R-5000"   : 2015,
        "Kenwood TH-D7A"   : 2017,
        "Kenwood TH-D72A"  : 2033,
        "Kenwood TH-D74"   : 2042,
        "Kenwood TH-F6A"   : 2019,
        "Kenwood TH-F7E"   : 2020,
        "Kenwood TH-G71"   : 2023,
        "Kenwood TM-D700"  : 2026,
        "Kenwood TM-D710(G)" : 2034,
        "Kenwood TM-V7"    : 2027,
        "Kenwood TRC-80"   : 2030,
        "Kenwood TS-50S"   : 2001,
        "Kenwood TS-440S"  : 2002,
        "Kenwood TS-450S"  : 2003,
        "Kenwood TS-480"   : 2028,
        "Kenwood TS-570D"  : 2004,
        "Kenwood TS-570S"  : 2016,
        "Kenwood TS-590S"  : 2031,
        "Kenwood TS-590SG" : 2037,
        "Kenwood TS-690S"  : 2005,
        "Kenwood TS-711"   : 2006,
        "Kenwood TS-790"   : 2007,
        "Kenwood TS-811"   : 2008,
        "Kenwood TS-850"   : 2009,
        "Kenwood TS-870S"  : 2010,
        "Kenwood TS-890S"  : 2041,
        "Kenwood TS-940S"  : 2011,
        "Kenwood TS-950S"  : 2012,
        "Kenwood TS-950SDX" : 2013,
        "Kenwood TS-990S"  : 2039,
        "Kenwood TS-2000"  : 2014,
        "Kenwood TS-930"   : 2022,
        "Kenwood TS-680S"  : 2024,
        "Kenwood TS-140S"  : 2025,

        "KTH-SDR Si570 PIC-USB" : 25011,
        "Lowe HF-235"           : 10004,
        "Malachite DSP"         : 2049,
        "Microtelecom Perseus"  : 3074,
        "mRS miniVNA"           : 25008,
        "N2ADR HiQSDR"          : 25014,
        "OpenHPSDR PiHPSDR"     : 2040,

        "Optoelectronics OptoScan535" : 3052,
        "Optoelectronics OptoScan456" : 3053,

        "Philips/Simoco PRM8060" : 28001,
        "Racal RA3702"           : 11005,
        "Racal RA6790/GM"        : 11003,
        "RadioShack PRO-2052"    : 8004,
        "RFT EKD-500"            : 24001,
        "Rohde & Schwarz EB200"  : 27002,
        "Rohde & Schwarz ESMC"   : 27001,
        "Rohde & Schwarz XK2100" : 27003,
        "SAT-Schneider DRT1"     : 25002,
        "SigFox Transfox"        : 2032,
        "Skanti TRP8000"         : 14002,
        "Skanti TRP8255SR"       : 14004,
        "SoftRock Si570 AVR-USB" : 25009,
        "TAPR DSP-10"            : 22001,

        "Ten-Tec Delta II"        : 3064,
        "Ten-Tec Omni VI Plus"    : 3051,
        "Ten-Tec RX-320"          : 16003,
        "Ten-Tec RX-331"          : 16012,
        "Ten-Tec RX-340"          : 16004,
        "Ten-Tec RX-350"          : 16005,
        "Ten-Tec TT-516 Argonaut V" : 16007,
        "Ten-Tec TT-538 Jupiter"  : 16002,
        "Ten-Tec TT-550"          : 16001,
        "Ten-Tec TT-565 Orion"    : 16008,
        "Ten-Tec TT-585 Paragon"  : 16009,
        "Ten-Tec TT-588 Omni VII" : 16011,
        "Ten-Tec TT-599 Eagle"    : 16013,

        "Uniden BC245xlt" : 8002,
        "Uniden BC250D"   : 8006,
        "Uniden BC780xlt" : 8001,
        "Uniden BC895xlt" : 8003,
        "Uniden BC898T"   : 8012,
        "Uniden BCD-396T" : 8010,
        "Uniden BCD-996T" : 8011,

        "Vertex Standard VX-1700"  : 1033,
        "Video4Linux SW/FM Radio"  : 26001,
        "Video4Linux2 SW/FM Radio" : 26002,
        "Watkins-Johnson WJ-8888"  : 12004,

        "Winradio WR-1000" : 15001,
        "Winradio WR-1500" : 15002,
        "Winradio WR-1550" : 15003,
        "Winradio WR-3100" : 15004,
        "Winradio WR-3150" : 15005,
        "Winradio WR-3500" : 15006,
        "Winradio WR-3700" : 15007,
        "Winradio WR-G313" : 15009,

        "Xiegu X108G" : 3076,

        "Yaesu FRG-100"    : 1017,
        "Yaesu FRG-8800"   : 1019,
        "Yaesu FRG-9600"   : 1018,
        "Yaesu FT-100"     : 1021,
        "Yaesu FT-450"     : 1027,
        "Yaesu FT-600"     : 1039,
        "Yaesu FT-736R"    : 1010,
        "Yaesu FT-747GX"   : 1005,
        "Yaesu FT-757GX"   : 1006,
        "Yaesu FT-757GXII" : 1007,
        "Yaesu FT-767GX"   : 1009,
        "Yaesu FT-817"     : 1020,
        "Yaesu FT-818"     : 1041,
        "Yaesu FT-840"     : 1011,
        "Yaesu FT-847"     : 1001,
        "Yaesu FT-847UNI"  : 1038,
        "Yaesu FT-857"     : 1022,
        "Yaesu FT-890"     : 1015,
        "Yaesu FT-891"     : 1036,
        "Yaesu FT-897"     : 1023,
        "Yaesu FT-897D"    : 1043,
        "Yaesu FT-900"     : 1013,
        "Yaesu FT-920"     : 1014,
        "Yaesu FT-950"     : 1028,
        "Yaesu FT-980"     : 1031,
        "Yaesu FT-990"     : 1016,
        "Yaesu FT-991"     : 1035,
        "Yaesu FT-1000D"   : 1003,
        "Yaesu FT-1000MP"  : 1024,
        "Yaesu FT-1000MP Mark-V" : 1004,
        "Yaesu FT-1000MP Mark-V Field" : 1025,
        "Yaesu FT-2000"    : 1029,
        "Yaesu FTDX-10"    : 1042,
        "Yaesu FTDX-101D"  : 1040,
        "Yaesu FTDX-101MP" : 1044,
        "Yaesu FTDX-1200"  : 1034,
        "Yaesu FTDX-3000"  : 1037,
        "Yaesu FTDX-5000"  : 1032,
        "Yaesu FTDX-9000"  : 1030,
        "Yaesu VR-5000"    : 1026,
    }

    # Mapping from OpenWebRX modulations to Rigctl modulations
    MODES = {
        "nfm"  : "FM",     "wfm"  : "WFM",
        "am"   : "AM",     "sam"  : "SAM",
        "lsb"  : "LSB",    "usb"  : "USB",
        "lsbd" : "PKTLSB", "usbd" : "PKTUSB",
        "cw"   : "CWR",
    }

    def __init__(self, props: PropertyStack):
        pm = Config.get()
        self.enabled = pm["rig_enabled"]
        self.rigctl  = None
        self.thread  = None
        self.mod     = None
        self.fCenter = None
        self.fOffset = None
        self.subscriptions = [
            props.wireProperty("offset_freq", self.setFrequencyOffset),
            props.wireProperty("center_freq", self.setCenterFrequency),
            props.wireProperty("rig_enabled", self.setRigEnabled),
            props.wireProperty("mod", self.setDemodulator),
        ]
        super().__init__()
        # Start RigControl if enabled
        if self.enabled:
            self.enabled = self.rigStart()

    def stop(self):
        for sub in self.subscriptions:
            sub.cancel()
        self.subscriptions = []
        self.rigStop()

    def setFrequencyOffset(self, offset: int) -> None:
        if self.fCenter is not None and offset != self.fOffset:
            self.rigFrequency(self.fCenter + offset)
            self.fOffset = offset

    def setCenterFrequency(self, center: int) -> None:
        self.fCenter = center
        self.fOffset = None

    def setDemodulator(self, mod: str) -> None:
        if mod != self.mod:
            self.rigModulation(mod)
            self.mod = mod

    def setRigEnabled(self, enabled: bool) -> None:
        if enabled != self.enabled:
            self.enabled = enabled
            if enabled:
                self.enabled = self.rigStart()
            else:
                self.rigStop()

    # Press or release rig's PTT (i.e. transmit)
    def rigTX(self, active: bool) -> bool:
        return self.rigCommand("T {0}".format(1 if active else 0))

    # Set rig's frequency
    def rigFrequency(self, freq: int) -> bool:
        return self.rigCommand("F {0}".format(freq))

    # Set rig's modulation
    def rigModulation(self, mod: str) -> bool:
        if mod in self.MODES:
            return self.rigCommand("M {0} 0".format(self.MODES[mod]))
        else:
            return False

    # Start Rigctl and associated thread
    def rigStart(self):
        # Do not start twice
        if self.rigctl is not None:
            return True
        # Must have Hamlib/Rigctl installed
        if not FeatureDetector().is_available("rigcontrol"):
            return False
        # Must have rig control enabled
        if not self.enabled:
            return False
        # Compose Rigctl command
        pm = Config.get()
        address = pm["rig_address"]
        cmd = [
            "rigctl", "-m", str(pm["rig_model"]), "-r", pm["rig_device"]
        ] + (
            ["-c", str(address)] if address > 0 and address < 256 else []
        ) + ["-"]
        #cmd = ["rigctl", "-"] # @@@ REMOVE ME!!!!
        # Create Rigctl process, make stdout/stderr pipes non-blocking
        self.rigctl = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, text=True)
        os.set_blocking(self.rigctl.stdout.fileno(), False)
        os.set_blocking(self.rigctl.stderr.fileno(), False)
        # Create and start thread
        self.thread = threading.Thread(target=self._rigThread, name=type(self).__name__)
        self.thread.start()
        # Clear current frequency and modulation
        self.mod     = None
        self.fCenter = None
        self.fOffset = None
        # Done
        logger.debug("Started RigControl as '{0}'.".format(" ".join(cmd)))
        return True

    # Stop Rigctl and associated thread
    def rigStop(self):
        # Do not stop twice
        if self.rigctl is None:
            return
        # If Rigctl still running...
        if self.rigctl.poll() is None:
            # Try terminating Rigctl normally, kill if failed
            logger.info("Stopping RigControl executable...")
            try:
                self.rigctl.terminate()
                self.rigctl.wait(3)
            except TimeoutExpired:
                self.rigctl.kill()
        # The thread should have exited, since Rigctl exited
        logger.info("Waiting for RigControl thread...")
        self.thread.join()
        logger.info("Stopped RigControl.")
        self.thread = None
        self.rigctl = None

    # Send command to Rigctl
    def rigCommand(self, cmd: str) -> bool:
        if self.rigctl is not None:
            if self.rigctl.poll() is not None:
                self.rigctl = None
                return False
            try:
                self.rigctl.stdin.write(cmd + "\n")
                self.rigctl.stdin.flush()
                logger.debug("Sent '{0}' to RigControl.".format(cmd))
                return True
            except Exception as e:
                logger.debug("Failed sending '{0}' to RigControl: {1}.".format(cmd, str(e)))
        # Failed to send command
        return False

    # This thread function reads from Rigctl process' stdout/stderr
    def _rigThread(self):
        # While process is running...
        while self.rigctl.poll() is None:
            try:
                # Wait for output from the process
                readable, _, _ = select.select([self.rigctl.stdout, self.rigctl.stderr], [], [])
                for pipe in readable:
                    rsp = pipe.read().strip()
                    logger.debug("STD{0}: {1}".format("ERR" if pipe==self.rigctl.stderr else "OUT", rsp))
            except Exception as e:
                logger.debug("Failed receiving from RigControl: {1}.".format(str(e)))

        # Process stopped
        logger.debug("RigControl process quit ({0}).".format(self.rigctl.poll()))
