/* node --test tests/map_legend.test.js (no npm dependencies) */
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const api = require('../htdocs/lib/MapLayers.js');
const legend = require('../htdocs/lib/MapLegend.js');
const picker = require('../htdocs/lib/settings/MapInput.js');
const box = (w, s, e, n) => ({getWest: () => w, getSouth: () => s, getEast: () => e, getNorth: () => n});
const point = (lng, lat, options = {}) => ({getLatLng: () => ({lat, lng}), options});
function view(bounds = box(-120, 30, -110, 40), zoom = 8) {
    return {getBounds: () => bounds, getZoom: () => zoom, hasLayer: l => !l.hidden};
}
const metadata = {layers: [
    {id: 0, parentLayerId: -1, defaultVisibility: true},
    {id: 1, parentLayerId: 0, defaultVisibility: true},
    {id: 2, parentLayerId: 0, defaultVisibility: false},
    {id: 3, parentLayerId: -1, defaultVisibility: true, minScale: 10000},
]};
const response = {layers: [1, 2, 3].map(id => ({layerId: id, layerName: 'Layer ' + id, legend: [{label: 'symbol'}]}))};

test('receiver coordinates parse finite values and preserve precision', () => {
    assert.deepEqual(picker.position('32.712345678', '-117.123456789'), {lat: 32.712345678, lng: -117.123456789});
    assert.deepEqual(picker.position('0', '0'), {lat: 0, lng: 0});
});
test('receiver coordinates reject blanks, infinities and the server open-range boundaries', () => {
    for (const values of [['', 0], [' ', 1], ['abc', 0], [NaN, 0], [90, 0], [-90, 0], [0, 180], [0, -180], [0, Infinity]])
        assert.equal(picker.position(...values), null);
});
test('map selection wraps repeated worlds and stays within server coordinate ranges', () => {
    assert.deepEqual(picker.pickedPosition({lat: 32.1234567, lng: 243}), {lat: 32.123457, lng: -117});
    assert.ok(picker.pickedPosition({lat: 90, lng: 180}).lat < 90);
    assert.ok(picker.pickedPosition({lat: -90, lng: -180}).lng > -180);
});
test('legend image URLs reject executable schemes, secrets and credentials', () => {
    for (const url of ['javascript:alert(1)', 'data:image/svg+xml,test', '//example.org/x', 'https://u:p@example.org/x', 'https://example.org/x#y', 'https://example.org/?TOKEN=x'])
        assert.throws(() => legend.imageURL(url));
    assert.equal(legend.imageURL('https://example.org/legend.png?map=public'), 'https://example.org/legend.png?map=public');
});
test('HTTPS pages reject HTTP legend images', () => {
    global.location = {protocol: 'https:'};
    try { assert.throws(() => legend.imageURL('http://example.org/legend.png')); }
    finally { delete global.location; }
});
test('WMS legends preserve routing parameters and use one selected style per layer', () => {
    const images = legend.wmsImages({url: 'https://example.org/ows?map=public&SERVICE=WMS&REQUEST=GetCapabilities&LAYERS=old',
        layers: 'rain, cloud', style: 'blue, gray', version: '1.3.0'}, 8, api);
    assert.equal(images.length, 2);
    for (let i = 0; i < 2; i++) {
        const p = new URL(images[i].url).searchParams;
        assert.equal(p.get('REQUEST'), 'GetLegendGraphic'); assert.equal(p.get('map'), 'public');
        assert.equal(p.get('VERSION'), '1.3.0'); assert.equal(p.get('FORMAT'), 'image/png');
        assert.equal(p.get('LAYER'), ['rain', 'cloud'][i]); assert.equal(p.get('STYLE'), ['blue', 'gray'][i]);
        assert.equal(p.has('LAYERS'), false); assert.ok(Number(p.get('SCALE')) > 0);
    }
});
test('WMS legend fan-out is bounded', () => {
    assert.equal(legend.wmsImages({url: 'https://example.org/wms', layers: Array(30).fill('x').join(',')}, 3, api).length, 10);
});
test('ArcGIS legend default visibility excludes hidden and out-of-scale sublayers', () => {
    assert.deepEqual(legend.arcgisGroups(response, metadata, [], 20000).groups.map(g => g.id), [1]);
});
test('ArcGIS explicit layer selection overrides default visibility', () => {
    assert.deepEqual(legend.arcgisGroups(response, metadata, [2], 20000).groups.map(g => g.id), [2]);
});
test('ArcGIS selected groups expand descendants, not unrelated layers', () => {
    assert.deepEqual(legend.arcgisGroups(response, metadata, [0], 20000).groups.map(g => g.id), [1, 2]);
});
test('ArcGIS scale honors parent and service limits', () => {
    const data = structuredClone(metadata); data.layers[0].minScale = 500;
    assert.equal(legend.arcgisGroups(response, data, [1, 2], 1000).groups.length, 0);
    data.minScale = 500;
    assert.equal(legend.arcgisGroups(response, data, [3], 1000).groups.length, 0);
    assert.equal(legend.inScale({minScale: 1000, maxScale: 100}, 100), true);
    assert.equal(legend.inScale({minScale: 1000, maxScale: 100}, 99), false);
    assert.equal(legend.inScale({minScale: 'bad'}, 100), false);
});
test('ArcGIS invalid hierarchy and oversized metadata fail independently', () => {
    const data = structuredClone(metadata); data.layers[0].parentLayerId = 1;
    assert.throws(() => legend.arcgisGroups(response, data, [], 1000), /hierarchy/);
    assert.throws(() => legend.arcgisGroups({}, data, [], 1000), /metadata/);
    assert.throws(() => legend.arcgisGroups({layers: Array(2049).fill({})}, metadata, [], 1000), /too many/);
});
test('ArcGIS symbol cap is explicit rather than unbounded', () => {
    const data = {layers: [{layerId: 1, layerName: 'Many', legend: Array(300).fill({label: 'x'})}]};
    const result = legend.arcgisGroups(data, metadata, [1], 1000);
    assert.equal(result.groups[0].symbols.length, 256); assert.equal(result.truncated, true);
});
test('ArcGIS PNG symbols use inline data without executing remote HTML/SVG', () => {
    assert.equal(legend.symbolImage({imageData: 'YQ==', contentType: 'image/png'}, 'https://example.org/MapServer', 0), 'data:image/png;base64,YQ==');
    assert.equal(legend.symbolImage({imageData: 'YQ==', contentType: 'image/svg+xml'}, 'https://example.org/MapServer', 0), null);
    assert.equal(legend.symbolImage({imageData: '" onerror=x', contentType: 'image/png'}, 'https://example.org/MapServer', 0), null);
});
test('ArcGIS relative symbol URLs resolve to the selected layer images resource', () => {
    assert.equal(legend.symbolImage({url: 'symbol.png'}, 'https://example.org/a/MapServer?route=one', 2), 'https://example.org/a/MapServer/2/images/symbol.png?route=one');
    assert.throws(() => legend.symbolImage({url: 'javascript:alert(1)'}, 'https://example.org/MapServer', 0));
});
test('legend follows actual map attachment, opacity and supported zoom', () => {
    const entry = {desired: true, layer: {options: {maxZoom: 12}}, source: {}};
    assert.equal(legend.isActive(entry, view()), true);
    entry.desired = false; assert.equal(legend.isActive(entry, view()), false);
    entry.desired = true; entry.source.opacity = 0; assert.equal(legend.isActive(entry, view()), false);
    entry.source.opacity = 1; entry.layer.hidden = true; assert.equal(legend.isActive(entry, view()), false);
    entry.layer.hidden = false; assert.equal(legend.isActive(entry, view(undefined, 13)), false);
});
test('vector legend samples only already-loaded visible features in the viewport', () => {
    const features = [point(-117, 33), point(0, 0), Object.assign(point(-115, 35), {hidden: true})];
    const samples = legend.vectorSwatches({eachLayer: f => features.forEach(f)}, view(), api);
    assert.equal(samples.length, 1); assert.equal(samples[0].kind, 'point');
    assert.equal(samples[0].style.color, '#3388ff');
});
test('vector legend matches actual polygon, line and point styling', () => {
    const features = [point(-117, 33, {color: '#f00', fillColor: '#0f0', opacity: .5}),
        {getBounds: () => box(-118, 32, -116, 34), feature: {geometry: {type: 'Polygon'}}, options: {color: '#444', fillOpacity: .6}},
        {getBounds: () => box(-118, 32, -116, 34), feature: {geometry: {type: 'LineString'}}, options: {color: '#999', weight: 2}}];
    const samples = legend.vectorSwatches({eachLayer: f => features.forEach(f)}, view(), api);
    assert.deepEqual(samples.map(s => s.kind), ['point', 'polygon', 'line']);
    assert.equal(samples[0].style.fillColor, '#0f0'); assert.equal(samples[1].style.fillOpacity, .6);
    assert.equal(samples[2].style.fillOpacity, 0);
});
test('vector legend handles antimeridian viewports and repeated worlds', () => {
    const features = [point(-179, 0), point(179, 0), point(181, 0), point(0, 0)];
    assert.equal(legend.vectorSwatches({eachLayer: f => features.forEach(f)}, view(box(170, -10, 190, 10)), api).length, 1);
});
test('invisible styles and CSS injection do not produce false/unsafe swatches', () => {
    const features = [point(-117, 33, {stroke: false, fill: false}), point(-117, 33, {color: 'url(javascript:alert(1))'})];
    const samples = legend.vectorSwatches({eachLayer: f => features.forEach(f)}, view(), api);
    assert.equal(samples.length, 1); assert.equal(samples[0].style.color, '#3388ff');
});
test('existing ArcGIS export and WFS query adapters retain required requests', () => {
    const exp = new URL(api.exportURL({url: 'https://example.org/MapServer/3'}, {x: 1, y: 1, z: 2}, 5));
    assert.equal(exp.searchParams.get('layers'), 'show:3'); assert.equal(exp.searchParams.get('imageSR'), '3857');
    const wfs = new URL(api.wfsURL({url: 'https://example.org/wfs', layers: 'roads', version: '2.0.0'}, [1, 2, 3, 4]));
    assert.equal(wfs.searchParams.get('request'), 'GetFeature'); assert.equal(wfs.searchParams.get('typeNames'), 'roads');
});
test('existing Entry cancellation does not resurrect a removed layer', async () => {
    let resolve, added = 0;
    const entry = new api.Entry({}, () => new Promise(r => { resolve = r; }), () => {});
    const map = {hasLayer: () => false};
    const promise = entry.activate(map); entry.deactivate(map);
    resolve({addTo: () => { added++; }}); await promise;
    assert.equal(added, 0);
});
