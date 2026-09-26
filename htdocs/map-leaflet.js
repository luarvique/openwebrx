var mapSources = [
    {
        name: 'OpenStreetMap',
        url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
        options: {
            maxZoom: 19,
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        },
    },
    {
        name: 'OpenTopoMap',
        url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
        options: {
            maxZoom: 17,
            attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)'
        }
    },
    {
        name: 'Esri WorldTopo',
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
        options: {
            attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ, TomTom, Intermap, iPC, USGS, FAO, NPS, NRCAN, GeoBase, Kadaster NL, Ordnance Survey, Esri Japan, METI, Esri China (Hong Kong), and the GIS User Community'
        }
    },
    {
        name: 'Esri WorldStreet',
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
        options: {
            attribution: 'Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, USGS, Intermap, iPC, NRCAN, Esri Japan, METI, Esri China (Hong Kong), Esri (Thailand), TomTom, 2012'
        }
    },
    {
        name: 'Esri WorldImagery',
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        options: {
            attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
        }
    },
    {
        name: 'Esri NatGeoWorld',
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/NatGeo_World_Map/MapServer/tile/{z}/{y}/{x}',
        options: {
            attribution: 'Tiles &copy; Esri &mdash; National Geographic, Esri, DeLorme, NAVTEQ, UNEP-WCMC, USGS, NASA, ESA, METI, NRCAN, GEBCO, NOAA, iPC',
            maxZoom: 16
        }
    },
    {
        name: 'Esri WorldGray',
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
        options: {
            attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
            maxZoom: 16
        }
    },
    {
        name: 'CartoDB Positron',
        url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
        options: {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 20
        }
    },
    {
        name: 'CartoDB DarkMatter',
        url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
        options: {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 20
        }
    },
    {
        name: 'CartoDB Voyager',
        url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
        options: {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 20
        }
    },
    {
        name: 'Stadia Alidade',
        url: 'https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png',
        options: {
            maxZoom: 20,
            noWrap: true,
            attribution: '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a>, &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors',
        },
        info: 'In order to use Stadia maps, you must register. Once registered, you can whitelist your domain within your account settings.'
    },
    {
        name: 'Stadia AlidadeDark',
        url: 'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png',
        options: {
            maxZoom: 20,
            noWrap: true,
            attribution: '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a>, &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors'
        },
        info: 'In order to use Stadia maps, you must register. Once registered, you can whitelist your domain within your account settings.'
    },
];

var mapExtraLayers = [
    {
        name: 'OpenWeatherMap',
        url: 'https://tile.openweathermap.org/map/{layer}/{z}/{x}/{y}.png?appid={apikey}',
        options: { layer: 'clouds_new', attribution: 'Map data: &copy; OpenWeatherMap' }
    },
    {
        name: 'OpenWeatherMap',
        url: 'https://tile.openweathermap.org/map/{layer}/{z}/{x}/{y}.png?appid={apikey}',
        options: { layer: 'precipitation_new', attribution: 'Map data: &copy; OpenWeatherMap' }
    },
    {
        name: 'OpenSeaMap',
        url: 'https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png',
        options: { attribution: 'Map data: &copy; <a href="https://openseamap.org">OpenSeaMap</a> contributors' }
    },
    {
        name: 'Maidenhead-QTH',
        createLayer: async function () {
            await $.when($.getScript('https://ha8tks.github.io/Leaflet.Maidenhead/src/L.Maidenhead.js'));
            return L.maidenhead({ color: 'rgba(100, 100, 100, 0.6)' });
        }
    },
];

// Reasonable defaults, overridden by the server.
var retention_time = 2 * 60 * 60 * 1000;
var call_retention_time = 15 * 60;
var max_calls = 5;
var map = null;
var layerControl;
var receiverMarker = null;
var infoWindow = null;
var updateQueue = [];
var mapManager = new MapManager();
var mapClientConfig = OWRXMapLayers.readConfig();
var query = new URLSearchParams(window.location.search);
var expectedCallsign = query.get('callsign');
var expectedLocator = query.get('locator');

function fetchStyleSheet(url) {
    return new Promise(function(resolve, reject) {
        var link = document.createElement('link');
        link.rel = 'stylesheet'; link.href = url;
        var timer = setTimeout(function() { reject(new Error('Map stylesheet timed out.')); }, 20000);
        link.onload = function() { clearTimeout(timer); resolve(); };
        link.onerror = function() { clearTimeout(timer); reject(new Error('Map stylesheet could not load.')); };
        document.head.appendChild(link);
    });
}

