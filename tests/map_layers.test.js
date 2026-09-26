'use strict';
const {test, afterEach} = require('node:test');
const assert = require('node:assert/strict');
const api = require('../htdocs/lib/MapLayers.js');
const originalFetch = global.fetch;
const originalTimeout = global.setTimeout;
afterEach(() => { global.fetch = originalFetch; global.setTimeout = originalTimeout; delete global.location; delete global.document; });
const box = (w = -118, s = 32, e = -116, n = 34) => ({getWest: () => w, getSouth: () => s, getEast: () => e, getNorth: () => n});
const feature = id => ({type: 'Feature', id, geometry: {type: 'Point', coordinates: [-117, 33]}, properties: {name: String(id)}});
const fc = ids => ({type: 'FeatureCollection', features: ids.map(feature)});
const response = data => new Response(JSON.stringify(data), {headers: {'Content-Type': 'application/json'}});
const tick = () => new Promise(resolve => setImmediate(resolve));
function deferred() { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return {resolve, reject, promise}; }
class Evented {
    constructor() { this.events = {}; }
    on(name, fn) { (this.events[name] ||= []).push(fn); return this; }
    off(name, fn) { this.events[name] = (this.events[name] || []).filter(f => f !== fn); return this; }
    fire(name) { (this.events[name] || []).forEach(f => f()); return this; }
}
class TestLayer extends Evented {
    constructor(url, options) { super(); this.url = url; this.options = options || {}; this.adds = 0; this.clears = 0; }
    addTo(map) { map.addLayer(this); return this; }
    clearLayers() { this.clears++; this.data = null; return this; }
    addData(data) { this.data = data; return this; }
    setUrl(url) { this.url = url; return this; }
    setParams(params) { this.params = Object.assign(this.params || {}, params); return this; }
    redraw() { this.redraws = (this.redraws || 0) + 1; return this; }
    static extend(properties) { class Extended extends TestLayer {} Object.assign(Extended.prototype, properties); return Extended; }
}
function fakeMap() {
    const map = new Evented(); map.layers = new Set(); map.panes = {};
    map.getPane = name => map.panes[name];
    map.createPane = name => (map.panes[name] = {style: {}});
    map.hasLayer = l => map.layers.has(l);
    map.addLayer = l => { if (!map.layers.has(l)) { map.layers.add(l); l.adds++; l.fire('add'); } };
    map.removeLayer = l => { if (map.layers.delete(l)) l.fire('remove'); };
    map.getBounds = () => box();
    return map;
}
function fakeLeaflet() {
    const L = {CRS: {EPSG3857: {code: 'EPSG:3857'}}, TileLayer: TestLayer,
        tileLayer: (url, options) => new TestLayer(url, options),
        geoJSON: (data, options) => new TestLayer(null, options), circleMarker: () => ({})};
    L.tileLayer.wms = (url, options) => new TestLayer(url, options);
    return L;
}

