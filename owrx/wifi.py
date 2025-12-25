from owrx.config import Config
import subprocess
import threading
import time
import re

import logging

logger = logging.getLogger(__name__)

class WiFi(object):
    sharedInstance = None
    creationLock = threading.Lock()

    # Return a global instance of the WiFi manager.
    @staticmethod
    def getSharedInstance():
        with WiFi.creationLock:
            if WiFi.sharedInstance is None:
                WiFi.sharedInstance = WiFi()
        return WiFi.sharedInstance

    def __init__(self):
        self.lock = threading.Lock()
        self.event = threading.Event()
        self.thread = None

    def startConnectionCheck(self, delay: int = 1):
        # Stop existing connection check
        if self.thread is not None:
            self.event.set()
            while self.thread is not None:
                time.sleep(1)
        # This is how much we wait until the actual check
        self.checkDelay = delay
        # Start delayed connection check
        self.thread = threading.Thread(target=self._connectionThread, name=type(self).__name__ + ".Check")
        self.thread.start()

    def startHotspot(self, ssid: str = "openwebrx", password: str = "openwebrx", ip: str = "192.168.10.1", device: str = "wlan0"):
        if len(ssid) > 0 and len(password) > 0 and len(device) > 0:
            # Make sure WiFi is on
            self.enableRadio()
            # Create a WiFi hotspot
            logger.info("Starting hotspot '{0}'...".format(ssid))
            command1 = [
                "nmcli", "device", "wifi", "hotspot",
                "con-name", "owrx-hotspot",
                "ifname", device,
                "ssid", ssid,
                "password", password
            ]
            command2 = [
                "nmcli", "con", "modify", "owrx-hotspot",
                "ipv4.addresses", ip + "/24",
                "ipv4.gateway", ip
            ]
            command3 = [
                "nmcli", "con", "up", "owrx-hotspot"
            ]
            try:
                subprocess.run(command1, check=True)
                subprocess.run(command2, check=True)
                subprocess.run(command3, check=True)
                return True
            except Exception as e:
                logger.error("Failed to start hotspot '{0}': {1}".format(ssid, str(e)))
        return False

    def stopHotspot(self):
        return self.delete("owrx-hotspot")

    def enableRadio(self, enable: bool = True):
        command = ["nmcli", "radio", "wifi", "on" if enable else "off"]
        try:
            subprocess.run(command, check=True)
            return True
        except Exception as e:
            logger.error("Failed to {0} radio: {1}".format("enable" if enable else "disable", str(e)))
        return False

    def getCurrentSSID(self, device: str = "wlan0"):
        command = ["nmcli", "-t", "-c", "no", "device", "status"]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            lines = result.stdout.splitlines()
            for line in lines:
                m = re.match(r"^(.*):(.*):(.*):(.*)\s*$", line)
                if m is not None and m.group(1) == device and m.group(3) == "connected":
                    return m.group(4)
        except Exception as e:
            logger.error("Failed to get connected SSID: " + str(e))
        return None

    def getAll(self):
        command = ["nmcli", "-t", "-c", "no", "con", "show"]
        out = []
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            lines = result.stdout.splitlines()
            for line in lines:
                m = re.match(r"^(.*):(.*):(.*):(.*)\s*$", line)
                if m is not None and m.group(3) == "802-11-wireless":
                    name = m.group(1)
                    uuid = m.group(2)
                    type = m.group(3)
                    dev  = m.group(4)
                    out.append({ "name": name, "uuid": uuid })
        except Exception as e:
            logger.error("Failed to get connections: " + str(e))
        return out

    def add(self, ssid: str, password: str, device: str = "wlan0"):
        if len(ssid) > 0 and len(password) > 0 and len(device) > 0:
            logger.info("Adding connection '{0}'...".format(ssid))
            command = [
                "nmcli", "con", "add",
                "con-name", "owrx." + ssid,
                "ifname", device,
                "type", "wifi",
                "ssid", ssid,
                "wifi-sec.key-mgmt", "wpa-psk",
                "wifi-sec.psk", password,
                "connection.autoconnect", "yes"
            ]
            try:
                subprocess.run(command, check=True)
                return True
            except Exception as e:
                logger.error("Failed to add connection '{0}': {1}".format(ssid, str(e)))
        return False

    def delete(self, name: str):
        if len(name) > 0:
            command = [ "nmcli", "con", "delete", name ]
            logger.info("Deleting connection '{0}'...".format(name))
            try:
                subprocess.run(command, check=True)
                return True
            except Exception as e:
                logger.error("Failed to delete connection '{0}': {1}".format(name, str(e)))
        return False

    def applyNewSettings(self):
        # Delete all connections added by OpenWebRX, including hotspot
        for ap in self.getAll():
            if ap["name"] == "owrx-hotspot" or ap["name"].startswith("owrx."):
                self.delete(ap["uuid"])
        # Add active WiFi connections from config
        pm = Config()
        on = 0
        if pm["wifi_enable_1"]:
            self.add(pm["wifi_name_1"], pm["wifi_pass_1"])
            on += 1
        if pm["wifi_enable_2"]:
            self.add(pm["wifi_name_2"], pm["wifi_pass_2"])
            on += 1
        if pm["wifi_enable_3"]:
            self.add(pm["wifi_name_3"], pm["wifi_pass_3"])
            on += 1
        if pm["wifi_enable_4"]:
            self.add(pm["wifi_name_4"], pm["wifi_pass_4"])
            on += 1
        # If any connections added, make sure WiFi is enabled
        if on > 0:
            self.enableRadio()
        # If no WiFi connections go up after a while, become hotspot
        self.startConnectionCheck(60)

    # Wait for a while, then check if WiFi connection is active
    # Start WiFi hotspot if there is no active WiFi connection
    def _connectionThread(self):
        logger.info("Will check for active connection in {0} seconds.".format(self.checkDelay))
        self.event.wait(self.checkDelay)
        if self.event.is_set():
            logger.info("Cancelled active connection check.")
        else:
            ssid = self.getCurrentSSID()
            if ssid is not None:
                logger.info("Found active connection to '{0}'.".format(ssid))
            else:
                logger.info("No active connection, becoming hotspot...")
                pm = Config.get()
                if pm["wifi_enable_ap"]:
                    self.startHotspot(pm["wifi_name_ap"], pm["wifi_pass_ap"])
        # Thread completed
        self.thread = None
