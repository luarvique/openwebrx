from owrx.source.soapy import SoapyConnectorSource, SoapyConnectorDeviceDescription
from owrx.form.input import Input, TextInput, CheckboxInput, NumberInput
from owrx.form.input.validator import Range, RangeValidator
from typing import List


class DubokSource(SoapyConnectorSource):
    def getSoapySettingsMappings(self):
        mappings = super().getSoapySettingsMappings()
        mappings.update(
            {
                "biasT"       : "biasT",
                "highZ"       : "highZ",
                "lna"         : "lna",
                "attenuator"  : "attenuator"
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
            CheckboxInput(
                "biasT",
                "External antenna power output (Bias-T)",
            ),
            CheckboxInput(
                "highZ",
                "High-impedance antenna input",
            ),
            CheckboxInput(
                "lna",
                "Low-noise amplifier (LNA)",
            ),
            NumberInput(
                "attenuator",
                "Attenuation level",
                validator=RangeValidator(0, 30),
            ),
        ]

    def getDeviceOptionalKeys(self):
        return super().getDeviceOptionalKeys() + ["biasT", "highZ", "lna", "attenuator"]

    def getSampleRateRanges(self) -> List[Range]:
        return [ Range(744192) ]

