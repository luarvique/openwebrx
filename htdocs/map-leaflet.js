var mapSources = [
    {
        name: 'OpenStreetMap',
        url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
        options: {
            maxZoom: 19,
            noWrap: false,
            attribution: '© OpenStreetMap'
        },
    },
    {
        name: 'OpenTopoMap',
        url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
        options: {
            maxZoom: 17,
            noWrap: true,
            attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)'
        }
    },
    {
        name: 'Esri WorldTopo',
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
        config: {
            noWrap: true,
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
        config: {
            maxZoom: 20,
            noWrap: true,
            attribution: '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a>, &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors',
        },
        info: 'In order to use Stadia maps, you must register. Once registered, you can whitelist your domain within your account settings.'
    },
    {
        name: 'Stadia AlidadeDark',
        url: 'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png',
        config: {
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
        options: {
            layer: 'clouds_new',
            attribution: 'Map data: &copy; OpenWeatherMap'
        },
        depends: "weather_key"
    },
    {
        name: 'OpenWeatherMap',
        url: 'https://tile.openweathermap.org/map/{layer}/{z}/{x}/{y}.png?appid={apikey}',
        options: {
            layer: 'precipitation_new',
            attribution: 'Map data: &copy; OpenWeatherMap'
        },
        depends: "weather_key"
    },
    {
        name: 'WeatherRadar-USA',
        url: 'http://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/nexrad-n0q-900913/{z}/{x}/{y}.png',
        options: {
            attribution: 'Map data: &copy; Iowa State University'
        },
        depends: "!weather_key"
    },
    {
        name: 'OpenSeaMap',
        url: 'https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png',
        options: {
            attribution: 'Map data: &copy; <a href="http://www.openseamap.org">OpenSeaMap</a> contributors'
        },
    },
    {
        name: 'Maidenhead-QTH',
        createLayer: async function () {
            await $.when($.getScript('https://ha8tks.github.io/Leaflet.Maidenhead/src/L.Maidenhead.js'));
            return L.maidenhead({ color: 'rgba(100, 100, 100, 0.6)' });
        }
    },
];

// Reasonable defaults, will be overriden by server
var retention_time = 2 * 60 * 60 * 1000;
var call_retention_time = 15 * 60;
var max_calls = 5;

// Our Leaflet Map and layerControl
var map = null;
var layerControl;

// Receiver location marker
var receiverMarker = null;

// Information bubble window
var infoWindow = null;

// Updates are queued here
var updateQueue = [];

// Web socket connection management, message processing
var mapManager = new MapManager();

var query = window.location.search.replace(/^\?/, '').split('&').map(function(v){
    var s = v.split('=');
    var r = {};
    r[s[0]] = s.slice(1).join('=');
    return r;
}).reduce(function(a, b){
    return a.assign(b);
});

var expectedCallsign = query.callsign? decodeURIComponent(query.callsign) : null;
var expectedLocator  = query.locator? query.locator : null;

// https://stackoverflow.com/a/46981806/420585
function fetchStyleSheet(url, media = 'screen') {
    let $dfd = $.Deferred(),
        finish = () => $dfd.resolve(),
        $link = $(document.createElement('link')).attr({
            media,
            type: 'text/css',
            rel: 'stylesheet'
        })
        .on('load', 'error', finish)
        .appendTo('head'),
        $img = $(document.createElement('img'))
            .on('error', finish); // Support browsers that don't fire events on link elements
    $link[0].href = $img[0].src = url;
    return $dfd.promise();
}

// Get information bubble window
function getInfoWindow(name = null) {
    // If no bubble...
    if (!infoWindow || (infoWindow.name !== name)) {
        if (infoWindow) delete infoWindow;
        infoWindow = L.popup();
        infoWindow.on('remove', function() { infoWindow.name = null; });
        infoWindow.name = name;
    }
    return infoWindow;
};

// Show information bubble for a locator
function showLocatorInfoWindow(locator, rectangle) {
    // Bind information bubble to the rectangle
    infoWindow = getInfoWindow(locator);
    rectangle._rect.unbindPopup().bindPopup(infoWindow).openPopup();

    // Update information inside the bubble
    var p = new posObj(rectangle.center);
    infoWindow.setContent(
        mapManager.lman.getInfoHTML(locator, p, receiverMarker)
    );
};

// Show information bubble for a marker
function showMarkerInfoWindow(name) {
    var marker = mapManager.mman.find(name);
    if (!marker) return;

    // Bind information bubble to the marker
    infoWindow = getInfoWindow(name);
    marker._marker.unbindPopup().bindPopup(infoWindow).openPopup();

    // Update information inside the bubble
    infoWindow.setContent(marker.getInfoHTML(name, receiverMarker));
};

//
// Leaflet-SPECIFIC MAP MANAGER METHODS
//

MapManager.prototype.setReceiverName = function(name) {
    if (receiverMarker) receiverMarker.setTitle(name);
}

MapManager.prototype.removeReceiver = function() {
    if (receiverMarker) receiverMarker.setMap();
}

MapManager.prototype.initializeMap = async function(receiver_gps, api_key, weather_key) {
    if (map) {
        receiverMarker.setLatLng(receiver_gps.lat, receiver_gps.lon);
        receiverMarker.setMarkerOptions(this.config);
        receiverMarker.setMap(map);
    } else {
        var self = this;

        // load Leaflet CSS first
        await fetchStyleSheet('https://unpkg.com/leaflet@1.9.4/dist/leaflet.css');
        // now load Leaflet JS
        await $.getScript('https://unpkg.com/leaflet@1.9.4/dist/leaflet.js');
        // load geodesic and textpath plugins
        await $.getScript('https://cdn.jsdelivr.net/npm/leaflet.geodesic');
        await $.getScript('https://cdn.jsdelivr.net/npm/leaflet-textpath@1.2.3/leaflet.textpath.min.js');

        // create map
        map = L.map('openwebrx-map', { zoomControl: false, worldCopyJump: true }).setView([receiver_gps.lat, receiver_gps.lon], 5);

        // add zoom control
        new L.Control.Zoom({ position: 'bottomright' }).addTo(map);

        // add night overlay
        $.getScript('https://unpkg.com/@joergdietrich/leaflet.terminator@1.1.0/L.Terminator.js').done(function () {
            var pane = map.createPane('nite');
            pane.style.zIndex = 201;
            pane.style.pointerEvents = 'none !important';
            pane.style.cursor = 'grab !important';
            var t = L.terminator({ fillOpacity: 0.2, interactive: false, pane });
            t.addTo(map);
            setInterval(function () { t.setTime(); }, 60000); // refresh every 60 secs
            map.addEventListener('zoomstart movestart popupopen', function (e) { t.setTime(); }); // refresh on zoom and move
        });

        // create layerControl and add more maps
        if (!layerControl) {
            // used to open or collapse the layerControl by default
            // function isMobile () {
            //     try { document.createEvent("TouchEvent"); return true; }
            //     catch (e) { return false; }
            // }

            layerControl = L.control.layers({}, null, {
                collapsed: false, //isMobile(), // we have collapsing already made in the utc clock
                hideSingleBase: true,
                position: 'bottomleft'
            }).addTo(map);

            // move legend div to our layerControl
            layerControl.legend = $('.openwebrx-map-legend')
                .css({'padding': '0', 'margin': '0'})
                .insertAfter(layerControl._overlaysList);
        } // layerControl

        // Load and initialize OWRX-specific map item managers
        $.getScript('static/lib/Leaflet.js').done(function() {
            // Process any accumulated updates
            self.processUpdates(updateQueue);
            updateQueue = [];

            if (!receiverMarker) {
                receiverMarker = new LSimpleMarker();
                receiverMarker.setMarkerPosition(self.config['receiver_name'], receiver_gps.lat, receiver_gps.lon);
                receiverMarker.addListener('click', function () {
                    L.popup(receiverMarker.getPos(), {
                        content: '<h3>' + self.config['receiver_name'] + '</h3>' +
                            '<div>Receiver location</div>'
                    }).openOn(map);
                });
                receiverMarker.setMarkerOptions(this.config);
                receiverMarker.setMap(map);
            }
        });

        var map_idx = LS.loadInt('leaflet_map_idx'); // should return 0 if not found
        $.each(mapSources, function (idx, ms) {
            $('#openwebrx-map-source').append(
                $('<option></option>')
                    .attr('selected', idx == map_idx ? true : false)
                    .attr('value', idx)
                    .attr('title', ms.info)
                    .text(ms.name)
            );
            ms.layer = L.tileLayer(ms.url, ms.options);
            if (idx == map_idx) ms.layer.addTo(map);
        });

        var apiKeys = {};
        if (weather_key) {
            apiKeys['weather_key'] = weather_key;
        }

        function isMapEligible (m) {
            if (!m) return false;
            if (!m.depends || !m.depends.length) return true; // if no depends -> true
            var looking = m.depends;
            var invert = false;
            if (looking.charAt(0) === '!') {
                invert = true;
                looking = looking.slice(1);
            }
            var eligible = false; // we have deps, so default is false until we find the dep keys
            Object.keys(apiKeys).forEach(function (k) {
                if (looking === k) eligible = true; // if we have the key and depend on it -> true
            });
            return invert ? !eligible : eligible;
        }

        function addMapOverlay (name) {
            $.each(mapExtraLayers, async function (idx, mel) {
                if (mel.name === name) {
                    if (!mel.layer) {
                        if (apiKeys[mel.depends]) mel.options.apikey = apiKeys[mel.depends];
                        if (typeof mel.url !== 'undefined') {
                            mel.layer = L.tileLayer(mel.url, mel.options);
                        } else if (typeof mel.createLayer === 'function') {
                            mel.layer = await mel.createLayer();
                        } else {
                            console.error('Cannot create layer for ' + mel.name);
                        }
                    }
                    if (map.hasLayer(mel.layer))
                        map.removeLayer(mel.layer);
                    map.addLayer(mel.layer);
                }
            });
        }
        function removeMapOverlay (name) {
            $.each(mapExtraLayers, function (idx, mel) {
                if (mel.name === name) {
                    if (map.hasLayer(mel.layer))
                        map.removeLayer(mel.layer);
                }
            });
        }
        $('#openwebrx-map-source').on('change', function (e) {
            var id = this.value;
            var m = mapSources[id];
            $.each(mapSources, function (idx, ms) {
                if (map.hasLayer(ms.layer))
                    map.removeLayer(ms.layer);
            });
            map.addLayer(m.layer);
            LS.save('leaflet_map_idx', id);
            $('#openwebrx-map-extralayers').find('input').each(function (idx, inp) {
                if ($(inp).is(':checked')) {
                    addMapOverlay($(inp).attr('name'));
                }
            });
        });
        $.each(mapExtraLayers, function (idx, mel) {
            if (!isMapEligible(mel)) return;
            if ($('#openwebrx-map-layer-' + mel.name).length)
                return; // checkbox with that name exists already
            var enabled = LS.loadBool('leaflet-layer-' + mel.name); // should return false if not found
            if (enabled) addMapOverlay(mel.name);
            $('#openwebrx-map-extralayers').append(
                $('<label><input type="checkbox" ' +
                    'name="' + mel.name + '" ' +
                    'idx="' + idx + '" ' +
                    'id="openwebrx-map-layer-' + mel.name + '"' +
                    (enabled ? ' checked ' : '') +
                    '>' + mel.name + '</label>'
                ).on('change', function (e) {
                    LS.save('leaflet-layer-' + mel.name, e.target.checked);
                    if (e.target.checked) {
                        addMapOverlay(mel.name);
                    } else {
                        removeMapOverlay(mel.name);
                    }
                })
            );
        });

        // Create map legend selectors
        self.setupLegendFilters(layerControl.legend);
    }
};

MapManager.prototype.processUpdates = function(updates) {
    var self = this;

    if (typeof(LMarker) === 'undefined') {
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

                // If new item, create a new marker for it
                if (!marker) {
                    switch(update.mode) {
                        case 'HFDL': case 'VDL2': case 'ADSB': case 'ACARS':
                            marker = new LAircraftMarker();
                            break;
                        case 'APRS': case 'AIS': case 'HDR':
                            marker = new LAprsMarker();
                            break;
                        case 'KiwiSDR': case 'WebSDR': case 'OpenWebRX':
                        case 'Stations': case 'Repeaters':
                            marker = new LFeatureMarker();
                            // If no symbol or color supplied, use defaults by type
                            if (!update.location.symbol) update.location.symbol = self.mman.getSymbol(update.mode);
                            if (!update.location.color)  update.location.color  = self.mman.getColor(update.mode);
                            break;
                        default:
                            marker = new LAprsMarker();
                            break;
                    }

                    self.mman.add(update.callsign, marker);
                    marker.addListener('click', function() {
                        showMarkerInfoWindow(update.callsign);
                    });

                    // If displaying a symbol, create it
                    if (update.location.symbol) marker.onAdd();
                }

                // Keep track of new marker types as they may change
                self.mman.addType(update.mode);

                // Update marker attributes and age
                marker.update(update);

                // Assign marker to map
                marker.setMap(self.mman.isEnabled(update.mode)? map : null);

                // Apply marker options
                if (marker instanceof LFeatureMarker) {
                    marker.setMarkerOptions({
                        symbol : update.location.symbol,
                        color  : update.location.color
                    });
                } else if (update.location.symbol) {
                    marker.setMarkerOptions({
                        symbol : update.location.symbol,
                        course : update.location.course,
                        speed  : update.location.speed
                    });
                }

                if (expectedCallsign && expectedCallsign === update.callsign) {
                    map.setView(marker.getPos());
                    showMarkerInfoWindow(update.callsign);
                    expectedCallsign = false;
                }

                if (infoWindow && infoWindow.name && infoWindow.name === update.callsign) {
                    showMarkerInfoWindow(update.callsign);
                }
            break;

            case 'locator':
                var rectangle = self.lman.find(update.callsign);

                // If new item, create a new locator for it
                if (!rectangle) {
                    rectangle = new LLocator();
                    self.lman.add(update.location.locator, rectangle);
                    rectangle.addListener('click', function() {
                        showLocatorInfoWindow(update.location.locator, rectangle);
                    });
                }

                // Update locator attributes, center, age
                self.lman.update(update.location.locator, update, map);

                if (expectedLocator && expectedLocator === update.location.locator) {
                    map.setView(rectangle.center);
                    showLocatorInfoWindow(update.location.locator, rectangle);
                    expectedLocator = false;
                }

                if (infoWindow && infoWindow.name && infoWindow.name === rectangle.locator) {
                    showMarkerInfoWindow(update.location.locator, rectangle);
                }
            break;
        }
    });
};
