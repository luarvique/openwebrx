from unittest import TestCase, skipUnless
import math
import random

from array import array
import threading

try:
    from pycsdr.modules import FskUartDecoder, Buffer
    from pycsdr.types import Format
except ImportError:
    FskUartDecoder = None
from owrx.modbus import crc16, findFrames, isPlausible, ModbusDecoder, ModbusStreamDecoder


def adu(body: bytes) -> bytes:
    c = crc16(body)
    return body + bytes([c & 0xFF, c >> 8])


def synth(frames, fs=12000, baud=1200, mark=1300, space=2100, parity=None, lead=0.1, gap=0.05, noise=0.0, seed=1):
    """Continuous-phase audio FSK with asynchronous characters, idle mark between frames."""
    rnd = random.Random(seed)
    out = []
    phase = 0.0
    t = 0.0

    def emit(bit, duration):
        nonlocal phase, t
        start = len(out)
        t += duration
        freq = mark if bit else space
        for _ in range(int(round(t * fs)) - start):
            phase += 2 * math.pi * freq / fs
            out.append(0.5 * math.sin(phase) + (rnd.gauss(0, noise) if noise else 0.0))

    for frame in frames:
        emit(1, lead)
        for byte in frame:
            bits = [0] + [(byte >> i) & 1 for i in range(8)]
            if parity is not None:
                ones = bin(byte).count("1")
                bits.append(ones & 1 if parity == "E" else 1 - (ones & 1))
            bits.append(1)
            for b in bits:
                emit(b, 1 / baud)
        emit(1, gap)
    return out


def nativeLines(samples, fs=12000, chunkSize=1000, **kwargs):
    # A final non-Modbus UART run marks completion of the asynchronous worker.
    # This avoids sleeps and an implementation-only "process Python samples" API.
    marker = b"\xfeNativeEnd\x00\xaa\x55"
    samples = list(samples) + synth([marker], fs=fs,
        baud=kwargs.get("baudRate", 1200), mark=kwargs.get("markFreq", 1300),
        space=kwargs.get("spaceFreq", 2100))
    size = max(65536, len(samples) * 32)
    source, sink = Buffer(Format.FLOAT, size), Buffer(Format.CHAR, size)
    reader = sink.getReader()
    decoder = FskUartDecoder(fs, **kwargs)
    lines, errors = [], []
    completed = threading.Event()

    def collect():
        pending = b""
        try:
            while True:
                data = reader.read()
                if data is None:
                    return
                pending += data.tobytes()
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    if bytes.fromhex(line.split()[2].decode()) == marker:
                        completed.set()
                        return
                    lines.append(line)
        except Exception as error:
            errors.append(error)
            completed.set()

    thread = threading.Thread(target=collect, daemon=True)
    thread.start()
    try:
        decoder.setReader(source.getReader())
        decoder.setWriter(sink)
        for i in range(0, len(samples), chunkSize):
            source.write(array("f", samples[i:i + chunkSize]).tobytes())
        if not completed.wait(10):
            raise AssertionError("native CSDR stream did not finish")
        if errors:
            raise errors[0]
        return lines
    finally:
        decoder.stop()
        reader.stop()
        thread.join(2)


def decodeAll(samples, fs=12000, **kwargs):
    found = []
    for line in nativeLines(samples, fs, **kwargs):
        data = bytes.fromhex(line.split()[2].decode())
        for frame in findFrames(data):
            if frame not in found:
                found.append(frame)
    return found


def uartLine(bits, data, starts):
    return b"%d %s %s" % (bits, ",".join(map(str, starts)).encode(), data.hex().encode())


def decodeStream(samples, chunkSize=1000):
    decoder = ModbusStreamDecoder()
    return [frame for line in nativeLines(samples, chunkSize=chunkSize)
            for frame in decoder.decode(line, now=100.0)]


REQ = adu(bytes.fromhex("0d170002001b000000020404454504"))
RESP = adu(bytes([0x0D, 0x17, 0x36]) + bytes(range(0x0A, 0x0A + 54)))


class CrcTest(TestCase):
    def testKnownVector(self):
        # Read Holding Registers, server 1, 10 registers from 0
        self.assertEqual(adu(bytes.fromhex("01030000000a")).hex(), "01030000000ac5cd")

    def testPlausibility(self):
        self.assertTrue(isPlausible(REQ))
        self.assertTrue(isPlausible(RESP))
        self.assertTrue(isPlausible(adu(bytes.fromhex("018302"))))
        self.assertFalse(isPlausible(adu(bytes.fromhex("0103000000"))))
        self.assertFalse(isPlausible(adu(bytes.fromhex("01ff00"))))


