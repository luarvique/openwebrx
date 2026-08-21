from owrx.source.soapy import SoapyConnectorSource, SoapyConnectorDeviceDescription
from owrx.form.input import Input, NumberInput
from owrx.form.input.validator import Range, RangeValidator
from typing import List


class M17sx1255hat36000Source(SoapyConnectorSource):
    def getSoapySettingsMappings(self):
        mappings = super().getSoapySettingsMappings()
        mappings.update(
            {
                "rfgain_sel": "rfgain_sel"
            }
        )
        return mappings

    def getDriver(self):
        return "sx"


class M17sx1255hat36000DeviceDescription(SoapyConnectorDeviceDescription):
    def getName(self):
        return "M17 SX1255 HAT (with 36 MHz TCXO)"

    def hasAgc(self):
        return False

    def getInputs(self) -> List[Input]:
        return super().getInputs() + [
            NumberInput(
                "rfgain_sel",
                "RF gain reduction",
                validator=RangeValidator(0, 78),
            ),
        ]

    def getDeviceOptionalKeys(self):
        return super().getDeviceOptionalKeys() + [
            "rfgain_sel"
        ]

    def getProfileOptionalKeys(self):
        return super().getProfileOptionalKeys() + [
            "rfgain_sel"
        ]

    def getSampleRateRanges(self) -> List[Range]:
        # For SXceiver, SoapySX only implements these prescalers: 64, 128, 256, 512, 768 and 1536.
        # These seem to provide stable outputs, so i honour that.
        # This variant is for M17 Project SX1255 HAT that uses TCXO 36 MHz,
        # so these sample rates reflect that.
        # If you replace the TCXO, you should try the other variants (e.g. SXceiver for 38.4 MHz TCXO).
        # I don't think it's accurate, but this is the limitation we'd be running into if we had proper soapy
        # integration.
        return [
            Range(36000000 // 1536),
            Range(36000000 // 768),
            Range(36000000 // 512),
            Range(36000000 // 256),
            Range(36000000 // 128),
            Range(36000000 // 64),
        ]
