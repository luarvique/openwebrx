"""
TETRA (TErrestrial Trunked RAdio) parser for OpenWebRX+.

OpenWebRX frontend panel/map.

tetrarx verbose output format — two lines per frame burst:

  Line 1  (frame decode):
    FT=<type> [TN=<n> FN=<n> MN=<n>] [CC=<mcc>,<mnc>,<bcc>]
              [TX=<mhz> [RX=<mhz>] Po=<n>dBm LA=<n>] [Voice-Sv] [Air-encr]
              [[Network Name]] [SSI=<n>] [USSI=<n>]

  Line 2  (modem status, always present):
    Tetra:<modem> fr:<ftyp> offs:<n>Hz afc:<n>Hz <qual>% <db>dB len:<n>

Example pair:
  FT=1  TN=2 FN=07 MN=3 CC=234,30,5 TX=430.5125 RX=420.5125 Po=35dBm LA=1234 Voice-Sv [MyNetwork] SSI=1234567
  Tetra:1 fr:1 offs:37500Hz afc:0Hz 50% 15.2dB len:510
"""

import re
import logging
from owrx.toolbox import TextParser

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Compiled patterns                                                    #
# ------------------------------------------------------------------ #

# Frame decode line — starts with optional legacy MHz/dB/Hz prefix
# (tetradec prepended those; tetrarx does not), then FT=<type>.
# rfdb and offset are optional here; tetrarx puts them on the Tetra: line.
_RE_MAIN = re.compile(
    r"(?:(?P<rxmhz>\d+\.\d+)MHz\s+)?"          # optional: legacy tetradec RX freq
    r"(?:(?P<rfdb>-?\d+(?:\.\d+)?)dB\s+)?"     # optional: legacy signal level
    r"(?:(?P<offset>-?\d+)Hz\s+)?"             # optional: legacy freq offset
    r"FT=(?P<ft>\d+)"                           # frame type — always present
)

# tetrarx modem status line: "Tetra:<n> fr:<n> offs:<n>Hz afc:<n>Hz <n>% <n>dB len:<n>"
_RE_TETRA_STATUS = re.compile(
    r"^Tetra:\d+\s+fr:\d+\s+offs:(?P<offset>-?\d+)Hz\s+afc:-?\d+Hz\s+"
    r"-?\d+%\s+(?P<rfdb>-?\d+(?:\.\d+)?)dB"
)

# Network identifier — CC=<MCC>,<MNC>,<BCC>
_RE_CC   = re.compile(r"CC=(?P<mcc>\d+),(?P<mnc>\d+),(?P<bcc>\d+)")

# Timeslot / frame / multiframe counters
_RE_TN   = re.compile(r"TN=(?P<tn>\d+)")
_RE_FN   = re.compile(r"FN=(?P<fn>\d+)")
_RE_MN   = re.compile(r"MN=(?P<mn>\d+)")

# TX / RX frequencies (MHz, from SYSINFO block)
_RE_TX   = re.compile(r"TX=(?P<tx>\d+\.\d+)")
_RE_RX   = re.compile(r"RX=(?P<rx>\d+\.\d+)")

# Location area and MS power
_RE_LA   = re.compile(r"LA=(?P<la>\d+)")
_RE_PO   = re.compile(r"Po=(?P<power>-?\d+)dBm")

# Subscriber identities (may appear on FT= line or, rarely, on sub-lines)
_RE_SSI  = re.compile(r"\bSSI=(?P<ssi>\d+)")
_RE_USSI = re.compile(r"\bUSSI=(?P<ussi>\d+)")

# Network name in brackets (MCC/MNC lookup)
_RE_NET  = re.compile(r"\[(?P<network>[^\]]+)\]")

# Service flags embedded in the FT= line
_FLAG_VOICE   = re.compile(r"\bVoice-Sv\b")
_FLAG_AIRENC  = re.compile(r"\bAir-encr\b")


