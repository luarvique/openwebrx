//
// Map Locators Management
//

LocatorManager.strokeOpacity = 0.8;
LocatorManager.fillOpacity   = 0.35;

function LocatorManager(spectral = true) {
    // Base colors used for the color scale
    var colors = spectral? ['darkviolet', 'blue', 'green', 'red'] : ['red', 'blue', 'green'];

    // Current locators
    this.locators = {};
    this.bands    = {};
    this.modes    = {};
    this.calls    = [];

    // The color scale used
    this.colorScale = chroma.scale(colors).mode('hsl');

    // Current coloring mode
    this.colorMode = 'band';
}

LocatorManager.prototype.getColors = function() {
    var colors =
        this.colorMode === 'band'? this.bands
      : this.colorMode === 'mode'? this.modes
      : null;
    return colors;
};

LocatorManager.prototype.find = function(id) {
    return id in this.locators? this.locators[id] : null;
};

LocatorManager.prototype.add = function(id, locator) {
    // Add a new locator, if missing
    if (!(id in this.locators)) {
        locator.create(id);
        locator.colorKeys = this.getColors();
        locator.colorMode = this.colorMode;
        this.locators[id] = locator;
    }

    // Return locator
    return this.locators[id];
};

LocatorManager.prototype.update = function(id, data, map) {
    // Do not update unless locator present
    if (!(id in this.locators)) return false;

    // Make sure we have valid band and mode names
    if (!data.band) data.band = 'other';
    if (!data.mode) data.mode = 'other';

    // Keep track of bands
    if (!(data.band in this.bands)) {
        this.bands[data.band] = '#000000';
        this.assignColors(this.bands);
        if (this.colorMode === 'band') {
            this.reColor();
            this.updateLegend();
        }
    }

    // Keep track of modes
    if (!(data.mode in this.modes)) {
        this.modes[data.mode] = '#000000';
        this.assignColors(this.modes);
        if (this.colorMode === 'mode') {
            this.reColor();
            this.updateLegend();
        }
    }

    // Update locator
    this.locators[id].update(data, map);
    return true;
};

LocatorManager.prototype.getSortedKeys = function(colorMap) {
    var keys = colorMap? Object.keys(colorMap) : [];

    // Sort color keys
    keys.sort(function(a, b) {
        var pa = parseFloat(a);
        var pb = parseFloat(b);
        if (isNaN(pa) || isNaN(pb)) return a.localeCompare(b);
        return pa - pb;
    });

    return keys;
};

LocatorManager.prototype.assignColors = function(colorMap) {
    // Recompute colors
    var keys = this.getSortedKeys(colorMap);
    var colors = this.colorScale.colors(keys.length);
    for(var j=0 ; j<keys.length ; ++j) {
        colorMap[keys[j]] = colors[j];
    }
};

LocatorManager.prototype.ageAll = function() {
    var now = new Date().getTime();
    var data = this.locators;
    $.each(data, function(id, x) {
        if (!x.age(now)) delete data[id];
    });
};

LocatorManager.prototype.clear = function() {
    // Remove all locators from the map
    $.each(this.locators, function(_, x) { x.setMap(); });
    // Delete all locators
    this.locators = {};
};

LocatorManager.prototype.setFilter = function(filterBy = null) {
    var colors = this.getColors();
    this.assignColors(colors);

    if (filterBy) {
        $.each(colors, function(id, x) {
            if (id !== filterBy) colors[id] = null;
        });
    }

    this.reColor();
    this.updateLegend();
};

LocatorManager.prototype.reColor = function() {
    var mode = this.colorMode;
    var keys = this.getColors();

    $.each(this.locators, function(_, x) {
        x.colorKeys = keys;
        x.colorMode = mode;
        x.reColor();
    });
};

LocatorManager.prototype.updateLegend = function() {
    var colors = this.getColors();
    var keys = this.getSortedKeys(colors);
    var list = $.map(keys, function(key) {
        var value = colors[key]? colors[key] : '#000000';
        return '<li class="square' + (colors[key]? '' : ' disabled')
            + '" data-selector="' + key
            + '"><span class="illustration" style="background-color:'
            + chroma(value).alpha(LocatorManager.fillOpacity) + ';border-color:'
            + chroma(value).alpha(LocatorManager.strokeOpacity) + ';"></span>'
            + key + '</li>';
    });

    $(".openwebrx-map-legend .content").html('<ul>' + list.join('') + '</ul>');
}

LocatorManager.prototype.setColorMode = function(newColorMode) {
    $('#openwebrx-map-colormode').val(newColorMode);
    LS.save('mapColorMode', newColorMode);
    // Clearing filter when color mode is changed
    this.colorMode = newColorMode;
    this.setFilter();
};

