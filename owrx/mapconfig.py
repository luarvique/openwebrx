"""Public map-client configuration. Validation is deliberately network-free.

Custom service URLs are delivered to every map visitor; this is not a credential
store or an HTTP proxy. Existing installations acquire defaults without a config
migration or changes to receiver_gps.
"""
import copy
import hashlib
import json
import math
import re
from urllib.parse import parse_qsl, urlsplit

BASEMAP_NAMES = (
    "OpenStreetMap", "OpenTopoMap", "Esri WorldTopo", "Esri WorldStreet",
    "Esri WorldImagery", "Esri NatGeoWorld", "Esri WorldGray",
    "CartoDB Positron", "CartoDB DarkMatter", "CartoDB Voyager",
    "Stadia Alidade (registration required)", "Stadia AlidadeDark (registration required)",
)

# Public, anonymous services. These are latest-available observations, not a
# guarantee of instantaneous data. Provider documentation is in docs/MAP_CLIENT.md.
WEATHER_LAYERS = (
    dict(id="iem-radar", name="IEM NEXRAD radar (USA)", type="xyz",
         url="https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/nexrad-n0q-900913/{z}/{x}/{y}.png",
         attribution="Iowa Environmental Mesonet / NOAA", refresh=300, max_zoom=12),
    dict(id="nws-alerts", name="NOAA watches, warnings and advisories (USA)", type="arcgis-map",
         url="https://mapservices.weather.noaa.gov/eventdriven/rest/services/WWA/watch_warn_adv/MapServer",
         layers="0,1", attribution="NOAA / National Weather Service", refresh=300),
    dict(id="iem-rain", name="IEM MRMS precipitation, past hour (USA)", type="wms",
         url="https://mesonet.agron.iastate.edu/cgi-bin/wms/us/mrms_nn.cgi",
         layers="mrms_p1h", attribution="Iowa Environmental Mesonet / NOAA", refresh=300),
    dict(id="goes-east-ir", name="GOES East infrared (Americas / Atlantic)", type="wms",
         url="https://mesonet.agron.iastate.edu/cgi-bin/wms/goes_east.cgi",
         layers="fulldisk_ch13", attribution="NOAA GOES / Iowa Environmental Mesonet", refresh=600),
    dict(id="goes-west-ir", name="GOES West infrared (Americas / Pacific)", type="wms",
         url="https://mesonet.agron.iastate.edu/cgi-bin/wms/goes_west.cgi",
         layers="fulldisk_ch13", attribution="NOAA GOES / Iowa Environmental Mesonet", refresh=600),
    dict(id="goes-east-vis", name="GOES East visible (daylight only)", type="wms",
         url="https://mesonet.agron.iastate.edu/cgi-bin/wms/goes_east.cgi",
         layers="fulldisk_ch02", attribution="NOAA GOES / Iowa Environmental Mesonet", refresh=600),
    dict(id="goes-west-vis", name="GOES West visible (daylight only)", type="wms",
         url="https://mesonet.agron.iastate.edu/cgi-bin/wms/goes_west.cgi",
         layers="fulldisk_ch02", attribution="NOAA GOES / Iowa Environmental Mesonet", refresh=600),
)
LAYER_TYPES = ("xyz", "arcgis-map", "arcgis-feature", "wms", "wmts", "wfs", "geojson", "wps")
BOOL_FIELDS = ("enabled", "basemap", "visible", "tms")
TEXT_LIMITS = {
    "id": 80, "name": 120, "type": 30, "url": 4096, "layers": 512,
    "attribution": 1000, "version": 20, "format": 80, "style": 256,
    "matrix_set": 120, "matrix_prefix": 120, "wps_inputs": 2048, "wps_output": 120,
}
NUMBER_LIMITS = {
    "opacity": (0, 1, 0.7), "refresh": (0, 86400, 0),
    "max_features": (1, 10000, 2000), "max_zoom": (0, 22, 19),
}


def value(config, key, default=None):
    return config[key] if key in config else default


def defaults(config):
    gps = value(config, "receiver_gps", {})
    def coordinate(key, limit):
        # Saved nested dictionaries are PropertyLayer objects after a restart.
        try:
            v = value(gps, key, 0)
        except (TypeError, AttributeError):
            v = 0
        return max(-limit, min(limit, v)) if type(v) in (int, float) and math.isfinite(v) else 0
    return {
        "map_enabled": True,
        "map_allow_google": bool(value(config, "google_maps_api_key", "")),
        "map_use_initial_view": False,
        "map_initial_lat": coordinate("lat", 85.05112878), "map_initial_lon": coordinate("lon", 180),
        "map_initial_zoom": 5, "map_show_receiver": True, "map_night": True,
        "map_basemaps": ["builtin-" + str(i) for i in range(len(BASEMAP_NAMES))],
        "map_default_basemap": "builtin-0", "map_layers": [],
        "map_weather_layers": [layer["id"] for layer in WEATHER_LAYERS],
        "map_openweather": bool(value(config, "openweathermap_api_key", "")),
        "map_seamarks": True, "map_maidenhead": True,
    }


