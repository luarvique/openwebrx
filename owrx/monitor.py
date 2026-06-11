from owrx.config.core import CoreConfig

import socket
import json
import threading
import time
import logging
import uuid
import os

logger = logging.getLogger(__name__)

class FileMonitor(threading.Thread):
    @staticmethod
    def getNewFilePath(prefix: str = "openwebrx") -> str:
        # Generate new file name
        filePath = "{tmp_dir}/{prefix}_{uid}.sock".format(
            tmp_dir = CoreConfig().get_temporary_directory(),
            prefix = prefix,
            uid = str(uuid.uuid4())[:8]
        )
        # Remove existing file, if present
        if os.path.exists(filePath):
            try:
                os.unlink(filePath)
            except OSError:
                pass
        # Done
        return filePath

    def __init__(self, file_path="/tmp/status.sock"):
        super().__init__(daemon=True)
        self.file_path = file_path
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
        fr = None

        while self.running:
            try:
                # Open File
                fr  = open(self.file_path,'rb')
                logger.debug(f"Monitor connected: {self.file_path}")

                buffer = b""
                while self.running:
                    try:
                        data = fr.read(4096)
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

                    except Exception as e:
                        logger.error(f"Data read error: {e}")
                        break

            except (FileNotFoundError, ConnectionRefusedError):
                logger.debug(f"File not ready: {self.file_path}")
            except Exception as e:
                logger.error(f"Monitor error: {e}")
            finally:
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 1.5, 10.0)
                if fr:
                    try:
                        fr.close()
                    except:
                        pass
                    fr = None

        # Monitor thread done
        self.running = False
        logger.debug(f"Monitor stopped: {self.file_path}")

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
            logger.debug(f"Stopping monitor: {self.file_path}")
            self.join(timeout = 2.0)

class SocketMonitor(threading.Thread):
    @staticmethod
    def getNewSocketPath(prefix: str = "openwebrx") -> str:
        # Generate new socket name
        socketPath = "{tmp_dir}/{prefix}_{uid}.sock".format(
            tmp_dir = CoreConfig().get_temporary_directory(),
            prefix = prefix,
            uid = str(uuid.uuid4())[:8]
        )
        # Remove existing socket, if present
        if os.path.exists(socketPath):
            try:
                os.unlink(socketPath)
            except OSError:
                pass
        # Done
        return socketPath

    def __init__(self, socket_path="/tmp/status.sock"):
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
                # Connect new socket
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect(self.socket_path)
                logger.debug(f"Monitor connected: {self.socket_path}")
                reconnect_delay = 1.0

                # Keep reading status via socket
                buffer = b""
                while self.running:
                    try:
                        data = sock.recv(4096)
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
                if sock:
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                        sock.close()
                    except (OSError, AttributeError) as e:
                        logger.debug(f"Socket cleanup error: {e}")
                    sock = None

            except (FileNotFoundError, ConnectionRefusedError):
                logger.debug(f"Socket not ready: {self.socket_path}")
            except Exception as e:
                logger.error(f"Monitor error: {e}")
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
        logger.debug(f"Monitor stopped: {self.socket_path}")

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
            logger.debug(f"Stopping monitor: {self.socket_path}")
            self.join(timeout = 2.0)
