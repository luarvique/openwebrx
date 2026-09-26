"""Configuration/coordinate regressions; no SDR modules are required."""
import copy
import importlib.util
import math
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


config = load('legend_mapconfig', 'owrx/mapconfig.py')


class StubInput:
    def __init__(self, id, label, validator=None):
        self.id, self.label, self.validator, self.disabled = id, label, validator, False

    def input_classes(self, errors):
        return 'form-control is-invalid' if errors else 'form-control'

    def render_errors(self, errors):
        return ''


class StubValidationError(Exception):
    pass


def location_module():
    # Only the form framework is stubbed; the real location rendering/parser runs.
    modules = {name: ModuleType(name) for name in
               ('owrx', 'owrx.form', 'owrx.form.input', 'owrx.form.input.validator', 'owrx.form.error')}
    modules['owrx.form.input'].Input = StubInput
    modules['owrx.form.input.validator'].Validator = object
    modules['owrx.form.error'].ValidationError = StubValidationError
    with patch.dict(sys.modules, modules):
        return load('legend_location', 'owrx/form/input/location.py')


location = location_module()


def layer(**changes):
    value = dict(id='custom-test', name='Test', type='arcgis-map',
                 url='https://example.org/arcgis/rest/services/Test/MapServer')
    value.update(changes)
    return value


