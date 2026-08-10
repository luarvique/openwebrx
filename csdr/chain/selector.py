from csdr.chain import Chain
from pycsdr.modules import Shift, FirDecimate, Bandpass, Squelch, FractionalDecimator, Writer
from pycsdr.types import Format
from typing import Union
import math
import logging

logger = logging.getLogger(__name__)


class Decimator(Chain):
    def __init__(self, inputRate: int, outputRate: int):
        if outputRate > inputRate:
            logger.error("impossible decimation: cannot upsample {} to {}".format(inputRate, outputRate))
            outputRate = inputRate
# @@@ Avoid exceptions, since later GC may crash Python!
#            raise ValueError("impossible decimation: cannot upsample {} to {}".format(inputRate, outputRate))
        self.inputRate = inputRate
        self.outputRate = outputRate

        decimation, fraction = self._getDecimation(outputRate)
        transition = 0.15 * (outputRate / float(self.inputRate))
        # set the cutoff on the fist decimation stage lower so that the resulting output
        # is already prepared for the second (fractional) decimation stage.
        # this spares us a second filter.
        cutoff = 0.5 * decimation / (self.inputRate / outputRate)

        workers = [
            FirDecimate(decimation, transition, cutoff),
        ]

        if fraction != 1.0:
            workers += [FractionalDecimator(Format.COMPLEX_FLOAT, fraction)]

        super().__init__(workers)

    def _getDecimation(self, outputRate: int) -> (int, float):
        if outputRate > self.inputRate:
            logger.error("cannot provide selected output rate {} since it is bigger than input rate {}".format(outputRate, self.inputRate))
            outputRate = self.inputRate
# @@@ Avoid exceptions, since later GC may crash Python!
#            raise SelectorError(
#                "cannot provide selected output rate {} since it is bigger than input rate {}".format(
#                    outputRate,
#                    self.inputRate
#                )
#            )
        d = self.inputRate / outputRate
        dInt = int(d)
        dFloat = float(self.inputRate / dInt) / outputRate
        return dInt, dFloat

    def _reconfigure(self):
        decimation, fraction = self._getDecimation(self.outputRate)
        transition = 0.15 * (self.outputRate / float(self.inputRate))
        cutoff = 0.5 * decimation / (self.inputRate / self.outputRate)
        self.replace(0, FirDecimate(decimation, transition, cutoff))
        index = self.indexOf(lambda x: isinstance(x, FractionalDecimator))
        if fraction != 1.0:
            decimator = FractionalDecimator(Format.COMPLEX_FLOAT, fraction)
            if index >= 0:
                self.replace(index, decimator)
            else:
                self.append(decimator)
        elif index >= 0:
            self.remove(index)

    def setOutputRate(self, outputRate: int) -> None:
        if outputRate == self.outputRate:
            return
        self.outputRate = outputRate
        self._reconfigure()

    def setInputRate(self, inputRate: int) -> None:
        if inputRate == self.inputRate:
            return
        self.inputRate = inputRate
        self._reconfigure()

    def __str__(self):
        decimation, fraction = self._getDecimation(self.outputRate)
        transition = 0.15 * (self.outputRate / float(self.inputRate))
        cutoff = 0.5 * decimation / (self.inputRate / self.outputRate)
        return "{0}(decimation {1} * {2}, transition {3}, cutoff {4})".format(
            type(self).__name__, decimation, fraction, transition, cutoff
        )


