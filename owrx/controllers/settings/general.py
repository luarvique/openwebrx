from owrx.controllers.settings import SettingsFormController
from owrx.form.section import Section
from owrx.config.core import CoreConfig
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
from owrx.form.input.converter import WaterfallColorsConverter, IntConverter
from owrx.form.input.receiverid import ReceiverKeysInput
from owrx.form.input.gfx import AvatarInput, TopPhotoInput
from owrx.form.input.device import WaterfallLevelsInput, WaterfallAutoLevelsInput
from owrx.form.input.location import LocationInput
from owrx.waterfall import WaterfallOptions
from owrx.breadcrumb import Breadcrumb, BreadcrumbItem
from owrx.controllers.settings import SettingsBreadcrumb
import shutil
import os
import re
from glob import glob

import logging

logger = logging.getLogger(__name__)


class GeneralSettingsController(SettingsFormController):
    def getTitle(self):
        return "General Settings"

    def get_breadcrumb(self) -> Breadcrumb:
        return SettingsBreadcrumb().append(BreadcrumbItem("General Settings", "settings/general"))

    def getSections(self):
        return [
            Section(
                "Receiver information",
                TextInput("receiver_name", "Receiver name"),
                TextInput("receiver_location", "Receiver location"),
                NumberInput(
                    "receiver_asl",
                    "Receiver elevation",
                    append="meters above mean sea level",
                ),
                TextInput("receiver_admin", "Receiver admin"),
                DropdownInput(
                    "bandplan_region",
                    "Receiver band plan",
                    options=[
                        Option("0", "Default (generalized for all regions)"),
                        Option("1", "ITU Region 1 (Africa, Europe, Middle East, North Asia)"),
                        Option("2", "ITU Region 2 (North America, South America)"),
                        Option("3", "ITU Region 3 (South Asia, Pacific)"),
                    ],
                    converter=IntConverter(),
                ),
                LocationInput("receiver_gps", "Receiver coordinates"),
                CheckboxInput(
                    "gps_updates",
                    "Update receiver coordinates via GPS (if device present)",
                ),
                TextInput("photo_title", "Photo title"),
                TextAreaInput("photo_desc", "Photo description", infotext="HTML supported "),
            ),
            Section(
                "Receiver images",
                AvatarInput(
                    "receiver_avatar",
                    "Receiver Avatar",
                    infotext="Maximum file size is 256kB. For performance reasons, images are cached. "
                    + "It can take a few hours until they appear on the site.",
                ),
                TopPhotoInput(
                    "receiver_top_photo",
                    "Receiver Panorama",
                    infotext="Maximum file size is 2MB. For performance reasons, images are cached. "
                    + "It can take a few hours until they appear on the site.",
                ),
            ),
            Section(
                "Receiver limits",
                NumberInput(
                    "max_clients",
                    "Maximum number of clients",
                    infotext="Number of people who can connect at the same time.",
                ),
                NumberInput(
                    "max_clients_per_ip",
                    "Number of clients per IP",
                    infotext="Number of people who can connect from the same IP address.",
                ),
                NumberInput(
                    "keep_files",
                    "Maximum number of files",
                    infotext="Number of received images and other files to keep.",
                ),
                NumberInput(
                    "session_timeout",
                    "Session timeout",
                    infotext="Client session timeout in seconds (0 to disable timeout).",
                    append="s",
                ),
                TextInput(
                    "usage_policy_url",
                    "Usage policy URL",
                    infotext="Specifies web page describing receiver usage policy "
                    + "and shown when a client session times out.",
                ),
                CheckboxInput(
                    "allow_chat",
                    "Allow users to chat with each other",
                ),
                CheckboxInput(
                    "allow_audio_recording",
                    "Allow users to record received audio",
                ),
                CheckboxInput(
                    "allow_center_freq_changes",
                    "Allow users to change center frequency",
                ),
                TextInput(
                    "magic_key",
                    "Magic key",
                    infotext="Enter a key the user has to supply to change center frequency."
                    + " Leave empty if you do not want to protect frequency changes with a key."
                    + " When enabled, the key has to be added to receiver's URL after the hash"
                    + " sign: http://my.receiver.com/#key=keyvalue.",
                ),
            ),
            Section(
                "Receiver listings",
                ReceiverKeysInput(
                    "receiver_keys",
                    "Receiver keys",
                ),
            ),
            Section(
                "Waterfall settings",
                DropdownInput(
                    "waterfall_scheme",
                    "Waterfall color theme",
                    options=WaterfallOptions,
                ),
                TextAreaInput(
                    "waterfall_colors",
                    "Custom waterfall colors",
                    infotext="Please provide 6-digit hexadecimal RGB colors in HTML notation (#RRGGBB)"
                    + " or HEX notation (0xRRGGBB), one per line",
                    converter=WaterfallColorsConverter(),
                ),
                NumberInput(
                    "fft_fps",
                    "FFT speed",
                    infotext="This setting specifies how many lines are being added to the waterfall per second. "
                    + "Higher values will give you a faster waterfall, but will also use more CPU.",
                    append="frames per second",
                ),
                NumberInput("fft_size", "FFT size", append="bins"),
                FloatInput(
                    "fft_voverlap_factor",
                    "FFT vertical overlap factor",
                    infotext="If fft_voverlap_factor is above 0, multiple FFTs will be used for creating a line on the "
                    + "diagram.",
                    validator=RangeValidator(0.0, 0.9),
                ),
                WaterfallLevelsInput("waterfall_levels", "Waterfall levels"),
                WaterfallAutoLevelsInput(
                    "waterfall_auto_levels",
                    "Automatic adjustment margins",
                    infotext="Specifies the upper and lower dynamic headroom that should be added when automatically "
                    + "adjusting waterfall colors",
                ),
                CheckboxInput(
                    "waterfall_auto_level_default_mode",
                    "Automatically adjust waterfall level by default",
                    infotext="Enable this to automatically enable auto adjusting waterfall levels on page load.",
                ),
                NumberInput(
                    "waterfall_auto_min_range",
                    "Automatic adjustment minimum range",
                    append="dB",
                    infotext="Minimum dynamic range the waterfall should cover after automatically adjusting "
                    + "waterfall colors",
                ),
            ),
            Section(
                "Compression",
                DropdownInput(
                    "audio_compression",
                    "Audio compression",
                    options=[
                        Option("adpcm", "ADPCM"),
                        Option("none", "None"),
                    ],
                ),
                DropdownInput(
                    "fft_compression",
                    "Waterfall compression",
                    options=[
                        Option("adpcm", "ADPCM"),
                        Option("none", "None"),
                    ],
                ),
            ),
            Section(
                "Display settings",
                DropdownInput(
                    "ui_theme",
                    "User interface color theme",
                    options=[
                        Option("default", "Gray"),
                        Option("brown", "Brown"),
                        Option("red", "Red"),
                        Option("green", "Green"),
                        Option("khaki", "Khaki"),
                        Option("blue", "Blue"),
                        Option("navy", "Navy"),
                        Option("black", "Black"),
                        Option("night", "Night")
                    ]
                ),
                DropdownInput(
                    "tuning_precision",
                    "Tuning precision",
                    options=[Option(str(i), "{} Hz".format(10 ** i)) for i in range(0, 6)],
                    converter=IntConverter(),
                ),
                NumberInput(
                    "eibi_bookmarks_range",
                    "Shortwave bookmarks range",
                    infotext="Specifies the distance from the receiver location to "
                    + "search EIBI schedules for stations when creating automatic "
                    + "bookmarks. Set to 0 to disable automatic EIBI bookmarks.",
                    validator=RangeValidator(0, 25000),
                    append="km",
                ),
                NumberInput(
                    "repeater_range",
                    "Repeater bookmarks range",
                    infotext="Specifies the distance from the receiver location to "
                    + "search RepeaterBook.com for repeaters when creating automatic "
                    + "bookmarks. Set to 0 to disable automatic repeater bookmarks.",
                    validator=RangeValidator(0, 200),
                    append="km",
                ),
            ),
            Section(
                "Map settings",
                DropdownInput(
                    "map_type",
                    "Map type",
                    options=[
                        Option("google", "Google Maps"),
                        Option("leaflet", "OpenStreetMap, etc."),
                    ],
                ),
                TextInput(
                    "google_maps_api_key",
                    "Google Maps API key",
                    infotext="Google Maps requires an API key, check out "
                    + '<a href="https://developers.google.com/maps/documentation/embed/get-api-key" target="_blank">'
                    + "their documentation</a> on how to obtain one.",
                ),
                TextInput(
                    "openweathermap_api_key",
                    "OpenWeatherMap API key",
                    infotext="OpenWeatherMap requires an API key, check out "
                    + '<a href="https://openweathermap.org/appid" target="_blank">'
                    + "their documentation</a> on how to obtain one.",
                ),
                NumberInput(
                    "map_position_retention_time",
                    "Map retention time",
                    infotext="Specifies how long markers / grids will remain visible on the map.",
                    append="s",
                ),
                NumberInput(
                    "map_call_retention_time",
                    "Call retention time",
                    infotext="Specifies how long calls will remain visible on the map.",
                    validator=RangeValidator(15, 60*60),
                    append="s",
                ),
                NumberInput(
                    "map_max_calls",
                    "Number of calls shown",
                    infotext="Specifies how many calls between grids are visible on the map.",
                    validator=RangeValidator(0, 50),
                ),
                CheckboxInput(
                    "map_ignore_indirect_reports",
                    "Ignore position reports arriving via indirect path.",
                ),
                CheckboxInput(
                    "map_prefer_recent_reports",
                    "Prefer more recent position reports to shorter path reports.",
                ),
            ),
            Section(
                "External links",
                TextInput(
                    "callsign_url",
                    "Callsign database URL",
                    infotext="Specifies callsign lookup URL, such as QRZ.COM "
                    + "or QRZCQ.COM. Place curly brackets ({}) where callsign "
                    + "is supposed to be.",
                ),
                TextInput(
                    "vessel_url",
                    "Vessel database URL",
                    infotext="Specifies vessel lookup URL, such as VESSELFINDER.COM, "
                    + "allowing to look up vessel information by its AIS MMSI number. "
                    + "Place curly brackets ({}) where MMSI is supposed to be.",
                ),
                TextInput(
                    "flight_url",
                    "Flight database URL",
                    infotext="Specifies flight lookup URL, such as FLIGHTAWARE.COM, "
                    + "allowing to look up flights and aircraft. Place curly brackets "
                    + "({}) where flight or aircraft identifier is supposed to be.",
                ),
                TextInput(
                    "modes_url",
                    "Aircraft database URL",
                    infotext="Specifies aircraft lookup URL, such as PLANESPOTTERS.NET, "
                    + "allowing to look up aircraft by their Mode-S codes. Place curly "
                    + "brackets ({}) where aircraft Mode-S code is supposed to be.",
                ),
            ),
        ]

    def remove_existing_image(self, image_id):
        config = CoreConfig()
        # remove all possible file extensions
        for ext in ["png", "jpg", "webp"]:
            try:
                os.unlink("{}/{}.{}".format(config.get_data_directory(), image_id, ext))
            except FileNotFoundError:
                pass

    def handle_image(self, data, image_id):
        if image_id in data:
            config = CoreConfig()
            if data[image_id] == "restore":
                self.remove_existing_image(image_id)
            elif data[image_id]:
                if not data[image_id].startswith(image_id):
                    logger.warning("invalid file name: %s", data[image_id])
                else:
                    # get file extension (at least 3 characters)
                    # should be all lowercase since they are set by the upload script
                    pattern = re.compile(".*\\.([a-z]{3,})$")
                    matches = pattern.match(data[image_id])
                    if matches is None:
                        logger.warning("could not determine file extension for %s", image_id)
                    else:
                        self.remove_existing_image(image_id)
                        ext = matches.group(1)
                        data_file = "{}/{}.{}".format(config.get_data_directory(), image_id, ext)
                        temporary_file = "{}/{}".format(config.get_temporary_directory(), data[image_id])
                        shutil.copy(temporary_file, data_file)
            del data[image_id]
            # remove any accumulated temporary files on save
            for file in glob("{}/{}*".format(config.get_temporary_directory(), image_id)):
                os.unlink(file)

    def processData(self, data):
        # Image handling
        for img in ["receiver_avatar", "receiver_top_photo"]:
            self.handle_image(data, img)
        # special handling for waterfall colors: custom colors only stay in config if custom color scheme is selected
        if "waterfall_scheme" in data:
            scheme = WaterfallOptions(data["waterfall_scheme"])
            if scheme is not WaterfallOptions.CUSTOM and "waterfall_colors" in data:
                data["waterfall_colors"] = None
        super().processData(data)
