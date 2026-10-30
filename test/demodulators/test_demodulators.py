from owrx.demodulators import DemodulatorHandle, DemodulatorPool, parseDemodulatorId, \
    InvalidDemodulatorIdException, TooManyDemodulatorsException, PRIMARY_DEMODULATOR, \
    TYPE_AUDIO, TYPE_SECONDARY_FFT, TYPE_HD_AUDIO
from unittest import TestCase
from unittest.mock import Mock
import struct
import threading


class ParseDemodulatorIdTest(TestCase):
    def testMissingIdIsPrimary(self):
        self.assertEqual(parseDemodulatorId({"type": "dspcontrol"}), PRIMARY_DEMODULATOR)

    def testValidIds(self):
        self.assertEqual(parseDemodulatorId({"demod": 0}), 0)
        self.assertEqual(parseDemodulatorId({"demod": 3}), 3)
        self.assertEqual(parseDemodulatorId({"demod": 255}), 255)

    def testOutOfRange(self):
        for value in [-1, 256, 100000]:
            with self.assertRaises(InvalidDemodulatorIdException):
                parseDemodulatorId({"demod": value})

    def testWrongType(self):
        for value in ["1", 1.0, None, True, [1], {"id": 1}]:
            with self.assertRaises(InvalidDemodulatorIdException):
                parseDemodulatorId({"demod": value})


class DemodulatorHandleTest(TestCase):
    def setUp(self):
        self.client = Mock()
        self.handle = DemodulatorHandle(self.client, 7)

    def testAudioIsTagged(self):
        self.handle.write_dsp_data(b"\x01\x02\x03")
        self.client.send.assert_called_once_with(bytes([TYPE_AUDIO, 7, 1, 2, 3]))

    def testHdAudioIsTagged(self):
        self.handle.write_hd_audio(b"\xff")
        self.client.send.assert_called_once_with(bytes([TYPE_HD_AUDIO, 7, 0xff]))

    def testSecondaryFftIsTagged(self):
        self.handle.write_secondary_fft(b"")
        self.client.send.assert_called_once_with(bytes([TYPE_SECONDARY_FFT, 7]))

    def testTaggedTypesDoNotCollideWithPrimaryTypes(self):
        # 0x01 - 0x04 are used by the untagged primary demodulator and the main fft
        self.assertTrue({TYPE_AUDIO, TYPE_SECONDARY_FFT, TYPE_HD_AUDIO}.isdisjoint({0x01, 0x02, 0x03, 0x04}))

    def testSmeterUsesLastSample(self):
        self.handle.write_s_meter_level(struct.pack("ff", 0.25, 0.5))
        self.client.send.assert_called_once_with({"type": "smeter", "demod": 7, "value": 0.5})

    def testJsonMessagesAreTagged(self):
        cases = [
            (self.handle.write_secondary_demod, "secondary_demod", "decoded text"),
            (self.handle.write_secondary_dsp_config, "secondary_config", {"secondary_bw": 31.25}),
            (self.handle.write_metadata, "metadata", {"protocol": "DMR"}),
            (self.handle.write_demodulator_error, "demodulator_error", "broken"),
        ]
        for method, t, value in cases:
            self.client.send.reset_mock()
            method(value)
            self.client.send.assert_called_once_with({"type": t, "demod": 7, "value": value})

    def testCoversDspManagerOutputs(self):
        # every handler method DspManager writes to must exist on the handle
        for name in ["write_dsp_data", "write_hd_audio", "write_s_meter_level", "write_secondary_fft",
                     "write_secondary_demod", "write_metadata", "write_secondary_dsp_config",
                     "write_demodulator_error"]:
            self.assertTrue(callable(getattr(self.handle, name, None)), name)


class DemodulatorPoolTest(TestCase):
    def setUp(self):
        self.created = {}

        def factory(demodId):
            demod = Mock()
            demod.id = demodId
            self.created[demodId] = demod
            return demod

        self.factory = factory

    def testPrimaryIsCreatedOnce(self):
        pool = DemodulatorPool(self.factory, 1)
        first = pool.get()
        self.assertIs(pool.get(), first)
        self.assertIs(pool.get(PRIMARY_DEMODULATOR), first)
        self.assertEqual(len(pool), 1)

    def testDefaultLimitOnlyAllowsPrimary(self):
        pool = DemodulatorPool(self.factory, 1)
        pool.get(0)
        with self.assertRaises(TooManyDemodulatorsException):
            pool.get(1)
        self.assertEqual(len(pool), 1)

    def testPrimaryIsExemptFromLimit(self):
        pool = DemodulatorPool(self.factory, 2)
        pool.get(1)
        pool.get(2)
        # the limit is reached, but the primary must still be available
        self.assertIsNotNone(pool.get(0))
        self.assertEqual(len(pool), 3)

    def testLimitIsEnforced(self):
        pool = DemodulatorPool(self.factory, 3)
        for i in range(3):
            pool.get(i)
        with self.assertRaises(TooManyDemodulatorsException):
            pool.get(3)
        # existing demodulators can still be looked up at the limit
        self.assertIs(pool.get(2), self.created[2])

    def testLimitIsReadOnEveryCall(self):
        limit = {"value": 1}
        pool = DemodulatorPool(self.factory, lambda: limit["value"])
        pool.get(0)
        with self.assertRaises(TooManyDemodulatorsException):
            pool.get(1)
        limit["value"] = 2
        self.assertIsNotNone(pool.get(1))

    def testStopSingle(self):
        pool = DemodulatorPool(self.factory, 4)
        pool.get(0)
        pool.get(1)
        pool.stop(1)
        self.created[1].stop.assert_called_once_with()
        self.created[0].stop.assert_not_called()
        self.assertIsNone(pool.get(1, create=False))
        self.assertEqual(len(pool), 1)

    def testStopFreesSlot(self):
        pool = DemodulatorPool(self.factory, 2)
        pool.get(0)
        pool.get(1)
        pool.stop(1)
        self.assertIsNotNone(pool.get(2))

    def testStopUnknownIsNoop(self):
        pool = DemodulatorPool(self.factory, 2)
        pool.stop(5)
        self.assertEqual(len(pool), 0)

    def testStopAll(self):
        pool = DemodulatorPool(self.factory, 4)
        for i in range(3):
            pool.get(i)
        pool.stop()
        for demod in self.created.values():
            demod.stop.assert_called_once_with()
        self.assertEqual(len(pool), 0)
        self.assertEqual(pool.all(), [])

    def testFactoryReturningNoneIsNotStored(self):
        # e.g. no sdr is available yet
        pool = DemodulatorPool(lambda demodId: None, 2)
        self.assertIsNone(pool.get(0))
        self.assertEqual(len(pool), 0)

    def testGetWithoutCreate(self):
        pool = DemodulatorPool(self.factory, 2)
        self.assertIsNone(pool.get(1, create=False))
        self.assertEqual(self.created, {})

    def testStopDoesNotHoldLock(self):
        # stopping a DspManager may call back into the client, which must not deadlock
        pool = DemodulatorPool(self.factory, 2)
        demod = pool.get(0)
        demod.stop.side_effect = lambda: pool.all()
        thread = threading.Thread(target=pool.stop)
        thread.start()
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())

    def testConcurrentGetCreatesOnce(self):
        pool = DemodulatorPool(self.factory, 2)
        results = []
        threads = [threading.Thread(target=lambda: results.append(pool.get(1))) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(set(id(r) for r in results)), 1)
        self.assertEqual(len(pool), 1)
