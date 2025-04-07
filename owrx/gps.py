#
# This code is derived from the gpsd-py3 library code found at
# https://github.com/MartijnBraam/gpsd-py3/
#

from owrx.config import Config

import socket
import json
import logging
import datetime
import threading

gpsTimeFormat = "%Y-%m-%dT%H:%M:%S.%fZ"

logger = logging.getLogger(__name__)


#
# Exception that occurs when asking for location that has not been received
#
class NoFixError(Exception):
    pass


#
# GPS Update Thread
#
class GpsUpdater(object):
    sharedInstance = None
    creationLock = threading.Lock()

    @staticmethod
    def getSharedInstance():
        with GpsUpdater.creationLock:
            if GpsUpdater.sharedInstance is None:
                GpsUpdater.sharedInstance = GpsUpdater()
        return GpsUpdater.sharedInstance

    @staticmethod
    def start():
        GpsUpdater.getSharedInstance().startThread()

    @staticmethod
    def stop():
        GpsUpdater.getSharedInstance().stopThread()

    @staticmethod
    def init():
        # The __init__() method will do its job here
        GpsUpdater.getSharedInstance()

    def __init__(self):
        # Refresh every 5 minutes for now
        self.refreshPeriod = 5*60
        self.event  = threading.Event()
        self.thread = None
        # Start/stop main thread when setting changes
        Config.get().wireProperty("gps_updates", self._toggleUpdates)

    # Toggle GPS updates when setting changes
    def _toggleUpdates(self, enable):
        if (self.thread is not None) != enable:
            if enable:
                self.startThread()
            else:
                self.stopThread()

    # Start the main thread
    def startThread(self):
        if self.thread is None:
            self.event.clear()
            self.thread = threading.Thread(target=self._refreshThread, name=type(self).__name__)
            self.thread.start()

    # Stop the main thread
    def stopThread(self):
        if self.thread is not None:
            logger.info("Stopping GPS updater thread.")
            self.event.set()
            self.thread.join()

    # This is the actual thread function
    def _refreshThread(self):
        logger.info("Starting GPS updater thread...")
        gps = GpsdClient()
        pm  = Config.get()
        # Main loop
        while not self.event.is_set():
            try:
                pos = gps.getPosition()
                pos = pos.position() if pos else None
                pos = { "lat": pos[0], "lon": pos[1] } if pos else None
                if pos and pos != pm["receiver_gps"]:
                    logger.info("New position is {0}, {1}".format(pos["lat"], pos["lon"]))
                    pm["receiver_gps"] = pos
            except Exception as e:
                logger.error("Failed to get GPS position: " + str(e))
            # Wait until the next refresh
            self.event.wait(self.refreshPeriod)
        # Done with GPS
        gps.disconnect()


#
# GPSD Client
#
class GpsdClient(object):
    def __init__(self, host: str = "127.0.0.1", port: int = 2947):
        self.socket = None
        self.stream = None
        self.state  = {}
        self.connect(host, port)

    # Disconnect from GPSD if connected
    def disconnect(self):
        self.state = {}
        if self.stream:
            self.stream.close()
            self.stream = None
        if self.socket:
            self.socket.close()
            self.socket = None

    # Connect to GPSD at given address and port
    def connect(self, host: str = "127.0.0.1", port: int = 2947):
        self.disconnect()
        logger.info("Connecting to GPSD at {}:{}".format(host, port))
        try:
            # Connect socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, port))
            self.stream = self.socket.makefile(mode="rw")
            # Perform initial exchange
            logger.info("Waiting for welcome message...")
            welcome = json.loads(self.stream.readline())
            if "class" not in welcome or welcome["class"] != "VERSION":
                raise Exception("Unexpected data received as welcome. Not a GPSD v3 server?")
            logger.info("Enabling GPS...")
            self.stream.write('?WATCH={"enable":true}\n')
            self.stream.flush()
            # Get initial state
            for i in range(0, 2):
                self._parse_state(json.loads(self.stream.readline()))
            # Success
            return True
        except Exception as e:
            logger.error("Failed to connect: " + str(e))
        # Failed to connect
        self.disconnect()
        return False

    # Get current GPS device information
    def getDevice(self):
        try:
            return self.state["devices"]["devices"][0]
        except:
            return None

    # Get current GPS position
    def getPosition(self):
        if self.stream:
            logger.debug("Polling GPSD for position...")
            try:
                # Poll GPSD
                self.stream.write("?POLL;\n")
                self.stream.flush()
                response = json.loads(self.stream.readline())
                # Parse and return response
                if response["class"] != "POLL":
                    raise Exception("Unexpected message received: {}".format(response["class"]))
                return GpsResponse.from_json(response)
            except Exception as e:
                logger.error("Failed to poll: " + str(e))
        # Failed to poll
        return None

    # Parse JSON state data received from GPSD
    def _parse_state(self, data):
        try:
            if data["class"] == "DEVICES":
                if not data["devices"]:
                    logger.warn("No GPS devices found")
                self.state["devices"] = data
            elif data["class"] == "WATCH":
                self.state["watch"] = data
            else:
                raise Exception("Unexpected GPS message: {}".format(data["class"]))
        except Exception as e:
            logger.error("Failed to parse: " + str(e))


