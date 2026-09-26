/* Receiver-coordinate picker: Leaflet + OpenStreetMap, independent of map engine/API keys. */
(function (root, factory) {
    'use strict';
    const api = factory(root);
    if (typeof module === 'object' && module.exports) module.exports = api;
    else root.OWRXLocationPicker = api;
    if (root.jQuery) root.jQuery.fn.mapInput = function () {
        return this.each(function () { api.attach(this); });
    };
})(typeof globalThis !== 'undefined' ? globalThis : this, function (root) {
    'use strict';
    let leafletReady = null;
    function position(latitude, longitude) {
        if (String(latitude).trim() === '' || String(longitude).trim() === '') return null;
        const lat = Number(latitude), lng = Number(longitude);
        return Number.isFinite(lat) && Number.isFinite(lng) && lat > -90 && lat < 90 && lng > -180 && lng < 180
            ? {lat, lng} : null;
    }
    function pickedPosition(point) {
        // Leaflet may report longitudes in a repeated world. Match the server's open ranges.
        const lat = Math.max(-89.999999, Math.min(89.999999, point.lat));
        const lng = Math.max(-179.999999, Math.min(179.999999, ((point.lng + 180) % 360 + 360) % 360 - 180));
        return position(lat.toFixed(6), lng.toFixed(6));
    }
    function loadLeaflet() {
        if (leafletReady) return leafletReady;
        const doc = root.document;
        function resource(id, tag, url) {
            const existing = doc.getElementById(id);
            if (existing && existing.dataset.loaded === 'true') return Promise.resolve();
            if (existing) existing.remove();
            return new Promise((resolve, reject) => {
                const element = doc.createElement(tag); element.id = id;
                const finish = error => {
                    clearTimeout(timer); element.onload = element.onerror = null;
                    if (error) { element.remove(); reject(new Error('Map library could not load.')); }
                    else { element.dataset.loaded = 'true'; resolve(); }
                };
                const timer = setTimeout(() => finish(true), 20000);
                element.onload = () => finish(false); element.onerror = () => finish(true);
                if (tag === 'link') { element.rel = 'stylesheet'; element.href = url; }
                else { element.src = url; element.async = true; }
                doc.head.append(element);
            });
        }
        leafletReady = Promise.all([
            resource('owrx-location-leaflet-css', 'link', 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'),
            root.L && root.L.map ? Promise.resolve() :
                resource('owrx-location-leaflet-js', 'script', 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js')
        ]).then(() => {
            if (!root.L || !root.L.map) throw new Error('Map library unavailable.');
            return root.L;
        }).catch(error => { leafletReady = null; throw error; });
        return leafletReady;
    }
    function attach(element) {
        if (element.owrxLocationPicker) return element.owrxLocationPicker;
        const doc = element.ownerDocument;
        const field = element.getAttribute('for');
        const lat = doc.getElementById(field + '-lat'), lon = doc.getElementById(field + '-lon');
        if (!lat || !lon) return null;
        const message = doc.createElement('p');
        message.className = 'small'; message.setAttribute('role', 'status');
        const retry = doc.createElement('button');
        retry.type = 'button'; retry.className = 'btn btn-sm btn-secondary'; retry.textContent = 'Retry map preview'; retry.hidden = true;
        // Keep status outside the Leaflet-owned element and Bootstrap row.
        element.parentNode.after(message, retry);
        element.style.height = '220px'; element.style.width = '100%'; element.style.zIndex = '0';
        element.setAttribute('aria-label', 'Receiver coordinates map (OpenStreetMap)');
        let map = null, marker = null, observer = null, disposed = false, syncing = false, busy = false;
        const editable = () => !lat.disabled && !lon.disabled && !lat.readOnly && !lon.readOnly;
        function instructions() {
            message.textContent = 'Click the map or drag the marker to choose coordinates, or edit latitude and longitude above.';
        }
        function updateFromFields() {
            if (!map || syncing) return;
            const point = position(lat.value, lon.value);
            if (!point) {
                marker.remove();
                message.textContent = 'Enter valid latitude and longitude, or click the map to select a location.';
                return;
            }
            marker.setLatLng(point).addTo(map); map.panTo(point, {animate: false}); instructions();
        }
        function updateFromMap(point) {
            if (!editable()) return;
            const selected = pickedPosition(point);
            if (!selected) return;
            syncing = true;
            lat.value = selected.lat; lon.value = selected.lng;
            marker.setLatLng(selected).addTo(map);
            [lat, lon].forEach(input => {
                input.dispatchEvent(new Event('input', {bubbles: true}));
                input.dispatchEvent(new Event('change', {bubbles: true}));
            });
            syncing = false; instructions();
        }
        function resize() { if (map && !disposed) map.invalidateSize({pan: false}); }
        async function start() {
            if (busy || disposed || map) return;
            busy = true; retry.hidden = true; message.textContent = 'Loading OpenStreetMap preview…';
            try {
                const L = await loadLeaflet();
                if (disposed || !element.isConnected) return;
                const selected = position(lat.value, lon.value);
                map = L.map(element, {scrollWheelZoom: false}).setView(selected || [0, 0], selected ? 7 : 2);
                // Do not suppress Referer or defeat caching: respect OSM's tile usage policy.
                const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                }).addTo(map);
                tiles.on('tileerror', () => { message.textContent = 'Some OpenStreetMap tiles could not load. Numeric coordinate entry still works.'; });
                const pin = doc.createElement('span');
                pin.style.cssText = 'display:block;width:18px;height:18px;box-sizing:border-box;border:2px solid white;border-radius:50%;background:#1769aa;box-shadow:0 0 3px #000';
                marker = L.marker(selected || [0, 0], {
                    icon: L.divIcon({html: pin, className: 'owrx-location-marker', iconSize: [18, 18], iconAnchor: [9, 9]}),
                    draggable: editable(), autoPan: true, title: 'Receiver location (drag to change)'
                });
                if (selected) marker.addTo(map);
                marker.on('dragend', () => updateFromMap(marker.getLatLng()));
                map.on('click', event => updateFromMap(event.latlng));
                [lat, lon].forEach(input => { input.addEventListener('input', updateFromFields); input.addEventListener('change', updateFromFields); });
                if (root.ResizeObserver) { observer = new root.ResizeObserver(resize); observer.observe(element); }
                root.addEventListener('resize', resize);
                instructions(); resize();
                // Loading/recentering never writes the form's saved coordinates.
            } catch (_) {
                if (!disposed) {
                    if (map) { map.remove(); map = null; }
                    message.textContent = 'Map preview unavailable. You can still enter and save latitude/longitude above.';
                    retry.hidden = false;
                }
            } finally { busy = false; }
        }
        function dispose() {
            if (disposed) return;
            disposed = true;
            if (observer) observer.disconnect();
            [lat, lon].forEach(input => { input.removeEventListener('input', updateFromFields); input.removeEventListener('change', updateFromFields); });
            retry.removeEventListener('click', start); root.removeEventListener('resize', resize);
            root.removeEventListener('pagehide', pageHide);
            if (map) map.remove();
            message.remove(); retry.remove(); delete element.owrxLocationPicker;
        }
        const pageHide = event => { if (!event.persisted) dispose(); };
        root.addEventListener('pagehide', pageHide); retry.addEventListener('click', start);
        const handle = {dispose, ready: null, getMap: () => map, getMarker: () => marker};
        element.owrxLocationPicker = handle; handle.ready = start();
        return handle;
    }
    return {position, pickedPosition, loadLeaflet, attach};
});
