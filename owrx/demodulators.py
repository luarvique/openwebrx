import struct
import threading

import logging

logger = logging.getLogger(__name__)


# demodulator 0 is the primary one and uses the original, untagged message types
PRIMARY_DEMODULATOR = 0
MAX_DEMODULATOR_ID = 255

# binary message types for tagged demodulators: [type][demod id][payload]
TYPE_AUDIO = 0x12
TYPE_SECONDARY_FFT = 0x13
TYPE_HD_AUDIO = 0x14


class InvalidDemodulatorIdException(ValueError):
    pass


class TooManyDemodulatorsException(Exception):
    pass


def parseDemodulatorId(message: dict) -> int:
    """
    Extract the demodulator id from a client message. Messages without an id refer to the primary demodulator.
    """
    if "demod" not in message:
        return PRIMARY_DEMODULATOR
    demodId = message["demod"]
    # bool is a subclass of int, but true / false are not valid ids
    if not isinstance(demodId, int) or isinstance(demodId, bool):
        raise InvalidDemodulatorIdException("demodulator id must be an integer: {}".format(demodId))
    if demodId < 0 or demodId > MAX_DEMODULATOR_ID:
        raise InvalidDemodulatorIdException("demodulator id out of range: {}".format(demodId))
    return demodId


class DemodulatorHandle(object):
    """
    Stands in for the client connection towards a secondary DspManager, tagging all of its output
    with the demodulator id.
    """
    def __init__(self, client, demodId: int):
        self.client = client
        self.id = demodId

    def _json(self, t: str, value):
        self.client.send({"type": t, "demod": self.id, "value": value})

    def _binary(self, t: int, data):
        self.client.send(bytes([t, self.id]) + data)

    def write_dsp_data(self, data):
        self._binary(TYPE_AUDIO, data)

    def write_secondary_fft(self, data):
        self._binary(TYPE_SECONDARY_FFT, data)

    def write_hd_audio(self, data):
        self._binary(TYPE_HD_AUDIO, data)

    def write_s_meter_level(self, level):
        # may contain more than one sample, so only take the last 4 bytes = 1 float
        level, = struct.unpack('f', level[-4:])
        try:
            self._json("smeter", level)
        except ValueError:
            logger.warning("unable to send smeter value: %s", str(level))

    def write_secondary_demod(self, message):
        self._json("secondary_demod", message)

    def write_secondary_dsp_config(self, cfg):
        self._json("secondary_config", cfg)

    def write_metadata(self, metadata):
        self._json("metadata", metadata)

    def write_demodulator_error(self, message):
        self._json("demodulator_error", message)


class DemodulatorPool(object):
    """
    Keeps track of the demodulators (DspManager instances) of one client connection.

    factory(demodId) must return a new, configured demodulator object with a stop() method.
    """
    def __init__(self, factory, limit):
        self.factory = factory
        # callable, so that config changes are picked up without re-creating the pool
        self.limit = limit if callable(limit) else (lambda: limit)
        self.demodulators = {}
        self.lock = threading.Lock()

    def get(self, demodId: int = PRIMARY_DEMODULATOR, create: bool = True):
        with self.lock:
            if demodId in self.demodulators:
                return self.demodulators[demodId]
            if not create:
                return None
            # the primary demodulator is always allowed, the limit applies to the total count
            if demodId != PRIMARY_DEMODULATOR and len(self.demodulators) >= self.limit():
                raise TooManyDemodulatorsException("maximum number of demodulators reached")
            demodulator = self.factory(demodId)
            if demodulator is not None:
                self.demodulators[demodId] = demodulator
            return demodulator

    def stop(self, demodId: int = None):
        """
        Stop a single demodulator, or all of them if no id is given.
        """
        with self.lock:
            if demodId is None:
                stopping = list(self.demodulators.values())
                self.demodulators = {}
            else:
                demodulator = self.demodulators.pop(demodId, None)
                stopping = [] if demodulator is None else [demodulator]
        # stop outside the lock, DspManager.stop() can take a while
        for demodulator in stopping:
            demodulator.stop()

    def all(self):
        with self.lock:
            return list(self.demodulators.values())

    def __len__(self):
        with self.lock:
            return len(self.demodulators)
