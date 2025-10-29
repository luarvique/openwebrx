from pycsdr.modules import ExecModule
from pycsdr.types import Format

import uuid
import os

class DrmModule(ExecModule):
    def __init__(self):
        # Each instances gets its own status socket
        self.instance_id = str(uuid.uuid4())[:8]
        self.socket_path = f"/tmp/dream_status_{self.instance_id}.sock"

        # Remove old status socket, if present
        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except OSError:
                pass

        super().__init__(
            Format.COMPLEX_SHORT,
            Format.SHORT,
            [
                "dream", "-c", "6", "--sigsrate", "48000",
                "--audsrate", "48000", "-I", "-", "-O", "-",
                "--status-socket", self.socket_path
            ]
        )

    def getSocketPath(self):
        return self.socket_path

    def stop(self):
        # Stop execution
        super().stop()
        # Remove status socket
        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except OSError:
                pass
