"""
Modbus RTU frame recovery and decoding.

Frames come from an asynchronous UART deframer (see owrx.fsk) and may carry
junk characters around the real frame when squelch is open. Frames are
recovered by their CRC-16 and a structure check against the function code,
then decoded into readable requests, responses and exceptions. Requests
are remembered per server address, so that responses can be labelled with
the register or coil addresses they belong to.

This module has no dependencies beyond the Python standard library.
"""

import time


def _crcTable():
    table = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
        table.append(c)
    return table


CRC_TABLE = _crcTable()


def crc16(data: bytes) -> int:
    """Modbus CRC-16 (polynomial 0xA001, initial value 0xFFFF)."""
    crc = 0xFFFF
    for b in data:
        crc = (crc >> 8) ^ CRC_TABLE[(crc ^ b) & 0xFF]
    return crc


FUNCTIONS = {
    0x01: "Read Coils",
    0x02: "Read Discrete Inputs",
    0x03: "Read Holding Registers",
    0x04: "Read Input Registers",
    0x05: "Write Single Coil",
    0x06: "Write Single Register",
    0x07: "Read Exception Status",
    0x08: "Diagnostics",
    0x0B: "Get Comm Event Counter",
    0x0C: "Get Comm Event Log",
    0x0F: "Write Multiple Coils",
    0x10: "Write Multiple Registers",
    0x11: "Report Server ID",
    0x14: "Read File Record",
    0x15: "Write File Record",
    0x16: "Mask Write Register",
    0x17: "Read/Write Multiple Registers",
    0x18: "Read FIFO Queue",
    0x2B: "Encapsulated Interface Transport",
}

EXCEPTIONS = {
    0x01: "Illegal Function",
    0x02: "Illegal Data Address",
    0x03: "Illegal Data Value",
    0x04: "Server Device Failure",
    0x05: "Acknowledge",
    0x06: "Server Device Busy",
    0x08: "Memory Parity Error",
    0x0A: "Gateway Path Unavailable",
    0x0B: "Gateway Target Device Failed to Respond",
}

# Frames that only ever carry a request / a response of a given length
REQ_ONLY_LEN4 = (0x07, 0x0B, 0x0C, 0x11)


def _u16(b: bytes, i: int) -> int:
    return (b[i] << 8) | b[i + 1]


def _bytecountFits(adu: bytes, pos: int, extra: int) -> bool:
    """True if the byte count at pos plus the fixed part matches the length."""
    return len(adu) > pos and len(adu) == pos + 1 + adu[pos] + extra


def isPlausible(adu: bytes) -> bool:
    """Check that the frame length is consistent with its function code."""
    n = len(adu)
    if n < 4 or adu[0] > 247:
        return False
    fc = adu[1]
    if fc & 0x80:
        return n == 5 and (fc & 0x7F) in FUNCTIONS and adu[2] in EXCEPTIONS
    if fc not in FUNCTIONS:
        return False
    if fc in (0x01, 0x02, 0x03, 0x04):
        return n == 8 or _bytecountFits(adu, 2, 2)
    if fc in (0x05, 0x06, 0x08):
        return n == 8
    if fc in (0x0F, 0x10):
        return n == 8 or _bytecountFits(adu, 6, 2)
    if fc == 0x16:
        return n == 10
    if fc == 0x17:
        return _bytecountFits(adu, 10, 2) or _bytecountFits(adu, 2, 2)
    if fc in REQ_ONLY_LEN4:
        return n == 4 or _bytecountFits(adu, 2, 2) or (fc == 0x07 and n == 5) or (fc == 0x0B and n == 8)
    if fc == 0x18:
        return n == 6 or (n >= 8 and n == 6 + _u16(adu, 2))
    # 0x14, 0x15, 0x2B: variable, accept any byte-count framed or short frame
    return n >= 5


def findFrames(data: bytes, maxJunk: int = 8) -> list:
    """
    Find Modbus RTU frames with a valid CRC in a deframed character run.
    Up to maxJunk leading characters and any trailing characters are
    tolerated. Returns a list of frames in order of appearance.
    """
    frames = []
    pos = 0
    n = len(data)
    while pos <= n - 4:
        best = None
        for i in range(pos, min(pos + maxJunk + 1, n - 3)):
            crc = 0xFFFF
            for j in range(i, n - 2):
                crc = (crc >> 8) ^ CRC_TABLE[(crc ^ data[j]) & 0xFF]
                if j - i >= 1 and crc == (data[j + 1] | (data[j + 2] << 8)):
                    adu = data[i:j + 3]
                    if isPlausible(adu) and (best is None or len(adu) > len(best[1])):
                        best = (i, adu)
            if best is not None:
                break
        if best is None:
            break
        frames.append(best[1])
        pos = best[0] + len(best[1])
    return frames


def _words(b: bytes) -> list:
    return [_u16(b, i) for i in range(0, len(b) - 1, 2)]


def _hexWords(words: list, limit: int = 32) -> str:
    s = " ".join("%04X" % w for w in words[:limit])
    return s + (" ..." if len(words) > limit else "")


