from csdr.module import ThreadModule
from pycsdr.types import Format
from owrx.reporting import ReportingEngine
from owrx.storage import DataRecorder
from owrx.config import Config
from datetime import datetime

import urllib.request
import urllib.error
import threading
import json
import logging
import time

logger = logging.getLogger(__name__)


class WhisperTranscriber(ThreadModule, DataRecorder):
    def __init__(self, sampleRate: int = 12000, service: bool = False, chunkSeconds: int = 20, maxBytes: int = 1024 * 1024):
        self.sampleRate = sampleRate
        self.service    = service
        self.chunkSeconds = max(10, chunkSeconds)
        self.chunkSize  = self.chunkSeconds * sampleRate * 2
        self.event      = threading.Event()
        self.lock       = threading.RLock()
        self.buffer     = b""
        DataRecorder.__init__(self, "SPEECH", ".txt", maxBytes)
        ThreadModule.__init__(self)

    def getInputFormat(self) -> Format:
        return Format.SHORT

    def getOutputFormat(self) -> Format:
        return Format.CHAR

    def setDialFrequency(self, frequency: int) -> None:
        if frequency != self.frequency:
            self.frequency = frequency
            self.closeFile()
            with self.lock:
                self.buffer = b""

    def writeOutput(self, output):
        with self.lock:
            if self.service:
                self.writeFile(output.encode("utf-8"))
            elif self.writer is not None:
                self.writer.write(output.encode("utf-8"))

    def run(self):
        # Spawn a worker thread for sending queued data to Whisper
        self.thread = threading.Thread(target=self.whisperWorker, name="WhisperWorker").start()
        # Consume input audio until it ends
        while self.doRun and self.reader is not None:
            data = self.reader.read()
            if data is None:
                self.doRun = False
                break
            with self.lock:
                # Make a timestamp
                if len(self.buffer) == 0:
                    self.tstamp = datetime.now().timestamp()
                # Collect incoming data
                self.buffer += data
                # Truncate extra data
                if len(self.buffer) >= self.chunkSize * 2:
                    t = (len(self.buffer) - self.chunkSize) / self.sampleRate
                    logger.info(f"Skipping {t:.2f} seconds...")
                    self.writeOutput(f"[skipping {t:.2f} sec]\n")
                    self.buffer = self.buffer[-self.chunkSize:]
                # Kick transcription worker thread
                if len(self.buffer) >= self.chunkSize:
                    self.event.set()
        # Signal worker thread to stop
        self.doRun = False
        self.event.set()

    # This thread keeps sending queue data to Whisper
    def whisperWorker(self):
        logger.info("Whisper worker thread is running")
        url = Config.get()["speech_url"]
        ts = time.time()
        while self.doRun and self.writer is not None:
            try:
                # Wait for enough input data
                t = self.chunkSeconds - (time.time() - ts);
                if t > 0:
                    self.event.wait(t)
                    if not self.doRun:
                        break
                # Get accumulated data from the buffer
                data = None
                stmp = None
                with self.lock:
                    self.event.clear()
                    if len(self.buffer) > 0:
                        stmp = self.tstamp
                        data = self.buffer
                        self.buffer = b""
                # Mark time when the buffer became empty
                ts = time.time()
                # If there is data...
                if data is not None and self.doRun:
                    t = len(data) / self.sampleRate / 2
                    logger.info(f"Transcribing {t:.2f} seconds...")
                    out = self.sendToWhisper(data, url, stmp)
                    if out:
                        self.writeOutput(out)
            except Exception as e:
                logger.error(f"Whisper thread failed: {e}")
                break
        # Stop main thread as well
        logger.info("Whisper worker thread is quitting")
        self.doRun = False
        self.thread = None

    # Send data to Whisper at given URL
    def sendToWhisper(self, data: bytes, url: str, tstamp = None):
        # Length of data in seconds
        t = len(data) / self.sampleRate / 2
        # Must have server
        if not url:
            return "[no server for {t:.2f} sec]\n"
        # Create request body
        boundary = "----WhisperFormBoundary7MA4YWxkTrZu0gW"
        payload = b"\r\n".join([
            f"--{boundary}".encode("utf-8"),
            f'Content-Disposition: form-data; name="file"; filename="file"'.encode("utf-8"),
            f"Content-Type: application/octet-stream\r\n".encode("utf-8"),
            self.getWavHeader(len(data)),
            data,
            f"\r\n--{boundary}--\r\n".encode("utf-8")
        ])
        # Build the request
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        req.add_header("Content-Length", str(len(payload)))
        # Send the request
        try:
            with urllib.request.urlopen(req) as response:
                responseData = response.read().decode("utf-8")
                try:
                    result = json.loads(responseData)
                    if "text" in result:
                        # Report transcribed text
                        if tstamp and self.frequency:
                            ReportingEngine.getSharedInstance().spot({
                                "mode": "SPEECH",
                                "text": result["text"],
                                "freq": self.frequency,
                                "timestamp": round(tstamp * 1000)
                            })
                        # Return transcribed text
                        return result["text"]
                except json.JSONDecodeError:
                    logger.error(f"JSON Error: {responseData}")
        except urllib.error.HTTPError as e:
            logger.error(f"HTTP Error {e.code}: {e.read().decode('utf-8')}")
            return f"[http error {e.code} for {t:.2f} sec]\n"
        except urllib.error.URLError as e:
            logger.error(f"Failed to reach the server: {e.reason}")
            return f"[no server for {t:.2f} sec]\n"
        except Exception as e:
            logger.error(f"Error: {e}")
        # Something bad happened
        return "[failed for {t:.2f} sec]\n"

    # Create a .WAV file header for given amount of data
    def getWavHeader(self, byteCount):
        # Create empty .WAV file
        byteRate = (self.sampleRate * 16 * 1) // 8
        out = bytearray(44)
        out[0:3]   = b"RIFF"
        out[4:7]   = (byteCount + 36).to_bytes(4, byteorder="little")
        out[8:11]  = b"WAVE"
        out[12:15] = b"fmt "
        out[16]    = 16      # Chunk size
        out[20]    = 1       # Format (PCM)
        out[22]    = 1       # Number of channels (1)
        out[24:27] = self.sampleRate.to_bytes(4, byteorder="little")
        out[28:31] = byteRate.to_bytes(4, byteorder="little")
        out[32]    = 2       # Block alignment (2 bytes)
        out[34]    = 16      # Bits per sample (16)
        out[36:39] = b"data"
        out[40:43] = byteCount.to_bytes(4, byteorder="little")
        return bytes(out)