test('ArcGIS export uses Web Mercator, correct imageSR, and sublayer selection', () => {
    const url = new URL(api.exportURL({url: 'https://example.org/MapServer/7?f=pjson'}, {x: 0, y: 0, z: 0}, 123));
    assert.equal(url.pathname, '/MapServer/export');
    assert.equal(url.searchParams.get('imageSR'), '3857');
    assert.equal(url.searchParams.get('bboxSR'), '3857');
    assert.equal(url.searchParams.get('layers'), 'show:7');
    assert.equal(url.searchParams.get('f'), 'image');
    assert.equal(url.searchParams.get('size'), '256,256');
    assert.equal(url.searchParams.get('_owrx_refresh'), '123');
    assert.deepEqual(url.searchParams.get('bbox').split(',').map(Math.round), [-20037508, -20037508, 20037508, 20037508]);
});
test('service URLs replace conflicting case-insensitive capability parameters', () => {
    const url = new URL(api.wfsURL({url: 'https://example.org/ows?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=9&map=public.map', layers: 'ns:roads', version: '2.0.0', max_features: 17}, [-118, 32, -116, 34]));
    assert.equal(url.searchParams.get('request'), 'GetFeature');
    assert.equal(url.searchParams.has('REQUEST'), false);
    assert.equal(url.searchParams.get('version'), '2.0.0');
    assert.equal(url.searchParams.get('typeNames'), 'ns:roads');
    assert.equal(url.searchParams.get('count'), '17');
    assert.equal(url.searchParams.get('map'), 'public.map');
    assert.match(url.searchParams.get('bbox'), /^-118,32,-116,34,urn:ogc:def:crs:OGC:1.3:CRS84$/);
});
test('WFS 1.0 and 1.1 use the appropriate longitude-first CRS', () => {
    const legacy = new URL(api.wfsURL({url: 'https://example.org/wfs', layers: 'roads'}, [-1, -2, 3, 4]));
    assert.equal(legacy.searchParams.get('srsName'), 'EPSG:4326');
    assert.equal(legacy.searchParams.get('typeName'), 'roads');
    assert.equal(legacy.searchParams.get('maxFeatures'), '2000');
    const newer = new URL(api.wfsURL({url: 'https://example.org/wfs', layers: 'roads', version: '1.1.0'}, [-1, -2, 3, 4]));
    assert.match(newer.searchParams.get('srsName'), /CRS84$/);
});
test('WMTS preserves matrix prefix and row/column order', () => {
    const url = new URL(api.wmtsURL({url: 'https://example.org/wmts', layers: 'imagery', matrix_set: 'EPSG:3857', matrix_prefix: 'EPSG:3857:'}, {z: 4, x: 7, y: 9}));
    assert.equal(url.searchParams.get('TILEMATRIX'), 'EPSG:3857:4');
    assert.equal(url.searchParams.get('TILECOL'), '7');
    assert.equal(url.searchParams.get('TILEROW'), '9');
    assert.equal(url.searchParams.get('TILEMATRIXSET'), 'EPSG:3857');
});
test('WPS builds explicit synchronous raw GeoJSON execution', () => {
    const url = new URL(api.wpsURL({url: 'https://example.org/wps?request=GetCapabilities', layers: 'demo:buffer', wps_inputs: 'distance=1;units=km', wps_output: 'geom'}));
    assert.equal(url.searchParams.get('request'), 'Execute');
    assert.equal(url.searchParams.get('identifier'), 'demo:buffer');
    assert.equal(url.searchParams.get('DataInputs'), 'distance=1;units=km');
    assert.equal(url.searchParams.get('RawDataOutput'), 'geom@mimeType=application/json');
});
test('dateline and world wrapping are split into valid longitude bounds', () => {
    assert.deepEqual(api.viewport(box(170, -10, 190, 10)), [[170, -10, 180, 10], [-180, -10, -170, 10]]);
    assert.deepEqual(api.viewport(box(530, -10, 550, 10)), [[170, -10, 180, 10], [-180, -10, -170, 10]]);
    assert.deepEqual(api.viewport(box(-300, -100, 300, 100)), [[-180, -90, 180, 90]]);
});
test('GeoJSON is bounded and rejects projected or malformed coordinates', () => {
    assert.equal(api.featureCollection(fc([1, 2, 3]), 2).features.length, 2);
    for (const coordinates of ([300000, 500000], [NaN, 1], [1], [[1, 2]], [])) {
        const data = fc([1]); data.features[0].geometry.coordinates = coordinates;
        assert.throws(() => api.featureCollection(data));
    }
    assert.throws(() => api.featureCollection({...fc([1]), crs: {properties: {name: 'EPSG:3857'}}}), /projected/);
    const data = fc([1]); data.features[0].geometry = {type: 'Polygon', coordinates: [[0, 0], [1, 1]]};
    assert.throws(() => api.featureCollection(data));
});
test('anonymous JSON requests omit credentials and report service errors safely', async () => {
    let options;
    global.fetch = async (url, opts) => { options = opts; return response(fc([1])); };
    assert.equal((await api.getJSON('https://example.org/data')).features.length, 1);
    assert.equal(options.credentials, 'omit');
    global.fetch = async () => response({error: {message: '<script>alert(1)</script>'}});
    await assert.rejects(api.getJSON('https://example.org/data'), /rejected the request/);
});
test('JSON parsing, HTTP errors, and response size limits are enforced', async () => {
    global.fetch = async () => new Response('<ServiceException>not JSON</ServiceException>');
    await assert.rejects(api.getJSON('https://example.org/data'), /did not return JSON/);
    global.fetch = async () => new Response('', {status: 403});
    await assert.rejects(api.getJSON('https://example.org/data'), /HTTP 403/);
    global.fetch = async () => new Response('{}', {headers: {'content-length': String(6 * 1024 * 1024)}});
    await assert.rejects(api.getJSON('https://example.org/data'), /5 MiB/);
    global.fetch = async () => new Response(' '.repeat(5 * 1024 * 1024 + 1));
    await assert.rejects(api.getJSON('https://example.org/data'), /5 MiB/);
});
test('requests reject mixed content and embedded credentials before fetching', async () => {
    let requests = 0; global.fetch = async () => { requests++; return response({}); };
    global.location = {protocol: 'https:'};
    await assert.rejects(api.getJSON('http://example.org/data'), /insecure/);
    await assert.rejects(api.getJSON('https://user:pass@example.org/data'), /credentials/);
    assert.equal(requests, 0);
});
test('request timeout is reported distinctly from user cancellation', async () => {
    global.setTimeout = (fn, ms, ...args) => originalTimeout(fn, ms === 20000 ? 5 : ms, ...args);
    global.fetch = (url, options) => new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(new DOMException('cancel', 'AbortError'))));
    await assert.rejects(api.getJSON('https://example.org/data'), /timed out/);
    const c = new AbortController(); c.abort();
    await assert.rejects(api.getJSON('https://example.org/data', c.signal), {name: 'AbortError'});
});
test('ArcGIS ID batches respect the feature cap and output spatial reference', async () => {
    const urls = [];
    global.fetch = async url => {
        const u = new URL(url); urls.push(u);
        if (u.searchParams.get('returnIdsOnly') === 'true') return response({objectIds: [1, 2, 3, 4]});
        return response(fc(u.searchParams.get('objectIds').split(',').map(Number)));
    };
    const result = await api.loadFeatures({type: 'arcgis-feature', url: 'https://example.org/FeatureServer/0', max_features: 3}, box());
    assert.equal(result.data.features.length, 3); assert.equal(result.limited, true);
    assert.equal(urls.length, 2);
    assert.equal(urls[1].searchParams.get('outSR'), '4326');
    assert.equal(urls[1].searchParams.get('f'), 'geojson');
    assert.equal(urls[0].searchParams.get('inSR'), '4326');
});
test('ArcGIS root service discovery skips group layers and queries numbered children', async () => {
    const urls = [];
    global.fetch = async url => {
        const u = new URL(url); urls.push(u);
        if (u.pathname.endsWith('FeatureServer')) return response({layers: [{id: 0, type: 'Group Layer', subLayerIds: [1]}, {id: 1, type: 'Feature Layer'}]});
        if (u.searchParams.get('returnIdsOnly') === 'true') return response({objectIds: [99]});
        return response(fc([99]));
    };
    const result = await api.loadFeatures({type: 'arcgis-feature', url: 'https://example.org/FeatureServer'}, box());
    assert.equal(result.data.features.length, 1);
    assert.equal(urls[1].pathname, '/FeatureServer/1/query');
});
test('WFS dateline requests deduplicate IDs and show incomplete-result warning', async () => {
    const urls = [];
    global.fetch = async url => { urls.push(url); return response({...fc([1, 2]), numberMatched: 20}); };
    const result = await api.loadFeatures({type: 'wfs', url: 'https://example.org/wfs', layers: 'roads'}, box(170, -10, 190, 10));
    assert.equal(urls.length, 2); assert.equal(result.data.features.length, 2); assert.equal(result.limited, true);
});
test('toggle off while creating an asynchronous layer never adds it later', async () => {
    const map = fakeMap(), waiting = deferred(), layer = new TestLayer();
    const entry = new api.Entry({id: 'test'}, () => waiting.promise, () => {});
    const pending = entry.activate(map); entry.deactivate(map); waiting.resolve(layer); await pending;
    assert.equal(map.layers.size, 0);
});
test('rapid on/off/on shares a pending creation and adds only the latest selection', async () => {
    const map = fakeMap(), waiting = deferred(), layer = new TestLayer(); let creates = 0;
    const entry = new api.Entry({id: 'test'}, () => { creates++; return waiting.promise; }, () => {});
    const first = entry.activate(map); entry.deactivate(map); const latest = entry.activate(map);
    waiting.resolve(layer); await Promise.all([first, latest]);
    assert.equal(creates, 1); assert.equal(layer.adds, 1); assert.equal(map.layers.size, 1);
});
test('one failed layer does not prevent another from activating', async () => {
    const map = fakeMap(), reports = [];
    const bad = new api.Entry({id: 'bad'}, async () => { throw new Error('bad service'); }, (...v) => reports.push(v));
    const good = new api.Entry({id: 'good'}, async () => new TestLayer(), () => {});
    await Promise.all([bad.activate(map), good.activate(map)]);
    assert.equal(map.layers.size, 1); assert.equal(reports[0][0], 'error');
});
test('disabled and non-refreshing layers do not make periodic refresh requests', async () => {
    const map = fakeMap(); let refreshes = 0; const layer = new TestLayer(); layer.owrxRefresh = () => refreshes++;
    const entry = new api.Entry({refresh: 0}, async () => layer, () => {});
    await entry.activate(map); entry.refresh(map); assert.equal(refreshes, 0);
    entry.refresh(map, true); assert.equal(refreshes, 1);
    entry.deactivate(map); entry.refresh(map, true); assert.equal(refreshes, 1);
});
test('vector layers are lazy and newer requests win over stale responses', async () => {
    global.document = {hidden: false};
    const requests = [];
    global.fetch = (url, options) => { const d = deferred(); requests.push({...d, options}); return d.promise; };
    const map = fakeMap(), reports = [];
    const layer = await api.createLayer(fakeLeaflet(), map, {id: 'custom-a', type: 'geojson', url: 'https://example.org/data'}, (...v) => reports.push(v));
    assert.equal(requests.length, 0);
    layer.addTo(map); assert.equal(requests.length, 1);
    const second = layer.owrxRefresh(); assert.equal(requests[0].options.signal.aborted, true);
    requests[1].resolve(response(fc([2]))); await second;
    requests[0].resolve(response(fc([1]))); await tick(); await tick();
    assert.equal(layer.data.features[0].id, 2); assert.equal(layer.clears, 1);
    map.removeLayer(layer);
});
test('removing a vector layer cancels work and prevents late results from repopulating it', async () => {
    global.document = {hidden: false}; const waiting = deferred(); let signal;
    global.fetch = (url, options) => { signal = options.signal; return waiting.promise; };
    const map = fakeMap();
    const layer = await api.createLayer(fakeLeaflet(), map, {type: 'geojson', url: 'https://example.org/data'}, () => {});
    layer.addTo(map); map.removeLayer(layer); assert.equal(signal.aborted, true);
    waiting.resolve(response(fc([1]))); await tick(); await tick();
    assert.equal(layer.clears, 0);
});
test('malformed vector refresh retains the previous successful dataset', async () => {
    global.document = {hidden: false}; global.fetch = async () => response(fc([1]));
    const map = fakeMap(), reports = [];
    const layer = await api.createLayer(fakeLeaflet(), map, {type: 'geojson', url: 'https://example.org/data'}, (...v) => reports.push(v));
    layer.addTo(map); await tick(); await tick();
    const malformed = fc([2]); malformed.features[0].geometry.coordinates = [1000000, 1000000];
    global.fetch = async () => response(malformed); await layer.owrxRefresh();
    assert.equal(layer.data.features[0].id, 1); assert.equal(layer.clears, 1);
    assert.equal(reports.at(-1)[0], 'error'); map.removeLayer(layer);
});
test('hidden documents skip vector refreshes', async () => {
    global.document = {hidden: true}; let count = 0; global.fetch = async () => { count++; return response(fc([1])); };
    const map = fakeMap();
    const layer = await api.createLayer(fakeLeaflet(), map, {type: 'geojson', url: 'https://example.org/data'}, () => {});
    layer.addTo(map); await layer.owrxRefresh(); assert.equal(count, 0); map.removeLayer(layer);
});
test('WMS uses EPSG3857 and transparent images; tile errors remain visible until a clean load', async () => {
    const map = fakeMap(), L = fakeLeaflet(), reports = [];
    const layer = await api.createLayer(L, map, {type: 'wms', url: 'https://example.org/wms?REQUEST=GetCapabilities', layers: 'clouds', version: '1.3.0'}, (...v) => reports.push(v));
    assert.equal(layer.options.crs, L.CRS.EPSG3857); assert.equal(layer.options.transparent, true);
    assert.equal(layer.options.version, '1.3.0'); assert.equal(new URL(layer.url).searchParams.has('REQUEST'), false);
    layer.fire('loading').fire('tileerror').fire('load'); assert.equal(reports.at(-1)[0], 'error');
    layer.fire('loading').fire('load'); assert.equal(reports.at(-1)[0], 'ok');
});
test('custom basemap vectors stay below radio markers; attribution is escaped', async () => {
    const map = fakeMap();
    const layer = await api.createLayer(fakeLeaflet(), map, {type: 'geojson', url: 'https://example.org/data', basemap: true, attribution: '<img src=x onerror=bad()>'}, () => {});
    assert.equal(map.getPane('owrx-basemaps').style.zIndex, 200);
    assert.equal(layer.options.pane, 'owrx-basemaps');
    assert.match(layer.options.attribution, /^&lt;img/);
});
test('XYZ cache refresh preserves placeholders including subdomains and retina suffix', async () => {
    const layer = await api.createLayer(fakeLeaflet(), fakeMap(), {type: 'xyz', url: 'https://{s}.example.org/{z}/{x}/{y}{r}.png', refresh: 300}, () => {});
    layer.owrxRefresh();
    assert.match(layer.url, /\{s\}\.example\.org\/\{z\}\/\{x\}\/\{y\}\{r\}\.png/);
    assert.match(layer.url, /_owrx_refresh=/);
});

test('short ArcGIS batches are explicitly marked incomplete even without a transfer-limit flag', async () => {
    global.fetch = async url => new URL(url).searchParams.get('returnIdsOnly') === 'true'
        ? response({objectIds: [1, 2, 3]}) : response(fc([1]));
    const result = await api.loadFeatures({type: 'arcgis-feature', url: 'https://example.org/FeatureServer/0', max_features: 10}, box());
    assert.equal(result.data.features.length, 1); assert.equal(result.limited, true);
});
