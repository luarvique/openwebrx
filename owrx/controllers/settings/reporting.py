from owrx.controllers.settings import SettingsFormController, SettingsBreadcrumb
from owrx.form.section import Section
from owrx.form.input.converter import OptionalConverter, IntConverter
from owrx.form.input.aprs import AprsBeaconSymbols, AprsAntennaDirections
from owrx.form.input import TextInput, CheckboxInput, DropdownInput, NumberInput, PasswordInput, Option
from owrx.form.input.validator import AddressAndOptionalPortValidator
from owrx.breadcrumb import Breadcrumb, BreadcrumbItem
from owrx.rigcontrol import RigControl

class ReportingController(SettingsFormController):
    def getTitle(self):
        return "Spotting and reporting"

    def get_breadcrumb(self) -> Breadcrumb:
        return SettingsBreadcrumb().append(BreadcrumbItem("Spotting and reporting", "settings/reporting"))

    def getSections(self):
        return [
            Section(
                "APRS-IS settings",
                CheckboxInput(
                    "aprs_igate_enabled",
                    "Send received APRS data to APRS-IS",
                    infotext="Due to limits of the APRS-IS network, reporting will only work for background decoders"
                ),
                TextInput(
                    "aprs_callsign",
                    "APRS callsign",
                    infotext="This callsign will be used to send data to the APRS-IS network",
                ),
                TextInput("aprs_igate_server", "APRS-IS server"),
                PasswordInput("aprs_igate_password", "APRS-IS network password"),
                CheckboxInput(
                    "aprs_igate_beacon",
                    "Send the receiver position to the APRS-IS network",
                    infotext="Please check that your receiver location is setup correctly before enabling the beacon",
                ),
                DropdownInput(
                    "aprs_igate_symbol",
                    "APRS beacon symbol",
                    AprsBeaconSymbols,
                ),
                TextInput(
                    "aprs_igate_comment",
                    "APRS beacon text",
                    infotext="This text will be sent as APRS comment along with your beacon",
                    converter=OptionalConverter(),
                ),
                NumberInput(
                    "aprs_igate_height",
                    "Antenna height",
                    infotext="Antenna height above average terrain (HAAT)",
                    append="m",
                    converter=OptionalConverter(),
                ),
                NumberInput(
                    "aprs_igate_gain",
                    "Antenna gain",
                    append="dBi",
                    converter=OptionalConverter(),
                ),
                DropdownInput("aprs_igate_dir", "Antenna direction", AprsAntennaDirections),
            ),
            Section(
                "PSKReporter settings",
                CheckboxInput(
                    "pskreporter_enabled",
                    "Enable sending spots to pskreporter.info",
                ),
                TextInput(
                    "pskreporter_callsign",
                    "pskreporter callsign",
                    infotext="This callsign will be used to send spots to pskreporter.info",
                ),
                TextInput(
                    "pskreporter_antenna_information",
                    "Antenna information",
                    infotext="Antenna description to be sent along with spots to pskreporter",
                    converter=OptionalConverter(),
                ),
                TextInput(
                    "pskreporter_rig_information",
                    "Rig information",
                    infotext="SDR description to be sent along with spots to pskreporter",
                    converter=OptionalConverter(),
                ),
            ),
            Section(
                "WSPRnet settings",
                CheckboxInput(
                    "wsprnet_enabled",
                    "Enable sending spots to wsprnet.org",
                ),
                TextInput(
                    "wsprnet_callsign",
                    "wsprnet callsign",
                    infotext="This callsign will be used to send spots to wsprnet.org",
                ),
            ),
            Section(
                "MQTT settings",
                CheckboxInput(
                    "mqtt_enabled",
                    "Enable publishing reports to MQTT",
                ),
                CheckboxInput(
                    "report_clients",
                    "Report clients connecting to the server (disable for public MQTT brokers!)",
                ),
                CheckboxInput(
                    "report_radio",
                    "Report server startup and SDR profile changes (disable for public MQTT brokers!)",
                ),
                TextInput(
                    "mqtt_host",
                    "Broker address",
                    infotext="Address of the MQTT broker to send reports to (address[:port])",
                    validator=AddressAndOptionalPortValidator(),
                ),
                TextInput(
                    "mqtt_client_id",
                    "Client ID",
                    converter=OptionalConverter(),
                ),
                TextInput(
                    "mqtt_user",
                    "Username",
                    converter=OptionalConverter(),
                ),
                PasswordInput(
                    "mqtt_password",
                    "Password",
                    converter=OptionalConverter(),
                ),
                CheckboxInput(
                    "mqtt_use_ssl",
                    "Use SSL",
                ),
                TextInput(
                    "mqtt_topic",
                    "MQTT topic",
                    infotext="MQTT topic to publish reports to (default: openwebrx)",
                    converter=OptionalConverter(),
                ),
                CheckboxInput(
                    "mqtt_chat",
                    "Receive chat messages over MQTT",
                ),
                CheckboxInput(
                    "mqtt_aircraft",
                    "Receive aircraft data over MQTT",
                ),
                CheckboxInput(
                    "mqtt_ais",
                    "Receive marine data over MQTT",
                ),
                CheckboxInput(
                    "mqtt_aprs",
                    "Receive APRS reports over MQTT",
                ),
                CheckboxInput(
                    "mqtt_wsjt",
                    "Receive WSJT decodes over MQTT",
                ),
                CheckboxInput(
                    "mqtt_sonde",
                    "Receive radiosonde reports over MQTT",
                ),
            ),
            Section(
                "RigControl settings",
                CheckboxInput(
                    "rig_enabled",
                    "Enable sending changes to a standalone transceiver",
                ),
                DropdownInput(
                    "rig_model",
                    "Transceiver model",
                    options=[Option(str(RigControl.RIGS[x]), x) for x in RigControl.RIGS.keys()],
                    converter=IntConverter(),
                ),
                TextInput(
                    "rig_device",
                    "Transceiver CAT device",
                    infotext="Device or IP address:port used to control transceiver",
                ),
                NumberInput(
                    "rig_address",
                    "Transceiver CI-V address",
                    infotext="Optional transceiver CI-V address (used by Icom)",
                ),
            )
        ]
