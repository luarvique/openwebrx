from csdr.module import PopenModule
from pycsdr.types import Format

import os

class TetraModule(PopenModule):
    # TETRA D4PSK: 18 kbit/s, 25 kHz channel
    baudRate = 18000
    ifWidth  = 20000 # 18kHz signal + 2kHz margin

    def __init__(self, sampleRate: int = 96000, socketPath: str = "/tmp/tetra_status.sock"):
        # Save sample rate and status socket path
        self.sampleRate = sampleRate
        self.socketPath = socketPath
        super().__init__()

    def getInputFormat(self) -> Format:
        return Format.COMPLEX_FLOAT

    def getOutputFormat(self) -> Format:
        return Format.SHORT

    def getCommand(self):
        # Compose basic command line
        return [
            "tetrarx",
            "-i", "/dev/stdin", "-f", "f32",
            "-w", "/dev/stdout", "-c", "1",
            "-r", str(self.sampleRate),
            "-d", f"{self.baudRate},{self.ifWidth}",
            "-t", "0,5000",
            "-j", self.socketPath,
        ]

    def stop(self):
        # Stop execution
        super().stop()
        # Remove status socket
        if os.path.exists(self.socketPath):
            try:
                os.unlink(self.socketPath)
            except OSError:
                pass