class TetraParser(TextParser):
    """
    Line-based parser that converts tetrarx -v stdout into JSON dicts
    understood by the OpenWebRX frontend.

    Stateful: accumulates fields from the FT= frame line and the
    subsequent Tetra: status line until a new frame begins.
    """

    def __init__(self, service: bool = False):
        self._current: dict = {}
        super().__init__(filePrefix="TETRA", service=service)

    # ------------------------------------------------------------------ #
    # TextParser interface                                                 #
    # ------------------------------------------------------------------ #

    def parse(self, line: bytes) -> dict | None:
        try:
            text = line.decode("ascii", errors="replace").rstrip()
        except Exception:
            return None

        if not text:
            return None

        # -------------------------------------------------------------- #
        # Tetra: status line (tetrarx) — fills in signal stats then done  #
        # -------------------------------------------------------------- #
        m_status = _RE_TETRA_STATUS.match(text)
        if m_status:
            # Backfill rfdb / offset that were absent from the FT= line.
            if self._current:
                if "rfdb" not in self._current:
                    self._current["rfdb"] = float(m_status.group("rfdb"))
                if "offset" not in self._current:
                    self._current["offset"] = int(m_status.group("offset"))
            return None

        # -------------------------------------------------------------- #
        # FT= frame decode line — start of a new frame                    #
        # -------------------------------------------------------------- #
        m_main = _RE_MAIN.search(text)
        if m_main:
            # Flush the previous frame before starting a new one.
            out = self._flush()

            self._current = {
                "mode": "TETRA",
                "ft"  : int(m_main.group("ft")),
            }
            if self.frequency:
                self._current["freq"] = self.frequency

            rfdb = m_main.group("rfdb")
            if rfdb is not None:
                self._current["rfdb"] = float(rfdb)
            offset = m_main.group("offset")
            if offset is not None:
                self._current["offset"] = int(offset)

            rxmhz = m_main.group("rxmhz")
            if rxmhz:
                self._current["rxmhz"] = float(rxmhz)

            # CC = MCC, MNC, BCC
            mc = _RE_CC.search(text)
            if mc:
                self._current["mcc"] = int(mc.group("mcc"))
                self._current["mnc"] = int(mc.group("mnc"))
                self._current["bcc"] = int(mc.group("bcc"))

            # Timeslot / frame numbers
            for pat, key in ((_RE_TN, "tn"), (_RE_FN, "fn"), (_RE_MN, "mn")):
                m = pat.search(text)
                if m:
                    self._current[key] = int(m.group(1))

            # TX / RX frequencies from SYSINFO
            for pat, key in ((_RE_TX, "tx_mhz"), (_RE_RX, "rx_mhz")):
                m = pat.search(text)
                if m:
                    self._current[key] = float(m.group(1))

            # Location area / power
            for pat, key in ((_RE_LA, "la"), (_RE_PO, "power_dbm")):
                m = pat.search(text)
                if m:
                    self._current[key] = int(m.group(1))

            # Service flags
            if _FLAG_VOICE.search(text):
                self._current["voice_service"] = True
            if _FLAG_AIRENC.search(text):
                self._current["air_encrypted"] = True

            # Network name from MCC/MNC lookup
            nm = _RE_NET.search(text)
            if nm:
                self._current["network"] = nm.group("network").strip()

            # SSI / USSI — on the FT= line in tetrarx (inline with frame data)
            for ms in _RE_SSI.finditer(text):
                self._current.setdefault("ssi", []).append(int(ms.group("ssi")))
            for mu in _RE_USSI.finditer(text):
                self._current.setdefault("ussi", []).append(int(mu.group("ussi")))

            return out  # emit the previous frame (None if this is the first)

        # -------------------------------------------------------------- #
        # Sub-lines: additional SSI / USSI / network name continuations   #
        # (tetradec style — kept for compatibility)                        #
        # -------------------------------------------------------------- #
        for ms in _RE_SSI.finditer(text):
            self._current.setdefault("ssi", []).append(int(ms.group("ssi")))
        for mu in _RE_USSI.finditer(text):
            self._current.setdefault("ussi", []).append(int(mu.group("ussi")))

        nm = _RE_NET.search(text)
        if nm and "network" not in self._current:
            self._current["network"] = nm.group("network").strip()

        return None

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _flush(self) -> dict | None:
        """Return current accumulated frame dict (or None if empty)."""
        if not self._current:
            return None
        out = self._current
        self._current = {}
        return out

    # ------------------------------------------------------------------ #
    # DialFrequencyReceiver passthrough                                    #
    # ------------------------------------------------------------------ #

    def setDialFrequency(self, frequency: int) -> None:
        super().setDialFrequency(frequency)
        if self._current:
            self._current["freq"] = frequency

