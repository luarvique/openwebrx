from owrx.controllers.settings import SettingsFormController, SettingsBreadcrumb
from owrx.form.section import Section
from owrx.form.input import CheckboxInput, NumberInput, DropdownInput, Js8ProfileCheckboxInput, MultiCheckboxInput, Option, TextInput
from owrx.form.input.wfm import WfmTauValues
from owrx.form.input.wsjt import Q65ModeMatrix, WsjtDecodingDepthsInput
from owrx.form.input.converter import OptionalConverter
from owrx.form.input.validator import RangeValidator
from owrx.wsjt import Fst4Profile, Fst4wProfile
from owrx.breadcrumb import Breadcrumb, BreadcrumbItem


class DecodingSettingsController(SettingsFormController):
    def getTitle(self):
        return "Demodulation and decoding"

    def get_breadcrumb(self) -> Breadcrumb:
        return SettingsBreadcrumb().append(BreadcrumbItem("Demodulation and decoding", "settings/decoding"))

    def getSections(self):
        return [
            Section(
                "Miscellaneous",
                NumberInput(
                    "squelch_auto_margin",
                    "Auto-Squelch threshold",
                    infotext="Offset to be added to the current signal level when using the auto-squelch",
                    append="dB",
                ),
                NumberInput(
                    "digimodes_fft_size",
                    "Secondary FFT size",
                    infotext="Secondary waterfall resolution in digital modes",
                    append="bins"
                ),
                DropdownInput(
                    "wfm_deemphasis_tau",
                    "Tau setting for WFM (broadcast FM) deemphasis",
                    WfmTauValues,
                    infotext='See <a href="https://en.wikipedia.org/wiki/FM_broadcasting#Pre-emphasis_and_de-emphasis"'
                    + ' target="_blank">this Wikipedia article</a> for more information',
                ),
                CheckboxInput(
                    "wfm_rds_rbds",
                    "Decode USA-specific RBDS information from WFM broadcasts",
                ),
                CheckboxInput(
                    "cw_showcw",
                    "Show CW codes (dits / dahs) when decoding CW",
                ),
                CheckboxInput(
                    "dsc_show_errors",
                    "Show partial messages when decoding DSC",
                ),
            ),
            Section(
                "Digital voice",
                TextInput(
                    "digital_voice_codecserver",
                    "Codecserver address",
                    infotext="Address of a remote codecserver instance (name[:port]). Leave empty to use local"
                    + " codecserver",
                    converter=OptionalConverter(),
                ),
                CheckboxInput(
                    "digital_voice_dmr_id_lookup",
                    'Enable lookup of DMR ids in the <a href="https://www.radioid.net/" target="_blank">'
                    + "radioid</a> database to show callsigns and names",
                ),
                CheckboxInput(
                    "digital_voice_nxdn_id_lookup",
                    'Enable lookup of NXDN ids in the <a href="https://www.radioid.net/" target="_blank">'
                    + "radioid</a> database to show callsigns and names",
                ),
            ),
            Section(
                "Aircraft messages",
                NumberInput(
                    "adsb_ttl",
                    "ADSB reports expiration time",
                    validator=RangeValidator(30, 100000),
                    append="s",
                ),
                NumberInput(
                    "vdl2_ttl",
                    "VDL2 reports expiration time",
                    validator=RangeValidator(30, 100000),
                    append="s",
                ),
                NumberInput(
                    "hfdl_ttl",
                    "HFDL reports expiration time",
                    validator=RangeValidator(30, 100000),
                    append="s",
                ),
                NumberInput(
                    "acars_ttl",
                    "ACARS reports expiration time",
                    validator=RangeValidator(30, 100000),
                    append="s",
                ),
            ),
            Section(
                "Paging messages",
                DropdownInput(
                    "paging_charset",
                    "Message character set",
                    options=[
                        Option("US", "English (USA)"),
                        Option("FR", "French"),
                        Option("DE", "German"),
                        Option("SE", "Swedish"),
                        Option("SI", "Slovenian"),
                    ],
                ),
                CheckboxInput(
                    "paging_filter",
                    "Filter out empty, numeric, or unreadable pager messages",
                ),
            ),
            Section(
                "Fax transmissions",
                NumberInput(
                    "fax_lpm",
                    "Transmission speed",
                    validator=RangeValidator(30, 480),
                    append="lpm",
                ),
                NumberInput(
                    "fax_min_length",
                    "Minimum page length",
                    validator=RangeValidator(50, 450),
                    append="lines",
                ),
                NumberInput(
                    "fax_max_length",
                    "Maximum page length",
                    validator=RangeValidator(500, 3000),
                    append="lines",
                ),
                CheckboxInput("fax_postprocess", "Post-process received images to reduce noise"),
                CheckboxInput("fax_color", "Receive color images"),
                CheckboxInput("fax_am", "Use amplitude modulation"),
            ),
            Section(
                "WSJT decoders",
                NumberInput("decoding_queue_workers", "Number of decoding workers"),
                NumberInput("decoding_queue_length", "Maximum length of decoding job queue"),
                NumberInput(
                    "wsjt_decoding_depth",
                    "Default WSJT decoding depth",
                    infotext="A higher decoding depth will allow more results, but will also consume more cpu",
                ),
                WsjtDecodingDepthsInput(
                    "wsjt_decoding_depths",
                    "Individual decoding depths",
                ),
                NumberInput(
                    "js8_decoding_depth",
                    "Js8Call decoding depth",
                    infotext="A higher decoding depth will allow more results, but will also consume more cpu",
                ),
                Js8ProfileCheckboxInput("js8_enabled_profiles", "Js8Call enabled modes"),
                MultiCheckboxInput(
                    "fst4_enabled_intervals",
                    "Enabled FST4 intervals",
                    [Option(v, "{}s".format(v)) for v in Fst4Profile.availableIntervals],
                ),
                MultiCheckboxInput(
                    "fst4w_enabled_intervals",
                    "Enabled FST4W intervals",
                    [Option(v, "{}s".format(v)) for v in Fst4wProfile.availableIntervals],
                ),
                Q65ModeMatrix("q65_enabled_combinations", "Enabled Q65 Mode combinations"),
            ),
        ]