class FindFramesTest(TestCase):
    def testLeadingAndTrailingJunk(self):
        self.assertEqual(findFrames(b"\x55\xaa\x13" + REQ + b"\xfe\x01"), [REQ])

    def testBackToBack(self):
        self.assertEqual(findFrames(REQ + RESP), [REQ, RESP])

    def testNoFrame(self):
        self.assertEqual(findFrames(REQ[:-1]), [])


@skipUnless(FskUartDecoder is not None, "requires native CSDR/PyCSDR FskUartDecoder")
class FskUartTest(TestCase):
    def testV23With8N1AndCarriageReturns(self):
        # 0x0D bytes (address 13) must survive the deframer
        self.assertEqual(decodeAll(synth([REQ, RESP])), [REQ, RESP])

    def testBell202(self):
        self.assertEqual(decodeAll(synth([REQ, RESP], mark=1200, space=2200)), [REQ, RESP])

    def testEvenParity(self):
        self.assertEqual(decodeAll(synth([REQ, RESP], parity="E")), [REQ, RESP])

    def testNoise(self):
        self.assertEqual(decodeAll(synth([REQ, RESP], noise=0.15)), [REQ, RESP])

    def testPureNoiseProducesNoFrames(self):
        rnd = random.Random(7)
        self.assertEqual(decodeAll([rnd.gauss(0, 0.3) for _ in range(12000 * 10)]), [])

    def testMaximumReadResponseWithJunk(self):
        frame = adu(bytes([1, 3, 250]) + bytes(range(250)))
        for parity in (None, "E"):
            for mark, space in ((1300, 2100), (1200, 2200)):
                for junk in (2, 8):
                    with self.subTest(parity=parity, mark=mark, junk=junk):
                        samples = synth([b"\x55" * junk + frame], parity=parity, mark=mark, space=space)
                        self.assertEqual(decodeAll(samples), [frame])


class ModbusDecoderTest(TestCase):
    def testReadWriteRegistersPairing(self):
        d = ModbusDecoder()
        req = d.decode(REQ, 100.0)
        self.assertEqual(req["type"], "request")
        self.assertEqual(req["address"], 13)
        self.assertEqual(req["function"], 0x17)
        self.assertEqual(req["message"], "read 27 from 2, write 2 from 0: 0445 4504")
        resp = d.decode(RESP, 100.3)
        self.assertEqual(resp["type"], "response")
        self.assertTrue(resp["message"].startswith("registers from 2: 0A0B 0C0D"))

    def testReadHoldingRegisters(self):
        d = ModbusDecoder()
        self.assertEqual(d.decode(adu(bytes.fromhex("010300000002")), 1.0)["message"], "2 registers from 0")
        r = d.decode(adu(bytes.fromhex("0103041234abcd")), 1.1)
        self.assertEqual(r["type"], "response")
        self.assertEqual(r["message"], "registers from 0: 1234 ABCD")

    def testReadRequestAfterMissedReply(self):
        for fc in (3, 4):
            with self.subTest(fc=fc):
                d = ModbusDecoder()
                d.decode(adu(bytes([1, fc, 0, 0, 0, 1])), 100.0)
                r = d.decode(adu(bytes([1, fc, 3, 0, 0, 1])), 101.0)
                self.assertEqual(r["type"], "request")
                self.assertEqual(r["message"], "1 registers from 768")
                r = d.decode(adu(bytes([1, fc, 2, 0x12, 0x34])), 101.2)
                self.assertEqual(r["message"], "registers from 768: 1234")

    def testOddRegisterResponseRejected(self):
        for fc in (3, 4):
            frame = adu(bytes([1, fc, 5, 0, 1, 0, 2, 0]))
            self.assertFalse(isPlausible(frame))
            self.assertEqual(findFrames(frame), [])

    def testMismatchedReplyDoesNotUseStaleAddress(self):
        d = ModbusDecoder()
        d.decode(adu(bytes.fromhex("01030064000a")), 1.0)
        r = d.decode(adu(bytes.fromhex("0103041234abcd")), 1.1)
        self.assertEqual(r["type"], "response")
        self.assertEqual(r["message"], "registers: 1234 ABCD")

    def testCoilRequestDoesNotMatchWrongPendingQuantity(self):
        d = ModbusDecoder()
        d.decode(adu(bytes.fromhex("010100000001")), 1.0)
        r = d.decode(adu(bytes.fromhex("010103000001")), 1.1)
        self.assertEqual(r["type"], "request")
        self.assertEqual(r["message"], "1 coils from 768")

    def testReadCoilsAmbiguousLength(self):
        # a response with a byte count of 3 has the same length as a request
        d = ModbusDecoder()
        d.decode(adu(bytes.fromhex("010100130013")), 1.0)
        r = d.decode(adu(bytes.fromhex("010103cd6b05")), 1.1)
        self.assertEqual(r["type"], "response")
        self.assertEqual(r["message"], "coils from 19: 1011001111010110101")

    def testWriteSingleRegisterEcho(self):
        d = ModbusDecoder()
        frame = adu(bytes.fromhex("110600010003"))
        self.assertEqual(d.decode(frame, 1.0)["type"], "request")
        r = d.decode(frame, 1.2)
        self.assertEqual(r["type"], "response")
        self.assertEqual(r["message"], "register 1 = 0003")

    def testWriteMultipleRegisters(self):
        d = ModbusDecoder()
        r = d.decode(adu(bytes.fromhex("011000010002040000000a")), 1.0)
        self.assertEqual(r["message"], "write 2 registers from 1: 0000 000A")
        self.assertEqual(d.decode(adu(bytes.fromhex("011000010002")), 1.1)["type"], "response")

    def testException(self):
        r = ModbusDecoder().decode(adu(bytes.fromhex("018302")))
        self.assertEqual(r["type"], "exception")
        self.assertEqual(r["function"], 3)
        self.assertEqual(r["message"], "Illegal Data Address")


