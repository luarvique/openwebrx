from owrx.config.core import CoreConfig

import select
import socket
import json
import threading
import time
import logging
import uuid
import os

logger = logging.getLogger(__name__)


class Monitor(threading.Thread):
    @staticmethod
    def getNewPathName(prefix: str = "openwebrx") -> str:
        # Generate new pathname
        pathName = "{tmp_dir}/{prefix}_{uid}".format(
            tmp_dir = CoreConfig().get_temporary_directory(),
            prefix = prefix,
            uid = str(uuid.uuid4())[:8]
        )
        # Remove existing file or socket, if present
        if os.path.exists(pathName):
            try:
                os.unlink(pathName)
            except OSError:
                pass
        # Done
        return pathName

    def __init__(self, pathName: str):
        super().__init__(daemon=True)
        self.pathName = pathName
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
        source = None

        while self.running:
            try:
                # Open monitored file or socket
                source = self._open(self.pathName)
                logger.debug(f"Monitor connected: {self.pathName}")
                reconnect_delay = 1.0

                # Keep reading status
                buffer = b""
                while self.running:
                    try:
                        data = self._read(source)
                        if not data:
                            break

                        buffer += data
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            try:
                                decoded_line = line.decode("utf-8").strip()
                                if decoded_line:
                                    self._process_status(decoded_line)
                            except UnicodeDecodeError as e:
                                logger.error(f"Data decode error: {e}")

                    except socket.timeout:
                        continue
                    except Exception as e:
                        logger.error(f"Data read error: {e}")
                        break

                # Clean up and close socket
                if source:
                    try:
                        self._close(source)
                    except (OSError, AttributeError) as e:
                        logger.debug(f"Cleanup error: {e}")
                    source = None

            except (FileNotFoundError, ConnectionRefusedError):
                logger.debug(f"Not ready: {self.pathName}")
            except Exception as e:
                logger.error(f"Monitor error: {e}")
            finally:
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 1.5, 10.0)
                if source:
                    try:
                        self._close(source)
                    except:
                        pass
                    source = None

        # Monitor thread done
        self.running = False
        logger.debug(f"Monitor stopped: {self.pathName}")

    def _process_status(self, json_str):
        try:
            status = json.loads(json_str)
            logger.debug(f"Status: {status}")
            for callback in self.callbacks:
                try:
                    callback(status)
                except Exception as e:
                    logger.error(f"Monitor callback error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: '{json_str}'")

    def stop(self):
        self.running = False
        if self.is_alive():
            logger.debug(f"Stopping monitor: {self.pathName}")
            self.join(timeout = 2.0)

    def _open(self, filePath: str):
        return None

    def _read(self, source):
        return None

    def _close(self, source):
        pass


class SocketMonitor(Monitor):
    def _open(self, filePath: str):
        source = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        source.settimeout(5.0)
        source.connect(filePath)
        return source

    def _read(self, source):
        return source.recv(4096)

    def _close(self, source):
        source.shutdown(socket.SHUT_RDWR)
        source.close()


class FileMonitor(Monitor):
    def _open(self, filePath: str):
        source = open(filePath, "rb")
        os.set_blocking(source.fileno(), False)
        return source

    def _read(self, source):
        while self.running:
            try:
                r, w, x = select.select([source], [], [], 1.0)
                if r:
                    data = source.read()
                    if data:
                        return data
            except BlockingIOError:
                pass
            except Exception as e:
                logger.error(f"Exception reading data: {e}")
                return None
        return None

    def _close(self, source):
        source.close()