def settings(config):
    result = defaults(config)
    result.update({key: config[key] for key in result if key in config})
    return copy.deepcopy(result)


def validate_url(url):
    if not isinstance(url, str) or not url or len(url) > 4096:
        raise ValueError("Supply an HTTP or HTTPS service URL (maximum 4096 characters).")
    if any(c.isspace() or ord(c) < 33 for c in url) or "\\" in url:
        raise ValueError("Service URLs must not contain whitespace, control characters or backslashes.")
    try:
        parts = urlsplit(url)
        _ = parts.port  # Also validates malformed port numbers.
    except ValueError:
        raise ValueError("Invalid service URL.") from None
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.fragment:
        raise ValueError("Use an absolute HTTP(S) service URL without a fragment.")
    if parts.username is not None or parts.password is not None:
        raise ValueError("Service URLs are public: embedded usernames and passwords are not allowed.")
    secret_names = {"token", "access_token", "api_key", "apikey", "key", "password", "signature"}
    if any(k.lower() in secret_names for k, _ in parse_qsl(parts.query, keep_blank_values=True)):
        raise ValueError("Use an anonymous service URL without credentials or API keys.")
    return url


def validate_layers(layers):
    """Return normalized, allowlisted layer definitions; never perform a request."""
    if not isinstance(layers, list) or len(layers) > 50:
        raise ValueError("Custom layers must be a list containing at most 50 entries.")
    result, identifiers = [], set()
    allowed = set(TEXT_LIMITS) | set(NUMBER_LIMITS) | set(BOOL_FIELDS)
    for index, raw in enumerate(layers, 1):
        try:
            if not isinstance(raw, dict) or set(raw) - allowed:
                raise ValueError("A layer contains unknown fields or is not an object.")
            layer = {}
            for key, limit in TEXT_LIMITS.items():
                text = raw.get(key, "")
                if not isinstance(text, str) or len(text) > limit or any(ord(c) < 32 for c in text):
                    raise ValueError("Invalid or overlong " + key + ".")
                layer[key] = text.strip()
            if not re.fullmatch(r"custom-[A-Za-z0-9_-]{1,72}", layer["id"]):
                raise ValueError("Layer IDs must start with custom- and contain letters, digits, - or _.")
            if layer["id"] in identifiers:
                raise ValueError("Layer IDs must be unique.")
            identifiers.add(layer["id"])
            if not layer["name"] or layer["type"] not in LAYER_TYPES:
                raise ValueError("Supply a name and a supported layer type.")
            validate_url(layer["url"])
            for key in BOOL_FIELDS:
                flag = raw.get(key, key == "enabled")
                if type(flag) is not bool:
                    raise ValueError(key + " must be a checkbox value.")
                layer[key] = flag
            for key, (low, high, default) in NUMBER_LIMITS.items():
                number = raw.get(key, default)
                if type(number) not in (int, float) or not math.isfinite(number) or not low <= number <= high:
                    raise ValueError(key + " is outside its allowed range.")
                if key != "opacity" and int(number) != number:
                    raise ValueError(key + " must be a whole number.")
                layer[key] = number
            if 0 < layer["refresh"] < 60:
                raise ValueError("Refresh must be disabled (0), or at least 60 seconds.")
            kind = layer["type"]
            path = urlsplit(layer["url"]).path.rstrip("/")
            if kind == "arcgis-map" and not re.search(r"/MapServer(?:/\d+)?$", path, re.I):
                raise ValueError("ArcGIS map URLs must end with /MapServer or /MapServer/<layer ID>.")
            if kind == "arcgis-feature" and not re.search(r"/(?:FeatureServer|MapServer)(?:/\d+)?$", path, re.I):
                raise ValueError("ArcGIS feature URLs must end with /FeatureServer, /MapServer or a numeric sublayer.")
            if kind.startswith("arcgis-") and layer["layers"] and not re.fullmatch(r"\d+(?:,\d+){0,9}", layer["layers"]):
                raise ValueError("ArcGIS layer IDs must be comma-separated integers (at most 10).")
            if kind in ("wms", "wmts", "wfs", "wps") and not layer["layers"]:
                raise ValueError("Supply the service layer/type name, or the WPS process identifier.")
            versions = {"wms": ("1.1.1", "1.3.0"), "wfs": ("1.0.0", "1.1.0", "2.0.0"),
                        "wmts": ("1.0.0",), "wps": ("1.0.0",)}
            if kind in versions:
                layer["version"] = layer["version"] or versions[kind][0]
                if layer["version"] not in versions[kind]:
                    raise ValueError("Unsupported service version for " + kind + ".")
            if kind == "wmts" and not layer["matrix_set"]:
                raise ValueError("Supply a Web Mercator, XYZ-compatible WMTS tile matrix set.")
            if kind == "xyz":
                if not all("{" + key + "}" in layer["url"] for key in ("z", "x", "y")):
                    raise ValueError("XYZ templates must include {z}, {x} and {y}.")
                if set(re.findall(r"\{([^}]+)\}", layer["url"])) - {"z", "x", "y", "s", "r"}:
                    raise ValueError("Unsupported XYZ template placeholder.")
            if kind in ("wms", "wmts"):
                layer["format"] = layer["format"] or "image/png"
                if layer["format"] not in ("image/png", "image/jpeg"):
                    raise ValueError("Raster services must return image/png or image/jpeg.")
            if kind in ("wfs", "wps"):
                layer["format"] = layer["format"] or "application/json"
                if layer["format"] not in ("application/json", "application/geo+json", "json"):
                    raise ValueError("Vector services must return GeoJSON, not GML or XML.")
            if kind == "wps":
                layer["wps_output"] = layer["wps_output"] or "result"
                if layer["refresh"] or layer["visible"] or layer["basemap"]:
                    raise ValueError("WPS execution must be a manually enabled overlay, without automatic refresh.")
            result.append(layer)
        except ValueError as error:
            # Errors do not interpolate user-provided names/URLs into HTML.
            raise ValueError("Layer {}: {}".format(index, error)) from None
    return result


