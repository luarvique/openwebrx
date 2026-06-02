//
// GoogleMaps-Specific Marker
//

function GMarker() {}
GMarker.prototype = new google.maps.OverlayView();

GMarker.prototype.setMarkerOptions = function(options) {
    this.setOptions(options);
    this.draw();
};

GMarker.prototype.onAdd = function() {
    // Create HTML elements representing the mark
    var div = this.create();

    var self = this;
    google.maps.event.addDomListener(div, "click", function(event) {
        event.stopPropagation();
        google.maps.event.trigger(self, "click", event);
    });

    var panes = this.getPanes();
    panes.overlayImage.appendChild(div);
};

GMarker.prototype.getAnchorPoint = function() {
    var offset = this.getAnchorOffset();
    return new google.maps.Point(offset[0], offset[1]);
};

GMarker.prototype.setMarkerOpacity = function(opacity) {
    this.setOptions({ opacity: opacity });
};

GMarker.prototype.setMarkerPosition = function(title, lat, lon) {
    this.setOptions({
        title    : title,
        position : new google.maps.LatLng(lat, lon)
    });
};

//
// GoogleMaps-Specific FeatureMarker
//

function GFeatureMarker() { $.extend(this, new FeatureMarker()); }
GFeatureMarker.prototype = new GMarker();

GFeatureMarker.prototype.place = function() {
    // Project location and place symbol
    var div = this.div;
    if (div) {
        var point = this.getProjection().fromLatLngToDivPixel(this.position);
        if (point) {
            div.style.left = point.x - this.symWidth / 2 + 'px';
            div.style.top = point.y - this.symHeight / 2 + 'px';
        }
    }
};

//
// GoogleMaps-Specific AprsMarker
//

function GAprsMarker() { $.extend(this, new AprsMarker()); }
GAprsMarker.prototype = new GMarker();

GAprsMarker.prototype.place = function() {
    // Project location and place symbol
    var div = this.div;
    if (div) {
        var point = this.getProjection().fromLatLngToDivPixel(this.position);
        if (point) {
            div.style.left = point.x - 12 + 'px';
            div.style.top = point.y - 12 + 'px';
        }
    }
};

//
// GoogleMaps-Specific AircraftMarker
//

function GAircraftMarker() { $.extend(this, new AircraftMarker()); }
GAircraftMarker.prototype = new GMarker();

GAircraftMarker.prototype.place = function() {
    // Project location and place symbol
    var div = this.div;
    if (div) {
        var point = this.getProjection().fromLatLngToDivPixel(this.position);
        if (point) {
            div.style.left = point.x - 36 + 'px';
            div.style.top = point.y - 36 + 'px';
        }
    }
};

//
// GoogleMaps-Specific SimpleMarker
//

function GSimpleMarker() { $.extend(this, new AprsMarker()); }
GSimpleMarker.prototype = new google.maps.Marker();

GSimpleMarker.prototype.setMarkerOpacity = function(opacity) {
    this.setOptions({ opacity: opacity });
};

GSimpleMarker.prototype.setMarkerPosition = function(title, lat, lon) {
    this.setOptions({
        title    : title,
        position : new google.maps.LatLng(lat, lon)
    });
};

GSimpleMarker.prototype.setMarkerOptions = function(options) {
    this.setOptions(options);
    this.draw();
};

//
// GoogleMaps-Specific Locator
//

function GLocator() {
    this.rect = new google.maps.Rectangle({
        strokeWeight : 0,
        strokeColor  : "#FFFFFF",
        fillColor    : "#FFFFFF",
        fillOpacity  : 1.0
    });
}

GLocator.prototype = new Locator();

GLocator.prototype.setMap = function(map = null) {
    this.rect.setMap(map);
};

GLocator.prototype.setCenter = function(lat, lon) {
    this.center = new google.maps.LatLng({lat: lat, lng: lon});

    this.rect.setOptions({ bounds : {
        north : lat - 0.5,
        south : lat + 0.5,
        west  : lon - 1.0,
        east  : lon + 1.0
    }});
}

GLocator.prototype.setColor = function(color) {
    this.rect.setOptions({ strokeColor: color, fillColor: color });
};

GLocator.prototype.setOpacity = function(opacity) {
    this.rect.setOptions({
        strokeOpacity : LocatorManager.strokeOpacity * opacity,
        fillOpacity   : LocatorManager.fillOpacity * opacity
    });
};

//
// GoogleMaps-Specific Call
//

function GCall() {
    const dash = {
        path          : 'M 0,-1 0,1',
        scale         : 2,
        strokeColor   : '#000000',
        strokeWeight  : 1,
        strokeOpacity : 0.5
    };
    const arrow = {
        path          : google.maps.SymbolPath.FORWARD_CLOSED_ARROW,
        scale         : 1.5,
        strokeColor   : '#000000',
        strokeWeight  : 1,
        strokeOpacity : 0.5,
        fillOpacity   : 1.0
    };

    this.line = new google.maps.Polyline({
        geodesic      : true,
        strokeColor   : '#000000',
        strokeOpacity : 0,
        strokeWeight  : 0,
        icons         : [
             { icon: dash, offset: '0%', repeat: '8px' },
             { icon: arrow, offset: '25px' },
             { icon: arrow, offset: '100%' }
        ]
    });
}

GCall.prototype = new Call();

GCall.prototype.setMap = function(map = null) {
    this.line.setMap(map);
};

GCall.prototype.setEnds = function(lat1, lon1, lat2, lon2) {
    this.line.setOptions({ path : [
        { lat: lat1, lng: lon1 }, { lat: lat2, lng: lon2 }
    ]});
};

GCall.prototype.setColor = function(color) {
    this.line.icons.forEach((x) => { x.icon.strokeColor = color; });
    this.line.setOptions({ icons: this.line.icons });
//    this.line.setOptions({ strokeColor: color });
};

GCall.prototype.setOpacity = function(opacity) {
    this.line.icons.forEach((x) => {
        x.icon.strokeOpacity = opacity;
        x.icon.fillOpacity = opacity;
    });
    this.line.setOptions({ icons: this.line.icons });
//    this.line.setOptions({ strokeOpacity : opacity });
};
