import socket
import json
import threading
import time
import logging


logger = logging.getLogger(__name__)


class DrmStatusMonitor(threading.Thread):
    def __init__(self, socket_path="/tmp/dream_status.sock"):
        super().__init__(daemon=True)
        self.socket_path = socket_path
        self.running = False
        self.callbacks = []

    def add_callback(self, callback):
        self.callbacks.append(callback)

    def remove_callback(self, callback):
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def run(self):
        self.running = True
        reconnect_delay = 1.0
        sock = None

        while self.running:
            try:
                # Connect new socket to Dream status
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect(self.socket_path)
                logger.debug(f"DRM monitor connected: {self.socket_path}")
                reconnect_delay = 1.0

                # Keep reading Dream status via socket
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
                                logger.error(f"DRM decode error: {e}")

                    except socket.timeout:
                        continue
                    except Exception as e:
                        logger.error(f"DRM read error: {e}")
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
                logger.debug(f"DRM socket not ready: {self.socket_path}")
            except Exception as e:
                logger.error(f"DRM monitor error: {e}")
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
        logger.debug(f"DRM monitor stopped: {self.socket_path}")

    def _process_status(self, json_str):
        try:
            status = json.loads(json_str)
#            logger.debug(f"DRM status: {status}")
            for callback in self.callbacks:
                try:
                    callback(status)
                except Exception as e:
                    logger.error(f"DRM callback error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid DRM JSON: {e}")

    def stop(self):
        self.running = False
        if self.is_alive():
            logger.info(f"Stopping DRM monitor: {self.socket_path}")
            self.join(timeout = 2.0)