function mapNotice(message) {
    var notice = document.getElementById('owrx-map-notice');
    if (!notice) {
        notice = document.createElement('div'); notice.id = 'owrx-map-notice';
        notice.className = 'owrx-map-error'; notice.setAttribute('role', 'alert');
        document.getElementById('openwebrx-map').appendChild(notice);
    }
    notice.textContent = message;
}

function getInfoWindow(name = null) {
    if (!infoWindow || infoWindow.name !== name) {
        var popup = L.popup();
        popup.on('remove', function() { popup.name = null; });
        infoWindow = popup;
        infoWindow.name = name;
    }
    return infoWindow;
}

function showLocatorInfoWindow(locator, rectangle) {
    infoWindow = getInfoWindow(locator);
    rectangle._rect.unbindPopup().bindPopup(infoWindow).openPopup();
    var p = new posObj(rectangle.center);
    infoWindow.setContent(mapManager.lman.getInfoHTML(locator, p, receiverMarker));
}

function showMarkerInfoWindow(name) {
    var marker = mapManager.mman.find(name);
    if (!marker) return;
    infoWindow = getInfoWindow(name);
    marker._marker.unbindPopup().bindPopup(infoWindow).openPopup();
    infoWindow.setContent(marker.getInfoHTML(name, receiverMarker));
}

MapManager.prototype.setReceiverName = function(name) {
    if (receiverMarker) receiverMarker.setTitle(name);
};
MapManager.prototype.removeReceiver = function() {
    if (receiverMarker) receiverMarker.setMap();
};

MapManager.prototype.initializeMap = function(receiver_gps, api_key, weather_key) {
    var self = this;
    self._receiverGPS = receiver_gps;
    function updateReceiver() {
        if (!receiverMarker) return;
        receiverMarker.setLatLng(self._receiverGPS.lat, self._receiverGPS.lon);
        receiverMarker.setMarkerOptions(self.config);
        receiverMarker.setMap(mapClientConfig.map_show_receiver === false ? null : map);
    }
    if (receiverMarker) { updateReceiver(); return Promise.resolve(); }
    // WebSocket reconnects/config updates must not initialize the same map twice.
    if (self._mapInitialization) return self._mapInitialization;
    self._mapInitialization = (async function() {
        await fetchStyleSheet('https://unpkg.com/leaflet@1.9.4/dist/leaflet.css');
        await $.getScript('https://unpkg.com/leaflet@1.9.4/dist/leaflet.js');
        await $.getScript('https://cdn.jsdelivr.net/npm/leaflet.geodesic');
        await $.getScript('https://cdn.jsdelivr.net/npm/leaflet-textpath@1.2.3/leaflet.textpath.min.js');
        var center = mapClientConfig.map_use_initial_view
            ? [mapClientConfig.map_initial_lat, mapClientConfig.map_initial_lon]
            : [self._receiverGPS.lat, self._receiverGPS.lon];
        var zoom = mapClientConfig.map_use_initial_view ? mapClientConfig.map_initial_zoom : 5;
        map = L.map('openwebrx-map', {zoomControl: false, worldCopyJump: true, minZoom: 0, maxZoom: 22}).setView(center, zoom);
        new L.Control.Zoom({position: 'bottomright'}).addTo(map);
        layerControl = L.control.layers({}, null, {collapsed: false, hideSingleBase: true, position: 'bottomleft'}).addTo(map);
        layerControl.legend = $('.openwebrx-map-legend').css({padding: '0', margin: '0'}).insertAfter(layerControl._overlaysList);

        await $.getScript('static/lib/Leaflet.js');
        receiverMarker = new LSimpleMarker();
        receiverMarker.setMarkerPosition(self.config['receiver_name'], self._receiverGPS.lat, self._receiverGPS.lon);
        receiverMarker.addListener('click', function() {
            L.popup(receiverMarker.getPos(), {content: '<h3>' + OWRXMapLayers.escapeText(self.config['receiver_name']) +
                '</h3><div>Receiver location</div>'}).openOn(map);
        });
        updateReceiver();
        self._gisLayers = OWRXMapLayers.install(L, map, mapSources, mapExtraLayers, mapClientConfig, weather_key);
        self.setupLegendFilters(layerControl.legend);
        self.processUpdates(updateQueue);
        updateQueue = [];
        if (mapClientConfig.map_night !== false) {
            $.getScript('https://unpkg.com/@joergdietrich/leaflet.terminator@1.1.0/L.Terminator.js').done(function() {
                if (!map) return;
                var pane = map.createPane('nite'); pane.style.zIndex = 201; pane.style.pointerEvents = 'none';
                var night = L.terminator({fillOpacity: 0.2, interactive: false, pane: 'nite'}).addTo(map);
                var timer = setInterval(function() { if (!document.hidden) night.setTime(); }, 60000);
                map.on('unload', function() { clearInterval(timer); });
                window.addEventListener('pagehide', function(event) { if (!event.persisted) clearInterval(timer); });
            }).fail(function() { mapNotice('The optional day/night overlay could not load. The map remains available.'); });
        }
    })().catch(function(error) {
        console.error('Map initialization failed:', error);
        mapNotice('The map could not initialize. Check network access to the map libraries, then reload this page.');
        // Keep queued radio updates; do not create unhandled promise rejections.
    });
    return self._mapInitialization;
};

