from owrx.source.soapy import SoapyConnectorSource, SoapyConnectorDeviceDescription
from owrx.form.input.validator import Range
from typing import List

class FileSource(SoapyConnectorSource): 
    def getDriver(self):
        return "file"

class FileDeviceDescription(SoapyConnectorDeviceDescription):
    def getName(self):
        return "IQ File / FIFO source (SoapyFile)"

    def getSampleRateRanges(self) -> List[Range]:
        return [Range(525000, 1775000)]