LocatorManager.prototype.getInfoHTML = function(id, pos, receiverMarker = null) {
    return id in this.locators? this.locators[id].getInfoHTML(id, pos, receiverMarker) : '';
}

//
// Generic Map Locator
//     Derived classes have to implement:
//     setMap(), setCenter(), setColor(), setOpacity()
//

function Locator() {}

Locator.prototype.create = function(id) {
    // No callsigns yet
    this.callsigns = {};
    this.lastseen  = 0;
    this.colorKeys = null;
    this.colorMode = 'band';

    // Center locator at its maidenhead id
    var center = Utils.loc2latlng(id);
    this.setCenter(center[0], center[1]);
}

Locator.prototype.update = function(data, map) {
    // Update callsign information
    this.callsigns[data.callsign] = {
        callsign : data.callsign,
        lastseen : data.lastseen,
        relayed  : 'hops' in data && data.hops.length > 0,
        mode     : data.mode,
        band     : data.band,
        weight   : 1
    };

    // Keep track of the total last-seen for this locator
    this.lastseen = Math.max(data.lastseen, this.lastseen);

    // Update color and opacity
    this.map = map;
    this.reColor();

    // Age locator
    this.age(new Date().getTime());
};

Locator.prototype.reColor = function() {
    var c = this.getColor();
    if (!c) {
        this.setMap();
    } else {
        this.setColor(c);
        this.setMap(this.map);
    }
};

Locator.prototype.getColor = function() {
    var keys = this.colorKeys;
    if (!keys) return null;

    var attr   = this.colorMode;
    var maxw   = 0.0;
    var weight = [];
    var colors = $.map(this.callsigns, function(x) {
        var y = x[attr] in keys? keys[x[attr]] : null;
        if (y) {
            var w = x.weight;
            maxw = Math.max(maxw, w);
            weight.push(w);
        }
        return y;
    });

    if (!colors.length) return null;

    return chroma.average(colors, 'lrgb', weight).alpha(
        maxw * (0.4 + Math.min(0.5, colors.length / 15))
    );
};

Locator.prototype.age = function(now) {
    var newest = 0;
    var data = this.callsigns;
    var cnt0 = Object.keys(data).length;

    // Perform an initial check on the whole locator
    if (now - this.lastseen > retention_time) {
        this.callsigns = {};
        this.setMap();
        return false;
    }

    // Scan individual callsigns
    $.each(data, function(id, x) {
        var age = now - x.lastseen;
        if (age > retention_time) {
            delete data[id];
        } else {
            x.weight = Utils.getOpacityScale(age);
            newest = Math.max(newest, x.lastseen);
        }
    });

    // Keep track of the total last-seen for this locator
    this.lastseen = newest;

    // Update locator's color and opacity
    var cnt1 = Object.keys(data).length;
//    if (cnt1 == cnt0) return true;
    if (cnt1 > 0) {
        this.reColor();
        return true;
    } else {
        this.setMap();
        return false;
    }
};

Locator.prototype.getInfoHTML = function(locator, pos, receiverMarker = null) {
    // Filter out currently hidden bands/modes, sort by recency
    var self = this;
    var inLocator = $.map(this.callsigns, function(x, id) {
        return self.colorKeys && self.colorKeys[x[self.colorMode]]? x : null;
    }).sort(function(a, b){
        return b.lastseen - a.lastseen;
    });

    var odd = false;
    var list = inLocator.map(function(x) {
        var mc = self.colorMode === 'mode'? chroma(self.colorKeys[x.mode]).alpha(0.5) : 'inherit';
        var bc = self.colorMode === 'band'? chroma(self.colorKeys[x.band]).alpha(0.5) : 'inherit';

        var row = '<tr style="background-color:' + (odd? '#E0FFE0':'#FFFFFF')
            + ';color:' + (x.relayed? '#808080':'#000000') + ';">'
            + '<td>' + Utils.linkifyCallsign(x.callsign) + '</td>'
            + '<td>' + moment(x.lastseen).fromNow() + '</td>'
            + '<td style="background-color:' + mc + ';">' + x.mode + '</td>'
            + '<td style="background-color:' + bc + ';">' + x.band + '</td>'
            + '</tr>';

        odd = !odd;
        return row;
    }).join("");

    var distance = receiverMarker?
        " at " + Utils.distanceKm(receiverMarker.position, pos) + " km" : "";

    var latest = inLocator[0];
    var lastReport = moment(latest.lastseen).fromNow() + ' using '
        + latest.mode + ( latest.band ? ' on ' + latest.band : '' );

    return '<h3>Locator ' + locator + distance + '</h3>'
        + '<div align="center">' + lastReport + '</div>'
        + Utils.makeListTitle('Active Callsigns')
        + '<table align="center" class="openwebrx-map-info">' + list + '</table>';
};
