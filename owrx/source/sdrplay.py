from owrx.source.soapy import SoapyConnectorSource, SoapyConnectorDeviceDescription
from owrx.form.input import Input, CheckboxInput, DropdownInput, NumberInput, DropdownEnum
from owrx.form.input.device import BiasTeeInput, GainInput
from owrx.form.input.validator import Range, RangeValidator
from typing import List


class SdrplaySource(SoapyConnectorSource):
    def getSoapySettingsMappings(self):
        mappings = super().getSoapySettingsMappings()
        mappings.update(
            {
                "bias_tee": "biasT_ctrl",
                "rf_notch": "rfnotch_ctrl",
                "dab_notch": "dabnotch_ctrl",
                "external_reference": "extref_ctrl",
                "hdr_ctrl": "hdr_ctrl",
                "if_mode": "if_mode",
                "rfgain_sel": "rfgain_sel",
                "agc_setpoint": "agc_setpoint",
            }
        )
        return mappings

    def getDriver(self):
        return "sdrplay"


class IfModeOptions(DropdownEnum):
    IFMODE_ZERO_IF = "Zero-IF"
    IFMODE_450 = "450kHz"
    IFMODE_1620 = "1620kHz"
    IFMODE_2048 = "2048kHz"

    def __str__(self):
        return self.value


class SdrplayDeviceDescription(SoapyConnectorDeviceDescription):
    def getName(self):
        return "SDRPlay device (RSP1, RSP2, RSPduo, RSPdx)"

    def getInputs(self) -> List[Input]:
        return super().getInputs() + [
            BiasTeeInput(),
            CheckboxInput(
                "rf_notch",
                "Enable RF notch filter",
            ),
            CheckboxInput(
                "dab_notch",
                "Enable DAB notch filter",
            ),
            CheckboxInput(
                "external_reference",
                "Enable external reference clock",
            ),
            CheckboxInput(
                "hdr_ctrl",
                "Enable HDR mode (RSPdx only)",
                infotext = "The high dynamic resolution (HDR) mode will "
                + "only work when the center frequency is set to 135kHz, "
                + "175kHz, 220kHz, 250kHz, 340kHz, 475kHz, 516kHz, 875kHz, "
                + "1.125MHz, or 1.9MHz. It will not work on devices other "
                + "than RSPdx or at other center frequencies."
            ),
            DropdownInput(
                "if_mode",
                "IF Mode",
                IfModeOptions,
            ),
            NumberInput(
                "rfgain_sel",
                "RF gain reduction",
                validator=RangeValidator(0, 27),
            ),
            NumberInput(
                "agc_setpoint",
                "AGC setpoint",
                append="dBFS",
                validator=RangeValidator(-60, 0),
            ),
            GainInput(
                "rf_gain",
                "IF gain reduction",
                has_agc=self.hasAgc(),
            ),
        ]

    def getDeviceOptionalKeys(self):
        return super().getDeviceOptionalKeys() + [
            "bias_tee", "rf_notch", "dab_notch", "external_reference", "hdr_ctrl",
            "if_mode", "rfgain_sel", "agc_setpoint"
        ]

    def getProfileOptionalKeys(self):
        return super().getProfileOptionalKeys() + [
            "bias_tee", "rf_notch", "dab_notch", "external_reference", "hdr_ctrl",
            "if_mode", "rfgain_sel", "agc_setpoint"
        ]

    def getSampleRateRanges(self) -> List[Range]:
        # this is from SoapySDRPlay3's implementation of listSampleRates().
        # i don't think it's accurate, but this is the limitation we'd be running into if we had proper soapy
        # integration.
        return [
            Range(62500),
            Range(96000),
            Range(125000),
            Range(192000),
            Range(250000),
            Range(384000),
            Range(500000),
            Range(768000),
            Range(1000000),
            Range(1536000),
            Range(2000000, 10660000),
        ]
