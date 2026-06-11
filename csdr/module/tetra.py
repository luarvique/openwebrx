from pycsdr.modules import ExecModule
from pycsdr.types import Format

import os

class TetraModule(ExecModule):
    # TETRA D4PSK: 18 kbit/s, 25 kHz channel
    baudRate = 18000
    ifWidth  = 20000 # 18kHz signal + 2kHz margin

    def __init__(self, sampleRate: int = 96000, socketPath: str = "/tmp/tetra_status.sock"):
        # Save sample rate and status socket path
        self.sampleRate = sampleRate
        self.socketPath = socketPath

        # Compose basic command line
        cmd = [
            "tetrarx",
            "-i", "/dev/stdin", "-f", "f32",
            "-w", "/dev/stdout", "-c", "1",
            "-r", str(self.sampleRate),
            "-d", f"{self.baudRate},{self.ifWidth}",
            "-t", "0,5000",
            "-j", self.socketPath,
        ]

        # 8000Hz 16-bit PCM from tetrarx
        super().__init__(Format.COMPLEX_FLOAT, Format.SHORT, cmd)

    def stop(self):
        # Stop execution
        super().stop()
        # Remove status socket
        if os.path.exists(self.socketPath):
            try:
                os.unlink(self.socketPath)
            except OSError:
                pass