def _bits(b: bytes, count: int) -> str:
    bits = []
    for i in range(min(count, len(b) * 8)):
        bits.append("1" if b[i // 8] & (1 << (i % 8)) else "0")
    return "".join(bits)


class ModbusDecoder(object):
    """Turns Modbus RTU frames into dictionaries, pairing requests and responses."""

    def __init__(self, pairTimeout: float = 5.0):
        self.pairTimeout = pairTimeout
        # (address, function) -> (time, request details)
        self.pending = {}

    def _pendingRequest(self, addr: int, fc: int, now: float):
        req = self.pending.get((addr, fc))
        if req is not None and now - req[0] <= self.pairTimeout:
            return req[1]
        return None

    def decode(self, adu: bytes, now: float = None) -> dict:
        now = time.time() if now is None else now
        addr, fc = adu[0], adu[1]
        pdu = adu[2:-2]
        n = len(adu)
        out = {
            "address": addr,
            "function": fc & 0x7F,
            "name": FUNCTIONS.get(fc & 0x7F, "Function 0x%02X" % (fc & 0x7F)),
            "raw": adu.hex().upper(),
        }

        if fc & 0x80:
            out["type"] = "exception"
            out["message"] = EXCEPTIONS.get(adu[2], "Exception 0x%02X" % adu[2])
            self.pending.pop((addr, fc & 0x7F), None)
            return out

        req = self._pendingRequest(addr, fc, now)

        if fc in (0x01, 0x02, 0x03, 0x04):
            isResp = _bytecountFits(adu, 2, 2) and (n != 8 or req is not None)
            kind = "coils" if fc in (0x01, 0x02) else "registers"
            if not isResp:
                start, qty = _u16(pdu, 0), _u16(pdu, 2)
                self._request(addr, fc, now, {"start": start, "qty": qty})
                out["type"] = "request"
                out["message"] = "%d %s from %d" % (qty, kind, start)
            else:
                data = pdu[1:]
                out["type"] = "response"
                self.pending.pop((addr, fc), None)
                at = " from %d" % req["start"] if req else ""
                if fc in (0x01, 0x02):
                    qty = req["qty"] if req else len(data) * 8
                    out["message"] = "%s%s: %s" % (kind, at, _bits(data, qty))
                else:
                    out["message"] = "%s%s: %s" % (kind, at, _hexWords(_words(data)))

        elif fc in (0x05, 0x06):
            ref, value = _u16(pdu, 0), _u16(pdu, 2)
            what = "coil %d = %s" % (ref, "ON" if value == 0xFF00 else "OFF") if fc == 0x05 \
                else "register %d = %04X" % (ref, value)
            if req is not None and req.get("raw") == adu:
                out["type"] = "response"
                self.pending.pop((addr, fc), None)
            else:
                out["type"] = "request"
                self._request(addr, fc, now, {"raw": adu})
            out["message"] = what

        elif fc in (0x0F, 0x10):
            start, qty = _u16(pdu, 0), _u16(pdu, 2)
            kind = "coils" if fc == 0x0F else "registers"
            if n == 8:
                out["type"] = "response"
                self.pending.pop((addr, fc), None)
                out["message"] = "wrote %d %s from %d" % (qty, kind, start)
            else:
                data = pdu[5:]
                out["type"] = "request"
                self._request(addr, fc, now, {"start": start, "qty": qty})
                values = _bits(data, qty) if fc == 0x0F else _hexWords(_words(data))
                out["message"] = "write %d %s from %d: %s" % (qty, kind, start, values)

        elif fc == 0x17:
            if _bytecountFits(adu, 10, 2) and not (req is not None and _bytecountFits(adu, 2, 2)):
                rstart, rqty, wstart, wqty = _u16(pdu, 0), _u16(pdu, 2), _u16(pdu, 4), _u16(pdu, 6)
                self._request(addr, fc, now, {"start": rstart, "qty": rqty})
                out["type"] = "request"
                out["message"] = "read %d from %d, write %d from %d: %s" % (
                    rqty, rstart, wqty, wstart, _hexWords(_words(pdu[9:]))
                )
            else:
                self.pending.pop((addr, fc), None)
                at = " from %d" % req["start"] if req else ""
                out["type"] = "response"
                out["message"] = "registers%s: %s" % (at, _hexWords(_words(pdu[1:])))

        elif fc == 0x16:
            ref, andMask, orMask = _u16(pdu, 0), _u16(pdu, 2), _u16(pdu, 4)
            if req is not None and req.get("raw") == adu:
                out["type"] = "response"
                self.pending.pop((addr, fc), None)
            else:
                out["type"] = "request"
                self._request(addr, fc, now, {"raw": adu})
            out["message"] = "register %d AND %04X OR %04X" % (ref, andMask, orMask)

        elif fc == 0x08:
            sub, value = _u16(pdu, 0), _u16(pdu, 2)
            out["type"] = "response" if req is not None else "request"
            if req is None:
                self._request(addr, fc, now, {})
            else:
                self.pending.pop((addr, fc), None)
            out["message"] = "sub-function %d, data %04X" % (sub, value)

        else:
            if n == 4:
                out["type"] = "request"
                self._request(addr, fc, now, {})
                out["message"] = ""
            else:
                out["type"] = "response" if req is not None else ""
                self.pending.pop((addr, fc), None)
                out["message"] = pdu.hex(" ").upper()

        return out

    def _request(self, addr: int, fc: int, now: float, details: dict) -> None:
        self.pending[(addr, fc)] = (now, details)
