/* Legends for active Leaflet layers. Remote labels are text, never executable HTML. */
(function (root, factory) {
    const api = factory(root);
    if (typeof module === 'object' && module.exports) module.exports = api;
    else root.OWRXMapLegend = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (root) {
    'use strict';
    const VECTOR_TYPES = ['arcgis-feature', 'wfs', 'geojson', 'wps'];
    const CACHE_TIME = 300000;
    const MAX_SYMBOLS = 256;
    let nextId = 0;
    function imageURL(raw) {
        const url = new URL(raw);
        const secrets = ['token', 'access_token', 'api_key', 'apikey', 'key', 'password', 'signature'];
        if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password || url.hash ||
            Array.from(url.searchParams.keys()).some(k => secrets.includes(k.toLowerCase())) ||
            (root.location && root.location.protocol === 'https:' && url.protocol !== 'https:'))
            throw new Error('Legend images require an anonymous HTTP(S) URL (HTTPS on an HTTPS receiver).');
        return url.href;
    }
    // ArcGIS export uses 96 dpi; OGC portrayal uses a standard 0.28 mm pixel.
    function scaleAt(zoom, dpi = 96) { return 40075016.68557849 / (256 * Math.pow(2, zoom)) * dpi / 0.0254; }
    function inScale(layer, scale) {
        const min = Number(layer.minScale || 0), max = Number(layer.maxScale || 0);
        return Number.isFinite(min) && Number.isFinite(max) && min >= 0 && max >= 0 &&
            (!min || scale <= min) && (!max || scale >= max);
    }
    function isActive(entry, map) {
        if (!entry.desired || !entry.layer || !map.hasLayer(entry.layer)) return false;
        const options = entry.layer.options || {}, zoom = map.getZoom();
        return entry.source.opacity !== 0 && options.opacity !== 0 &&
            (options.minZoom == null || zoom >= options.minZoom) && (options.maxZoom == null || zoom <= options.maxZoom);
    }
    function wmsImages(source, zoom, api) {
        const names = String(source.layers || '').split(',').map(s => s.trim()).filter(Boolean);
        const styles = String(source.style || '').split(',').map(s => s.trim());
        return names.slice(0, 10).map((name, index) => ({label: name, url: imageURL(api.queryURL(api.serviceURL(source.url).href, {
            SERVICE: 'WMS', REQUEST: 'GetLegendGraphic', VERSION: source.version || '1.1.1',
            LAYER: name, STYLE: styles[index] || '', FORMAT: 'image/png',
            WIDTH: 20, HEIGHT: 20, SCALE: Math.round(scaleAt(zoom, 25.4 / 0.28))
        }))}));
    }
    function arcgisGroups(legend, metadata, selectedIds, scale) {
        if (!legend || !Array.isArray(legend.layers) || !metadata || !Array.isArray(metadata.layers))
            throw new Error('The service did not return ArcGIS legend/layer metadata.');
        if (legend.layers.length > 2048 || metadata.layers.length > 2048)
            throw new Error('The service has too many legend layers. Use a smaller service.');
        const layers = new Map(metadata.layers.map(l => [l.id, l]));
        if (!inScale(metadata, scale)) return {groups: [], truncated: false};
        let count = 0, truncated = false;
        const groups = [];
        for (const item of legend.layers) {
            if (!Number.isInteger(item.layerId) || !Array.isArray(item.legend) || !inScale(item, scale)) continue;
            let current = layers.get(item.layerId), chain = [], seen = new Set();
            while (current) {
                if (seen.has(current.id)) throw new Error('Invalid ArcGIS layer hierarchy.');
                seen.add(current.id); chain.push(current);
                if (current.parentLayerId == null || current.parentLayerId === -1) break;
                current = layers.get(current.parentLayerId);
                if (!current) throw new Error('Incomplete ArcGIS layer hierarchy.');
            }
            if (!chain.length || !chain.every(l => inScale(l, scale))) continue;
            const visible = selectedIds.length ? chain.some(l => selectedIds.includes(l.id)) :
                chain.every(l => l.defaultVisibility !== false);
            if (!visible) continue;
            const remaining = MAX_SYMBOLS - count;
            const symbols = item.legend.slice(0, remaining);
            count += symbols.length;
            if (symbols.length < item.legend.length) truncated = true;
            if (symbols.length) groups.push({id: item.layerId, name: String(item.layerName || item.layerId), symbols});
        }
        return {groups, truncated};
    }
    function symbolImage(symbol, service, layerId) {
        const mime = String(symbol.contentType || '').toLowerCase();
        const data = symbol.imageData;
        if (['image/png', 'image/jpeg', 'image/gif', 'image/webp'].includes(mime) && typeof data === 'string' &&
            data.length <= 262144 && data.length > 0 && /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(data))
            return 'data:' + mime + ';base64,' + data;
        if (typeof symbol.url !== 'string' || !symbol.url || symbol.url.length > 4096) return null;
        const base = new URL(service); base.pathname = base.pathname.replace(/\/$/, '') + '/' + layerId + '/images/';
        // A relative image URL must retain non-secret service routing parameters.
        const url = new URL(symbol.url, base);
        if (!/^[a-z][a-z0-9+.-]*:/i.test(symbol.url) && !symbol.url.startsWith('//'))
            base.searchParams.forEach((v, k) => { if (!url.searchParams.has(k)) url.searchParams.set(k, v); });
        return imageURL(url.href);
    }
    function vectorSwatches(layer, map, api) {
        const boxes = api.viewport(map.getBounds()), samples = new Map();
        const intersects = (a, b) => a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1];
        function visit(child) {
            if (child.eachLayer) { child.eachLayer(visit); return; }
            if (!map.hasLayer(child)) return;
            let visible = false, kind;
            if (child.getLatLng) {
                const p = child.getLatLng(), lon = ((p.lng + 180) % 360 + 360) % 360 - 180;
                visible = boxes.some(b => intersects(b, [lon, p.lat, lon, p.lat])); kind = 'point';
            } else if (child.getBounds) {
                const bounds = child.getBounds();
                if (bounds.isValid && !bounds.isValid()) return;
                visible = api.viewport(bounds).some(b => boxes.some(a => intersects(a, b)));
                const geometry = child.feature && child.feature.geometry;
                kind = ((geometry && /Polygon/.test(geometry.type)) || (child.options && child.options.fill)) ? 'polygon' : 'line';
            }
            if (!visible || !kind) return;
            const o = child.options || {};
            const number = (v, fallback, max = 1) => Number.isFinite(v) ? Math.max(0, Math.min(max, v)) : fallback;
            const color = v => typeof v === 'string' && /^(#[\da-f]{3,8}|rgba?\([\d.,%\s]+\)|[a-z]+)$/i.test(v) ? v : '#3388ff';
            const style = {color: color(o.color), fillColor: color(o.fillColor || o.color),
                opacity: o.stroke === false ? 0 : number(o.opacity, 1), weight: number(o.weight, 3, 8),
                fillOpacity: kind === 'line' || o.fill === false ? 0 : number(o.fillOpacity, 0.2)};
            if (!style.opacity && !style.fillOpacity) return;
            const key = kind + JSON.stringify(style);
            if (!samples.has(key) && samples.size < 12) samples.set(key, {kind, style});
        }
        if (layer.eachLayer) layer.eachLayer(visit);
        return Array.from(samples.values());
    }
    function install(L, map, entries) {
        const api = root.OWRXMapLayers, doc = root.document;
        if (!api) throw new Error('Map layer adapters must load before the legend.');
        const control = L.control({position: 'topright'});
        const details = doc.createElement('details'); details.className = 'owrx-map-legend';
        const summary = doc.createElement('summary'); summary.textContent = 'Legend';
        const body = doc.createElement('div'); body.className = 'owrx-legend-body';
        body.id = 'owrx-layer-legends-' + (++nextId); summary.setAttribute('aria-controls', body.id);
        const note = doc.createElement('p'); note.className = 'owrx-legend-note';
        note.textContent = 'Active layers. Raster keys may include classes not present in this view; colors are shown before layer blending.';
        const list = doc.createElement('div'); body.append(note, list); details.append(summary, body);
        try { details.open = root.localStorage.getItem('owrx-legend-open') !== 'false'; } catch (_) { details.open = true; }
        const records = new Map(), cache = new Map(), queue = [];
        let disposed = false, debounce = null, running = 0;
        const abortError = () => new DOMException('Legend request cancelled', 'AbortError');
        function pump() {
            while (running < 4 && queue.length) {
                const task = queue.shift();
                if (task.signal.aborted || disposed) { task.reject(abortError()); continue; }
                running++;
                api.getJSON(task.url, task.signal).then(data => {
                    if (task.signal.aborted || disposed) throw abortError();
                    cache.set(task.url, {data, time: Date.now()});
                    while (cache.size > 8) cache.delete(cache.keys().next().value);
                    task.resolve(data);
                }).catch(task.reject).finally(() => { running--; pump(); });
            }
        }
        function json(url, signal) {
            const found = cache.get(url);
            if (found && Date.now() - found.time < CACHE_TIME) return Promise.resolve(found.data);
            return new Promise((resolve, reject) => { queue.push({url, signal, resolve, reject}); pump(); });
        }
        function text(parent, message, tag = 'p') {
            const node = doc.createElement(tag); node.textContent = String(message).slice(0, 1000); parent.append(node); return node;
        }
        function release(record) {
            record.controller.abort(); record.cleanups.forEach(cleanup => cleanup()); record.node.remove();
        }
        function clear() { records.forEach(release); records.clear(); }
        function image(record, parent, url, alt, swatch = false) {
            const img = doc.createElement('img');
            img.className = swatch ? 'owrx-legend-symbol' : 'owrx-legend-image';
            img.alt = String(alt).slice(0, 240); img.referrerPolicy = 'no-referrer';
            const status = text(parent, 'Loading legend image…'); status.className = 'owrx-legend-note';
            let settled = false;
            const done = ok => {
                if (settled) return; settled = true; clearTimeout(timer);
                img.onload = img.onerror = null;
                if (record.controller.signal.aborted) return;
                if (ok) status.remove();
                else {
                    img.remove(); status.textContent = 'Legend image unavailable. The map layer is unaffected.';
                    const retry = doc.createElement('button'); retry.type = 'button'; retry.textContent = 'Retry legend';
                    retry.addEventListener('click', () => { release(record); records.delete(record.id); update(); }); status.append(' ', retry);
                }
            };
            const timer = setTimeout(() => done(false), 20000);
            img.onload = () => done(true); img.onerror = () => done(false);
            parent.append(img); img.src = url;
            record.cleanups.push(() => { settled = true; clearTimeout(timer); img.onload = img.onerror = null; img.removeAttribute('src'); });
        }
        function swatch(parent, sample) {
            const row = doc.createElement('div'); row.className = 'owrx-legend-row';
            const svg = doc.createElementNS('http://www.w3.org/2000/svg', 'svg');
            svg.setAttribute('viewBox', '0 0 32 24'); svg.setAttribute('aria-hidden', 'true'); svg.classList.add('owrx-legend-symbol');
            const tag = sample.kind === 'point' ? 'circle' : sample.kind === 'line' ? 'line' : 'rect';
            const shape = doc.createElementNS('http://www.w3.org/2000/svg', tag);
            const geometry = tag === 'circle' ? {cx: 16, cy: 12, r: 5} : tag === 'line' ? {x1: 3, y1: 18, x2: 29, y2: 6} : {x: 4, y: 4, width: 24, height: 16};
            const s = sample.style;
            Object.entries(Object.assign(geometry, {stroke: s.color, 'stroke-width': s.weight, 'stroke-opacity': s.opacity,
                fill: s.fillColor, 'fill-opacity': s.fillOpacity})).forEach(([key, value]) => shape.setAttribute(key, value));
            svg.append(shape); row.append(svg); text(row, {point: 'Point features', line: 'Line features', polygon: 'Area features'}[sample.kind], 'span');
            parent.append(row);
        }
        async function populate(record, entry, samples) {
            const source = entry.source, container = record.content, signal = record.controller.signal;
            try {
                if (source.legend_caption) text(container, source.legend_caption);
                if (VECTOR_TYPES.includes(source.type)) {
                    samples.forEach(sample => swatch(container, sample));
                    text(container, 'Actual Leaflet styling for loaded features intersecting the view (bounds test), not the service\'s native categories.').className = 'owrx-legend-note';
                } else if (source.legend_url) {
                    image(record, container, imageURL(source.legend_url), source.name + ' legend');
                } else if (source.type === 'wms') {
                    const images = wmsImages(source, map.getZoom(), api);
                    images.forEach(item => { text(container, item.label, 'h4'); image(record, container, item.url, item.label + ' legend'); });
                    if (String(source.layers).split(',').length > images.length) text(container, 'Only the first 10 WMS sublayer legends are shown.');
                } else if (source.type === 'arcgis-map') {
                    const service = api.arcgisParts(source), legendURL = new URL(service.url);
                    legendURL.pathname = legendURL.pathname.replace(/\/$/, '') + '/legend';
                    const loading = text(container, 'Loading service legend…');
                    const metadata = await json(api.queryURL(service.url, {f: 'json'}), signal);
                    const data = await json(api.queryURL(legendURL.href, {f: 'json'}), signal);
                    if (signal.aborted) return;
                    const result = arcgisGroups(data, metadata, service.ids, scaleAt(map.getZoom()));
                    loading.remove();
                    result.groups.forEach(group => {
                        text(container, group.name, 'h4');
                        group.symbols.forEach(symbol => {
                            const row = doc.createElement('div'); row.className = 'owrx-legend-row'; container.append(row);
                            const label = String(symbol.label || group.name).slice(0, 240);
                            let url = null;
                            try { url = symbolImage(symbol, service.url, group.id); } catch (_) { /* Unsafe symbol URL: show text only. */ }
                            if (url) image(record, row, url, label, true);
                            else text(row, 'Symbol unavailable', 'span');
                            text(row, label, 'span');
                        });
                    });
                    if (!result.groups.length) text(container, 'No legend symbols for the selected sublayers at this scale.');
                    if (result.truncated) text(container, 'Legend truncated at ' + MAX_SYMBOLS + ' symbols.');
                } else {
                    text(container, source.basemap ? 'Basemap; no automatic legend is supplied.' : 'No automatic legend is supplied for this layer.');
                    if (String(source.id).startsWith('custom-')) text(container, 'A legend image URL can be set in Map settings.');
                }
            } catch (error) {
                if (signal.aborted) return;
                container.replaceChildren();
                text(container, 'Legend unavailable: ' + error.message + ' The map layer is unaffected.');
                const retry = doc.createElement('button'); retry.type = 'button'; retry.textContent = 'Retry legend';
                retry.addEventListener('click', () => { cache.clear(); release(record); records.delete(record.id); update(); });
                container.append(retry);
            }
        }
        function update() {
            if (disposed) return;
            clearTimeout(debounce);
            if (!details.open || doc.hidden) { clear(); list.replaceChildren(); return; }
            const wanted = new Set();
            entries.filter(entry => isActive(entry, map)).forEach(entry => {
                const source = entry.source;
                const samples = VECTOR_TYPES.includes(source.type) ? vectorSwatches(entry.layer, map, api) : null;
                if (samples && !samples.length) return;
                wanted.add(source.id);
                const key = samples ? JSON.stringify(samples) : JSON.stringify([source, map.getZoom(), Math.floor(Date.now() / CACHE_TIME)]);
                const old = records.get(source.id);
                if (old && old.key === key) return;
                if (old) release(old);
                const node = doc.createElement('section'); node.dataset.layerId = source.id;
                text(node, source.name, 'h3');
                const content = doc.createElement('div'); node.append(content);
                const record = {id: source.id, key, node, content, controller: new AbortController(), cleanups: []};
                records.set(source.id, record); populate(record, entry, samples);
            });
            records.forEach((record, id) => { if (!wanted.has(id)) { release(record); records.delete(id); } });
            // Preserve unchanged image nodes (and focus) rather than recreating them on each pan.
            Array.from(list.children).filter(node => !node.dataset.layerId).forEach(node => node.remove());
            let cursor = list.firstElementChild;
            entries.forEach(entry => {
                const record = records.get(entry.source.id);
                if (!record) return;
                if (record.node === cursor) cursor = cursor.nextElementSibling;
                else list.insertBefore(record.node, cursor);
            });
            if (!records.size) text(list, 'No visible layer legends. Enable a layer or move to its features.');
        }
        function schedule() { clearTimeout(debounce); debounce = setTimeout(update, 100); }
        function toggle() {
            try { root.localStorage.setItem('owrx-legend-open', String(details.open)); } catch (_) { /* Optional storage. */ }
            update();
        }
        const stopKey = event => event.stopPropagation();
        control.onAdd = () => {
            L.DomEvent.disableClickPropagation(details); L.DomEvent.disableScrollPropagation(details);
            return details;
        };
        const timer = setInterval(schedule, 60000);
        control.onRemove = () => {
            if (disposed) return; disposed = true;
            clearTimeout(debounce); clearInterval(timer); clear(); cache.clear();
            queue.splice(0).forEach(task => task.reject(abortError()));
            map.off('layeradd layerremove moveend', schedule);
            doc.removeEventListener('visibilitychange', update); details.removeEventListener('toggle', toggle);
            details.removeEventListener('keydown', stopKey);
        };
        details.addEventListener('toggle', toggle); details.addEventListener('keydown', stopKey);
        doc.addEventListener('visibilitychange', update); map.on('layeradd layerremove moveend', schedule);
        control.addTo(map); update();
        return {remove: () => control.remove(), update, control};
    }
    return {install, imageURL, scaleAt, inScale, isActive, wmsImages, arcgisGroups, symbolImage, vectorSwatches};
});