class ModbusStreamTest(TestCase):
    @skipUnless(FskUartDecoder is not None, "requires native CSDR/PyCSDR FskUartDecoder")
    def testEchoResponsesSurviveAudioPipeline(self):
        for body in ("01050001ff00", "110600010003", "01160001ffff0000"):
            for parity in (None, "E"):
                with self.subTest(body=body, parity=parity):
                    frame = adu(bytes.fromhex(body))
                    # Both packets are parsed at the same wall-clock time,
                    # as can happen when buffered audio arrives in one read.
                    result = decodeStream(synth([frame, frame], parity=parity))
                    self.assertEqual([r["type"] for r in result], ["request", "response"])
                    self.assertEqual([r["raw"] for r in result], [frame.hex().upper()] * 2)

    @skipUnless(FskUartDecoder is not None, "requires native CSDR/PyCSDR FskUartDecoder")
    def testParallelCopiesAndRepeatedPacketsAcrossChunkSizes(self):
        # Every byte has odd-parity bit 1, so both UARTs recover this frame.
        frame = adu(bytes.fromhex("030300000005"))
        samples = synth([frame, frame], parity="O")
        for size in (1, 997, len(samples)):
            with self.subTest(chunkSize=size):
                result = decodeStream(samples, size)
                self.assertEqual([r["raw"] for r in result], [frame.hex().upper()] * 2)

    def testDelayedParallelCopyWithDifferentJunk(self):
        d = ModbusStreamDecoder()
        frame = adu(bytes.fromhex("110600010003"))
        starts = tuple(range(1000, 1000 + 100 * len(frame), 100))
        self.assertEqual(len(d.decode(uartLine(8, b"\x55" + frame, (900,) + starts), 1.0)), 1)
        # An unrelated frame is reported before the second UART finishes.
        d.decode(uartLine(8, REQ, range(3000, 3000 + 100 * len(REQ), 100)), 1.1)
        self.assertEqual(d.decode(uartLine(9, frame + b"\xff", starts + (1800,)), 2.0), [])
        later = tuple(n + 10000 for n in starts)
        self.assertEqual(d.decode(uartLine(8, frame, later), 2.1)[0]["type"], "response")

    def testTwoIdenticalFramesInOneRun(self):
        frame = adu(bytes.fromhex("110600010003"))
        d = ModbusStreamDecoder()
        result = d.decode(uartLine(8, frame * 2, range(0, len(frame) * 200, 100)), 1.0)
        self.assertEqual([r["type"] for r in result], ["request", "response"])

    def testInvalidTimingMetadata(self):
        d = ModbusStreamDecoder()
        for line in (b"8 0 010203", b"8 0,0 0102", b"8 -1,2 0102", b"8 x 01",
                     b"8 1 gg", b"8 1 \xff", b"7 1 01", b"8 0102"):
            with self.subTest(line=line):
                self.assertEqual(d.decode(line), [])
