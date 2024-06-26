from abc import ABCMeta, abstractmethod
from owrx.command import Option
from owrx.source.connector import ConnectorSource, ConnectorDeviceDescription
from typing import List
from owrx.form.input import Input, NumberInput, TextInput
from owrx.form.input.validator import RangeValidator
from owrx.form.input.device import GainInput
from owrx.soapy import SoapySettings


class SoapyConnectorSource(ConnectorSource, metaclass=ABCMeta):
    def getCommandMapper(self):
        return (
            super()
            .getCommandMapper()
            .setBase("soapy_connector")
            .setMappings(
                {
                    "antenna": Option("-a"),
                    "soapy_settings": Option("-t"),
                    "channel": Option("-n"),
                }
            )
        )

    """
    must be implemented by child classes to be able to build a driver-based device selector by default.
    return value must be the corresponding soapy driver identifier.
    """

    @abstractmethod
    def getDriver(self):
        pass

    def getEventNames(self):
        return super().getEventNames() + list(self.getSoapySettingsMappings().keys())

    def buildSoapyDeviceParameters(self, parsed, values):
        """
        this method always attempts to inject a driver= part into the soapysdr query, depending on what connector was used.
        this prevents the soapy_connector from using the wrong device in scenarios where there's no same-type sdrs.
        """
        parsed = [v for v in parsed if "driver" not in v]
        parsed += [{"driver": self.getDriver()}]
        return parsed

    def getSoapySettingsMappings(self):
        return {}

    def buildSoapySettings(self, values):
        settings = {}
        for k, v in self.getSoapySettingsMappings().items():
            if k in values and values[k] is not None:
                settings[v] = self.convertSoapySettingsValue(values[k])
        return settings

    def convertSoapySettingsValue(self, value):
        if isinstance(value, bool):
            return "true" if value else "false"
        return value

    def getCommandValues(self):
        values = super().getCommandValues()
        if "device" in values and values["device"] is not None:
            parsed = SoapySettings.parse(values["device"])
        else:
            parsed = []
        modified = self.buildSoapyDeviceParameters(parsed, values)
        values["device"] = SoapySettings.encode(modified)
        settings = ",".join(["{0}={1}".format(k, v) for k, v in self.buildSoapySettings(values).items()])
        if len(settings):
            values["soapy_settings"] = settings
        return values

    def onPropertyChange(self, changes):
        mappings = self.getSoapySettingsMappings()
        affectsSettings = False
        forward = {}
        for prop, value in changes.items():
            if prop in mappings.keys():
                affectsSettings = True
            else:
                forward[prop] = value
        if affectsSettings:
            settings = {}
            for owrx_key, soapy_key in mappings.items():
                if owrx_key in self.props:
                    settings[soapy_key] = self.convertSoapySettingsValue(self.props[owrx_key])
            forward["settings"] = ",".join("{0}={1}".format(k, v) for k, v in settings.items())
        super().onPropertyChange(forward)


class SoapyConnectorDeviceDescription(ConnectorDeviceDescription):
    def getInputs(self) -> List[Input]:
        inputs = super().getInputs() + [
            TextInput(
                "device",
                "Device identifier",
                infotext='SoapySDR device identifier string (example: "serial=123456789")',
            ),
            GainInput(
                "rf_gain",
                "Device Gain",
                gain_stages=self.getGainStages(),
                has_agc=self.hasAgc(),
            ),
            TextInput("antenna", "Antenna"),
        ]
        if self.getNumberOfChannels() > 1:
            inputs += [
                NumberInput(
                    "channel",
                    "Select SoapySDR Channel",
                    validator=RangeValidator(0, self.getNumberOfChannels() - 1)
                )
            ]
        return inputs

    def getNumberOfChannels(self) -> int:
        """
        can be overridden for sdr devices that have multiple channels. will allow the user to select a channel from
        the device selection screen if > 1
        """
        return 1

    def getDeviceOptionalKeys(self):
        return super().getDeviceOptionalKeys() + ["device", "rf_gain", "antenna", "channel"]

    def getProfileOptionalKeys(self):
        return super().getProfileOptionalKeys() + ["antenna"]

    def getGainStages(self):
        return None
