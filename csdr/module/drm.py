from pycsdr.modules import ExecModule
from pycsdr.types import Format

import os

class DrmModule(ExecModule):
    def __init__(self, socketPath: str = None):
        # Compose basic command line
        cmd = [
            "dream", "-c", "6", "--sigsrate", "48000",
            "--audsrate", "48000", "-I", "-", "-O", "-",
        ]

        self.socketPath = socketPath
        if self.socketPath:
            cmd += [ "--status-socket", self.socketPath ]

        super().__init__(Format.COMPLEX_SHORT, Format.SHORT, cmd)

    def stop(self):
        # Stop execution
        super().stop()
        # Remove status socket
        if self.socketPath and os.path.exists(self.socketPath):
            try:
                os.unlink(self.socketPath)
            except OSError:
                pass
