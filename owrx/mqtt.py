from owrx.client import ClientRegistry
from owrx.map import Map, LocatorLocation
from owrx.bands import Bandplan
from owrx.config import Config

import logging

logger = logging.getLogger(__name__)

class MqttSubscriber(object):
    def __init__(self, mqttReporter):
        pm = Config.get()
        if pm["mqtt_chat"]:
            mqttReporter.addWatch("CLIENT", self._handleCHAT)
        if pm["mqtt_wsjt"]:
            mqttReporter.addWatch("JT9", self._handleWSJT)
            mqttReporter.addWatch("Q65", self._handleWSJT)
            mqttReporter.addWatch("FT8", self._handleWSJT)
            mqttReporter.addWatch("FT4", self._handleWSJT)
            mqttReporter.addWatch("FST4", self._handleWSJT)
            mqttReporter.addWatch("WSPR", self._handleWSJT)
            mqttReporter.addWatch("JT65", self._handleWSJT)
            mqttReporter.addWatch("FST4W", self._handleWSJT)

    def _handleCHAT(self, data):
        # Relay received chat messages to all connected users
        if data["state"] == "ChatMessage":
            ClientRegistry.getSharedInstance().RelayChatMessage(
                data["name"], data["message"]
            )

    def _handleWSJT(self, data):
        # Determine band by frequency
        band = None
        if "freq" in data:
            band = Bandplan.getSharedInstance().findBand(data["freq"])
        # Put callsigns with locators on the map
        if "callsign" in data and "locator" in data:
            Map.getSharedInstance().updateLocation(
                data["callsign"], LocatorLocation(data["locator"]), data["mode"], band
            )
        # Put calls between callsigns on the map
        if "callsign" in data and "callee" in data:
            Map.getSharedInstance().updateCall(
                data["callsign"], data["callee"], data["mode"], band
            )
