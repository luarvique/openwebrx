from owrx.aircraft import AircraftManager
from owrx.client import ClientRegistry
from owrx.map import Map, LocatorLocation
from owrx.aprs import AprsParser
from owrx.bands import Bandplan
from owrx.config import Config
from datetime import datetime, timezone

import logging

logger = logging.getLogger(__name__)

class MqttSubscriber(object):
    def __init__(self, mqttReporter):
        pm = Config.get()
        if pm["mqtt_chat"]:
            mqttReporter.addWatch("CLIENT", self._handleChat)
        if pm["mqtt_wsjt"]:
            mqttReporter.addWatch("JT9", self._handleWSJT)
            mqttReporter.addWatch("Q65", self._handleWSJT)
            mqttReporter.addWatch("FT8", self._handleWSJT)
            mqttReporter.addWatch("FT4", self._handleWSJT)
            mqttReporter.addWatch("FST4", self._handleWSJT)
            mqttReporter.addWatch("WSPR", self._handleWSJT)
            mqttReporter.addWatch("JT65", self._handleWSJT)
            mqttReporter.addWatch("FST4W", self._handleWSJT)
            mqttReporter.addWatch("MSK144", self._handleWSJT)
        if pm["mqtt_aircraft"]:
            mqttReporter.addWatch("ACARS", self._handleAircraft)
            mqttReporter.addWatch("ADSB", self._handleAircraft)
            mqttReporter.addWatch("HFDL", self._handleAircraft)
            mqttReporter.addWatch("VDL2", self._handleAircraft)
            mqttReporter.addWatch("UAT", self._handleAircraft)
        if pm["mqtt_aprs"]:
            mqttReporter.addWatch("APRS", self._handleAPRS)
        if pm["mqtt_ais"]:
            mqttReporter.addWatch("AIS", self._handleAPRS)

    def _handleChat(self, source, data):
        # Relay received chat messages to all connected users
        if data["state"] == "ChatMessage":
            ClientRegistry.getSharedInstance().RelayChatMessage(
                data["name"] + "@" + source, data["message"]
            )

    def _handleAircraft(self, source, data):
        # Remove original data from the message
        if "data" in data:
            del data["data"]
        # Update aircraft database with the received data
        AircraftManager.getSharedInstance().update(data)

    def _handleWSJT(self, source, data):
        band = None
        ts   = None
        # Determine band by frequency
        if "freq" in data:
            band = Bandplan.getSharedInstance().findBand(data["freq"])
        # Get timestamp, if available
        if "timestamp" in data:
            ts = datetime.fromtimestamp(data["timestamp"] / 1000, timezone.utc)
        # Put callsigns with locators on the map
        if "callsign" in data and "locator" in data:
            Map.getSharedInstance().updateLocation(
                data["callsign"], LocatorLocation(data["locator"]),
                data["mode"], band, hops=[source], timestamp=ts
            )
        # Put calls between callsigns on the map
        if "callsign" in data and "callee" in data:
            Map.getSharedInstance().updateCall(
                data["callsign"], data["callee"],
                data["mode"], band, timestamp=ts
            )

    def _handleAPRS(self, source, data):
        band = None
        ts   = None
        # Determine band by frequency
        if "freq" in data:
            band = Bandplan.getSharedInstance().findBand(data["freq"])
        # Get timestamp, if available
        if "timestamp" in data:
            ts = datetime.fromtimestamp(data["timestamp"] / 1000, timezone.utc)
        # Put APRS/AIS marker on the map
        AprsParser.updateMap(data, band, ts)
