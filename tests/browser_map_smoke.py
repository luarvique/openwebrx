"""Optional headless DOM/integration smoke tests, with stubbed GIS/renderer APIs.

Requires Playwright and Chromium; does not contact live services or an SDR.
Run: python tests/browser_map_smoke.py --chromium /usr/bin/chromium
"""
import argparse
import json
from pathlib import Path
import shutil

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

FAKES = r"""
class E {
    constructor() { this.events = {}; }
    on(n, f) { (this.events[n] ||= []).push(f); return this; }
    off(n, f) { this.events[n] = (this.events[n] || []).filter(x => x !== f); return this; }
    fire(n) { (this.events[n] || []).forEach(f => f()); return this; }
}
class Layer extends E {
    constructor(url, options) { super(); this.url = url; this.options = options || {}; }
    addTo(map) { map.addLayer(this); return this; }
    clearLayers() { this.data = null; return this; }
    addData(data) { this.data = data; return this; }
    setUrl(url) { this.url = url; return this; }
    setParams(params) { this.params = params; return this; }
    redraw() { return this; }
    static extend(p) { class Extended extends Layer {} Object.assign(Extended.prototype, p); return Extended; }
}
window.makeMap = function() {
    const m = new E(); m.layers = new Set(); m.panes = {};
    m.getPane = n => m.panes[n]; m.createPane = n => (m.panes[n] = {style: {}});
    m.hasLayer = l => m.layers.has(l);
    m.addLayer = l => { if (!m.layers.has(l)) { m.layers.add(l); l.fire('add'); } };
    m.removeLayer = l => { if (m.layers.delete(l)) l.fire('remove'); };
    m.setView = (center, zoom) => { m.center = center; m.zoom = zoom; return m; };
    m.getBounds = () => ({getWest: () => -118, getEast: () => -116, getSouth: () => 32, getNorth: () => 34});
    return m;
};
window.L = {TileLayer: Layer, CRS: {EPSG3857: {}},
    tileLayer: (url, opts) => new Layer(url, opts), geoJSON: (data, opts) => new Layer(null, opts),
    circleMarker: () => new Layer(), map: () => { window.mapCreates = (window.mapCreates || 0) + 1; return makeMap(); },
    Control: {Zoom: class {addTo() {return this;}}},
    control: {layers: () => ({addTo() {return this;}, _overlaysList: document.createElement('div')})}
};
L.tileLayer.wms = (url, opts) => new Layer(url, opts);
"""


def page_with(context, body):
    page = context.new_page()
    page.set_default_timeout(5000)
    # In-memory pages work even where browser navigation is administratively blocked.
    page.route("**/*", lambda route: route.abort())
    page.set_content(body)
    page.evaluate("""() => {
        const values = new Map();
        Object.defineProperty(window, 'localStorage', {configurable:true, value:{
            getItem: key => values.has(key) ? values.get(key) : null,
            setItem: (key, value) => values.set(key, String(value))
        }});
    }""")
    return page


