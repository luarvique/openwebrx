// Reasonable defaults, will be overriden by server
var retention_time = 2 * 60 * 60 * 1000;
var call_retention_time = 15 * 60;
var max_calls = 5;

// Our Google Map
var map = null;

// Receiver location marker
var receiverMarker = null;

// Information bubble window
var infoWindow = null;

// Updates are queued here
var updateQueue = [];

// Web socket connection management, message processing
var mapManager = new MapManager();
var mapClientConfig = OWRXMapLayers.readConfig();
var query = new URLSearchParams(window.location.search);
var expectedCallsign = query.get('callsign');
var expectedLocator = query.get('locator');

// Get information bubble window
function getInfoWindow(name = null) {
    if (!infoWindow) {
        infoWindow = new google.maps.InfoWindow();
        google.maps.event.addListener(infoWindow, 'closeclick', function() {
            delete infoWindow.name;
        });
    }
    infoWindow.name = name;
    return infoWindow;
};

// Show information bubble for a locator
function showLocatorInfoWindow(locator, pos) {
    var iw = getInfoWindow(locator);

    iw.setContent(mapManager.lman.getInfoHTML(locator, pos, receiverMarker));
    iw.setPosition(pos);
    iw.open(map);
};

// Show information bubble for a marker
function showMarkerInfoWindow(name, pos) {
    var marker = mapManager.mman.find(name);
    var iw = getInfoWindow(name);

    iw.setContent(marker.getInfoHTML(name, receiverMarker));
    iw.open(map, marker);
};

// Show information bubble for the receiver location
function showReceiverInfoWindow(marker) {
    var iw = getInfoWindow();
    iw.setContent(
        '<h3>' + OWRXMapLayers.escapeText(marker.config['receiver_name']) + '</h3>' +
        '<div>Receiver Location</div>'
    );
    iw.open(map, marker);
};

//
// GOOGLE-SPECIFIC MAP MANAGER METHODS
//

MapManager.prototype.setReceiverName = function(name) {
    if (receiverMarker) receiverMarker.setOptions({ title: name });
}

MapManager.prototype.removeReceiver = function() {
    if (receiverMarker) receiverMarker.setMap();
}

MapManager.prototype.initializeMap = function(receiver_gps, api_key, weather_key) {
    var self = this;
    self._receiverGPS = receiver_gps;
    function receiverPos() { return {lat: self._receiverGPS.lat, lng: self._receiverGPS.lon}; }
    function updateReceiver() {
        if (receiverMarker) receiverMarker.setOptions({
            map: mapClientConfig.map_show_receiver === false ? null : map,
            position: receiverPos(), title: self.config['receiver_name'], config: self.config
        });
    }
    if (map) { updateReceiver(); return; }
    if (self._googleLoading) return;
    self._googleLoading = true;
    // The controller falls back to Leaflet when Google is disabled or its key is absent.
    $.getScript('https://maps.googleapis.com/maps/api/js?key=' + encodeURIComponent(api_key)).done(function() {
        map = new google.maps.Map($('.openwebrx-map')[0], {
            zoomControl: true, cameraControl: false, mapTypeControl: true,
            scaleControl: true, streetViewControl: true, rotateControl: true, fullscreenControl: true,
            center: mapClientConfig.map_use_initial_view
                ? {lat: mapClientConfig.map_initial_lat, lng: mapClientConfig.map_initial_lon} : receiverPos(),
            zoom: mapClientConfig.map_use_initial_view ? mapClientConfig.map_initial_zoom : 5
        });
        if (mapClientConfig.map_night !== false) {
            $.getScript('static/lib/nite-overlay.js').done(function() {
                nite.init(map);
                var timer = setInterval(function() { if (!document.hidden) nite.refresh(); }, 10000);
                window.addEventListener('pagehide', function(event) { if (!event.persisted) clearInterval(timer); });
            });
        }
        $.getScript('static/lib/GoogleMaps.js').done(function() {
            self.processUpdates(updateQueue);
            updateQueue = [];
        });
        var $legend = $('.openwebrx-map-legend');
        self.setupLegendFilters($legend);
        map.controls[google.maps.ControlPosition.LEFT_BOTTOM].push($legend[0]);
        if (!receiverMarker) {
            receiverMarker = new google.maps.Marker();
            receiverMarker.addListener('click', function() { showReceiverInfoWindow(receiverMarker); });
        }
        updateReceiver();
    }).fail(function() {
        var notice = document.createElement('div'); notice.className = 'owrx-map-error';
        notice.setAttribute('role', 'alert');
        notice.textContent = 'Google Maps could not load. Use the Map toolbar button to switch to Leaflet.';
        document.getElementById('openwebrx-map').appendChild(notice);
    }).always(function() { self._googleLoading = false; });
};

MapManager.prototype.processUpdates = function(updates) {
    var self = this;

    if (typeof(GMarker) === 'undefined' || !map) {
        updateQueue = updateQueue.concat(updates);
        return;
    }

    updates.forEach(function(update) {
        // Process caller-callee updates
        if ('caller' in update) {
            var call = new GCall();
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
                        case 'HFDL': case 'VDL2': case 'ADSB':
                        case 'ACARS': case 'UAT':
                            marker = new GAircraftMarker();
                            break;
                        case 'APRS': case 'AIS': case 'HDR': case 'SONDE': case 'Meshtastic':
                            marker = new GAprsMarker();
                            break;
                        case 'KiwiSDR': case 'WebSDR': case 'OpenWebRX':
                        case 'Stations': case 'Repeaters':
                            marker = new GFeatureMarker();
                            // If no symbol or color supplied, use defaults by type
                            if (!update.location.symbol) update.location.symbol = self.mman.getSymbol(update.mode);
                            if (!update.location.color)  update.location.color  = self.mman.getColor(update.mode);
                            break;
                        default:
                            marker = new GSimpleMarker();
                            break;
                    }

                    self.mman.add(update.callsign, marker);
                    marker.addListener('click', function() {
                        showMarkerInfoWindow(update.callsign, marker.position);
                    });
                }

                // Keep track of new marker types as they may change
                self.mman.addType(update.mode);

                // Update marker attributes and age
                marker.update(update);

                // Assign marker to map
                marker.setMap(self.mman.isEnabled(update.mode)? map : null);

                // Apply marker options
                if (marker instanceof GFeatureMarker) {
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
                    map.panTo(marker.position);
                    showMarkerInfoWindow(update.callsign, marker.position);
                    expectedCallsign = false;
                }

                if (infoWindow && infoWindow.name && infoWindow.name === update.callsign) {
                    showMarkerInfoWindow(update.callsign, marker.position);
                }
            break;

            case 'locator':
                var rectangle = self.lman.find(update.location.locator);

                // If new item, create a new locator for it
                if (!rectangle) {
                    rectangle = new GLocator();
                    self.lman.add(update.location.locator, rectangle);
                    rectangle.rect.addListener('click', function() {
                        showLocatorInfoWindow(update.location.locator, rectangle.center);
                    });
                }

                // Update locator attributes, center, age
                self.lman.update(update.location.locator, update, map);

                if (expectedLocator && expectedLocator === update.location.locator) {
                    map.panTo(rectangle.center);
                    showLocatorInfoWindow(update.location.locator, rectangle.center);
                    expectedLocator = false;
                }

                if (infoWindow && infoWindow.name && infoWindow.name === update.location.locator) {
                    showLocatorInfoWindow(update.location.locator, rectangle.center);
                }
            break;
        }
    });
};
