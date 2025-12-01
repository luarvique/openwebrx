from paho.mqtt.client import Client, SubscribeOptions, MQTTv5
from owrx.reporting.reporter import Reporter
from owrx.config import Config
from owrx.property import PropertyDeleted
from owrx.client import ClientRegistry
from owrx.mqtt import MqttSubscriber
import json
import threading
import time

import logging

logger = logging.getLogger(__name__)


class MqttReporter(Reporter):
    DEFAULT_TOPIC = "openwebrx"

    def __init__(self):
        pm = Config.get()
        self.topic = self.DEFAULT_TOPIC
        self.client = self._getClient()
        self.connected = False
        self.watchLock = threading.Lock()
        self.watching = {}
        self.subscriber = MqttSubscriber(self)
        self.subscriptions = [
            pm.wireProperty("mqtt_topic", self._setTopic),
            pm.filter("mqtt_host", "mqtt_user", "mqtt_password", "mqtt_client_id", "mqtt_use_ssl").wire(self._reconnect),
            pm.filter("mqtt_chat", "mqtt_wsjt").wire(self._resubscribe)
        ]

    def _getClient(self):
        pm = Config.get()
        clientId = pm["mqtt_client_id"] if "mqtt_client_id" in pm else ""
        client = Client(client_id=clientId, protocol=MQTTv5)
        client.on_disconnect = self._onDisconnect
        client.on_connect = self._onConnect
        client.on_message = self._onMessage

        if "mqtt_user" in pm and "mqtt_password" in pm:
            client.username_pw_set(pm["mqtt_user"], pm["mqtt_password"])

        port = 1883
        if pm["mqtt_use_ssl"]:
            client.tls_set()
            port = 8883

        parts = pm["mqtt_host"].split(":")
        host = parts[0]
        if len(parts) > 1:
            port = int(parts[1])

        try:
            client.connect(host=host, port=port)
        except Exception as e:
            logger.error("Exception connecting: " + str(e))

        threading.Thread(target=client.loop_forever, name=type(self).__name__).start()

        return client

    def _setTopic(self, topic):
        if topic is PropertyDeleted:
            self.topic = self.DEFAULT_TOPIC
        else:
            self.topic = topic

    def _reconnect(self, *args, **kwargs):
        logger.debug("Reconnecting...")
        old = self.client
        self.client = self._getClient()
        old.disconnect()

    def _resubscribe(self, *args, **kwargs):
        logger.debug("Resubscribing...")
        # Remove all current subscriptions
        self.removeAllWatches()
        # Resubscribe
        self.subscriber = MqttSubscriber(self)

    def _onConnect(self, client, userdata, flags, rc, properties=None):
        options = SubscribeOptions(noLocal=1)
        with self.watchLock:
            # Subscribe to all watched topics
            for watch in list(self.watching.keys()):
                client.subscribe(self.topic + "/" + watch, options=options)
            # We are now connected to the MQTT broker
            self.connected = True

    def _onDisconnect(self, client, userdata, rc, properties=None):
        # We are now disconnected from the MQTT broker
        self.connected = False

    def _onMessage(self, client, userdata, msg, properties=None):
        # Call message handlers for topics we are watching
        if msg.topic.startswith(self.topic + "/"):
            watch = msg.topic[len(self.topic) + 1 : ]
            if watch in self.watching:
                try:
                    self.watching[watch](json.loads(msg.payload.decode()))
                except Exception as e:
                    logger.exception("Exception receving MQTT message: {}".format(e))

    # Watch given MQTT topic
    def addWatch(self, watch, handler):
        with self.watchLock:
            # When client already connected, subscribe to new topics immediately
            if watch not in self.watching and self.connected:
                options = SubscribeOptions(noLocal=1)
                self.client.subscribe(self.topic + "/" + watch, options=options)
            # Update topic-specific handler
            self.watching[watch] = handler

    # Stop watching all MQTT topics
    def removeAllWatches(self):
        with self.watchLock:
            # Unsubscribe from everything
            if self.connected:
                for watch in list(self.watching.keys()):
                    self.client.unsubscribe(self.topic + "/" + watch)
            # No more watches
            self.watching = {}

    def stop(self):
        self.client.disconnect()
        while self.subscriptions:
            self.subscriptions.pop().cancel()

    def spot(self, spot):
        topic = self.topic + "/" + spot["mode"] if "mode" in spot else self.topic
        self.client.publish(topic, payload=json.dumps(spot))
