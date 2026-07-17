from owrx.source.soapy import SoapyConnectorSource, SoapyConnectorDeviceDescription
from owrx.form.input import Input
from typing import List


class EladSource(SoapyConnectorSource):
    def getDriver(self):
        return "elad"


class EladDeviceDescription(SoapyConnectorDeviceDescription):
    def getName(self):
        return "ELAD FDM-S2"

    def getInputs(self) -> List[Input]:
        return super().getInputs()

    def getDeviceOptionalKeys(self):
        return super().getDeviceOptionalKeys()

    def getProfileOptionalKeys(self):
        return super().getProfileOptionalKeys()
