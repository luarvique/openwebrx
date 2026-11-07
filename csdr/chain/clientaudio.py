from csdr.chain import Chain
from pycsdr.modules import AudioResampler, Convert, AdpcmEncoder, Limit, NoiseFilter
from pycsdr.types import Format


def isStereo(format: Format):
    return format == Format.COMPLEX_FLOAT or format == Format.COMPLEX_SHORT


class Converter(Chain):
    def __init__(self, format: Format, inputRate: int, clientRate: int, nrEnabled: bool, nrThreshold: int):
        workers = []
        self.nr = None
        if isStereo(format):
            # we only have an audio resampler for complex float ATM,
            # so if we need to resample, we need to convert
            if inputRate != clientRate and format != Format.COMPLEX_FLOAT:
                workers += [Convert(format, Format.COMPLEX_FLOAT)]
            if inputRate != clientRate:
                workers += [
                    AudioResampler(Format.COMPLEX_FLOAT, inputRate, clientRate),
                    Limit(Format.COMPLEX_FLOAT),
                    Convert(Format.COMPLEX_FLOAT, Format.COMPLEX_SHORT)
                ]
            elif format != Format.COMPLEX_SHORT:
                workers += [Convert(format, Format.COMPLEX_SHORT)]
        else:
            # we only have an audio resampler and noise filter for float ATM,
            # so if we need to resample or remove noise, we need to convert
            if (inputRate != clientRate or nrEnabled) and format != Format.FLOAT:
                workers += [Convert(format, Format.FLOAT)]
            if nrEnabled:
                self.nr = NoiseFilter(nrThreshold)
                workers += [ self.nr ]
            if inputRate != clientRate:
                workers += [
                    AudioResampler(Format.FLOAT, inputRate, clientRate),
                    Limit(Format.FLOAT),
                    Convert(Format.FLOAT, Format.SHORT)
                ]
            elif format != Format.SHORT:
                workers += [Convert(format, Format.SHORT)]
        super().__init__(workers)

    def setNrThreshold(self, nrThreshold: int) -> None:
        if self.nr is not None:
            self.nr.setThreshold(nrThreshold)


class ClientAudioChain(Chain):
    def __init__(self, format: Format, inputRate: int, clientRate: int, compression: str, nrEnabled: bool, nrThreshold: int):
        self.format = format
        self.inputRate = inputRate
        self.clientRate = clientRate
        self.nrEnabled = nrEnabled
        self.nrThreshold = nrThreshold
        workers = []
        self.converter = self._buildConverter()
        if not self.converter.empty():
            workers += [self.converter]
        if compression == "adpcm":
            workers += [self._buildEncoder()]
        super().__init__(workers)

    def _buildConverter(self):
        return Converter(self.format, self.inputRate, self.clientRate, self.nrEnabled, self.nrThreshold)

    def _buildEncoder(self):
        format = Format.COMPLEX_SHORT if isStereo(self.format) else Format.SHORT
        return AdpcmEncoder(format, sync=True)

    def _updateConverter(self):
        self.converter = self._buildConverter()
        index = self.indexOf(lambda x: isinstance(x, Converter))
        if self.converter.empty():
            if index >= 0:
                self.remove(index)
        else:
            if index >= 0:
                self.replace(index, self.converter)
            else:
                self.insert(0, self.converter)

    def setFormat(self, format: Format) -> None:
        if format == self.format:
            return
        adpcmIndex = -1
        if isStereo(format) != isStereo(self.format):
            # is it safe to remove reader and writer here?
            # hopefully they get reattached in dsp.py
            self.writer = None
            self.reader = None
            # will have to recreate encoder later
            adpcmIndex = self.indexOf(lambda x: isinstance(x, AdpcmEncoder))
            if adpcmIndex >= 0:
                self.remove(adpcmIndex)
        self.format = format
        self._updateConverter()
        # recreate encoder if needed
        if adpcmIndex >= 0:
            self.append(self._buildEncoder())

    def setInputRate(self, inputRate: int) -> None:
        if inputRate == self.inputRate:
            return
        self.inputRate = inputRate
        self._updateConverter()

    def setClientRate(self, clientRate: int) -> None:
        if clientRate == self.clientRate:
            return
        self.clientRate = clientRate
        self._updateConverter()

    def setAudioCompression(self, compression: str) -> None:
        index = self.indexOf(lambda x: isinstance(x, AdpcmEncoder))
        if compression == "adpcm":
            if index < 0:
                self.append(self._buildEncoder())
        else:
            if index >= 0:
                self.remove(index)

    def setNrEnabled(self, nrEnabled: bool) -> None:
        if nrEnabled == self.nrEnabled:
            return
        self.nrEnabled = nrEnabled
        self._updateConverter()

    def setNrThreshold(self, nrThreshold: int) -> None:
        if self.converter is not None:
            self.converter.setNrThreshold(nrThreshold)
