from csdr.module import ThreadModule
from pycsdr.types import Format
from owrx.storage import DataRecorder
from owrx.config import Config
from queue import Queue, Full, Empty

import urllib.request
import urllib.error
import threading
import json
import logging

logger = logging.getLogger(__name__)

PoisonPill = object()

class WhisperTranscriber(ThreadModule, DataRecorder):
    def __init__(self, sampleRate: int = 12000, service: bool = False, chunkSeconds: int = 20, maxBytes: int = 1024 * 1024):
        self.sampleRate = sampleRate
        self.service    = service
        self.chunkSize  = max(10, chunkSeconds) * sampleRate * 2
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

    def writeOutput(self, output):
        if self.service:
            self.writeFile(output.encode("utf-8"))
        elif self.writer is not None:
            self.writer.write(output.encode("utf-8"))

    def run(self):
        # Spawn a worker thread for sending queued data to Whisper
        self.queue  = Queue(3)
        self.thread = threading.Thread(target=self.whisperWorker, name="WhisperWorker").start()
        self.buffer = b""

        # Consume input audio until it ends
        while self.doRun and self.reader is not None:
            data = self.reader.read()
            if data is None:
                self.doRun = False
                break
            self.buffer += data
            # If got enough audio to process...
            if len(self.buffer) >= self.chunkSize:
                 # Queue it for Whisper processing
                 try:
                     self.queue.put(self.buffer, block=False)
                 except Full:
                     t = len(self.buffer) / self.sampleRate / 2
                     self.writeOutput(f"[skipped {t} seconds]\n")
                 # Start accumulating new audio chunk
                 self.buffer = b""

        # If worker thread still running...
        if self.queue is not None:
            # Drain queue
            while True:
                try:
                    self.queue.get(block=False)
                except Empty:
                    break
            # Queue up poison pill to make worker quit
            try:
                self.queue.put(PoisonPill, block=False)
            except Exception:
                pass

    # This thread keeps sending queue data to Whisper
    def whisperWorker(self):
        logger.info("Whisper worker thread is running")
        running = True
        while running:
            try:
                data = self.queue.get()
                if data is PoisonPill:
                    running = False
                else:
                    out = self.sendToWhisper(data, Config.get()["whisper_url"])
                    if out is not None:
                        self.writeOutput(out)
                self.queue.task_done()
            except Exception as e:
                logger.error(f"Whisper thread failed: {e}")
                running = False
        logger.info("Whisper worker thread is quitting")
        self.queue = None
        self.thread = None

    # Send data to Whisper at given URL
    def sendToWhisper(self, data: bytes, url: str):
        # Length of data in seconds
        t = len(data) / self.sampleRate / 2
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
                        return result["text"]
                except json.JSONDecodeError:
                    logger.error(f"JSON Error: {responseData}")
        except urllib.error.HTTPError as e:
            logger.error(f"HTTP Error {e.code}: {e.read().decode("utf-8")}")
            return f"[http error {e.code} for {t} seconds]\n"
        except urllib.error.URLError as e:
            logger.error(f"Failed to reach the server: {e.reason}")
            return f"[no server for {t} seconds]\n"
        except Exception as e:
            logger.error(f"Error: {e}")
        # Something bad happened
        return "[failed for {t} seconds]\n"

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
