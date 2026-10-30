from csdr.chain import Chain
from pycsdr.modules import AudioResampler, Convert, AdpcmEncoder, Limit, NoiseFilter
from pycsdr.types import Format


class Converter(Chain):
    def __init__(self, format: Format, inputRate: int, clientRate: int, nrEnabled: bool, nrThreshold: int):
        workers = []
        # pass IQ or stereo streams through
        if format == Format.COMPLEX_SHORT:
            pass
        elif format == Format.COMPLEX_FLOAT:
            workers += [Convert(format, Format.COMPLEX_SHORT)]
        else:
            # we only have an audio resampler and noise filter for float ATM,
            # so if we need to resample or remove noise, we need to convert
            if (inputRate != clientRate or nrEnabled) and format != Format.FLOAT:
                workers += [Convert(format, Format.FLOAT)]
            if nrEnabled:
                workers += [NoiseFilter(nrThreshold)]
            if inputRate != clientRate:
                workers += [AudioResampler(inputRate, clientRate), Limit(), Convert(Format.FLOAT, Format.SHORT)]
            elif format != Format.SHORT:
                workers += [Convert(format, Format.SHORT)]
        super().__init__(workers)


class ClientAudioChain(Chain):
    def __init__(self, format: Format, inputRate: int, clientRate: int, compression: str, nrEnabled: bool, nrThreshold: int):
        self.format = format
        self.inputRate = inputRate
        self.clientRate = clientRate
        self.nrEnabled = nrEnabled
        self.nrThreshold = nrThreshold
        workers = []
        converter = self._buildConverter()
        if not converter.empty():
            workers += [converter]
        if compression == "adpcm" and format != Format.COMPLEX_FLOAT and format != Format.COMPLEX_SHORT:
            workers += [AdpcmEncoder(sync=True)]
        super().__init__(workers)

    def _buildConverter(self):
        return Converter(self.format, self.inputRate, self.clientRate, self.nrEnabled, self.nrThreshold)

    def _updateConverter(self):
        converter = self._buildConverter()
        index = self.indexOf(lambda x: isinstance(x, Converter))
        if converter.empty():
            if index >= 0:
                self.remove(index)
        else:
            if index >= 0:
                self.replace(index, converter)
            else:
                self.insert(0, converter)

    def setFormat(self, format: Format) -> None:
        if format == self.format:
            return
        self.format = format
        self._updateConverter()

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
                self.append(AdpcmEncoder(sync=True))
        else:
            if index >= 0:
                self.remove(index)

    def setNrEnabled(self, nrEnabled: bool) -> None:
        if nrEnabled == self.nrEnabled:
            return
        self.nrEnabled = nrEnabled
        self._updateConverter()

    def setNrThreshold(self, nrThreshold: int) -> None:
        if nrThreshold == self.nrThreshold:
            return
        self.nrThreshold = nrThreshold
        self._updateConverter()
