from owrx.source.soapy import SoapyConnectorSource, SoapyConnectorDeviceDescription
from owrx.form.input import Input, NumberInput
from owrx.form.input.validator import Range, RangeValidator
from typing import List


class SxceiverSource(SoapyConnectorSource):
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


class SxceiverDeviceDescription(SoapyConnectorDeviceDescription):
    def getName(self):
        return "OH2EAT SXceiver"

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
        # The SXceiver uses TCXO 38.4 MHz, so these sample rates reflect that.
        # I don't think it's accurate, but this is the limitation we'd be running into if we had proper soapy
        # integration.
        return [
            Range(38400000 // 1536),
            Range(38400000 // 768),
            Range(38400000 // 512),
            Range(38400000 // 256),
            Range(38400000 // 128),
            Range(38400000 // 64),
        ]
