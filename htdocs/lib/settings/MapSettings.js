/* Map settings editor. All labels, URLs and saved JSON are treated as text. */
(function () {
    'use strict';
    const editor = document.getElementById('map-layer-editor');
    const storage = document.getElementById('map_layers');
    if (!editor || !storage) return;
    let layers;
    try {
        layers = JSON.parse(storage.value);
        if (!Array.isArray(layers)) throw new Error('Expected a list');
    } catch (_) {
        editor.textContent = 'Fix the layer JSON below before using the editor.';
        return;
    }
    storage.readOnly = true;
    document.querySelector('#map-layer-json summary').textContent = 'Advanced: read-only layer JSON';
    const form = storage.closest('form');
    const bases = document.getElementById('map_default_basemap');
    const builtins = Array.from(bases.options).filter(o => o.value.startsWith('builtin-'))
        .map(o => ({id: o.value, name: o.textContent}));
    const cards = document.createElement('div');
    const add = button('Add layer', () => {
        if (layers.length >= 50) return;
        const bytes = new Uint32Array(3);
        window.crypto.getRandomValues(bytes);
        layers.push({id: 'custom-' + Array.from(bytes, n => n.toString(16)).join('-'),
            name: 'Custom layer', type: 'arcgis-map', url: '', layers: '', enabled: true,
            basemap: false, visible: false, opacity: 0.7, refresh: 0, max_features: 2000, max_zoom: 19});
        render();
        cards.lastElementChild.querySelector('input[type=text]').focus();
    });
    editor.append(cards, add);
    const types = {
        'arcgis-map': 'ArcGIS map service (MapServer)',
        'arcgis-feature': 'ArcGIS feature service / queryable map layer',
        wms: 'OGC WMS image service', wmts: 'OGC WMTS (Web Mercator XYZ matrix)',
        wfs: 'OGC WFS (GeoJSON output)', xyz: 'XYZ / TMS tile template',
        geojson: 'GeoJSON URL (including an existing WPS result)',
        wps: 'OGC WPS 1.0 Execute (synchronous GeoJSON)'
    };
    const help = {
        'arcgis-map': 'Use a MapServer root or numbered sublayer URL. Optional sublayer IDs: 0,1. The service must export EPSG:3857 images.',
        'arcgis-feature': 'Use FeatureServer, MapServer, or a numbered sublayer. Optional IDs: 0,1. A root without IDs discovers up to 10 feature layers. Query and GeoJSON output must be supported.',
        wms: 'Use the service URL and exact layer name(s) from GetCapabilities. EPSG:3857 must be supported. Versions: 1.1.1 or 1.3.0.',
        wmts: 'Use a KVP endpoint, exact layer ID and an EPSG:3857 matrix set with XYZ numbering. Set a matrix prefix such as EPSG:3857: when required. Arbitrary matrix sets are not supported.',
        wfs: 'Use the endpoint and exact feature type name. GeoJSON in WGS84 is required. Versions: 1.0.0, 1.1.0 or 2.0.0. The visible extent is queried; a feature limit is reported rather than silently ignored.',
        xyz: 'Include {z}, {x} and {y}; optional {s} (a/b/c) and {r}. TMS reverses the Y coordinate. Only Web Mercator XYZ-compatible tiles are supported.',
        geojson: 'A URL returning a WGS84 GeoJSON FeatureCollection. The whole response is fetched, subject to size and feature limits.',
        wps: 'Executing a process may consume server resources. Only manually enabled, synchronous WPS 1.0 GET Execute with raw GeoJSON is supported; no automatic refresh or basemap role. For completed results, use GeoJSON URL instead.'
    };
    function button(text, action) {
        const b = document.createElement('button');
        b.type = 'button'; b.className = 'btn btn-sm btn-secondary'; b.textContent = text;
        b.addEventListener('click', action);
        return b;
    }
    function sync() {
        storage.value = JSON.stringify(layers, null, 2);
        const chosen = bases.value;
        const options = [{id: 'none', name: 'None (markers without a basemap)'}];
        builtins.forEach(b => {
            const checkbox = document.getElementById('map_basemaps-' + b.id);
            if (checkbox && checkbox.checked) options.push(b);
        });
        layers.filter(l => l.enabled && l.basemap).forEach(l => options.push({id: l.id, name: l.name}));
        if (chosen && !options.some(o => o.id === chosen)) options.push({id: chosen, name: '(Unavailable — choose an enabled basemap)'});
        bases.replaceChildren();
        options.forEach(o => bases.add(new Option(o.name, o.id, false, o.id === chosen)));
        add.disabled = layers.length >= 50;
    }
    function render() {
        cards.replaceChildren();
        layers.forEach((layer, index) => {
            const card = document.createElement('fieldset'); card.className = 'map-layer-card';
            const legend = document.createElement('legend'); legend.textContent = 'Layer ' + (index + 1);
            const fields = document.createElement('div'); fields.className = 'map-layer-fields';
            const controls = {};
            function field(key, label, type = 'text', opts = {}) {
                const wrap = document.createElement('label');
                const caption = document.createElement('span'); caption.textContent = label;
                const input = document.createElement(type === 'select' ? 'select' : 'input');
                input.id = layer.id + '-' + key;
                caption.id = input.id + '-label';
                input.setAttribute('aria-labelledby', caption.id);
                wrap.htmlFor = input.id;
                if (type === 'select') Object.entries(types).forEach(([v, text]) => input.add(new Option(text, v)));
                else input.type = type;
                if (type === 'checkbox') input.checked = Boolean(layer[key]);
                else input.value = layer[key] == null ? (opts.default == null ? '' : opts.default) : layer[key];
                if (type !== 'checkbox') input.className = 'form-control form-control-sm';
                ['min', 'max', 'step', 'maxLength', 'placeholder'].forEach(k => { if (opts[k] != null) input[k] = opts[k]; });
                if (opts.required) input.required = true;
                wrap.append(caption, document.createElement('br'), input); fields.append(wrap);
                controls[key] = {input, wrap};
                input.addEventListener('input', () => {
                    layer[key] = type === 'checkbox' ? input.checked : type === 'number' ? Number(input.value) : input.value;
                    if (key === 'type') {
                        layer.version = ''; layer.format = ''; render();
                        document.getElementById(layer.id + '-type').focus();
                    }
                    else sync();
                });
            }
            field('name', 'Name', 'text', {required: true, maxLength: 120});
            field('type', 'Service type', 'select');
            field('url', 'Public service URL / tile template', 'text', {required: true, maxLength: 4096});
            field('layers', 'Layer IDs / feature type / process identifier', 'text', {maxLength: 512});
            field('enabled', 'Available to visitors', 'checkbox');
            field('basemap', 'Use as a basemap', 'checkbox');
            field('visible', 'Overlay initially visible', 'checkbox');
            field('opacity', 'Opacity (0–1)', 'number', {min: 0, max: 1, step: 0.05, default: 0.7});
            field('refresh', 'Refresh seconds (0 = off; minimum 60)', 'number', {min: 0, max: 86400, step: 1, default: 0});
            field('attribution', 'Attribution (plain text)', 'text', {maxLength: 1000});
            field('legend_url', 'Legend image URL (optional; overrides automatic raster legend)', 'text', {maxLength: 4096});
            field('legend_caption', 'Legend description / units (plain text, optional)', 'text', {maxLength: 500});
            field('version', 'Protocol version (blank = default)', 'text', {maxLength: 20});
            field('format', 'Output MIME type (blank = default)', 'text', {maxLength: 80});
            field('style', 'WMS / WMTS style (optional)', 'text', {maxLength: 256});
            field('matrix_set', 'WMTS tile matrix set', 'text', {maxLength: 120});
            field('matrix_prefix', 'WMTS tile matrix identifier prefix', 'text', {maxLength: 120});
            field('tms', 'Invert XYZ tile Y (TMS)', 'checkbox');
            field('max_zoom', 'Maximum native tile zoom', 'number', {min: 0, max: 22, step: 1, default: 19});
            field('max_features', 'Maximum displayed features', 'number', {min: 1, max: 10000, step: 1, default: 2000});
            field('wps_inputs', 'WPS literal inputs (name=value;name=value)', 'text', {maxLength: 2048});
            field('wps_output', 'WPS output identifier (default: result)', 'text', {maxLength: 120});
            const kind = layer.type;
            const only = {version: ['wms', 'wmts', 'wfs', 'wps'], format: ['wms', 'wmts', 'wfs', 'wps'],
                legend_url: ['xyz', 'wms', 'wmts', 'arcgis-map'],
                style: ['wms', 'wmts'], matrix_set: ['wmts'], matrix_prefix: ['wmts'], tms: ['xyz'],
                wps_inputs: ['wps'], wps_output: ['wps'], max_features: ['arcgis-feature', 'wfs', 'wps', 'geojson'],
                max_zoom: ['xyz', 'wmts'], layers: ['arcgis-map', 'arcgis-feature', 'wms', 'wmts', 'wfs', 'wps']};
            Object.entries(only).forEach(([key, kinds]) => { controls[key].wrap.hidden = !kinds.includes(kind); });
            if (kind === 'wps') {
                ['basemap', 'visible'].forEach(key => { layer[key] = false; controls[key].input.checked = false; controls[key].input.disabled = true; });
                layer.refresh = 0; controls.refresh.input.value = 0; controls.refresh.input.disabled = true;
            }
            const info = document.createElement('small'); info.className = 'map-layer-help'; info.textContent = help[kind] || '';
            const legendHelp = document.createElement('small'); legendHelp.className = 'map-layer-help';
            legendHelp.textContent = ['arcgis-feature', 'wfs', 'geojson', 'wps'].includes(kind)
                ? 'The map legend shows the actual Leaflet point, line and area styling of loaded features in view.'
                : 'ArcGIS map legends and WMS GetLegendGraphic are automatic when supported. Supply an anonymous legend image URL for other sources or to override the automatic legend.';
            card.append(legend, fields, info, legendHelp, button('Remove layer', () => { layers.splice(index, 1); render(); }));
            cards.append(card);
        });
        sync();
    }
    document.querySelectorAll('[id^="map_basemaps-"]').forEach(c => c.addEventListener('change', sync));
    form.addEventListener('submit', sync);
    function optional(toggle, names) {
        const checkbox = document.getElementById(toggle);
        const update = () => names.forEach(name => {
            const input = document.getElementById(name);
            if (!input) return;
            // Readonly (not disabled) retains values in normal form submission.
            input.readOnly = !checkbox.checked;
            if (toggle === 'map_allow_google' || toggle === 'map_openweather') input.required = checkbox.checked;
            input.closest('.form-group').classList.toggle('map-setting-inactive', !checkbox.checked);
            input.setAttribute('aria-disabled', String(!checkbox.checked));
        });
        checkbox.addEventListener('change', update); update();
    }
    optional('map_use_initial_view', ['map_initial_lat', 'map_initial_lon', 'map_initial_zoom']);
    optional('map_allow_google', ['google_maps_api_key']);
    optional('map_openweather', ['openweathermap_api_key']);
    const googleToggle = document.getElementById('map_allow_google');
    const engine = document.getElementById('map_type');
    function googleAvailability() {
        if (!engine) return;
        const option = engine.querySelector('option[value="google"]');
        if (option) option.disabled = !googleToggle.checked;
        if (!googleToggle.checked && engine.value === 'google') engine.value = 'leaflet';
    }
    googleToggle.addEventListener('change', googleAvailability);
    googleAvailability();
    render();
})();