MapManager.prototype.processUpdates = function(updates) {
    var self = this;

    if (typeof(LMarker) === 'undefined' || !map) {
        updateQueue = updateQueue.concat(updates);
        return;
    }

    updates.forEach(function(update) {
        // Process caller-callee updates
        if ('caller' in update) {
            var call = new LCall();
            call.create(update, map);
            self.cman.add(call);
            return;
        }

        // Process position updates
        switch (update.location.type) {
            case 'latlon':
                var marker = self.mman.find(update.callsign);
                if (!marker) {
                    switch(update.mode) {
                        case 'HFDL': case 'VDL2': case 'ADSB':
                        case 'ACARS': case 'UAT':
                            marker = new LAircraftMarker();
                            break;
                        case 'APRS': case 'AIS': case 'HDR': case 'SONDE': case 'Meshtastic':
                            marker = new LAprsMarker();
                            break;
                        case 'KiwiSDR': case 'WebSDR': case 'OpenWebRX':
                        case 'Stations': case 'Repeaters':
                            marker = new LFeatureMarker();
                            if (!update.location.symbol) update.location.symbol = self.mman.getSymbol(update.mode);
                            if (!update.location.color) update.location.color = self.mman.getColor(update.mode);
                            break;
                        default:
                            marker = new LAprsMarker();
                            break;
                    }
                    self.mman.add(update.callsign, marker);
                    marker.addListener('click', function() { showMarkerInfoWindow(update.callsign); });
                    if (update.location.symbol) marker.onAdd();
                }
                self.mman.addType(update.mode);
                marker.update(update);
                marker.setMap(self.mman.isEnabled(update.mode) ? map : null);
                if (marker instanceof LFeatureMarker) {
                    marker.setMarkerOptions({symbol: update.location.symbol, color: update.location.color});
                } else if (update.location.symbol) {
                    marker.setMarkerOptions({symbol: update.location.symbol, course: update.location.course, speed: update.location.speed});
                }
                if (expectedCallsign && expectedCallsign === update.callsign) {
                    map.setView(marker.getPos());
                    showMarkerInfoWindow(update.callsign);
                    expectedCallsign = false;
                }
                if (infoWindow && infoWindow.name && infoWindow.name === update.callsign) showMarkerInfoWindow(update.callsign);
                break;
            case 'locator':
                var rectangle = self.lman.find(update.location.locator);
                if (!rectangle) {
                    rectangle = new LLocator();
                    self.lman.add(update.location.locator, rectangle);
                    rectangle.addListener('click', function() { showLocatorInfoWindow(update.location.locator, rectangle); });
                }
                self.lman.update(update.location.locator, update, map);
                if (expectedLocator && expectedLocator === update.location.locator) {
                    map.setView(rectangle.center);
                    showLocatorInfoWindow(update.location.locator, rectangle);
                    expectedLocator = false;
                }
                if (infoWindow && infoWindow.name && infoWindow.name === rectangle.locator)
                    showLocatorInfoWindow(rectangle.locator, rectangle);
                break;
        }
    });
};
