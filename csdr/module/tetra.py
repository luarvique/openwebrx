from csdr.module import AutoStartModule
from pycsdr.modules import Buffer
from pycsdr.types import Format
from subprocess import Popen, PIPE, DEVNULL, TimeoutExpired
from threading import Thread
from functools import partial
import os
import logging

logger = logging.getLogger(__name__)

# Each instance gets a unique index so concurrent receivers don't clash.
_instance_count = 0


def _next_instance_id() -> int:
    global _instance_count
    _instance_count += 1
    return _instance_count


# Bytes in a standard WAV file header written by tetrarx before PCM data.
_WAV_HEADER = 44


class TetraDemodModule(AutoStartModule):
    """
    Single-process TETRA D4PSK demodulator -- produces both audio and metadata.

    Signal flow
    -----------
    OpenWebRX IQ buffer (COMPLEX_FLOAT, 96 kHz)
        -stdin->  tetrarx  (-f f32)
                      |
          named FIFO (WAV)<--|-->  stdout (verbose text)
                  |                      |
          (skip 44-byte header)    side Buffer(CHAR)
                  |                      |
           writer (SHORT)        getTextReader()
           [primary output]      [-> TetraParser]
    """

    # TETRA D4PSK: 18 kbit/s, 25 kHz channel
    _BAUD    = 18000
    _IFWIDTH = 20000   # Hz -- modest margin around the 18 kHz signal

    def __init__(self, sampleRate: int = 96000, tuneOffset: int = 0):
        self._sampleRate  = sampleRate
        self._tuneOffset  = tuneOffset
        self._iid         = _next_instance_id()
        self._pipePath    = "/tmp/tetra_audio_{}_{}.fifo".format(os.getpid(), self._iid)
        self._textBuffer  = Buffer(Format.CHAR)  # always created; text pump feeds it
        self._tetrarx     = None
        super().__init__()

    def getTextReader(self):
        """Return a reader on the text side-channel for TetraParser."""
        return self._textBuffer.getReader()

    def getInputFormat(self) -> Format:
        # OpenWebRX delivers COMPLEX_FLOAT via the selector buffer.
        return Format.COMPLEX_FLOAT

    def getOutputFormat(self) -> Format:
        # 8000 Hz 16-bit PCM from tetrarx -> SHORT
        return Format.SHORT

    def start(self):
        # Create the named pipe tetrarx will write audio to.
        try:
            os.mkfifo(self._pipePath)
        except FileExistsError:
            pass

        # tetrarx: IQ in (stdin), verbose text out (stdout), PCM audio out (named pipe)
        tetrarx_cmd = [
            "tetrarx",
            "-i", "/dev/stdin",
            "-f", "f32",                              # 32-bit float complex I/Q
            "-r", str(self._sampleRate),
            "-d", "{},{}".format(self._BAUD, self._IFWIDTH),
            "-t", "0,5000",
            "-w", self._pipePath,                     # audio -> named pipe (WAV wrapper)
            "-v",                                     # verbose metadata -> stdout
            "-c", "1",                                # mono output
        ]
        logger.info("TETRA: starting tetrarx: %s", tetrarx_cmd)
        self._tetrarx = Popen(tetrarx_cmd, stdin=PIPE, stdout=PIPE, stderr=DEVNULL)

        # Resume the IQ reader in case it was stopped.
        self.reader.resume()

        # Thread 1: IQ buffer -> tetrarx stdin (COMPLEX_FLOAT passed through as f32)
        Thread(
            target=self.pump(self.reader.read, self._tetrarx.stdin.write),
            name="tetra-iq-{}".format(self._iid),
            daemon=True,
        ).start()

        # Thread 2: tetrarx stdout -> text side-buffer (for TetraParser)
        Thread(
            target=self.pump(
                partial(self._tetrarx.stdout.read1, 1024),
                self._textBuffer.write,
            ),
            name="tetra-text-{}".format(self._iid),
            daemon=True,
        ).start()

        # Thread 3: named FIFO -> audio writer (skips WAV header first)
        Thread(
            target=self._audioPump,
            name="tetra-audio-{}".format(self._iid),
            daemon=True,
        ).start()

    def _audioPump(self):
        """
        Open the FIFO, discard tetrarx's 44-byte WAV header, then copy raw
        16-bit PCM samples to the module's output writer.

        """
        try:
            with open(self._pipePath, "rb") as f:
                # Skip the WAV header tetrarx prepends.
                to_skip = _WAV_HEADER
                while to_skip > 0:
                    chunk = f.read(to_skip)
                    if not chunk:
                        return
                    to_skip -= len(chunk)

                # Stream PCM audio to the output writer.
                while True:
                    data = f.read(4096)
                    if not data:
                        break
                    try:
                        self.writer.write(data)
                    except Exception:
                        break
        except Exception as exc:
            logger.info("TETRA audio pump ended: %s", exc)
        finally:
            self._removePipe()

    # ------------------------------------------------------------------ #
    # Cleanup                                                              #
    # ------------------------------------------------------------------ #

    def _removePipe(self):
        try:
            os.unlink(self._pipePath)
        except Exception:
            pass

    def _kill(self, proc):
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(3)
        except TimeoutExpired:
            proc.kill()
        except Exception:
            pass

    def stop(self):
        self._kill(self._tetrarx)
        self._tetrarx = None

        try:
            wfd = os.open(self._pipePath, os.O_WRONLY | os.O_NONBLOCK)
            os.close(wfd)
        except Exception:
            pass

        self._removePipe()
        if self.reader is not None:
            self.reader.stop()
        super().stop()