def editor_test(context):
    fields = ""
    for name, kind, value, checked in (
        ("map_use_initial_view", "checkbox", "1", False),
        ("map_initial_lat", "number", "32.7", False),
        ("map_initial_lon", "number", "-117.1", False),
        ("map_initial_zoom", "number", "5", False),
        ("map_allow_google", "checkbox", "1", False),
        ("google_maps_api_key", "text", "", False),
        ("map_openweather", "checkbox", "1", False),
        ("openweathermap_api_key", "text", "", False),
        ("map_basemaps-builtin-0", "checkbox", "on", True),
    ):
        fields += f'<div class="form-group"><input id="{name}" name="{name}" type="{kind}" value="{value}" {"checked" if checked else ""}></div>'
    body = ('<form>' + fields + '<select id="map_default_basemap"><option value="none">None</option>'
            '<option value="builtin-0" selected>OpenStreetMap</option></select>'
            '<div id="map-layer-editor"></div><details id="map-layer-json"><summary>JSON</summary>'
            '<textarea id="map_layers" name="map_layers">[]</textarea></details></form>')
    page = page_with(context, body)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.add_script_tag(path=str(ROOT / 'htdocs/lib/settings/MapSettings.js'))
    assert page.locator('#map_initial_lat').evaluate('(e) => e.readOnly')
    page.locator('#map_use_initial_view').check()
    assert not page.locator('#map_initial_lat').evaluate('(e) => e.readOnly')
    page.get_by_role('button', name='Add layer', exact=True).click()
    card = page.locator('.map-layer-card')
    card.get_by_label('Name', exact=True).fill('<img src=x onerror=alert(1)>')
    card.get_by_label('Public service URL / tile template', exact=True).fill('https://example.org/MapServer')
    card.get_by_label('Use as a basemap', exact=True).check()
    layers = json.loads(page.locator('#map_layers').input_value())
    assert layers[0]['basemap'] is True
    page.locator('#map_default_basemap').select_option(layers[0]['id'])
    assert page.locator('#map_default_basemap').input_value() == layers[0]['id']
    assert page.locator('img').count() == 0
    card.get_by_label('Service type', exact=True).select_option('wps')
    card = page.locator('.map-layer-card')
    assert card.get_by_label('Use as a basemap', exact=True).is_disabled()
    assert card.get_by_label('Overlay initially visible', exact=True).is_disabled()
    assert not json.loads(page.locator('#map_layers').input_value())[0]['basemap']
    page.get_by_role('button', name='Remove layer', exact=True).click()
    assert json.loads(page.locator('#map_layers').input_value()) == []
    assert not errors, errors
    page.close()
    print('PASS: editor add/remove, defaults, checkbox roles, optional fields and escaped names')


def registry_test(context):
    body = '<select id="openwebrx-map-source"></select><div id="openwebrx-map-extralayers"></div>'
    page = page_with(context, body)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_script_tag(path=str(ROOT / 'htdocs/lib/MapLayers.js'))
    page.add_script_tag(content=FAKES)
    result = page.evaluate(r"""async () => {
        window.fetches = 0;
        window.fetch = async () => { window.fetches++; return new Response(JSON.stringify({type:'FeatureCollection',features:[]})); };
        localStorage.setItem('owrx-map-smoke-custom-wps', 'true');
        const cfg = {revision: 'smoke', map_basemaps: [], map_default_basemap: 'none', map_layers: [
            {id:'custom-wps',name:'WPS <img src=x>',type:'wps',url:'https://example.org/wps',layers:'demo:test',enabled:true,basemap:false,visible:false,refresh:0},
            {id:'custom-base',name:'Custom basemap',type:'arcgis-map',url:'https://example.org/MapServer',enabled:true,basemap:true,visible:false}
        ]};
        const m = makeMap(); const manager = OWRXMapLayers.install(L, m, [], [], cfg, '');
        await new Promise(r => setTimeout(r, 0));
        const initially = fetches;
        const input = document.querySelector('#openwebrx-map-extralayers input');
        const checked = input.checked;
        input.click(); await new Promise(r => setTimeout(r, 0));
        const afterClick = fetches;
        manager.changeBase('custom-base', false); await new Promise(r => setTimeout(r, 0));
        const base = document.getElementById('openwebrx-map-source').value;
        const before = m.layers.size;
        window.dispatchEvent(new PageTransitionEvent('pagehide', {persisted:true}));
        const after = m.layers.size;
        manager.dispose();
        return {initially, checked, afterClick, base, before, after, remaining:m.layers.size, images:document.querySelectorAll('img').length};
    }""")
    assert result['initially'] == 0 and not result['checked'], result
    assert result['afterClick'] == 1 and result['base'] == 'custom-base', result
    assert result['before'] == result['after'] and result['remaining'] == 0 and result['images'] == 0, result
    assert not errors, errors
    page.close()
    print('PASS: map controls, manual-only WPS, custom basemap, safe labels, bfcache and cleanup')


