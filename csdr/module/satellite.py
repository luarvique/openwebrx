from pycsdr.modules import ExecModule
from pycsdr.types import Format

import os


class SatDumpModule(ExecModule):
    def __init__(self, mode: str = "noaa_apt", sampleRate: int = 50000, frequency: int = 137100000, outFolder: str = "/tmp/satdump", options = None):
        # Make sure we have output folder
        try:
            os.makedirs(outFolder, exist_ok = True)
        except:
            outFolder = "/tmp"
        # Compose command line
        cmd = [
            "satdump", "live", mode, outFolder,
            "--source", "file", "--file_path", "/dev/stdin",
            "--samplerate", str(sampleRate),
            "--frequency", str(frequency),
            "--baseband_format", "f32",
# Not trying to decode actual imagery for now, leaving .CADU file instead
#            "--finish_processing",
        ]
        # Add pipeline-specific options
        if options:
            for key in options.keys():
                cmd.append("--" + key)
                cmd.append(str(options[key]))
        # Create parent object
        super().__init__(Format.COMPLEX_FLOAT, Format.CHAR, cmd, doNotKill=True)
