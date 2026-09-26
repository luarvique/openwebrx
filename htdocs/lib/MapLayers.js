/* Anonymous GIS layers for the Leaflet client. No proxy and no executable remote data. */
(function (root, factory) {
    const api = factory(root);
    if (typeof module === 'object' && module.exports) module.exports = api;
    else root.OWRXMapLayers = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (root) {
    'use strict';
    const MAX_BYTES = 5 * 1024 * 1024;
    const TIMEOUT = 20000;
    const CONTROL_PARAMS = ['service', 'request', 'version', 'layers', 'styles', 'format', 'transparent',
        'bbox', 'width', 'height', 'srs', 'crs', 'typename', 'typenames', 'outputformat', 'srsname',
        'count', 'maxfeatures', 'startindex', 'f', 'tilematrix', 'tilematrixset', 'tilerow', 'tilecol',
        'layer', 'style', 'identifier', 'datainputs', 'rawdataoutput'];
    const escapeText = text => String(text || '').replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
    const abortError = () => new DOMException('Request cancelled', 'AbortError');
    function checkURL(raw) {
        const url = new URL(raw);
        if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password || url.hash)
            throw new Error('Use a public HTTP(S) URL without credentials or fragments.');
        if (root.location && root.location.protocol === 'https:' && url.protocol !== 'https:')
            throw new Error('This HTTPS map cannot load an insecure HTTP service.');
        return url;
    }
    function serviceURL(raw) {
        const url = checkURL(raw);
        Array.from(url.searchParams.keys()).forEach(key => {
            if (CONTROL_PARAMS.includes(key.toLowerCase())) url.searchParams.delete(key);
        });
        return url;
    }
    function queryURL(raw, params) {
        const url = checkURL(raw);
        const keys = Object.keys(params).map(k => k.toLowerCase());
        Array.from(url.searchParams.keys()).forEach(k => { if (keys.includes(k.toLowerCase())) url.searchParams.delete(k); });
        Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== '') url.searchParams.set(k, String(v)); });
        return url.href;
    }
    function childURL(raw, child) {
        const url = serviceURL(raw);
        url.pathname = url.pathname.replace(/\/$/, '') + '/' + child;
        return url.href;
    }
    async function getJSON(url, signal, cache = 'no-cache') {
        checkURL(url);
        if (signal && signal.aborted) throw abortError();
        const controller = new AbortController();
        let timedOut = false;
        const cancel = () => controller.abort();
        if (signal) signal.addEventListener('abort', cancel, {once: true});
        const timer = setTimeout(() => { timedOut = true; controller.abort(); }, TIMEOUT);
        try {
            const response = await root.fetch(url, {signal: controller.signal, credentials: 'omit',
                headers: {Accept: 'application/geo+json, application/json'}, referrerPolicy: 'no-referrer', cache});
            if (!response.ok) throw new Error('Service returned HTTP ' + response.status + '.');
            if (Number(response.headers.get('content-length')) > MAX_BYTES) throw new Error('Service response exceeds 5 MiB.');
            let text;
            if (response.body && response.body.getReader) {
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let length = 0; text = '';
                while (true) {
                    const chunk = await reader.read();
                    if (chunk.done) break;
                    length += chunk.value.byteLength;
                    if (length > MAX_BYTES) { await reader.cancel(); throw new Error('Service response exceeds 5 MiB.'); }
                    text += decoder.decode(chunk.value, {stream: true});
                }
                text += decoder.decode();
            } else {
                text = await response.text();
                if (new TextEncoder().encode(text).length > MAX_BYTES) throw new Error('Service response exceeds 5 MiB.');
            }
            let data;
            try { data = JSON.parse(text); } catch (_) { throw new Error('Service did not return JSON. Check GeoJSON support and service parameters.'); }
            if (data && data.error) throw new Error('The GIS service rejected the request. Check its URL, layers and access permissions.');
            return data;
        } catch (error) {
            if (timedOut) throw new Error('Service request timed out after 20 seconds.');
            if (signal && signal.aborted) throw abortError();
            if (error instanceof TypeError) throw new Error('Service cannot be reached. Check HTTPS, network access and CORS.');
            throw error;
        } finally {
            clearTimeout(timer);
            if (signal) signal.removeEventListener('abort', cancel);
        }
    }
    function viewport(bounds) {
        let west = bounds.getWest(), east = bounds.getEast();
        const south = Math.max(-90, bounds.getSouth()), north = Math.min(90, bounds.getNorth());
        if (![west, east, south, north].every(Number.isFinite) || south > north) throw new Error('Invalid map extent.');
        if (east < west) east += 360;
        const width = east - west;
        if (width >= 360) return [[-180, south, 180, north]];
        west = ((west + 180) % 360 + 360) % 360 - 180;
        east = west + width;
        return east > 180 ? [[west, south, 180, north], [-180, south, east - 360, north]] : [[west, south, east, north]];
    }
    function tileBounds(coords) {
        const half = 20037508.342789244, span = 2 * half / Math.pow(2, coords.z);
        const west = -half + coords.x * span, north = half - coords.y * span;
        return [west, north - span, west + span, north].map(n => n.toFixed(8)).join(',');
    }
    function arcgisParts(source) {
        const url = serviceURL(source.url);
        const match = url.pathname.match(/\/(MapServer|FeatureServer)(?:\/(\d+))?\/?$/i);
        if (!match) throw new Error('Expected an ArcGIS MapServer or FeatureServer URL.');
        url.pathname = url.pathname.slice(0, match.index) + '/' + match[1];
        const ids = source.layers ? source.layers.split(',').map(Number) : match[2] ? [Number(match[2])] : [];
        return {url: url.href, ids};
    }
    function exportURL(source, coords, bucket) {
        const service = arcgisParts(source);
        return queryURL(childURL(service.url, 'export'), {f: 'image', bbox: tileBounds(coords),
            bboxSR: 3857, imageSR: 3857, size: '256,256', format: 'png32', transparent: true,
            layers: service.ids.length ? 'show:' + service.ids.join(',') : '', _owrx_refresh: bucket});
    }
    function wmtsURL(source, coords, bucket) {
        return queryURL(serviceURL(source.url).href, {SERVICE: 'WMTS', REQUEST: 'GetTile', VERSION: '1.0.0',
            LAYER: source.layers, STYLE: source.style || 'default', FORMAT: source.format || 'image/png',
            TILEMATRIXSET: source.matrix_set, TILEMATRIX: (source.matrix_prefix || '') + coords.z,
            TILEROW: coords.y, TILECOL: coords.x, _owrx_refresh: bucket});
    }
    function wfsURL(source, box) {
        const version = source.version || '1.0.0';
        const crs = version === '1.0.0' ? 'EPSG:4326' : 'urn:ogc:def:crs:OGC:1.3:CRS84';
        const params = {service: 'WFS', request: 'GetFeature', version,
            outputFormat: source.format || 'application/json', srsName: crs,
            bbox: box.join(',') + ',' + crs};
        params[version === '2.0.0' ? 'typeNames' : 'typeName'] = source.layers;
        params[version === '2.0.0' ? 'count' : 'maxFeatures'] = source.max_features || 2000;
        return queryURL(serviceURL(source.url).href, params);
    }
    function wpsURL(source) {
        return queryURL(serviceURL(source.url).href, {service: 'WPS', request: 'Execute', version: '1.0.0',
            identifier: source.layers, DataInputs: source.wps_inputs || '',
            RawDataOutput: (source.wps_output || 'result') + '@mimeType=' + (source.format || 'application/json')});
    }
    function featureCollection(data, limit = 2000) {
        if (!data || typeof data !== 'object') throw new Error('Invalid GeoJSON response.');
        if (data.crs) {
            const name = data.crs.properties && data.crs.properties.name;
            if (typeof name !== 'string' || !/(?:CRS84|4326)$/i.test(name))
                throw new Error('GeoJSON must use longitude/latitude in WGS84, not a projected CRS.');
        }
        const features = data.type === 'FeatureCollection' ? data.features : data.type === 'Feature' ? [data] : null;
        if (!Array.isArray(features)) throw new Error('Expected a GeoJSON FeatureCollection or Feature (not GML/XML).');
        let positions = 0;
        function coordinates(c, depth) {
            if (!Array.isArray(c)) throw new Error('Invalid GeoJSON coordinates.');
            if (depth === 0) {
                positions++;
                if (positions > 200000) throw new Error('Too many coordinates; use a smaller extent or simpler data.');
                if (c.length < 2 || c.length > 4 || !c.every(Number.isFinite) || Math.abs(c[0]) > 180 || Math.abs(c[1]) > 90)
                    throw new Error('GeoJSON coordinates must be finite WGS84 longitude/latitude.');
            } else c.forEach(v => coordinates(v, depth - 1));
        }
        function geometry(g, depth = 0) {
            if (g === null) return;
            if (!g || depth > 4) throw new Error('Invalid GeoJSON geometry.');
            if (g.type === 'GeometryCollection') {
                if (!Array.isArray(g.geometries)) throw new Error('Invalid GeoJSON geometry collection.');
                g.geometries.forEach(v => { if (!v) throw new Error('Invalid GeoJSON geometry collection.'); geometry(v, depth + 1); });
            } else {
                const depths = {Point: 0, MultiPoint: 1, LineString: 1, MultiLineString: 2, Polygon: 2, MultiPolygon: 3};
                if (!Object.prototype.hasOwnProperty.call(depths, g.type)) throw new Error('Unsupported GeoJSON geometry.');
                coordinates(g.coordinates, depths[g.type]);
            }
        }
        const selected = features.slice(0, limit);
        selected.forEach(f => {
            if (!f || f.type !== 'Feature') throw new Error('Invalid GeoJSON feature.');
            geometry(f.geometry);
        });
        return {type: 'FeatureCollection', features: selected};
    }
    async function loadFeatures(source, bounds, signal) {
        const limit = source.max_features || 2000;
        const features = [], seen = new Set();
        let limited = false;
        function collect(data, namespace) {
            const parsed = featureCollection(data, limit);
            if ((data.features && data.features.length >= limit) || data.exceededTransferLimit ||
                (data.properties && data.properties.exceededTransferLimit) || Number(data.numberMatched) > parsed.features.length) limited = true;
            parsed.features.forEach(f => {
                const key = f.id == null ? null : namespace + ':' + f.id;
                if (key && seen.has(key)) return;
                if (key) seen.add(key);
                if (features.length < limit) features.push(f); else limited = true;
            });
        }
        if (source.type === 'arcgis-feature') {
            const service = arcgisParts(source);
            let ids = service.ids;
            if (!ids.length) {
                const metadata = await getJSON(queryURL(service.url, {f: 'json'}), signal);
                if (!Array.isArray(metadata.layers)) throw new Error('ArcGIS service has no discoverable feature layers.');
                const candidates = metadata.layers.filter(l => Number.isInteger(l.id) && !l.subLayerIds && !['Group Layer', 'Raster Layer'].includes(l.type));
                limited = candidates.length > 10;
                ids = candidates.slice(0, 10).map(l => l.id);
            }
            if (!ids.length) throw new Error('Select at least one queryable ArcGIS layer.');
            for (const id of ids) {
                const endpoint = childURL(service.url, id + '/query');
                const objectIds = new Set();
                for (const box of viewport(bounds)) {
                    const data = await getJSON(queryURL(endpoint, {f: 'json', where: '1=1', returnIdsOnly: true,
                        geometry: JSON.stringify({xmin: box[0], ymin: box[1], xmax: box[2], ymax: box[3], spatialReference: {wkid: 4326}}),
                        geometryType: 'esriGeometryEnvelope', inSR: 4326, spatialRel: 'esriSpatialRelIntersects'}), signal);
                    if (data.objectIds !== null && !Array.isArray(data.objectIds)) throw new Error('ArcGIS layer does not support object ID queries.');
                    (data.objectIds || []).forEach(n => {
                        if (!Number.isSafeInteger(n)) throw new Error('Invalid ArcGIS object ID.');
                        objectIds.add(n);
                    });
                }
                const remaining = limit - features.length;
                const selected = Array.from(objectIds).sort((a, b) => a - b).slice(0, remaining);
                if (objectIds.size > remaining) limited = true;
                for (let offset = 0; offset < selected.length; offset += 100) {
                    const batch = selected.slice(offset, offset + 100);
                    const data = await getJSON(queryURL(endpoint, {f: 'geojson', objectIds: batch.join(','),
                        outFields: '*', outSR: 4326, returnGeometry: true, returnZ: false, returnM: false}), signal);
                    if (Array.isArray(data.features) && data.features.length < batch.length) limited = true;
                    collect(data, String(id));
                }
                if (features.length >= limit) { limited = true; break; }
            }
        } else if (source.type === 'wfs') {
            for (const box of viewport(bounds)) collect(await getJSON(wfsURL(source, box), signal), source.layers);
        } else {
            collect(await getJSON(source.type === 'wps' ? wpsURL(source) : source.url, signal, source.type === 'wps' ? 'no-store' : 'no-cache'), source.id);
        }
        return {data: {type: 'FeatureCollection', features}, limited};
    }
    function popup(feature) {
        const container = root.document.createElement('div');
        const properties = feature.properties;
        if (!properties || typeof properties !== 'object') { container.textContent = 'No attributes'; return container; }
        Object.entries(properties).slice(0, 30).forEach(([key, value]) => {
            const row = root.document.createElement('div');
            const label = root.document.createElement('strong'); label.textContent = key.slice(0, 120) + ': ';
            const text = root.document.createElement('span');
            text.textContent = String(typeof value === 'object' ? JSON.stringify(value) : value).slice(0, 1000);
            row.append(label, text); container.append(row);
        });
        return container;
    }
    function vectorLayer(L, map, source, report, options) {
        const layer = L.geoJSON(null, {pane: options.pane, attribution: options.attribution,
            style: {pane: options.pane, opacity: options.opacity, fillOpacity: options.opacity * 0.4},
            pointToLayer: (f, p) => L.circleMarker(p, {pane: options.pane, radius: 5, opacity: options.opacity, fillOpacity: options.opacity * 0.6}),
            onEachFeature: (f, l) => l.bindPopup(() => popup(f))});
        let generation = 0, controller = null, debounce = null, active = false;
        const viewportQuery = ['wfs', 'arcgis-feature'].includes(source.type);
        async function refresh() {
            if (!active || (root.document && root.document.hidden)) return;
            const current = ++generation;
            if (controller) controller.abort();
            controller = new AbortController();
            report('loading', 'Loading…');
            try {
                const result = await loadFeatures(source, map.getBounds(), controller.signal);
                if (!active || current !== generation) return;
                layer.clearLayers(); layer.addData(result.data);
                report(result.limited ? 'warning' : 'ok', result.data.features.length + ' features' +
                    (result.limited ? ' — limit reached; results may be incomplete' : '') + '. Retrieved ' + new Date().toLocaleTimeString());
            } catch (error) {
                if (active && current === generation && error.name !== 'AbortError')
                    report('error', error.message + ' Last successful data, if any, is retained.');
            }
        }
        const move = () => {
            if (controller) controller.abort();
            generation++;
            clearTimeout(debounce); debounce = setTimeout(refresh, 250);
        };
        layer.on('add', () => { active = true; if (viewportQuery) map.on('moveend', move); refresh(); });
        layer.on('remove', () => {
            active = false; generation++; if (controller) controller.abort(); clearTimeout(debounce);
            if (viewportQuery) map.off('moveend', move);
        });
        layer.owrxRefresh = refresh;
        return layer;
    }
    async function createLayer(L, map, source, report) {
        checkURL(source.url || 'https://example.invalid/');
        const pane = source.basemap ? 'owrx-basemaps' : 'owrx-overlays';
        if (!map.getPane(pane)) map.createPane(pane).style.zIndex = source.basemap ? 200 : 300;
        const options = Object.assign({}, source.options || source.config || {}, {
            pane, opacity: source.opacity == null ? 1 : source.opacity,
            attribution: source.trustedAttribution ? (source.options || source.config || {}).attribution : escapeText(source.attribution),
            maxZoom: 22
        });
        const nativeZoom = source.max_zoom == null ? (source.options || source.config || {}).maxZoom : source.max_zoom;
        if (nativeZoom != null) options.maxNativeZoom = nativeZoom;
        let layer;
        if (['arcgis-feature', 'wfs', 'geojson', 'wps'].includes(source.type)) return vectorLayer(L, map, source, report, options);
        if (source.createLayer) {
            layer = await source.createLayer();
            report('ok', 'Ready');
            return layer;
        }
        if (source.type === 'arcgis-map' || source.type === 'wmts') {
            const ServiceTiles = L.TileLayer.extend({getTileUrl: function (coords) {
                return source.type === 'arcgis-map' ? exportURL(source, coords, this.owrxBucket) : wmtsURL(source, coords, this.owrxBucket);
            }});
            layer = new ServiceTiles(source.url, options);
        } else if (source.type === 'wms') {
            layer = L.tileLayer.wms(serviceURL(source.url).href, Object.assign({}, options, {
                layers: source.layers, styles: source.style || '', version: source.version || '1.1.1',
                format: source.format || 'image/png', transparent: true, crs: L.CRS.EPSG3857
            }));
        } else {
            layer = L.tileLayer(source.url, Object.assign({}, options, {tms: Boolean(source.tms)}));
        }
        let failed = false;
        layer.on('loading', () => { failed = false; report('loading', 'Loading tiles…'); });
        layer.on('tileerror', () => { failed = true; report('error', 'Some tiles failed. Check service availability, coverage and parameters.'); });
        layer.on('load', () => { if (!failed) report('ok', 'Tiles retrieved ' + new Date().toLocaleTimeString() + ' (not observation time)'); });
        layer.owrxRefresh = () => {
            const bucket = Math.floor(Date.now() / (Math.max(60, source.refresh || 300) * 1000));
            if (source.type === 'wms') layer.setParams({_owrx_refresh: bucket});
            else if (source.type === 'arcgis-map' || source.type === 'wmts') { layer.owrxBucket = bucket; layer.redraw(); }
            else layer.setUrl(queryURL(source.url, {_owrx_refresh: bucket}).replace(/%7B/gi, '{').replace(/%7D/gi, '}'));
        };
        return layer;
    }
    function readConfig() {
        const element = root.document && root.document.getElementById('openwebrx-map-config');
        if (!element) return {};
        try { return JSON.parse(element.textContent); }
        catch (_) { return {map_config_error: 'Map configuration could not be read. Reload the page.'}; }
    }
    function preference(key, fallback) {
        try { const value = root.localStorage.getItem(key); return value === null ? fallback : JSON.parse(value); }
        catch (_) { return fallback; }
    }
    function savePreference(key, value) { try { root.localStorage.setItem(key, JSON.stringify(value)); } catch (_) { /* Storage may be disabled. */ } }
    class Entry {
        constructor(source, create, report) {
            this.source = source; this.create = create; this.report = report;
            this.desired = false; this.layer = null; this.pending = null; this.generation = 0; this.lastRefresh = 0;
        }
        async activate(map) {
            this.desired = true;
            const current = ++this.generation;
            try {
                if (!this.layer) {
                    if (!this.pending) this.pending = this.create().finally(() => { this.pending = null; });
                    this.layer = await this.pending;
                }
                if (!this.desired || current !== this.generation) return;
                this.layer.addTo(map); this.lastRefresh = Date.now();
            } catch (error) { if (this.desired && current === this.generation) this.report('error', error && error.message ? error.message : 'Layer could not load. Check the provider and retry.'); }
        }
        deactivate(map) { this.desired = false; this.generation++; if (this.layer && map.hasLayer(this.layer)) map.removeLayer(this.layer); }
        refresh(map, force = false) {
            if (!this.desired) return;
            if (!this.layer) { if (force) this.activate(map); return; }
            if (!map.hasLayer(this.layer) || !this.layer.owrxRefresh) return;
            if (force || (this.source.refresh && Date.now() - this.lastRefresh >= this.source.refresh * 1000)) {
                this.lastRefresh = Date.now(); this.layer.owrxRefresh();
            }
        }
    }
    function install(L, map, mapSources, extraLayers, config, weatherKey) {
        const doc = root.document, entries = [], bases = new Map();
        const select = doc.getElementById('openwebrx-map-source');
        const overlays = doc.getElementById('openwebrx-map-extralayers');
        select.replaceChildren(); overlays.replaceChildren();
        select.setAttribute('aria-label', 'Basemap');
        select.add(new Option('None (markers only)', 'none'));
        const status = doc.createElement('div'); status.className = 'owrx-layer-status'; status.setAttribute('aria-live', 'polite');
        overlays.after(status);
        const prefix = 'owrx-map-' + (config.revision || 'legacy') + '-';
        if (config.map_config_error) { const error = doc.createElement('p'); error.textContent = config.map_config_error; status.append(error); }
        function register(source) {
            const row = doc.createElement('div'); row.className = 'owrx-layer-message'; row.hidden = true;
            const text = doc.createElement('span');
            const retry = doc.createElement('button'); retry.type = 'button'; retry.textContent = source.type === 'wps' ? 'Execute again' : 'Retry';
            retry.hidden = true; row.append(text, retry); status.append(row);
            let entry;
            function report(level, message) {
                if (!entry.desired) return;
                row.hidden = false; row.dataset.level = level; text.textContent = source.name + ': ' + message + ' ';
                retry.hidden = level !== 'error';
            }
            entry = new Entry(source, () => createLayer(L, map, source, report), report);
            retry.addEventListener('click', () => entry.refresh(map, true));
            entry.hideStatus = () => { row.hidden = true; };
            entries.push(entry);
            if (source.basemap) {
                bases.set(source.id, entry);
                const option = new Option(source.name, source.id);
                if (source.info) option.title = source.info;
                select.add(option);
            } else {
                const label = doc.createElement('label'), check = doc.createElement('input'); check.type = 'checkbox';
                check.checked = source.type !== 'wps' && Boolean(preference(prefix + source.id, Boolean(source.visible)));
                check.addEventListener('change', () => {
                    if (source.type !== 'wps') savePreference(prefix + source.id, check.checked);
                    if (check.checked) entry.activate(map); else { entry.deactivate(map); entry.hideStatus(); }
                });
                label.append(check, doc.createTextNode(' ' + source.name)); overlays.append(label);
                if (check.checked) entry.activate(map);
            }
        }
        mapSources.forEach((source, index) => {
            const id = 'builtin-' + index;
            if (!config.map_basemaps || config.map_basemaps.includes(id))
                register(Object.assign({}, source, {id, type: 'xyz', basemap: true, trustedAttribution: true}));
        });
        (config.map_layers || []).filter(l => l.enabled).forEach(register);
        (config.weather_catalog || []).forEach(register);
        // Existing providers remain optional; anonymous weather never depends on the OWM key.
        extraLayers.forEach((source, index) => {
            if (source.name === 'WeatherRadar-USA') return; // Replaced by the HTTPS weather catalog.
            if (source.name === 'OpenWeatherMap' && (!config.map_openweather || !weatherKey)) return;
            if (source.name === 'OpenSeaMap' && config.map_seamarks === false) return;
            if (source.name === 'Maidenhead-QTH' && config.map_maidenhead === false) return;
            const item = Object.assign({}, source, {id: 'extra-' + index, type: 'xyz', basemap: false, trustedAttribution: true});
            item.options = Object.assign({}, source.options || source.config || {});
            if (source.name === 'OpenWeatherMap') {
                item.options.apikey = weatherKey;
                item.name += item.options.layer === 'clouds_new' ? ' clouds' : ' precipitation';
                item.refresh = 600;
            }
            register(item);
        });
        function changeBase(id, remember) {
            if (!bases.has(id)) id = 'none';
            bases.forEach((entry, key) => {
                if (key !== id) { entry.deactivate(map); entry.hideStatus(); }
            });
            select.value = id;
            if (bases.has(id)) bases.get(id).activate(map);
            if (remember) savePreference(prefix + 'base', id);
        }
        let initial = preference(prefix + 'base', config.map_default_basemap || 'builtin-0');
        if (initial !== 'none' && !bases.has(initial)) initial = bases.has(config.map_default_basemap) ? config.map_default_basemap : (bases.keys().next().value || 'none');
        changeBase(initial, false);
        const change = () => changeBase(select.value, true);
        select.addEventListener('change', change);
        const refresh = () => { if (!doc.hidden) entries.forEach(e => e.refresh(map)); };
        const timer = setInterval(refresh, 30000);
        doc.addEventListener('visibilitychange', refresh);
        let disposed = false;
        function dispose() {
            if (disposed) return; disposed = true;
            clearInterval(timer); doc.removeEventListener('visibilitychange', refresh); select.removeEventListener('change', change);
            entries.forEach(e => e.deactivate(map)); root.removeEventListener('pagehide', pageHide);
        }
        const pageHide = event => { if (!event.persisted) dispose(); };
        root.addEventListener('pagehide', pageHide);
        map.on('unload', dispose);
        return {dispose, entries, changeBase};
    }
    return {readConfig, install, Entry, queryURL, serviceURL, viewport, tileBounds, arcgisParts,
        exportURL, wmtsURL, wfsURL, wpsURL, featureCollection, loadFeatures, getJSON, createLayer, escapeText};
});