def aircraft_test(context):
    cfg = {'map_use_initial_view': True, 'map_initial_lat': 34, 'map_initial_lon': -118, 'map_initial_zoom': 8,
           'map_show_receiver': False, 'map_night': False, 'map_basemaps': [], 'map_default_basemap': 'none',
           'map_layers': [{'id':'custom-bad','name':'Broken service','type':'geojson','url':'https://example.org/bad',
                           'enabled':True,'visible':True,'basemap':False}], 'revision': 'aircraft'}
    body = ('<script id="openwebrx-map-config" type="application/json">' + json.dumps(cfg) + '</script>'
            '<div id="openwebrx-map"></div><div class="openwebrx-map-legend">'
            '<select id="openwebrx-map-source"></select><div id="openwebrx-map-extralayers"></div></div>')
    page = page_with(context, body)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_script_tag(path=str(ROOT / 'htdocs/lib/MapLayers.js'))
    page.add_script_tag(content=FAKES + r"""
window.MapManager = function() {
    this.config = {receiver_name:'Test receiver'};
    this.mman = {markers:new Map(), find(k){return this.markers.get(k);}, add(k,v){this.markers.set(k,v);},
        addType(){}, isEnabled(){return true;}};
    this.cman = {add(){}}; this.lman = {};
};
MapManager.prototype.setupLegendFilters = function() {};
window.$ = function() {return {css(){return this;},insertAfter(){return this;}};};
$.getScript = function() {
    const p = Promise.resolve(); p.done = f => {p.then(f);return p;}; p.fail = f => {p.catch(f);return p;};return p;
};
window.LMarker = class {};
window.LSimpleMarker = class {
    setMarkerPosition(name,lat,lon) {this.position=[lat,lon];}
    setLatLng(lat,lon) {this.position=[lat,lon];}
    setMarkerOptions() {} addListener() {} setMap(map) {this.map=map;}
};
window.LAircraftMarker = class extends LSimpleMarker {
    update(data) {this.updateData=data;} getPos() {return [this.updateData.location.lat,this.updateData.location.lon];}
};
window.LAprsMarker = class extends LAircraftMarker {};
window.LFeatureMarker = class extends LAircraftMarker {};
window.fetch = async () => new Response('not valid JSON');
""")
    page.add_script_tag(path=str(ROOT / 'htdocs/map-leaflet.js'))
    result = page.evaluate(r"""async () => {
        fetchStyleSheet = async () => {};
        const first = mapManager.initializeMap({lat:32.7,lon:-117.1}, '', '');
        const second = mapManager.initializeMap({lat:32.8,lon:-117.2}, '', '');
        mapManager.processUpdates([{callsign:'TEST123',mode:'ADSB',location:{type:'latlon',lat:33,lon:-117}}]);
        await Promise.all([first,second]);
        await new Promise(r=>setTimeout(r,10));
        mapManager.processUpdates([{callsign:'TEST123',mode:'ADSB',location:{type:'latlon',lat:33.1,lon:-117.1}}]);
        const marker = mapManager.mman.find('TEST123');
        const result = {creates:mapCreates,center:map.center,zoom:map.zoom,receiver:receiverMarker.position,
            receiverHidden:receiverMarker.map===null,plane:marker.updateData.location.lat,planeShown:marker.map===map,
            queued:updateQueue.length,layerError:document.querySelector('.owrx-layer-message[data-level=error]')!==null};
        mapManager._gisLayers.dispose(); return result;
    }""")
    assert result == {'creates': 1, 'center': [34, -118], 'zoom': 8, 'receiver': [32.8, -117.2],
                      'receiverHidden': True, 'plane': 33.1, 'planeShown': True, 'queued': 0, 'layerError': True}, result
    assert not errors, errors
    page.close()
    print('PASS: actual Leaflet client initialization and ADS-B update handlers against stubbed renderer/services')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--chromium', default=shutil.which('chromium') or shutil.which('chromium-browser'))
    args = parser.parse_args()
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, headless=True, args=['--no-sandbox'])
        context = browser.new_context()
        editor_test(context)
        registry_test(context)
        aircraft_test(context)
        context.close()
        browser.close()


if __name__ == '__main__': main()
