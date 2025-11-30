from owrx.client import ClientRegistry

import logging
import json


logger = logging.getLogger(__name__)

class MqttSubscriber(object):
    def __init__(self, mqttReporter):
        mqttReporter.addWatch("CLIENT", self._handleCLIENT)

    def _handleCLIENT(self, msg):
        try:
            data = json.loads(msg)
            if data["state"] == "ChatMessage":
                ClientRegistry.getSharedInstance().RelayChatMessage(
                    data["name"], data["message"]
                )
        except Exception as e:
            logger.exception("Exception receving MQTT message: {}".format(e))
