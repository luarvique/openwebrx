"""Authenticated map configuration, separate from receiver/general settings."""
import html
import json

from owrx.breadcrumb import BreadcrumbItem
from owrx.controllers.settings import SettingsBreadcrumb, SettingsFormController
from owrx.form.error import FormError
from owrx.form.input import (CheckboxInput, DropdownInput, FloatInput, Input,
                             MultiCheckboxInput, NumberInput, Option, TextInput)
from owrx.form.input.validator import RangeValidator
from owrx.form.section import Section
from owrx.mapconfig import BASEMAP_NAMES, WEATHER_LAYERS, defaults, validate_layers, validate_settings


class MapLayersInput(Input):
    def render_input(self, value, errors):
        # Never interpolate a URL, layer name or JSON directly into HTML/JS.
        encoded = html.escape(json.dumps(value if isinstance(value, list) else [], ensure_ascii=True))
        return ('<div id="map-layer-editor"></div>'
                '<details id="map-layer-json"><summary>Advanced: layer JSON</summary>'
                '<textarea class="form-control" id="map_layers" name="map_layers" '
                'rows="12" aria-label="Custom map layers JSON">' + encoded + '</textarea></details>')

    def parse(self, data):
        if self.id not in data:
            return {}
        text = data[self.id][0]
        if len(text) > 300000:
            raise FormError(self.id, "Custom layer configuration is too large.")
        try:
            return {self.id: json.loads(text)}
        except (ValueError, RecursionError):
            raise FormError(self.id, "Custom layers must contain valid JSON.") from None

    def validate(self, data):
        if self.id in data:
            try:
                validate_layers(data[self.id])
            except ValueError as error:
                raise FormError(self.id, html.escape(str(error))) from None


class MapSettingsController(SettingsFormController):
    def getTitle(self):
        return "Map Settings"

    def get_breadcrumb(self):
        return SettingsBreadcrumb().append(BreadcrumbItem("Map Settings", "settings/map"))

    def buildRenderData(self):
        data = super().buildRenderData()
        return dict(defaults(data), **data)

    def getSections(self):
        data = self.buildRenderData()
        base_options = [Option("none", "None (markers without a basemap)")]
        base_options += [Option("builtin-" + str(i), name) for i, name in enumerate(BASEMAP_NAMES)]
        custom = data.get("map_layers", [])
        if isinstance(custom, list):
            for layer in custom:
                if isinstance(layer, dict) and isinstance(layer.get("id"), str) and isinstance(layer.get("name"), str):
                    base_options.append(Option(html.escape(layer["id"]), html.escape(layer["name"])))
        return [
            Section("Map client",
                CheckboxInput("map_enabled", "Enable the web map client"),
                DropdownInput("map_type", "Default map engine", options=[
                    Option("leaflet", "OpenStreetMap, etc. (Leaflet)"), Option("google", "Google Maps")],
                    infotext="The engine is not the basemap. Custom GIS layers and the free weather catalog use Leaflet."),
                CheckboxInput("map_allow_google", "Allow the optional Google Maps client"),
                TextInput("google_maps_api_key", "Google Maps API key",
                    infotext="Google requires a browser API key. Restrict it to your receiver domain. "
                    "Disabling Google preserves the key but uses Leaflet instead."),
                CheckboxInput("map_show_receiver", "Show the receiver location marker"),
                CheckboxInput("map_night", "Show the day/night overlay")),
            Section("Starting view",
                CheckboxInput("map_use_initial_view", "Use a custom starting coordinate and zoom",
                    infotext="Unchecked: center on the receiver at zoom 5. This does not change receiver coordinates "
                    "or GPS settings in General settings. Callsign/locator links can still recenter the map."),
                FloatInput("map_initial_lat", "Starting latitude", validator=RangeValidator(-85.05112878, 85.05112878)),
                FloatInput("map_initial_lon", "Starting longitude", validator=RangeValidator(-180, 180)),
                NumberInput("map_initial_zoom", "Starting zoom", validator=RangeValidator(0, 22))),
            Section("Basemaps (Leaflet)",
                MultiCheckboxInput("map_basemaps", "Available built-in basemaps",
                    options=[Option("builtin-" + str(i), name) for i, name in enumerate(BASEMAP_NAMES)],
                    infotext="Uncheck providers to remove them from the client. Provider terms still apply; "
                    "Stadia requires registration. No basemap is also supported."),
                DropdownInput("map_default_basemap", "Default basemap", options=base_options,
                    infotext="Select an enabled built-in or custom basemap. Browser choices are remembered until map settings change.")),
            Section("Weather and other overlays (Leaflet)",
                MultiCheckboxInput("map_weather_layers", "Free weather layers", options=[
                    Option(layer["id"], layer["name"]) for layer in WEATHER_LAYERS],
                    infotext="No API key or subscription. These checkboxes make layers available; visitors turn them on "
                    "in the map. Latest-available data can be delayed or unavailable. Visible imagery is daylight-only. "
                    "Not for navigation or safety-critical decisions."),
                CheckboxInput("map_openweather", "Offer optional OpenWeatherMap layers"),
                TextInput("openweathermap_api_key", "OpenWeatherMap API key",
                    infotext="Optional, separate from the free layers above. Existing provider terms apply."),
                CheckboxInput("map_seamarks", "Offer OpenSeaMap seamarks"),
                CheckboxInput("map_maidenhead", "Offer the Maidenhead locator grid")),
            Section("Custom GIS layers (Leaflet)",
                MapLayersInput("map_layers", "Additional layers",
                    infotext="Add public ArcGIS, WMS, WMTS, WFS, XYZ, GeoJSON or WPS layers. "
                    "URLs and attribution are public to every visitor: do not include credentials. "
                    "Services must permit browser access (CORS for vector data) and HTTPS on an HTTPS receiver. "
                    "WPS is processing, not imagery: only synchronous WPS 1.0 GeoJSON output is supported, "
                    "and execution is manual. Apply and save, then reload open map pages.")),
            Section("Position reports and calls",
                NumberInput("map_position_retention_time", "Map retention time", append="s",
                    infotext="How long markers and grids remain visible."),
                NumberInput("map_call_retention_time", "Call retention time", append="s",
                    validator=RangeValidator(15, 3600)),
                NumberInput("map_max_calls", "Number of calls shown", validator=RangeValidator(0, 50)),
                CheckboxInput("map_ignore_indirect_reports", "Ignore position reports arriving via indirect path."),
                CheckboxInput("map_prefer_recent_reports", "Prefer more recent position reports to shorter path reports.")),
        ]

    def render_sections(self):
        return ('<link rel="stylesheet" href="../static/css/map-settings.css">' + super().render_sections()
                + '<script src="../static/lib/settings/MapSettings.js"></script>')

    def processData(self, data):
        merged = self.buildRenderData()
        merged.update(data)
        data["map_layers"] = validate_settings(merged)
        if merged.get("map_type") not in ("leaflet", "google"):
            raise ValueError("Choose a supported map engine.")
        if merged["map_allow_google"] and not merged.get("google_maps_api_key", "").strip():
            raise ValueError("Google Maps requires a key. Uncheck Allow Google to use Leaflet without a key.")
        if merged["map_openweather"] and not merged.get("openweathermap_api_key", "").strip():
            raise ValueError("OpenWeatherMap requires a key. The free weather layers do not.")
        if not merged["map_allow_google"]:
            data["map_type"] = "leaflet"
        super().processData(data)
