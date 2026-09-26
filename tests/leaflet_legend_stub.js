/* TEST ONLY: event/layer API double. This is NOT Leaflet or a rendering validation. */
(function () {
    class Events {
        constructor() { this.events = {}; }
        on(names, fn) { names.split(' ').forEach(n => (this.events[n] ||= new Set()).add(fn)); return this; }
        off(names, fn) { names.split(' ').forEach(n => { if (this.events[n]) this.events[n].delete(fn); }); return this; }
        fire(name, data = {}) { Array.from(this.events[name] || []).forEach(fn => fn(Object.assign({type: name, target: this}, data))); return this; }
    }
    const coordinate = p => Array.isArray(p) ? {lat: p[0], lng: p[1]} : {lat: p.lat, lng: p.lng};
    const bounds = (w, s, e, n) => ({getWest: () => w, getSouth: () => s, getEast: () => e, getNorth: () => n, isValid: () => true});
    class TestMap extends Events {
        constructor(element) {
            super(); this.element = typeof element === 'string' ? document.getElementById(element) : element;
            this.layers = new Set(); this.panes = {}; this.zoom = 5; this.bounds = bounds(-120, 30, -110, 40);
            this.corner = document.createElement('div'); this.corner.style.cssText = 'position:absolute;right:10px;top:10px;z-index:1000';
            this.element.style.position = 'relative'; this.element.append(this.corner);
        }
        setView(p, zoom) { this.center = coordinate(p); this.zoom = zoom; return this; }
        panTo(p) { this.center = coordinate(p); this.fire('moveend'); return this; }
        getBounds() { return this.bounds; }
        getZoom() { return this.zoom; }
        setZoom(z) { this.zoom = z; this.fire('moveend'); }
        getPane(name) { return this.panes[name]; }
        createPane(name) { return this.panes[name] = {style: {}}; }
        addLayer(layer) {
            if (this.layers.has(layer)) return this;
            this.layers.add(layer); layer._map = this;
            if (layer.eachLayer) layer.eachLayer(child => this.addLayer(child));
            layer.fire('add'); this.fire('layeradd', {layer}); return this;
        }
        removeLayer(layer) {
            if (!this.layers.has(layer)) return this;
            if (layer.eachLayer) layer.eachLayer(child => this.removeLayer(child));
            this.layers.delete(layer); layer.fire('remove'); layer._map = null; this.fire('layerremove', {layer}); return this;
        }
        hasLayer(layer) { return this.layers.has(layer); }
        invalidateSize() { this.resized = true; }
        remove() { Array.from(this.layers).forEach(l => this.removeLayer(l)); this.fire('unload'); this.corner.remove(); this.removed = true; }
    }
    class Layer extends Events {
        constructor(options) { super(); this.options = options || {}; }
        addTo(map) { map.addLayer(this); return this; }
        remove() { if (this._map) this._map.removeLayer(this); return this; }
        bindPopup(fn) { this.popup = fn; return this; }
    }
    class Marker extends Layer {
        constructor(p, options) { super(options); this.p = coordinate(p); }
        setLatLng(p) { this.p = coordinate(p); return this; }
        getLatLng() { return this.p; }
    }
    class Tiles extends Layer {
        constructor(url, options) { super(options); this.url = url; }
        setUrl(url) { this.url = url; return this; }
        setParams(params) { this.params = params; return this; }
        redraw() { return this; }
        static extend(properties) { class Sub extends Tiles {} Object.assign(Sub.prototype, properties); return Sub; }
    }
    class Features extends Layer {
        constructor(options) { super(options); this.children = []; }
        eachLayer(fn) { this.children.forEach(fn); }
        clearLayers() { this.children.forEach(l => l.remove()); this.children = []; }
        addData(data) {
            data.features.forEach(feature => {
                if (!feature.geometry) return;
                let child;
                const g = feature.geometry;
                if (g.type === 'Point') child = this.options.pointToLayer(feature, {lat: g.coordinates[1], lng: g.coordinates[0]});
                else {
                    child = new Layer(Object.assign({color: '#3388ff', weight: 3, fill: /Polygon/.test(g.type)}, this.options.style));
                    const points = [];
                    const walk = v => { if (typeof v[0] === 'number') points.push(v); else v.forEach(walk); };
                    walk(g.coordinates);
                    child.getBounds = () => bounds(Math.min(...points.map(p => p[0])), Math.min(...points.map(p => p[1])), Math.max(...points.map(p => p[0])), Math.max(...points.map(p => p[1])));
                }
                child.feature = feature; this.children.push(child);
                if (this.options.onEachFeature) this.options.onEachFeature(feature, child);
                if (this._map) child.addTo(this._map);
            });
        }
    }
    const tileLayer = (url, options) => new Tiles(url, options);
    tileLayer.wms = tileLayer;
    window.L = {
        map: element => new TestMap(element), marker: (p, options) => new Marker(p, options),
        circleMarker: (p, options) => new Marker(p, Object.assign({color: '#3388ff', weight: 3, fill: true}, options)),
        divIcon: options => options, tileLayer, TileLayer: Tiles, CRS: {EPSG3857: {}},
        geoJSON: (_, options) => new Features(options),
        control: options => ({options, addTo(map) { this.map = map; this.node = this.onAdd(map); map.corner.append(this.node); return this; },
            remove() { if (this.onRemove) this.onRemove(this.map); this.node.remove(); return this; }}),
        DomEvent: {disableClickPropagation(el) { el.addEventListener('click', e => e.stopPropagation()); },
            disableScrollPropagation(el) { el.addEventListener('wheel', e => e.stopPropagation()); }}
    };
})();