class LegendConfigurationTests(unittest.TestCase):
    def test_existing_configuration_needs_no_migration(self):
        old = {'receiver_gps': {'lat': 32.71234567, 'lon': -117.12345678}, 'map_layers': [layer()]}
        original = copy.deepcopy(old)
        public = config.public_settings(old)
        self.assertEqual(old, original)
        self.assertNotIn('map_config_error', public)
        self.assertEqual(public['map_layers'][0]['legend_url'], '')
        self.assertEqual(public['map_layers'][0]['legend_caption'], '')
        self.assertEqual(public['map_initial_lat'], old['receiver_gps']['lat'])

    def test_anonymous_legend_fields_survive_normalization_and_publication(self):
        value = layer(legend_url='https://example.org/legend.png?style=blue', legend_caption='Rainfall (mm)')
        normalized = config.validate_layers([value])[0]
        self.assertEqual(normalized['legend_url'], value['legend_url'])
        self.assertEqual(config.public_settings({'map_layers': [value]})['map_layers'][0]['legend_caption'], 'Rainfall (mm)')

    def test_unsafe_legend_urls_are_rejected(self):
        for url in ('javascript:alert(1)', 'data:image/svg+xml,test', 'https://user:pass@example.org/a',
                    '//example.org/a', 'https://example.org/x#fragment', 'https://example.org/a\nb',
                    'https://example.org/?TOKEN=secret', 'https://example.org/{z}.png'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                config.validate_layers([layer(legend_url=url)])

    def test_legend_text_limits_are_enforced(self):
        for changes in ({'legend_url': 4}, {'legend_url': 'x' * 4097}, {'legend_caption': 'x' * 501},
                        {'legend_caption': 'a\nb'}, {'legend_caption': None}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                config.validate_layers([layer(**changes)])

    def test_disabled_layer_legend_urls_are_not_public(self):
        public = config.public_settings({'map_layers': [layer(enabled=False, legend_url='https://private.example/legend.png')]})
        self.assertNotIn('private.example', config.script_json(public))

    def test_caption_cannot_escape_json_script(self):
        public = config.public_settings({'map_layers': [layer(legend_caption='</script><img src=x onerror=alert(1)>')]})
        self.assertNotIn('<', config.script_json(public))

    def test_legend_changes_invalidate_configuration_revision(self):
        before = config.public_settings({'map_layers': [layer()]})['revision']
        after = config.public_settings({'map_layers': [layer(legend_url='https://example.org/legend.png')]})['revision']
        self.assertNotEqual(before, after)

    def test_weather_legends_are_https_anonymous_and_key_independent(self):
        for weather in config.WEATHER_LAYERS:
            if weather['type'] == 'arcgis-map':
                continue  # Automatic MapServer legend endpoint.
            self.assertTrue(weather['legend_url'].startswith('https://'))
            config.validate_url(weather['legend_url'])
            self.assertTrue(weather['legend_caption'])
        self.assertEqual(len(config.public_settings({})['weather_catalog']), 7)
        self.assertEqual(len(config.public_settings({'openweathermap_api_key': 'present'})['weather_catalog']), 7)

    def test_provider_units_are_explicit(self):
        catalog = {w['id']: w for w in config.WEATHER_LAYERS}
        self.assertIn('dBZ', catalog['iem-radar']['legend_caption'])
        self.assertIn('inches', catalog['iem-rain']['legend_caption'])
        self.assertIn('kelvin', catalog['goes-east-ir']['legend_caption'])
        self.assertIn('reflectance', catalog['goes-west-vis']['legend_caption'])

    def test_wps_remains_manual_even_with_legend_metadata(self):
        wps = layer(type='wps', url='https://example.org/wps', layers='process', legend_caption='Result')
        for changes in ({'visible': True}, {'basemap': True}, {'refresh': 60}):
            with self.assertRaises(ValueError):
                config.validate_layers([dict(wps, **changes)])
        self.assertEqual(config.validate_layers([wps])[0]['refresh'], 0)

    def test_invalid_layer_configuration_still_fails_closed(self):
        public = config.public_settings({'map_layers': [layer(legend_url='javascript:bad')]})
        self.assertEqual(public['map_layers'], [])
        self.assertEqual(public['weather_catalog'], [])
        self.assertIn('map_config_error', public)

    def test_numeric_limits_and_existing_service_validation_unchanged(self):
        for changes in ({'opacity': math.nan}, {'opacity': 2}, {'enabled': 'false'}, {'refresh': 10}, {'layers': 'show:0'}):
            with self.assertRaises(ValueError):
                config.validate_layers([layer(**changes)])

    def test_new_assets_are_loaded_in_order(self):
        template = (ROOT / 'htdocs/map-leaflet.html').read_text()
        self.assertLess(template.index('static/lib/MapLayers.js'), template.index('static/lib/MapLegend.js'))
        self.assertLess(template.index('static/lib/MapLegend.js'), template.index('compiled/map-leaflet.js'))
        self.assertIn('static/css/map-legend.css', template)
        self.assertIn('root.OWRXMapLegend.install(L, map, entries)', (ROOT / 'htdocs/lib/MapLayers.js').read_text())
        self.assertIn("field('legend_url'", (ROOT / 'htdocs/lib/settings/MapSettings.js').read_text())


class ReceiverPickerTests(unittest.TestCase):
    def test_picker_has_no_google_configuration_or_script_dependency(self):
        source = (ROOT / 'owrx/form/input/location.py').read_text()
        script = (ROOT / 'htdocs/lib/settings/MapInput.js').read_text()
        self.assertNotIn('Config.get', source)
        self.assertNotIn('data-key', source)
        self.assertNotIn('maps.googleapis.com', script)
        self.assertNotIn('locationPicker(', script)
        self.assertIn('https://tile.openstreetmap.org/{z}/{x}/{y}.png', script)
        self.assertIn('leaflet@1.9.4', script)

    def test_form_render_keeps_saved_coordinates_and_distinct_accessible_labels(self):
        form = location.LocationInput('receiver_gps', 'Receiver coordinates')
        html = form.render_input_group({'lat': 32.71234567, 'lon': -117.12345678}, [])
        self.assertIn('value="32.71234567"', html)
        self.assertIn('value="-117.12345678"', html)
        self.assertIn('aria-label="Receiver coordinates: Latitude"', html)
        self.assertIn('aria-label="Receiver coordinates: Longitude"', html)
        self.assertNotIn('data-key', html)

    def test_form_labels_and_values_are_escaped(self):
        form = location.LocationInput('receiver_gps', '<img onerror=alert(1)>')
        html = form.render_input_group({'lat': '" autofocus onfocus="x', 'lon': 0}, [])
        self.assertNotIn('<img', html)
        self.assertIn('&quot;', html)

    def test_coordinate_parser_and_validator_remain_compatible(self):
        form = location.LocationInput('receiver_gps', 'Receiver coordinates')
        parsed = form.parse({'receiver_gps-lat': ['32.7'], 'receiver_gps-lon': ['-117.1']})
        self.assertEqual(parsed, {'receiver_gps': {'lat': 32.7, 'lon': -117.1}})
        form.validator.validate('receiver_gps', parsed['receiver_gps'])
        for point in ({'lat': math.nan}, {'lat': 90}, {'lon': 180}, {'lon': float('inf')}):
            with self.assertRaises(StubValidationError):
                form.validator.validate('receiver_gps', point)


if __name__ == '__main__':
    unittest.main()
