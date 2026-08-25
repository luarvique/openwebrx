from owrx.source.soapy import SoapyConnectorSource, SoapyConnectorDeviceDescription
from owrx.form.input import Input, NumberInput, DropdownInput
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

    def getEventNames(self):
        return super().getEventNames() + [
            "clk_freq", "clk_prescaler"
        ]

    def getCommandValues(self):
        # calculate samp_rate and re-inject it back to command values
        dict = super().getCommandValues()
        if "clk_freq" in dict and "clk_prescaler" in dict:
            dict["samp_rate"] = round(dict["clk_freq"] / dict["clk_prescaler"])
        return dict

    def validateProfiles(self):
        # adding validator for new required clk_prescaler
        super(SxceiverSource, self).validateProfiles();
        props = PropertyStack()
        props.addLayer(1, self.props)
        for id, p in self.props["profiles"].items():
            props.replaceLayer(0, p)
            if "clk_prescaler" not in props:
                self.logger.warning('Profile "%s" does not specify a clk_prescaler', id)
                continue

    def reportProfileChange(self):
        self.reportRxEvent({
            "profile_id" : self.getProfileId(),
            "profile"    : self.getProfileName(),
            "freq"       : self.props["center_freq"],
            "samplerate" : round(self.sdrProps["clk_freq"] / self.props["clk_prescaler"])
        })

class SxceiverClockFrequency:
    def __init__(self, frequency):
        self.value = frequency
        self.text = f"%.3f MHz" % (frequency / 1000000)

class SxceiverSampleRatePrescaler:
    def __init__(self, prescaler):
        self.value = prescaler
        self.text = f"Clock divide by %d" % prescaler

class SxceiverDeviceDescription(SoapyConnectorDeviceDescription):
    def getName(self):
        return "OH2EAT SXceiver or M17 Project SX1255 HAT"

    def hasAgc(self):
        return False

    def supportsPpm(self):
        return False

    def getInputs(self) -> List[Input]:
        # Drop the sample rate input in favour of prescaler selection
        # Sample rate will be generated when getCommandValue is called
        inputs = super().getInputs()
        for i, elem in enumerate(inputs):
            if elem.id == "samp_rate":
                inputs[i] = DropdownInput(
                    "clk_prescaler",
                    "Sample rate prescaler",
                    [
                        SxceiverSampleRatePrescaler(1536),
                        SxceiverSampleRatePrescaler(768),
                        SxceiverSampleRatePrescaler(512),
                        SxceiverSampleRatePrescaler(256),
                        SxceiverSampleRatePrescaler(128),
                        SxceiverSampleRatePrescaler(64),
                    ],
                    "Selects the prescaler for calculating the sample rate for the HAT.  Sample rate is calculated by dividing the HAT TCXO frequency by the prescaler."
                )
                del elem
        return inputs + [
            DropdownInput(
                "clk_freq",
                "HAT TCXO frequency",
                [
                    SxceiverClockFrequency(38400000),
                    SxceiverClockFrequency(32000000),
                ],
                "Selects the HAT TCXO frequency: the official SXceiver HAT is 38.4 MHz while the M17 Project SX1255 HAT is 32 MHz.\
                This is important for setting the sample rate of the HAT and center frequency step size.",
            ),
            NumberInput(
                "rfgain_sel",
                "RF gain reduction",
                validator=RangeValidator(0, 78),
            ),
        ]

    def getDeviceMandatoryKeys(self):
        return super().getDeviceMandatoryKeys() + [
            "clk_freq"
        ]

    def getProfileMandatoryKeys(self):
        # Replacing samp_rate with our substitute clk_prescaler
        keys = super().getProfileMandatoryKeys()
        if "samp_rate" in keys:
            keys[keys.index("samp_rate")] = "clk_prescaler"
        return keys

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
        # Further checking is required before starting the SDR, since these rates evaluate both 32 and 38.4 MHz
        # TCXO inputs.
        # I don't think it's accurate, but this is the limitation we'd be running into if we had proper soapy
        # integration.
        return [
            Range(32000000 // 1536),
            Range(38400000 // 1536),
            Range(32000000 // 768),
            Range(38400000 // 768),
            Range(32000000 // 512),
            Range(38400000 // 512),
            Range(32000000 // 256),
            Range(38400000 // 256),
            Range(32000000 // 128),
            Range(38400000 // 128),
            Range(32000000 // 64),
            Range(38400000 // 64),
        ]
