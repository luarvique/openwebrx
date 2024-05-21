# eroyee; experimental module for soapyMiri driver that should run Mirics-based hardware.
#
# Library / driver is from Erik here : https://github.com/ericek111/SoapyMiri, and
# Edouard here: https://github.com/f4exb/libmirisdr-4
#
# This is quite alpha, I've tested it with just one device which seems to work,
# but there may be some spurious signals, and in some cases it won't receive
# dead on the centre frequency. This should be addressable by setting an offset.
# 
# Help to improve this is welcome, and there may be other settings to implement
# in time, just not yet.
#
# Sampling rate should be set at specified values such as 2, 5, 8 MHz, other rates 
# can give errors.
#
# If present you will need to blacklist the msi2500 device drivers. 
# See : https://www.radiosrs.net/msi2500_driver_conflicts.html

from owrx.source.soapy import SoapyConnectorSource, SoapyConnectorDeviceDescription
from owrx.form.input import Input, CheckboxInput, DropdownInput, DropdownEnum
from owrx.form.input.device import BiasTeeInput
from typing import List


class SoapymiriSource(SoapyConnectorSource):
    def getSoapySettingsMappings(self):
        mappings = super().getSoapySettingsMappings()
        mappings.update(
            {
                "bias_tee": "biasT_ctrl",
                "offset_tune": "offset_tune",
                "bufflen": "bufflen",
                "buffers": "buffers",
                "asyncbuffers": "asyncBuffs",
            }
        )
        return mappings

    def getDriver(self):
        return "soapyMiri"

class BuffLenOptions(DropdownEnum):
    BUFFLEN_15872 = "15872"
    BUFFLEN_36864 = "36864"
    BUFFLEN_73728 = "73728"

    def __str__(self):
        return self.value

class BuffersOptions(DropdownEnum):
    BUFFERS_8 = "8"
    BUFFERS_15 = "15"
    BUFFERS_24 = "24"

    def __str__(self):
        return self.value

class AsyncBuffsOptions(DropdownEnum):
    ASYNCBUFF_0 = "0"
    ASYNCBUFF_2 = "2"
    ASYNCBUFF_4 = "4"

    def __str__(self):
        return self.value

class SoapymiriDeviceDescription(SoapyConnectorDeviceDescription):
    def getName(self):
        return "Miric-based device (via SoapySDR)"

    def getInputs(self) -> List[Input]:
        return super().getInputs() + [
            BiasTeeInput(),
            CheckboxInput(
                "offset_tune",
                "Offset Tuning Mode, default=off",
            ),
            DropdownInput(
                "bufflen",
                "Bufferlength in 512byte multiples, default=36864",
                BuffLenOptions,
            ),
            DropdownInput(
                "buffers",
                "Buffers in ring, default=15",
                BuffersOptions,
            ),
            DropdownInput(
                "asyncbuffers",
                "Async USB buffers, default=0",
                AsyncBuffsOptions,
            ),
        ]

    def getDeviceOptionalKeys(self):
        return super().getDeviceOptionalKeys() + ["bias_tee", "offset_tune", "bufflen", "buffers", "asyncbuffers"]

    def getProfileOptionalKeys(self):
        return super().getProfileOptionalKeys() + ["bias_tee", "offset_tune", "bufflen" "buffers", "asyncbuffers"]