class Selector(Chain):
    def __init__(self, inputRate: int, outputRate: int, withSquelch: bool = True):
        self.inputRate = inputRate
        self.outputRate = outputRate
        self.frequencyOffset = 0

        self.shift = Shift(0.0)

        self.decimation = Decimator(inputRate, outputRate)

        self.bandpass = self._buildBandpass()
        self.bandpassCutoffs = [None, None]

        workers = [self.shift, self.decimation]

        self.measurementsPerSec = 16
        self.readingsPerSec = 4
        self.powerWriter = None
        if withSquelch:
            self.squelch = self._buildSquelch()
            workers += [self.squelch]
        else:
            self.squelch = None

        super().__init__(workers)

    def _buildBandpass(self) -> Bandpass:
        bp_transition = 320.0 / self.outputRate
        return Bandpass(transition=bp_transition, use_fft=True)

    def _buildSquelch(self):
        blockLength = int(self.outputRate / self.measurementsPerSec)
        squelch = Squelch(Format.COMPLEX_FLOAT,
            length      = blockLength,
            decimation  = 5,
            hangLength  = 2 * blockLength,
            flushLength = 5 * blockLength,
            reportInterval = int(self.measurementsPerSec / self.readingsPerSec)
        )
        if self.powerWriter is not None:
            squelch.setPowerWriter(self.powerWriter)
        return squelch

    def setFrequencyOffset(self, offset: int) -> None:
        if offset == self.frequencyOffset:
            return
        self.frequencyOffset = offset
        self._updateShift()

    def _updateShift(self):
        shift = -self.frequencyOffset / self.inputRate
        self.shift.setRate(shift)

    def _convertToLinear(self, db: float) -> float:
        return float(math.pow(10, db / 10))

    def setSquelchLevel(self, level: float) -> None:
        if self.squelch is not None:
            self.squelch.setSquelchLevel(self._convertToLinear(level))

    def _enableBandpass(self):
        index = self.indexOf(lambda x: isinstance(x, Bandpass))
        if index < 0:
            self.insert(2, self.bandpass)

    def _disableBandpass(self):
        index = self.indexOf(lambda x: isinstance(x, Bandpass))
        if index >= 0:
            self.remove(index)

    def setBandpass(self, lowCut: float, highCut: float) -> None:
        self.bandpassCutoffs = [lowCut, highCut]
        if None in self.bandpassCutoffs:
            self._disableBandpass()
        else:
            self._enableBandpass()
            scaled = [x / self.outputRate for x in self.bandpassCutoffs]
            self.bandpass.setBandpass(*scaled)

    def setLowCut(self, lowCut: Union[float, None]) -> None:
        self.bandpassCutoffs[0] = lowCut
        self.setBandpass(*self.bandpassCutoffs)

    def setHighCut(self, highCut: Union[float, None]) -> None:
        self.bandpassCutoffs[1] = highCut
        self.setBandpass(*self.bandpassCutoffs)

    def setPowerWriter(self, writer: Writer) -> None:
        self.powerWriter = writer
        if self.squelch is not None:
            self.squelch.setPowerWriter(writer)

    def setOutputRate(self, outputRate: int) -> None:
        if outputRate == self.outputRate:
            return
        self.outputRate = outputRate
        self.decimation.setOutputRate(outputRate)
        # update bandpass module
        self.bandpass = self._buildBandpass()
        self.setBandpass(*self.bandpassCutoffs)
        index = self.indexOf(lambda x: isinstance(x, Bandpass))
        if index >= 0:
            self.replace(index, self.bandpass)
        # update squelch module if present
        if self.squelch is not None:
            self.squelch = self._buildSquelch()
            index = self.indexOf(lambda x: isinstance(x, Squelch))
            if index >= 0:
                self.replace(index, self.squelch)

    def setInputRate(self, inputRate: int) -> None:
        if inputRate == self.inputRate:
            return
        self.inputRate = inputRate
        self.decimation.setInputRate(inputRate)
        self._updateShift()

    def __str__(self):
        return "{0}({1} => offset {2} => bandpass {3}..{4} => {5})".format(
            type(self).__name__,
            self.inputRate,
            self.frequencyOffset,
            self.bandpassCutoffs[0],
            self.bandpassCutoffs[1],
            self.outputRate
        )


class SecondarySelector(Chain):
    def __init__(self, sampleRate: int, bandwidth: float):
        self.sampleRate = sampleRate
        self.bandwidth = bandwidth
        self.frequencyOffset = 0
        self.shift = Shift(0.0)
        cutoffRate = bandwidth / sampleRate
        self.bandpass = Bandpass(-cutoffRate, cutoffRate, cutoffRate, use_fft=True)
        workers = [self.shift, self.bandpass]
        super().__init__(workers)

    def setFrequencyOffset(self, offset: int) -> None:
        if offset == self.frequencyOffset:
            return
        self.frequencyOffset = offset
        if self.frequencyOffset is None:
            return
        self.shift.setRate(-offset / self.sampleRate)

    def __str__(self):
        return "{0}({1} => offset {2} => bandpass {3}..{4} => {5})".format(
            type(self).__name__,
            self.sampleRate,
            self.frequencyOffset,
            -self.bandwidth,
            self.bandwidth,
            self.sampleRate
        )


class SelectorError(Exception):
    pass
