import cmath
import math


class FskUartDecoder(object):
    """
    Streaming non-coherent 2-FSK demodulator with asynchronous UART deframing.

    Input is real audio (e.g. FM discriminator output) at a fixed sample rate.
    Each tone is detected with a sliding one-bit-long DFT; the sign of the
    energy difference is the bit decision. The decision stream feeds one or
    more UART deframers (8 data bits, or 8 data bits plus a parity bit that
    is not checked), each of which splits characters into frames at
    inter-character gaps, as used by Modbus RTU (3.5 characters). A frame
    also ends at a framing error. With squelch open, noise produces random
    characters next to real frames; the protocol layer is expected to find
    real frames by their checksum.

    This class has no dependencies beyond the Python standard library so
    that it can be tested without pycsdr.
    """

    def __init__(
        self,
        sampleRate: int,
        baudRate: float = 1200,
        markFreq: float = 1300,
        spaceFreq: float = 2100,
        dataBits: tuple = (8, 9),
        gapChars: float = 3.5,
        maxFrame: int = 256,
    ):
        self.sampleRate = sampleRate
        self.baudRate = baudRate
        self.spb = sampleRate / baudRate
        self.win = max(2, int(round(self.spb)))
        self.markRot = cmath.exp(-2j * math.pi * markFreq / sampleRate)
        self.spaceRot = cmath.exp(-2j * math.pi * spaceFreq / sampleRate)
        self.markPh = 1 + 0j
        self.spacePh = 1 + 0j
        self.markBuf = [0j] * self.win
        self.spaceBuf = [0j] * self.win
        self.markAcc = 0j
        self.spaceAcc = 0j
        self.idx = 0
        self.dc = 0.0
        self.dcAlpha = 1.0 - math.exp(-2 * math.pi * 50.0 / sampleRate)
        self.lastBit = 1
        self.n = 0
        self.maxFrame = maxFrame
        self.uarts = [_Uart(bits, self.spb, gapChars) for bits in dataBits]

    def process(self, samples) -> list:
        """
        Feed audio samples. Returns a list of completed frames as
        (dataBits, frame: bytes) tuples.
        """
        out = []
        win = self.win
        markBuf = self.markBuf
        spaceBuf = self.spaceBuf
        markRot = self.markRot
        spaceRot = self.spaceRot
        markPh = self.markPh
        spacePh = self.spacePh
        markAcc = self.markAcc
        spaceAcc = self.spaceAcc
        idx = self.idx
        dc = self.dc
        dcAlpha = self.dcAlpha
        n = self.n
        uarts = self.uarts
        maxFrame = self.maxFrame

        for x in samples:
            # remove DC (FM carrier offset), then correlate with both tones
            dc += (x - dc) * dcAlpha
            x -= dc
            markPh *= markRot
            spacePh *= spaceRot
            m = x * markPh
            s = x * spacePh
            markAcc += m - markBuf[idx]
            spaceAcc += s - spaceBuf[idx]
            markBuf[idx] = m
            spaceBuf[idx] = s
            idx += 1
            if idx == win:
                idx = 0
            # decision: mark (binary 1) unless the space tone is stronger
            bit = 0 if (spaceAcc.real * spaceAcc.real + spaceAcc.imag * spaceAcc.imag) > (
                markAcc.real * markAcc.real + markAcc.imag * markAcc.imag
            ) else 1
            for u in uarts:
                frame = u.step(n, bit, maxFrame)
                if frame is not None:
                    out.append(frame)
            n += 1

            # periodically renormalize oscillators and recompute sums to stop drift
            if (n & 0xFFFF) == 0:
                markPh /= abs(markPh)
                spacePh /= abs(spacePh)
                markAcc = sum(markBuf)
                spaceAcc = sum(spaceBuf)

        self.markPh = markPh
        self.spacePh = spacePh
        self.markAcc = markAcc
        self.spaceAcc = spaceAcc
        self.idx = idx
        self.dc = dc
        self.n = n
        return out

    def flush(self) -> list:
        """Return any frames still being collected."""
        out = []
        for u in self.uarts:
            frame = u.flush()
            if frame is not None:
                out.append(frame)
        return out


class _Uart(object):
    """Asynchronous UART deframer on a per-sample bit decision stream."""

    def __init__(self, dataBits: int, spb: float, gapChars: float):
        self.dataBits = dataBits
        self.spb = spb
        # gap that ends a frame, measured from the centre of the last stop bit
        self.gap = int(round(gapChars * (dataBits + 2) * spb))
        self.prev = 1
        self.state = -1  # -1: hunting for start bit, else number of bits sampled
        self.next = 0.0
        self.shift = 0
        self.frame = bytearray()
        self.lastEnd = 0

    def step(self, n: int, bit: int, maxFrame: int):
        state = self.state
        if state < 0:
            result = None
            if self.frame and n - self.lastEnd > self.gap:
                result = self.flush()
            # mark to space transition: start bit edge, delayed by half a bit
            # by the detector, so the start bit centre is half a bit ahead
            if self.prev == 1 and bit == 0:
                self.state = 0
                self.next = n + self.spb / 2
                self.shift = 0
            self.prev = bit
            return result

        self.prev = bit
        if n < self.next:
            return None
        self.next += self.spb
        if state == 0:
            # confirm start bit in its centre, otherwise it was a glitch
            if bit != 0:
                self.state = -1
            else:
                self.state = 1
            return None
        if state <= self.dataBits:
            self.shift |= bit << (state - 1)
            self.state = state + 1
            return None
        # stop bit: the character is always read to the end, so that a bad
        # character does not make us resynchronize on a data bit edge
        self.state = -1
        if bit != 1:
            # framing error: drop the character, it ends the current frame
            return self.flush()
        self.frame.append(self.shift & 0xFF)
        self.lastEnd = n
        if len(self.frame) >= maxFrame:
            return self.flush()
        return None

    def flush(self):
        if not self.frame:
            return None
        result = (self.dataBits, bytes(self.frame))
        self.frame = bytearray()
        return result
