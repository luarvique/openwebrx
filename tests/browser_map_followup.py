"""Chromium DOM integration tests with stubbed Leaflet/network, NOT live GIS rendering.

Requires playwright and Chromium. Run: python tests/browser_map_followup.py
Set CHROMIUM to an executable path, or install a browser with playwright.
"""
import base64
import json
import os
from pathlib import Path
import shutil
import unittest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
STUB = (ROOT / 'tests/leaflet_legend_stub.js').read_text()
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==')


class BrowserMapFollowup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        executable = os.environ.get('CHROMIUM') or shutil.which('chromium') or shutil.which('chromium-browser')
        cls.browser = cls.playwright.chromium.launch(executable_path=executable, headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1100, 'height': 800})
        self.page = self.context.new_page()
        self.page.set_default_timeout(5000)
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        # No live navigation or HTTP: the browser environment may prohibit all networking.
        # Simulate only the external boundary; run the actual picker, layer manager and legend.
        self.page.evaluate("""([stub, png]) => {
            const state = window.testNetwork = {requests:[], failLibrary:false, failImages:false, failMetadata:false};
            const storage = new Map();
            Object.defineProperty(window, 'localStorage', {configurable:true, value:{
                getItem:k=>storage.has(k)?storage.get(k):null, setItem:(k,v)=>storage.set(k,String(v)), removeItem:k=>storage.delete(k)}});
            const nativeImage = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
            Object.defineProperty(HTMLImageElement.prototype, 'src', {configurable:true,
                get(){return nativeImage.get.call(this);}, set(url){
                    if (url.startsWith('data:')) { nativeImage.set.call(this,url); return; }
                    state.requests.push(url); this.dataset.requestedUrl=url;
                    if (state.failImages) setTimeout(()=>this.dispatchEvent(new Event('error')),0);
                    else nativeImage.set.call(this,'data:image/png;base64,'+png);
                }});
            for (const [proto, prop] of [[HTMLScriptElement.prototype,'src'],[HTMLLinkElement.prototype,'href']]) {
                const native = Object.getOwnPropertyDescriptor(proto,prop);
                Object.defineProperty(proto,prop,{configurable:true,
                    get(){return this.testURL || native.get.call(this);},
                    set(url){this.testURL=url;}});
            }
            const append = Element.prototype.append;
            Element.prototype.append = function(...nodes) {
                for (const node of nodes) {
                    if (this.tagName !== 'HEAD' || !node.testURL) { append.call(this,node); continue; }
                    state.requests.push(node.testURL);
                    const fail = state.failLibrary;
                    if (node.tagName==='SCRIPT' && !fail) node.textContent=stub;
                    append.call(this,node);
                    setTimeout(()=>node.dispatchEvent(new Event(fail?'error':'load')),0);
                }
            };
            window.fetch = async (url, options={}) => {
                state.requests.push(String(url));
                if (options.signal?.aborted) throw new DOMException('Cancelled','AbortError');
                if (state.failMetadata) return new Response('Unavailable',{status:503});
                const data = url.includes('/legend?') ? {layers:[{layerId:0,layerName:'Warnings',legend:[{
                    label:'<img src=x onerror=alert(1)> Warning',contentType:'image/png',imageData:png}]}]} :
                    url.includes('features.json') ? {type:'FeatureCollection',features:[{type:'Feature',properties:{name:'One'},
                        geometry:{type:'Point',coordinates:[-117,33]}}]} :
                    {layers:[{id:0,parentLayerId:-1,defaultVisibility:true}]};
                return new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}});
            };
        }""", [STUB, base64.b64encode(PNG).decode()])

    @property
    def requests(self):
        return self.page.evaluate('testNetwork.requests')

    def tearDown(self):
        errors = self.errors[:]
        self.context.close()
        self.assertEqual(errors, [], 'Uncaught browser errors')

    def script(self, path):
        self.page.add_script_tag(content=(ROOT / path).read_text())

    def picker(self):
        self.page.set_content('<label for="receiver_gps-lat">Latitude</label><input type="number" id="receiver_gps-lat" value="32.71234567">'
                              '<label for="receiver_gps-lon">Longitude</label><input type="number" id="receiver_gps-lon" value="-117.12345678">'
                              '<div class="row"><div class="map-input" for="receiver_gps"></div></div>')
        self.script('htdocs/lib/settings/MapInput.js')
        self.page.evaluate("window.picker = OWRXLocationPicker.attach(document.querySelector('.map-input')); picker.ready")

    def legend(self, sources=None):
        self.page.set_content('<main id="map" style="height:650px;background:#eef2f4"></main><select id="openwebrx-map-source"></select>'
                              '<div id="openwebrx-map-extralayers"></div>')
        self.page.add_style_tag(content=(ROOT / 'htdocs/css/map-legend.css').read_text())
        self.page.add_script_tag(content=STUB)
        self.script('htdocs/lib/MapLayers.js')
        self.script('htdocs/lib/MapLegend.js')
        sources = sources or [{'id': 'custom-radar', 'name': 'Radar reflectivity', 'type': 'wms', 'url': 'https://gis.example/wms',
                               'layers': 'radar', 'enabled': True, 'visible': False, 'opacity': .7, 'legend_caption': 'Reflectivity (dBZ)'}]
        self.page.evaluate('''sources => {
            window.map = L.map('map');
            window.manager = OWRXMapLayers.install(L, map, [], [], {revision:'test', map_basemaps:[],
                map_default_basemap:'none', map_layers:sources, weather_catalog:[]}, '');
        }''', sources)

    def test_coordinate_picker_initialization_bidirectional_sync_and_no_google(self):
        self.picker()
        self.assertEqual(self.page.input_value('#receiver_gps-lat'), '32.71234567')
        self.assertEqual(self.page.input_value('#receiver_gps-lon'), '-117.12345678')
        self.page.fill('#receiver_gps-lat', '34.25')
        self.assertEqual(self.page.evaluate('picker.getMarker().getLatLng().lat'), 34.25)
        self.page.evaluate("picker.getMap().fire('click', {latlng:{lat:40.5,lng:243}})")
        self.assertEqual(self.page.input_value('#receiver_gps-lon'), '-117')
        self.page.evaluate("picker.getMarker().setLatLng({lat:10,lng:20}).fire('dragend')")
        self.assertEqual(self.page.input_value('#receiver_gps-lat'), '10')
        self.assertEqual(self.page.input_value('#receiver_gps-lon'), '20')
        self.page.evaluate("picker.getMap().panTo({lat:0,lng:0})")
        self.assertEqual(self.page.input_value('#receiver_gps-lat'), '10')
        self.page.fill('#receiver_gps-lat', '')
        self.assertFalse(self.page.evaluate('picker.getMap().hasLayer(picker.getMarker())'))
        self.assertFalse(any('google' in url.lower() for url in self.requests))
        self.assertEqual(sum(url.endswith('/leaflet.js') for url in self.requests), 1)
        self.page.evaluate('picker.dispose()')
        self.assertEqual(self.page.locator('[role=status]').count(), 0)

    def test_picker_library_failure_keeps_numeric_inputs_and_retry_recovers(self):
        self.page.evaluate('testNetwork.failLibrary = true')
        self.picker()
        self.page.get_by_text('Map preview unavailable.', exact=False).wait_for()
        self.page.fill('#receiver_gps-lat', '12.75')
        self.assertEqual(self.page.input_value('#receiver_gps-lat'), '12.75')
        self.page.evaluate('testNetwork.failLibrary = false')
        self.page.get_by_role('button', name='Retry map preview').click()
        self.page.wait_for_function('picker.getMap() !== null')
        self.assertEqual(self.page.evaluate('picker.getMarker().getLatLng().lat'), 12.75)

    def test_wms_legend_toggles_with_layer_and_keyboard_collapse(self):
        self.legend()
        self.assertEqual(self.page.locator('.owrx-map-legend section').count(), 0)
        self.page.get_by_label('Radar reflectivity', exact=True).check()
        self.page.locator('[data-layer-id="custom-radar"] img').wait_for()
        self.assertTrue(any('GetLegendGraphic' in url for url in self.requests))
        summary = self.page.locator('.owrx-map-legend > summary')
        summary.focus(); summary.press('Enter')
        self.page.wait_for_function('!document.querySelector(".owrx-map-legend").open')
        self.page.wait_for_function('document.querySelectorAll(".owrx-map-legend section").length === 0')
        self.assertEqual(self.page.evaluate('localStorage.getItem("owrx-legend-open")'), 'false')
        summary.press('Enter')
        self.page.locator('[data-layer-id="custom-radar"] img').wait_for()
        self.page.get_by_label('Radar reflectivity', exact=True).uncheck()
        self.page.wait_for_function('document.querySelectorAll(".owrx-map-legend section").length === 0')
        self.page.evaluate('manager.dispose()')
        self.assertEqual(self.page.locator('.owrx-map-legend').count(), 0)

    def test_arcgis_symbols_are_safe_and_legend_failure_does_not_remove_layer(self):
        self.legend([{'id': 'custom-alerts', 'name': 'NOAA advisories', 'type': 'arcgis-map', 'url': 'https://gis.example/MapServer',
                      'layers': '0', 'enabled': True, 'visible': True}])
        self.page.get_by_text('<img src=x onerror=alert(1)> Warning', exact=True).wait_for()
        self.assertEqual(self.page.locator('.owrx-map-legend [onerror]').count(), 0)
        self.assertTrue(self.page.evaluate('map.hasLayer(manager.entries[0].layer)'))
        self.page.evaluate('manager.dispose()')
        self.page.evaluate('testNetwork.failMetadata = true')
        self.legend([{'id': 'custom-alerts', 'name': 'NOAA advisories', 'type': 'arcgis-map', 'url': 'https://gis.example/MapServer',
                      'layers': '0', 'enabled': True, 'visible': True}])
        self.page.get_by_role('button', name='Retry legend').wait_for()
        self.assertTrue(self.page.evaluate('map.hasLayer(manager.entries[0].layer)'))
        self.page.evaluate('testNetwork.failMetadata = false')
        self.page.get_by_role('button', name='Retry legend').click()
        self.page.get_by_text('<img src=x onerror=alert(1)> Warning', exact=True).wait_for()

    def test_custom_image_failure_retry_and_basemap_replacement(self):
        self.page.evaluate('testNetwork.failImages = true')
        sources = [dict(id='custom-base', name='Custom basemap', type='xyz', url='https://gis.example/{z}/{x}/{y}.png',
                        enabled=True, basemap=True, legend_url='https://gis.example/legend.png')]
        self.legend(sources)
        self.page.select_option('#openwebrx-map-source', 'custom-base')
        self.page.get_by_role('button', name='Retry legend').wait_for()
        self.assertTrue(self.page.evaluate('map.hasLayer(manager.entries[0].layer)'))
        self.page.evaluate('testNetwork.failImages = false')
        self.page.get_by_role('button', name='Retry legend').click()
        self.page.wait_for_function('document.querySelector(".owrx-map-legend img")?.naturalWidth > 0')
        self.page.select_option('#openwebrx-map-source', 'none')
        self.page.wait_for_function('document.querySelectorAll(".owrx-map-legend section").length === 0')

    def test_vector_legend_follows_loaded_features_and_never_executes_wps(self):
        self.legend([dict(id='custom-points', name='Feature observations', type='geojson', url='https://gis.example/features.json', enabled=True, visible=True),
                     dict(id='custom-wps', name='Manual process', type='wps', url='https://gis.example/wps', layers='test', enabled=True)])
        self.page.locator('[data-layer-id="custom-points"] svg').wait_for()
        self.assertEqual(self.page.locator('[data-layer-id="custom-wps"]').count(), 0)
        self.assertFalse(any('Execute' in url for url in self.requests))
        self.page.evaluate("map.bounds={getWest:()=>0,getSouth:()=>0,getEast:()=>1,getNorth:()=>1}; map.fire('moveend')")
        self.page.wait_for_function('document.querySelectorAll(".owrx-map-legend section").length === 0')
        self.assertFalse(any('Execute' in url for url in self.requests))

    def test_removed_layer_cancels_pending_legend_and_late_response_is_ignored(self):
        self.page.evaluate("""() => {
            const fetch = window.fetch;
            window.fetch = (url, options) => new Promise(resolve => {
                window.resolveLegend = () => resolve(fetch(url, options));
            });
        }""")
        self.legend([dict(id='custom-delayed', name='Delayed service', type='arcgis-map',
                          url='https://gis.example/MapServer', layers='0', enabled=True, visible=True)])
        self.page.wait_for_function('typeof window.resolveLegend === "function"')
        self.page.get_by_label('Delayed service', exact=True).uncheck()
        self.page.wait_for_function('document.querySelectorAll(".owrx-map-legend section").length === 0')
        self.page.evaluate('resolveLegend()')
        self.page.wait_for_timeout(150)
        self.assertEqual(self.page.locator('.owrx-map-legend section').count(), 0)
        self.assertFalse(self.page.evaluate('map.hasLayer(manager.entries[0].layer)'))

    def test_collapsed_legend_requests_nothing_and_fits_small_viewport(self):
        self.page.evaluate("localStorage.setItem('owrx-legend-open','false')")
        self.page.set_viewport_size({'width': 375, 'height': 640})
        self.legend([dict(id='custom-small', name='Radar colors', type='wms',
                          url='https://gis.example/wms', layers='radar', enabled=True, visible=True)])
        self.page.wait_for_timeout(150)
        self.assertFalse(any('GetLegendGraphic' in url for url in self.requests))
        self.page.locator('.owrx-map-legend > summary').click()
        self.page.locator('.owrx-map-legend img').wait_for()
        box = self.page.locator('.owrx-map-legend').bounding_box()
        self.assertGreaterEqual(box['x'], 0)
        self.assertLessEqual(box['x'] + box['width'], 375)
        self.assertLessEqual(self.page.locator('.owrx-legend-body').bounding_box()['height'], 640 / 2)

    def test_editor_serializes_legend_fields_as_text(self):
        self.page.set_content('''<form><div id="map-layer-editor"></div><details id="map-layer-json"><summary>JSON</summary>
            <textarea id="map_layers">[]</textarea></details><select id="map_default_basemap"><option value="none">None</option></select>
            <input type="checkbox" id="map_use_initial_view"><input type="checkbox" id="map_allow_google">
            <input type="checkbox" id="map_openweather"></form>''')
        self.script('htdocs/lib/settings/MapSettings.js')
        self.page.get_by_role('button', name='Add layer', exact=True).click()
        self.page.get_by_label('Legend image URL', exact=False).fill('https://example.org/legend.png')
        self.page.get_by_label('Legend description / units', exact=False).fill('<b>Units</b>')
        saved = json.loads(self.page.input_value('#map_layers'))[0]
        self.assertEqual(saved['legend_url'], 'https://example.org/legend.png')
        self.assertEqual(saved['legend_caption'], '<b>Units</b>')
        self.assertEqual(self.page.locator('b').count(), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
