from unittest import TestCase
import math
import random

from owrx.fsk import FskUartDecoder
from owrx.modbus import crc16, findFrames, isPlausible, ModbusDecoder


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


def decodeAll(samples, fs=12000, **kwargs):
    decoder = FskUartDecoder(fs, **kwargs)
    frames = []
    for i in range(0, len(samples), 1000):
        frames += decoder.process(samples[i:i + 1000])
    frames += decoder.flush()
    found = []
    for _, data in frames:
        for f in findFrames(data):
            if f not in found:
                found.append(f)
    return found


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
        self.assertEqual(d.decode(adu(bytes.fromhex("01030000000a")), 1.0)["message"], "10 registers from 0")
        r = d.decode(adu(bytes.fromhex("0103041234abcd")), 1.1)
        self.assertEqual(r["type"], "response")
        self.assertEqual(r["message"], "registers from 0: 1234 ABCD")

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
