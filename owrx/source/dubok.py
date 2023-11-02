from owrx.source.soapy import SoapyConnectorSource, SoapyConnectorDeviceDescription
from owrx.form.input import Input, TextInput, NumberInput
from owrx.form.input.validator import RangeValidator
from typing import List


class DubokSource(SoapyConnectorSource):
    def getSoapySettingsMappings(self):
        mappings = super().getSoapySettingsMappings()
        mappings.update(
            {
                "audioDevice" : "audioDevice",
                "i2cDevice"   : "i2cDevice",
                "i2cAddress"  : "i2cAddress",
            }
        )
        return mappings

    def getDriver(self):
        return "dubok"


class DubokDeviceDescription(SoapyConnectorDeviceDescription):
    def getName(self):
        return "DubokSDR device"

    def getInputs(self) -> List[Input]:
        return super().getInputs() + [
            TextInput(
                "audioDevice",
                "Audio Device",
                infotext="ALSA device to be used for IQ data",
            ),
            TextInput(
                "i2cDevice",
                "I2C Device",
                infotext="I2C device to be used for control",
            ),
            NumberInput(
                "i2cAddress",
                "I2C Address",
                infotext="I2C device address",
                validator=RangeValidator(0, 255),
            ),
        ]

    def getDeviceOptionalKeys(self):
        return super().getDeviceOptionalKeys() + ["audioDevice", "i2cDevice", "i2cAddress"]