def validate_settings(data):
    layers = validate_layers(data["map_layers"])
    available = {"builtin-" + str(i) for i in range(len(BASEMAP_NAMES))}
    for key, allowed in (("map_basemaps", available),
                         ("map_weather_layers", {layer["id"] for layer in WEATHER_LAYERS})):
        selected = data[key]
        if not isinstance(selected, list) or any(not isinstance(s, str) or s not in allowed for s in selected):
            raise ValueError("Invalid built-in layer selection.")
    bases = set(data["map_basemaps"]) | {l["id"] for l in layers if l["enabled"] and l["basemap"]}
    if data["map_default_basemap"] not in bases | {"none"}:
        raise ValueError("The default basemap must be enabled and marked as a basemap, or None.")
    for key in ("map_enabled", "map_allow_google", "map_use_initial_view", "map_show_receiver",
                "map_night", "map_openweather", "map_seamarks", "map_maidenhead"):
        if type(data[key]) is not bool:
            raise ValueError("Invalid map checkbox value.")
    for key, low, high in (("map_initial_lat", -85.05112878, 85.05112878),
                           ("map_initial_lon", -180, 180), ("map_initial_zoom", 0, 22)):
        v = data[key]
        if type(v) not in (float, int) or not math.isfinite(v) or not low <= v <= high:
            raise ValueError("Invalid initial map view.")
    if int(data["map_initial_zoom"]) != data["map_initial_zoom"]:
        raise ValueError("Initial zoom must be a whole number.")
    return layers


def public_settings(config):
    try:
        result = settings(config)
        result["map_layers"] = validate_settings(result)
    except (ValueError, TypeError, KeyError, RecursionError):
        result = defaults(config)
        result.update(map_layers=[], map_basemaps=[], map_default_basemap="none", map_weather_layers=[],
                      map_openweather=False, map_seamarks=False, map_maidenhead=False, map_night=False)
        result["map_config_error"] = "Invalid map configuration; optional providers disabled. Ask the administrator to review Map settings."
    # Only enabled custom URLs are public. No receiver/admin secrets are copied.
    result["map_layers"] = [l for l in result["map_layers"] if l["enabled"]]
    result["weather_catalog"] = [dict(l, enabled=True, basemap=False, visible=False, opacity=0.65)
                                 for l in WEATHER_LAYERS if l["id"] in result["map_weather_layers"]]
    result["revision"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()[:12]
    return result


def script_json(data):
    """JSON safe inside an application/json script element (not executable JS)."""
    return (json.dumps(data, ensure_ascii=True, allow_nan=False)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))
