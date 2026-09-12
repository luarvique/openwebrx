from owrx.source.soapy import SoapyConnectorSource, SoapyConnectorDeviceDescription
from owrx.form.input.validator import Range
from typing import List

class IQFileSource(SoapyConnectorSource): 
    def getDriver(self):
        return "iqfile"

class IQFileDeviceDescription(SoapyConnectorDeviceDescription):
    def getName(self):
        return "IQ File / FIFO source (SoapyIQFile)"

    def getSampleRateRanges(self) -> List[Range]:
        return [Range(525000, 1775000)]