#
# GPSD Response
#
#   Use the attributes to get the raw gpsd data, use the methods to get
#   parsed and corrected information.
#
#   mode:   Indicates the status of the GPS reception, 0=No value, 1=No fix, 2=2D fix, 3=3D fix
#   sats:   The number of satellites received by the GPS unit
#   sats_valid: The number of satellites with valid information
#   lon:    Longitude in degrees
#   lat:    Latitude in degrees
#   alt:    Altitude in meters
#   track:  Course over ground, degrees from true north
#   hspeed: Speed over ground, meters per second
#   climb:  Climb (positive) or sink (negative) rate, meters per second
#   time:   Time/date stamp in ISO8601 format, UTC. May have a fractional part of up to .001sec precision.
#   error:  GPSD error margin information
#
#   GPSD error margin information
#   -----------------------------
#   c: ecp: Climb/sink error estimate in meters/sec, 95% confidence.
#   s: eps: Speed error estinmate in meters/sec, 95% confidence.
#   t: ept: Estimated timestamp error (%f, seconds, 95% confidence).
#   v: epv: Estimated vertical error in meters, 95% confidence. Present if mode is 3 and DOPs can be
#           calculated from the satellite view.
#   x: epx: Longitude error estimate in meters, 95% confidence. Present if mode is 2 or 3 and DOPs
#           can be calculated from the satellite view.
#   y: epy: Latitude error estimate in meters, 95% confidence. Present if mode is 2 or 3 and DOPs can
#           be calculated from the satellite view.
#
class GpsResponse(object):
    def __init__(self):
        self.mode   = 0
        self.sats   = 0
        self.sats_valid = 0
        self.lon    = 0.0
        self.lat    = 0.0
        self.alt    = 0.0
        self.track  = 0
        self.hspeed = 0
        self.climb  = 0
        self.time   = ""
        self.error  = {}

    @classmethod
    def from_json(cls, packet):
        """ Create GpsResponse instance based on the json data from GPSD
        :type packet: dict
        :param packet: JSON decoded GPSD response
        :return: GpsResponse
        """
        result = cls()
        if not packet["active"]:
            raise UserWarning("GPS not active")
        last_tpv = packet["tpv"][-1]
        last_sky = packet["sky"][-1]

        if "satellites" in last_sky:
            result.sats = len(last_sky["satellites"])
            result.sats_valid = len(
                [sat for sat in last_sky["satellites"] if sat["used"] == True])
        else:
            result.sats = 0;
            result.sats_valid = 0;

        result.mode = last_tpv["mode"]

        if last_tpv["mode"] >= 2:
            result.lon = last_tpv["lon"] if "lon" in last_tpv else 0.0
            result.lat = last_tpv["lat"] if "lat" in last_tpv else 0.0
            result.track = last_tpv["track"] if "track" in last_tpv else 0
            result.hspeed = last_tpv["speed"] if "speed" in last_tpv else 0
            result.time = last_tpv["time"] if "time" in last_tpv else ""
            result.error = {
                "c": 0,
                "s": last_tpv["eps"] if "eps" in last_tpv else 0,
                "t": last_tpv["ept"] if "ept" in last_tpv else 0,
                "v": 0,
                "x": last_tpv["epx"] if "epx" in last_tpv else 0,
                "y": last_tpv["epy"] if "epy" in last_tpv else 0
            }

        if last_tpv["mode"] >= 3:
            result.alt = last_tpv["alt"] if "alt" in last_tpv else 0.0
            result.climb = last_tpv["climb"] if "climb" in last_tpv else 0
            result.error["c"] = last_tpv["epc"] if "epc" in last_tpv else 0
            result.error["v"] = last_tpv["epv"] if "epv" in last_tpv else 0

        return result

    def position(self):
        """ Get the latitude and longtitude as tuple.
        Needs at least 2D fix.

        :return: (float, float)
        """
        if self.mode < 2:
            raise NoFixError("Needs at least 2D fix")
        return self.lat, self.lon

    def altitude(self):
        """ Get the altitude in meters.
        Needs 3D fix

        :return: (float)
        """
        if self.mode < 3:
            raise NoFixError("Needs at least 3D fix")
        return self.alt

    def movement(self):
        """ Get the speed and direction of the current movement as dict

        The speed is the horizontal speed.
        The climb is the vertical speed
        The track is te direction of the motion
        Needs at least 3D fix

        :return: dict[str, float]
        """
        if self.mode < 3:
            raise NoFixError("Needs at least 3D fix")
        return {"speed": self.hspeed, "track": self.track, "climb": self.climb}

    def speed_vertical(self):
        """ Get the vertical speed with the small movements filtered out.
        Needs at least 2D fix

        :return: float
        """
        if self.mode < 2:
            raise NoFixError("Needs at least 2D fix")
        if abs(self.climb) < self.error["c"]:
            return 0
        else:
            return self.climb

    def speed(self):
        """ Get the horizontal speed with the small movements filtered out.
        Needs at least 2D fix

        :return: float
        """
        if self.mode < 2:
            raise NoFixError("Needs at least 2D fix")
        if self.hspeed < self.error["s"]:
            return 0
        else:
            return self.hspeed

    def position_precision(self):
        """ Get the error margin in meters for the current fix.

        The first value return is the horizontal error, the second
        is the vertical error if a 3D fix is available

        Needs at least 2D fix

        :return: (float, float)
        """
        if self.mode < 2:
            raise NoFixError("Needs at least 2D fix")
        return max(self.error["x"], self.error["y"]), self.error["v"]

    def map_url(self):
        """ Get a openstreetmap url for the current position
        :return: str
        """
        if self.mode < 2:
            raise NoFixError("Needs at least 2D fix")
        return "http://www.openstreetmap.org/?mlat={}&mlon={}&zoom=15".format(self.lat, self.lon)

    def get_time(self, local_time=False):
        """ Get the GPS time

        :type local_time: bool
        :param local_time: Return date in the local timezone instead of UTC
        :return: datetime.datetime
        """
        if self.mode < 2:
            raise NoFixError("Needs at least 2D fix")
        time = datetime.datetime.strptime(self.time, gpsTimeFormat)

        if local_time:
            time = time.replace(tzinfo=datetime.timezone.utc).astimezone()

        return time

    def __repr__(self):
        modes = {
            0: "No mode",
            1: "No fix",
            2: "2D fix",
            3: "3D fix"
        }
        if self.mode < 2:
            return "<GpsResponse {}>".format(modes[self.mode])
        if self.mode == 2:
            return "<GpsResponse 2D Fix {} {}>".format(self.lat, self.lon)
        if self.mode == 3:
            return "<GpsResponse 3D Fix {} {} ({} m)>".format(self.lat, self.lon, self.alt)
