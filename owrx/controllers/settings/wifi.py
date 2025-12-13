from owrx.controllers.settings import SettingsFormController
from owrx.form.section import Section
from owrx.form.input.wifi import WifiNameInput
from owrx.form.input import (
    CheckboxInput,
    TextInput,
    NumberInput,
    FloatInput,
    TextAreaInput,
    DropdownInput,
    Option,
)
from owrx.form.input.validator import RangeValidator
from owrx.breadcrumb import Breadcrumb, BreadcrumbItem
from owrx.controllers.settings import SettingsBreadcrumb

import logging

logger = logging.getLogger(__name__)


class WifiSettingsController(SettingsFormController):
    def getTitle(self):
        return "WiFi Settings"

    def get_breadcrumb(self) -> Breadcrumb:
        return SettingsBreadcrumb().append(BreadcrumbItem("WiFi Settings", "settings/wifi"))

    def getSections(self):
        return [
            Section(
                "Access Point 1",
                CheckboxInput("wifi_enable_1", "Enable this access point"),
                WifiNameInput("wifi_name_1", "Name"),
                TextInput("wifi_pass_1", "Password"),
            ),
            Section(
                "Access Point 2",
                CheckboxInput("wifi_enable_2", "Enable this access point"),
                WifiNameInput("wifi_name_2", "Name"),
                TextInput("wifi_pass_2", "Password"),
            ),
            Section(
                "Access Point 3",
                CheckboxInput("wifi_enable_3", "Enable this access point"),
                WifiNameInput("wifi_name_3", "Name"),
                TextInput("wifi_pass_3", "Password"),
            ),
            Section(
                "Access Point 4",
                CheckboxInput("wifi_enable_4", "Enable this access point"),
                WifiNameInput("wifi_name_4", "Name"),
                TextInput("wifi_pass_4", "Password"),
            ),
        ]

    def processData(self, data):
        super().processData(data)
