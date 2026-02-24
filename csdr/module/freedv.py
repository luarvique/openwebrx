from pycsdr.types import Format
from pycsdr.modules import ExecModule


class FreeDVModule(ExecModule):
    def __init__(self):
        super().__init__(
            Format.SHORT,
            Format.SHORT,
            ["webrx_rade_decode"]
        )
