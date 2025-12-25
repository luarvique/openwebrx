from owrx.wifi import WiFi
from owrx.controllers.settings import SettingsFormController
from owrx.form.section import Section
from owrx.form.input.wifi import WifiSsidValidator, WifiPassValidator
from owrx.form.input import CheckboxInput, TextInput
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
                "Self-Hosted Access Point",
                CheckboxInput("wifi_enable_ap", "Enable access point (192.168.10.1)"),
                TextInput("wifi_name_ap", "SSID", validator=WifiSsidValidator()),
                TextInput("wifi_pass_ap", "Password", validator=WifiPassValidator()),
            ),
            Section(
                "Connection 1",
                CheckboxInput("wifi_enable_1", "Enable this connection"),
                TextInput("wifi_name_1", "SSID", validator=WifiSsidValidator()),
                TextInput("wifi_pass_1", "Password", validator=WifiPassValidator()),
            ),
            Section(
                "Connection 2",
                CheckboxInput("wifi_enable_2", "Enable this connection"),
                TextInput("wifi_name_2", "SSID", validator=WifiSsidValidator()),
                TextInput("wifi_pass_2", "Password", validator=WifiPassValidator()),
            ),
            Section(
                "Connection 3",
                CheckboxInput("wifi_enable_3", "Enable this connection"),
                TextInput("wifi_name_3", "SSID", validator=WifiSsidValidator()),
                TextInput("wifi_pass_3", "Password", validator=WifiPassValidator()),
            ),
            Section(
                "Connection 4",
                CheckboxInput("wifi_enable_4", "Enable this connection"),
                TextInput("wifi_name_4", "SSID", validator=WifiSsidValidator()),
                TextInput("wifi_pass_4", "Password", validator=WifiPassValidator()),
            ),
        ]

    def processData(self, data):
        # Save data to config
        super().processData(data)
        super().store()
        # Apply new WiFi settings
        WiFi.getSharedInstance().applyNewSettings()
