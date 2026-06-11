from owrx.toolbox import TextParser

import socket
import json
import threading
import time
import logging


logger = logging.getLogger(__name__)


class TetraMonitor(threading.Thread):
    def __init__(self, socket_path="/tmp/tetra_status.sock"):
        super().__init__(daemon=True)
        self.socket_path = socket_path
        self.frequency = 0
        self.running = False
        self.callbacks = []

    def add_callback(self, callback):
        self.callbacks.append(callback)

    def remove_callback(self, callback):
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def setDialFrequency(self, frequency: int) -> None:
        self.frequency = frequency

    def stop(self):
        self.running = False
        if self.is_alive():
            logger.info(f"Stopping Tetra monitor: {self.socket_path}")
            self.join(timeout = 2.0)

    def run(self):
        self.running = True
        reconnect_delay = 1.0
        sock = None

        while self.running:
            try:
                # Connect new socket to Tetra status
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect(self.socket_path)
                logger.debug(f"Tetra monitor connected: {self.socket_path}")
                reconnect_delay = 1.0

                # Keep reading Tetra status via socket
                buffer = b""
                while self.running:
                    try:
                        data = sock.recv(4096)
                        if not data:
                            break

                        buffer += data
                        while b'\n' in buffer:
                            line, buffer = buffer.split(b'\n', 1)
                            try:
                                decoded_line = line.decode('utf-8').strip()
                                if decoded_line:
                                    self._process_status(decoded_line)
                            except UnicodeDecodeError as e:
                                logger.error(f"Tetra decode error: {e}")

                    except socket.timeout:
                        continue
                    except Exception as e:
                        logger.error(f"Tetra read error: {e}")
                        break

                # Clean up and close socket
                if sock:
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                        sock.close()
                    except (OSError, AttributeError) as e:
                        logger.debug(f"Socket cleanup error: {e}")
                    sock = None

            except (FileNotFoundError, ConnectionRefusedError):
                logger.debug(f"Tetra socket not ready: {self.socket_path}")
            except Exception as e:
                logger.error(f"Tetra monitor error: {e}")
            finally:
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 1.5, 10.0)
                if sock:
                    try:
                        sock.close()
                    except:
                        pass
                    sock = None

        # Monitor thread done
        self.running = False
        logger.debug(f"Tetra monitor stopped: {self.socket_path}")

    def _process_status(self, json_str):
        status = self.parse(json_str)
        if status:
            logger.debug(f"Tetra status: {status}")
            for callback in self.callbacks:
                try:
                    callback(status)
                except Exception as e:
                    logger.error(f"Tetra callback error: {e}")

    def parse(self, text):
        # Try parsing JSON
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.debug("Cannot parse JSON: '%s'", text)
            return None

        # Must be a dictionary containing FTYP
        if not isinstance(data, dict) or "FTYP" not in data:
            return None

        # Only output data when there is voice traffic
        if "AUDIO" not in data or data["AUDIO"] != 1:
            return None

        # Start parsing
        out = { "mode": "TETRA", "ft": int(data["FTYP"]) }

        # Current frequency
        if self.frequency:
            out["freq"] = self.frequency

        # Signal quality
        if "dB" in data:
            out["rfdb"] = float(data["dB"])
        if "AFC" in data:
            out["offset"] = int(data["AFC"])
        if "EYE" in data:
            out["eye"] = int(data["EYE"])

        # Timeslot / frame / multiframe counters
        if "TN" in data:
            out["tn"] = int(data["TN"])
        if "FN" in data:
            out["fn"] = int(data["FN"])
        if "MN" in data:
            out["mn"] = int(data["MN"])

        # Network code: CC = "MCC,MNC,BCC"
        if "CC" in data:
            parts = str(data["CC"]).split(",")
            if len(parts) == 3:
                try:
                    out["mcc"] = int(parts[0])
                    out["mnc"] = int(parts[1])
                    out["bcc"] = int(parts[2])
                except ValueError:
                    logger.debug("TetraParser: malformed CC: %r", data["CC"])

        # TX / RX frequencies
        if "TX" in data:
            out["tx_mhz"] = float(data["TX"])
        if "RX" in data:
            out["rx_mhz"] = float(data["RX"])

        # Location area / MS transmit power
        if "LA" in data:
            out["la"] = int(data["LA"])
        if "Po" in data:
            out["power_dbm"] = int(data["Po"])

        # Service flags
        if "VOICE" in data:
            out["voice_service"] = data["VOICE"] == 1
        if "ENC" in data:
            out["air_encrypted"] = data["ENC"] == 1
        if "AUDIO" in data:
            out["audio"] = data["AUDIO"] == 1

        # Subscriber identity
        if "ssi" in data:
            out["ssi"] = [int(data["ssi"])]

        # Addressing (traffic frames)
        if "ADRTYP" in data:
            out["adr_type"] = int(data["ADRTYP"])
        if "MAC" in data:
            out["mac"] = int(data["MAC"])

        # @@@ Why are we doing this?
        if "AUDIO" in data and data["AUDIO"] == 1:
            out["air_encrypted"] = False

        # Done
        return out
