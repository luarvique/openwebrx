//
// Leaflet-Specific Marker
//

function LMarker () {
    this._marker = L.marker();
}

LMarker.prototype.onAdd = function() {
    this.div   = this.create();

    this.setIcon(L.divIcon({
        html        : this.div,
        iconSize    : this.getSize(),
        popupAnchor : this.getAnchorOffset(),
        className   : 'dummy'
    }));
};

LMarker.prototype.setMarkerOptions = function(options) {
    $.extend(this, options);
    if (typeof this.draw !== 'undefined') {
        this.draw();
    }
};

LMarker.prototype.setMap = function (map = null) {
    if (map) this._marker.addTo(map); else this._marker.remove();
};

LMarker.prototype.addListener = function (e, f) {
    this._marker.on(e, f);
};

LMarker.prototype.getPos = function () {
    return [this.position.lat(), this.position.lng()];
};

LMarker.prototype.setMarkerOpacity = function(opacity) {
    this._marker.setOpacity(opacity);
};

LMarker.prototype.setLatLng = function(lat, lon) {
    this._marker.setLatLng([lat, lon]);
    this.position = new posObj([lat, lon]);
};

LMarker.prototype.setTitle = function(title) {
    this._marker.options.title = title;
};

LMarker.prototype.setIcon = function(opts) {
    this._marker.setIcon(opts);
};

LMarker.prototype.setMarkerPosition = function(title, lat, lon) {
    this.setLatLng(lat, lon);
    this.setTitle(title);
};

// Leaflet-Specific FeatureMarker
function LFeatureMarker() { $.extend(this, new LMarker(), new FeatureMarker()); }

// Leaflet-Specific AprsMarker
function LAprsMarker () { $.extend(this, new LMarker(), new AprsMarker()); }

// Leaflet-Specific AircraftMarker
function LAircraftMarker () { $.extend(this, new LMarker(), new AircraftMarker()); }

// Leaflet-Specific SimpleMarker
function LSimpleMarker() { $.extend(this, new LMarker(), new AprsMarker()); }

//
// Leaflet-Specific Locator
//

function LLocator() {
    this._rect = L.rectangle([[0,0], [1,1]], {
        color       : '#FFFFFF',
        weight      : 0,
        fillOpacity : 1
    });
}

LLocator.prototype = new Locator();

LLocator.prototype.setMap = function(map = null) {
    if (map) this._rect.addTo(map); else this._rect.remove();
};

LLocator.prototype.setCenter = function(lat, lon) {
    this.center = [lat, lon];
    this._rect.setBounds([[lat - 0.5, lon - 1], [lat + 0.5, lon + 1]]);
};

LLocator.prototype.setColor = function(color) {
    this._rect.setStyle({ color: color });
};

LLocator.prototype.setOpacity = function(opacity) {
    this._rect.setStyle({
        opacity     : LocatorManager.strokeOpacity * opacity,
        fillOpacity : LocatorManager.fillOpacity * opacity
    });
};

LLocator.prototype.addListener = function (e, f) {
    this._rect.on(e, f);
};

//
// Leaflet-Specific Call
//

function LCall() {
    // https://github.com/henrythasler/Leaflet.Geodesic
    // inherits from leaflet's polyline
    this._line = L.geodesic([[0, 0], [0, 0]], {
        dashArray  : [4, 4],
        dashOffset : 0,
        color      : '#000000',
        opacity    : 0.5,
        weight     : 1
    });
    // Ok, so textpath plugin is deleting its node and creates it again.
    // So we loose our settings (color, opacity) on each refresh
    // like when zooming in/out or dragging the map.
    // We need to replace its refresh function and apply our settings again.
    this._line._orgUpdatePath = this._line._updatePath;
    this._line._updatePath = () => {
        this._line._orgUpdatePath.call(this._line);
        if (typeof this._line._last_color !== 'undefined' && this._line._textNode)
            this._line._textNode.style.color = this._line._last_color;
        if (typeof this._line._last_opacity !== 'undefined' && this._line._textNode) {
            this._line._textNode.style.opacity = this._line._last_opacity;
        }
    }
}

LCall.prototype = new Call();

LCall.prototype.setMap = function(map = null) {
    if (map) this._line.addTo(map); else this._line.remove();
};

LCall.prototype.setEnds = function(lat1, lon1, lat2, lon2) {
    this._line.setLatLngs([[lat1, lon1], [lat2, lon2]]);
    const totalDistance = (this._line.statistics.totalDistance !== undefined
        ? (this._line.statistics.totalDistance > 10000)
            ? (this._line.statistics.totalDistance / 1000).toFixed(0) + ' km'
            : (this._line.statistics.totalDistance).toFixed(0) + ' m'
        : '???')
    // options for setText(): https://github.com/makinacorpus/Leaflet.TextPath
    this._line.setText('►' + totalDistance, { offset: -3, center: true });
};

LCall.prototype.setColor = function(color) {
    this._line.setStyle({ color: color });
    // Leaflet.Geodesic does not provide its own setStyle method, it
    // just passes it to Leaflet's polyline. Thus, we need to update
    // the textNode to reflect changes.
    if (this._line._textNode) this._line._textNode.style.color = color;
    this._line._last_color = color;
};

LCall.prototype.setOpacity = function(opacity) {
    this._line.setStyle({ opacity: opacity });
    // Leaflet.Geodesic does not provide its own setStyle method, it
    // just passes it to Leaflet's polyline. Thus, we need to update
    // the textNode to reflect changes.
    if (this._line._textNode) this._line._textNode.style.opacity = opacity;
    this._line._last_opacity = opacity;
};

//
// Position object
//

function posObj(pos) {
    if (typeof pos === 'undefined' || typeof pos[1] === 'undefined') {
        console.error('Cannot create position object with no LatLng.');
        return;
    }
    this._lat = pos[0];
    this._lng = pos[1];
}

posObj.prototype.lat = function () { return this._lat; };
posObj.prototype.lng = function () { return this._lng; };
