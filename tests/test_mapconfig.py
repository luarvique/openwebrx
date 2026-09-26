"""Run without SDR hardware/dependencies: python -m unittest discover -s tests -p 'test_mapconfig.py'."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mapconfig_under_test", ROOT / "owrx/mapconfig.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def layer(kind="arcgis-map", **overrides):
    result = {"id": "custom-test", "name": "Test", "type": kind,
              "url": "https://example.org/arcgis/rest/services/Test/MapServer"}
    result.update(overrides)
    return result


class MapConfigurationTests(unittest.TestCase):
    def test_legacy_defaults_without_migration(self):
        legacy = {"receiver_gps": {"lat": 32.7, "lon": -117.1}, "map_type": "leaflet"}
        before = copy.deepcopy(legacy)
        public = m.public_settings(legacy)
        self.assertEqual(legacy, before)
        self.assertEqual(public["map_initial_lat"], 32.7)
        self.assertFalse(public["map_use_initial_view"])
        self.assertEqual(len(public["map_basemaps"]), 12)
        self.assertFalse(public["map_allow_google"])
        self.assertEqual(len(public["weather_catalog"]), 7)

    def test_saved_property_layer_coordinates(self):
        class PropertyLayer:
            def __contains__(self, key): return key in ("lat", "lon")
            def __getitem__(self, key): return {"lat": 32.7, "lon": -117.1}[key]
        self.assertEqual(m.defaults({"receiver_gps": PropertyLayer()})["map_initial_lon"], -117.1)

    def test_invalid_or_polar_gps_is_safe(self):
        for gps in (None, {}, {"lat": math.nan}, {"lat": 90, "lon": -200}):
            public = m.public_settings({"receiver_gps": gps})
            self.assertLessEqual(abs(public["map_initial_lat"]), 85.05112878)
            self.assertLessEqual(abs(public["map_initial_lon"]), 180)
            m.script_json(public)

    def test_existing_keys_preserved_but_not_published_in_new_payload(self):
        public = m.public_settings({"google_maps_api_key": "secret-google", "openweathermap_api_key": "secret-weather", "admin_password": "secret-password"})
        self.assertTrue(public["map_allow_google"])
        self.assertTrue(public["map_openweather"])
        self.assertNotIn("secret-", m.script_json(public))

    def test_disabled_layers_not_published(self):
        public = m.public_settings({"map_layers": [layer(enabled=False)]})
        self.assertEqual(public["map_layers"], [])
        self.assertNotIn("example.org", m.script_json(public))

    def test_empty_catalog_and_no_basemap(self):
        public = m.public_settings({"map_basemaps": [], "map_default_basemap": "none", "map_weather_layers": [], "map_night": False})
        self.assertEqual(public["weather_catalog"], [])
        self.assertEqual(public["map_default_basemap"], "none")
        self.assertNotIn("map_config_error", public)

    def test_custom_default_basemap(self):
        settings = m.settings({"map_basemaps": [], "map_default_basemap": "custom-test", "map_layers": [layer(basemap=True)]})
        self.assertTrue(m.validate_settings(settings)[0]["basemap"])
        settings["map_layers"][0]["enabled"] = False
        with self.assertRaises(ValueError): m.validate_settings(settings)

    def test_unsafe_urls_rejected(self):
        for url in ("javascript:alert(1)", "data:text/html,test", "//example.org", "https://user:pass@example.org", "https://example.org#fragment", "https://example.org/a\nb", "https://example.org\\a", "https://example.org:bad/", "https://example.org/?TOKEN=secret"):
            with self.subTest(url=url), self.assertRaises(ValueError): m.validate_url(url)

    def test_plain_urls_templates_and_nonsecret_parameters_allowed(self):
        for url in ("http://localhost:8080/wms?map=public.map", "https://{s}.example.org/{z}/{x}/{y}{r}.png", "https://example.org/MapServer?f=pjson"):
            self.assertEqual(m.validate_url(url), url)

    def test_unknown_keys_and_duplicate_ids(self):
        for layers in ([layer(callback="alert(1)")], [layer(), layer()], [layer(id="bad")], {"not": "a list"}, [layer()] * 51):
            with self.subTest(layers=str(layers)[:50]), self.assertRaises(ValueError): m.validate_layers(layers)

    def test_numeric_and_boolean_validation(self):
        for field, bad in (("enabled", "false"), ("opacity", 2), ("opacity", math.nan), ("opacity", True), ("refresh", 10), ("refresh", -1), ("max_features", 1.5), ("max_zoom", 23)):
            with self.subTest(field=field, bad=bad), self.assertRaises(ValueError): m.validate_layers([layer(**{field: bad})])

    def test_arcgis_paths_and_ids(self):
        for kind in ("arcgis-map", "arcgis-feature"):
            m.validate_layers([layer(kind, layers="0,1", url="https://example.org/Test/MapServer/2")])
        m.validate_layers([layer("arcgis-feature", url="https://example.org/Test/FeatureServer")])
        with self.assertRaises(ValueError): m.validate_layers([layer(layers="show:0")])
        with self.assertRaises(ValueError): m.validate_layers([layer(url="https://example.org/Test/ImageServer")])

    def test_ogc_defaults_and_versions(self):
        for kind, version in (("wms", "1.1.1"), ("wfs", "1.0.0"), ("wmts", "1.0.0"), ("wps", "1.0.0")):
            normalized = m.validate_layers([layer(kind, url="https://example.org/ows", layers="test", matrix_set="EPSG:3857")])[0]
            self.assertEqual(normalized["version"], version)
        for kind in ("wms", "wfs", "wmts", "wps"):
            with self.assertRaises(ValueError): m.validate_layers([layer(kind)])
            with self.assertRaises(ValueError): m.validate_layers([layer(kind, layers="x", version="9.0.0")])

    def test_wps_never_automatically_executes(self):
        for option in ({"visible": True}, {"basemap": True}, {"refresh": 60}):
            with self.subTest(option=option), self.assertRaises(ValueError):
                m.validate_layers([layer("wps", url="https://example.org/wps", layers="example:process", **option)])

    def test_xyz_placeholders_and_wmts_matrix(self):
        m.validate_layers([layer("xyz", url="https://{s}.example.org/{z}/{x}/{y}{r}.png")])
        for url in ("https://example.org/{z}/{x}.png", "https://example.org/{z}/{x}/{y}/{secret}.png"):
            with self.assertRaises(ValueError): m.validate_layers([layer("xyz", url=url)])
        with self.assertRaises(ValueError): m.validate_layers([layer("wmts", layers="test")])

    def test_failed_configuration_is_fail_closed(self):
        public = m.public_settings({"map_layers": [layer(url="javascript:alert(1)")]})
        self.assertIn("map_config_error", public)
        self.assertEqual(public["map_basemaps"], [])
        self.assertEqual(public["weather_catalog"], [])
        self.assertEqual(public["map_layers"], [])
        self.assertFalse(public["map_maidenhead"])

    def test_script_json_cannot_close_script_element(self):
        dangerous = {"name": '</script><img src=x onerror="alert(1)">&\u2028'}
        encoded = m.script_json(dangerous)
        self.assertNotIn("<", encoded)
        self.assertNotIn("&", encoded)
        self.assertEqual(json.loads(encoded), dangerous)

    def test_revision_changes_with_settings_not_unrelated_secrets(self):
        first = m.public_settings({})["revision"]
        self.assertNotEqual(first, m.public_settings({"map_night": False})["revision"])
        self.assertEqual(first, m.public_settings({"admin_password": "secret"})["revision"])

    def test_weather_catalog_only_https_without_keys_or_auto_enable(self):
        for weather in m.public_settings({})["weather_catalog"]:
            m.validate_url(weather["url"])
            self.assertTrue(weather["url"].startswith("https://"))
            self.assertFalse(weather["visible"])
            self.assertGreaterEqual(weather["refresh"], 300)

    def test_new_assets_and_route_are_wired(self):
        http = (ROOT / "owrx/http.py").read_text()
        general = (ROOT / "owrx/controllers/settings/general.py").read_text()
        self.assertIn('"/settings/map", MapSettingsController', http)
        self.assertNotIn('"Map settings"', general)
        self.assertNotIn('"map_type"', general)
        for engine in ("leaflet", "google"):
            template = (ROOT / ("htdocs/map-" + engine + ".html")).read_text()
            self.assertLess(template.index('id="openwebrx-map-config"'), template.index('compiled/map-'))
            self.assertIn('static/lib/MapLayers.js', template)


if __name__ == "__main__": unittest.main()
