//
// Map Markers Management
//

function MarkerManager() {
    // Current markers
    this.markers = {};

    // Currently known marker types
    this.types = {};

    // Colors used for marker types
    this.colors = {
        'KiwiSDR'   : '#800000',
        'WebSDR'    : '#000080',
        'OpenWebRX' : '#004000',
        'HFDL'      : '#004000',
        'VDL2'      : '#000080',
        'ADSB'      : '#800000',
        'ACARS'     : '#000000'
    };

    // Symbols used for marker types
    this.symbols = {
        'KiwiSDR'   : '&tridot;',
        'WebSDR'    : '&tridot;',
        'OpenWebRX' : '&tridot;',
        'Stations'  : '&#9041;', //'&#9678;',
        'Repeaters' : '&bowtie;',
        'APRS'      : '&#9872;',
        'AIS'       : '&apacir;',
        'HFDL'      : '&#9992;',
        'VDL2'      : '&#9992;',
        'ADSB'      : '&#9992;',
        'ACARS'     : '&#9992;'
    };

    // Marker type shown/hidden status
    this.enabled = {
        'KiwiSDR'   : false,
        'WebSDR'    : false,
        'OpenWebRX' : false,
        'Stations'  : false,
        'Repeaters' : false
    };
}

MarkerManager.prototype.getColor = function(type) {
    // Default color is black
    return type in this.colors? this.colors[type] : '#000000';
};

MarkerManager.prototype.getSymbol = function(type) {
    // Default symbol is a rombus
    return type in this.symbols? this.symbols[type] : '&#9671;';
};

MarkerManager.prototype.isEnabled = function(type) {
    // Features are shown by default
    return type in this.enabled? this.enabled[type] : true;
};

MarkerManager.prototype.toggle = function(map, type, onoff) {
    // Keep track of each feature table being show or hidden
    this.enabled[type] = onoff;

    // Show or hide features on the map
    $.each(this.markers, function(_, x) {
        if (x.mode === type) x.setMap(onoff ? map : undefined);
    });
};

MarkerManager.prototype.addType = function(type) {
    // Do not add feature twice
    if (type in this.types) return;

    // Determine symbol and its color
    var color   = this.getColor(type);
    var symbol  = this.getSymbol(type);
    var enabled = this.isEnabled(type);

    // Add type to the list of known types
    this.types[type]   = symbol;
    this.enabled[type] = enabled;

    // If there is a list of features...
    var $content = $('.openwebrx-map-legend').find('.features');
    if($content)
    {
        // Add visual list item for the type
        $content.append(
            '<li class="square' + (enabled? '':' disabled') +
            '" data-selector="' + type + '">' +
            '<span class="feature" style="color:' + color + ';">' +
            symbol + '</span>' + type + '</li>'
        );
    }
};

MarkerManager.prototype.find = function(id) {
    return id in this.markers? this.markers[id] : null;
};

MarkerManager.prototype.add = function(id, marker) {
    this.markers[id] = marker;
};

MarkerManager.prototype.ageAll = function() {
    var now = new Date().getTime();
    var data = this.markers;
    $.each(data, function(id, x) {
        if (!x.age(now - x.lastseen)) delete data[id];
    });
};

MarkerManager.prototype.clear = function() {
    // Remove all markers from the map
    $.each(this.markers, function(_, x) { x.setMap(); });
    // Delete all markers
    this.markers = {};
};

//
// Generic Map Marker
// Derived classes have to implement:
//     setMap(), setMarkerOpacity()
//

function Marker() {}

// Wrap given callsign or other ID into a clickable link.
Marker.linkify = function(name, url = null, linkEntity = null) {
    // If no specific link entity, use the ID itself
    if (linkEntity == null) linkEntity = name;

    // If no URL given, assume HAM callsign
    if ((url == null) || (url == '')) url = callsign_url;

    // Must have valid ID and lookup URL
    if ((name == '') || (url == null) || (url == '')) {
        return name;
    } else {
        return '<a target="callsign_info" href="' +
            url.replaceAll('{}', linkEntity) + '">' + name + '</a>';
    }
};

// Create link to tune OWRX to the given frequency and modulation.
Marker.linkifyFreq = function(freq, mod) {
    var text;
    if (freq >= 30000000) {
        text = "" + (freq / 1000000.0) + "MHz";
    } else if (freq >= 10000) {
        text = "" + (freq / 1000.0) + "kHz";
    } else {
        text = "" + freq + "Hz";
    }

    return '<a target="openwebrx-rx" href="/#freq=' + freq +
        ',mod=' + mod + '">' + text + '</a>';
};

// Compute distance, in kilometers, between two latlons.
Marker.distanceKm = function(p1, p2) {
    // Earth radius in km
    var R = 6371.0;
    // Convert degrees to radians
    var rlat1 = p1.lat() * (Math.PI/180);
    var rlat2 = p2.lat() * (Math.PI/180);
    // Compute difference in radians
    var difflat = rlat2-rlat1;
    var difflon = (p2.lng()-p1.lng()) * (Math.PI/180);
    // Compute distance
    d = 2 * R * Math.asin(Math.sqrt(
        Math.sin(difflat/2) * Math.sin(difflat/2) +
        Math.cos(rlat1) * Math.cos(rlat2) * Math.sin(difflon/2) * Math.sin(difflon/2)
    ));
    return Math.round(d);
};

// Truncate string to a given number of characters, adding "..." to the end.
Marker.truncate = function(str, count) {
    return str.length > count? str.slice(0, count) + '&mldr;' : str;
};

// Convert degrees to compass direction.
Marker.degToCompass = function(deg) {
    dir = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
    return dir[Math.floor((deg/22.5) + 0.5) % 16];
};

// Convert given name to an information section title.
Marker.makeListTitle = function(name) {
    return '<div style="border-bottom:2px solid;"><b>' + name + '</b></div>';
};

// Convert given name/value to an information section item.
Marker.makeListItem = function(name, value) {
    return '<div style="display:flex;justify-content:space-between;border-bottom:1px dotted;white-space:nowrap;">'
        + '<span>' + name + '&nbsp;&nbsp;&nbsp;&nbsp;</span>'
        + '<span>' + value + '</span>'
        + '</div>';
};

// Get opacity value in the 0..1 range based on the given age.
Marker.getOpacityScale = function(age) {
    var scale = 1;
    if (age >= retention_time / 2) {
        scale = (retention_time - age) / (retention_time / 2);
    }
    return Math.max(0, Math.min(1, scale));
};

// Set marker's opacity based on the supplied age. Returns TRUE
// if the marker should still be visible, FALSE if it has to be
// removed.
Marker.prototype.age = function(age) {
    if(age <= retention_time) {
        this.setMarkerOpacity(Marker.getOpacityScale(age));
        return true;
    } else {
        this.setMap();
        return false;
    }
};

// Remove visual marker element from its parent, if that element exists.
Marker.prototype.remove = function() {
    if (this.div) {
        this.div.parentNode.removeChild(this.div);
        this.div = null;
    }
};

//
// Feature Marker
//     Represents static map features, such as stations and receivers.
// Derived classes have to implement:
//     setMarkerOpacity()
//

function FeatureMarker() {}

FeatureMarker.prototype = new Marker();

FeatureMarker.prototype.update = function(update) {
    this.lastseen = update.lastseen;
    this.mode     = update.mode;
    this.url      = update.location.url;
    this.comment  = update.location.comment;
    // Receivers
    this.altitude = update.location.altitude;
    this.device   = update.location.device;
    this.antenna  = update.location.antenna;
    // EIBI
    this.schedule = update.location.schedule;
    // Repeaters
    this.freq     = update.location.freq;
    this.status   = update.location.status;
    this.updated  = update.location.updated;
    this.mmode    = update.location.mmode;
    // Generic vendor-specific details
    this.details  = update.location.details;

    // Implementation-dependent function call
    this.setMarkerPosition(update.callsign, update.location.lat, update.location.lon);

    // Age locator
    this.age(new Date().getTime() - update.lastseen);
};

FeatureMarker.prototype.draw = function() {
    var div = this.div;
    if (!div) return;

    div.style.color = this.color? this.color : '#000000';
    div.innerHTML   = this.symbol? this.symbol : '&#9679;';

    if (this.place) this.place();
};

FeatureMarker.prototype.create = function() {
    var div = this.div = document.createElement('div');

    // Marker size
    this.symWidth  = 16;
    this.symHeight = 16;

    div.style.position   = 'absolute';
    div.style.cursor     = 'pointer';
    div.style.width      = this.symWidth + 'px';
    div.style.height     = this.symHeight + 'px';
    div.style.textAlign  = 'center';
    div.style.fontSize   = this.symHeight + 'px';
    div.style.lineHeight = this.symHeight + 'px';

    return div;
};

FeatureMarker.prototype.getAnchorOffset = function() {
    return [0, -this.symHeight/2];
};

FeatureMarker.prototype.getInfoHTML = function(name, receiverMarker = null) {
    var nameString    = this.url? Marker.linkify(name, this.url) : name;
    var commentString = this.comment? '<div align="center">' + this.comment + '</div>' : '';
    var detailsString = '';
    var scheduleString = '';
    var distance = '';

    // If it is a repeater, its name is a callsign
    if(!this.url && this.freq) {
        nameString = Marker.linkify(name);
    }

    if (this.altitude) {
        detailsString += Marker.makeListItem('Altitude', this.altitude.toFixed(0) + ' m');
    }

    if (this.device) {
        detailsString += Marker.makeListItem('Device', this.device.manufacturer?
            this.device.device + ' by ' + this.device.manufacturer : this.device
        );
    }

    if (this.antenna) {
        detailsString += Marker.makeListItem('Antenna', Marker.truncate(this.antenna, 24));
    }

    if (this.freq) {
        detailsString += Marker.makeListItem('Frequency', Marker.linkifyFreq(
            this.freq, this.mmode? this.mmode:'fm'
        ));
    }

    if (this.mmode) {
        detailsString += Marker.makeListItem('Modulation', this.mmode.toUpperCase());
    }

    if (!this.comment && this.status && this.updated) {
        commentString = '<div align="center">' + this.status
            + ', last updated on ' + this.updated + '</div>';
    } else {
        if (this.status) {
            detailsString += Marker.makeListItem('Status', this.status);
        }
        if (this.updated) {
            detailsString += Marker.makeListItem('Updated', this.updated);
        }
    }

    var moreDetails = this.detailsData;
    if (typeof moreDetails === 'object') {
        Object.keys(moreDetails).sort().forEach(function (k, i) {
            detailsString += Marker.makeListItem(k.charAt(0).toUpperCase() + k.slice(1), moreDetails[k]);
        });
    }

    if (this.schedule) {
        for (var j=0 ; j<this.schedule.length ; ++j) {
            var freq = this.schedule[j].freq;
            var mode = this.schedule[j].mode;
            var tune = mode === 'cw'?      freq - 800
                     : mode === 'fax'?     freq - 1900
                     : mode === 'rtty450'? freq - 1000
                     : freq;

            var name = ('0000' + this.schedule[j].time1).slice(-4)
                + '&#8209;' + ('0000' + this.schedule[j].time2).slice(-4)
                + '&nbsp;&nbsp;' + this.schedule[j].name;

            scheduleString += Marker.makeListItem(name, Marker.linkifyFreq(
                this.schedule[j].freq, mode? mode : 'am'
            ));
        }
    }

    if (detailsString.length > 0) {
        detailsString = '<p>' + Marker.makeListTitle('Details') + detailsString + '</p>';
    }

    if (scheduleString.length > 0) {
        scheduleString = '<p>' + Marker.makeListTitle('Schedule') + scheduleString + '</p>';
    }

    if (receiverMarker) {
        distance = ' at ' + Marker.distanceKm(receiverMarker.position, this.position) + ' km';
    }

    return '<h3>' + nameString + distance + '</h3>'
        + commentString + detailsString + scheduleString;
};

//
// APRS Marker
//     Represents APRS transmitters, as well as AIS (vessels)
//     and HFDL (planes).
// Derived classes have to implement:
//     setMarkerOpacity()
//

function AprsMarker() {}

AprsMarker.prototype = new Marker();

AprsMarker.prototype.update = function(update) {
    this.lastseen = update.lastseen;
    this.mode     = update.mode;
    this.hops     = update.hops;
    this.band     = update.band;
    this.comment  = update.location.comment;
    this.weather  = update.location.weather;
    this.altitude = update.location.altitude;
    this.height   = update.location.height;
    this.power    = update.location.power;
    this.gain     = update.location.gain;
    this.device   = update.location.device;
    this.directivity = update.location.directivity;
    this.aircraft = update.location.aircraft;
    this.destination = update.location.destination;
    this.origin   = update.location.origin;
    this.flight   = update.location.flight;
    this.icao     = update.location.icao;
    this.vspeed   = update.location.vspeed;

    // Implementation-dependent function call
    this.setMarkerPosition(update.callsign, update.location.lat, update.location.lon);

    // Age locator
    this.age(new Date().getTime() - update.lastseen);
};

AprsMarker.prototype.isFacingEast = function(symbol) {
    var eastward = symbol.table === '/' ?
        '(*<=>CFPUXYZabefgjkpsuv[' : '(T`efhjktuvw';
    return eastward.includes(symbol.symbol);
};

AprsMarker.prototype.draw = function() {
    var div = this.div;
    var overlay = this.overlay;
    if (!div || !overlay) return;

    if (this.symbol) {
        var tableId = this.symbol.table === '/' ? 0 : 1;
        div.style.background = 'url(aprs-symbols/aprs-symbols-24-' + tableId + '@2x.png)';
        div.style['background-size'] = '384px 144px';
        div.style['background-position-x'] = -(this.symbol.index % 16) * 24 + 'px';
        div.style['background-position-y'] = -Math.floor(this.symbol.index / 16) * 24 + 'px';
    }

    // If entity is flying at a significant altitude...
    if (this.altitude >= 500) {
        // r = elevation, a = rotation, <x,y> = shadow offset
        var r = Math.round(this.altitude / 1000);
        var a = - Math.PI * (this.course? this.course - 45 : -45) / 180;
        var x = r * Math.cos(a);
        var y = r * Math.sin(a);
        div.style.filter = 'drop-shadow(' + x + 'px ' + y + 'px 0.5px rgba(0,0,0,0.5))';
    } else {
        div.style.filter = 'none';
    }

    if (!this.course) {
        div.style.transform = null;
    } else if (this.symbol && !this.isFacingEast(this.symbol)) {
        // Airplanes and other symbols point up (to the north)
        div.style.transform = 'rotate(' + this.course + 'deg)';
    } else if (this.course > 180) {
        // Vehicles and vessels point right (to the east)
        div.style.transform = 'scalex(-1) rotate(' + (270 - this.course) + 'deg)'
    } else {
        // Vehicles and vessels point right (to the east)
        div.style.transform = 'rotate(' + (this.course - 90) + 'deg)';
    }

    if (this.symbol && this.symbol.table !== '/' && this.symbol.table !== '\\') {
        overlay.style.display = 'block';
        overlay.style['background-position-x'] = -(this.symbol.tableindex % 16) * 24 + 'px';
        overlay.style['background-position-y'] = -Math.floor(this.symbol.tableindex / 16) * 24 + 'px';
    } else {
        overlay.style.display = 'none';
    }

    if (this.opacity) {
        div.style.opacity = this.opacity;
    } else {
        div.style.opacity = null;
    }

    if (this.place) this.place();
};

AprsMarker.prototype.create = function() {
    var div = this.div = document.createElement('div');

    div.style.position = 'absolute';
    div.style.cursor = 'pointer';
    div.style.width = '24px';
    div.style.height = '24px';

    var overlay = this.overlay = document.createElement('div');
    overlay.style.width = '24px';
    overlay.style.height = '24px';
    overlay.style.background = 'url(aprs-symbols/aprs-symbols-24-2@2x.png)';
    overlay.style['background-size'] = '384px 144px';
    overlay.style.display = 'none';

    div.appendChild(overlay);

    return div;
};

AprsMarker.prototype.getAnchorOffset = function() {
    return [0, -12];
};

AprsMarker.prototype.getInfoHTML = function(name, receiverMarker = null) {
    var timeString = moment(this.lastseen).fromNow();
    var commentString = '';
    var weatherString = '';
    var detailsString = '';
    var hopsString = '';
    var distance = '';

    if (this.comment) {
        commentString += '<p>' + Marker.makeListTitle('Comment') + '<div>' +
            this.comment + '</div></p>';
    }

    if (this.weather) {
        weatherString += '<p>' + Marker.makeListTitle('Weather');

        if (this.weather.temperature) {
            weatherString += Marker.makeListItem('Temperature', this.weather.temperature.toFixed(1) + ' oC');
        }

        if (this.weather.humidity) {
            weatherString += Marker.makeListItem('Humidity', this.weather.humidity + '%');
        }

        if (this.weather.barometricpressure) {
            weatherString += Marker.makeListItem('Pressure', this.weather.barometricpressure.toFixed(1) + ' mbar');
        }

        if (this.weather.wind) {
            if (this.weather.wind.speed && (this.weather.wind.speed>0)) {
                weatherString += Marker.makeListItem('Wind',
                    Marker.degToCompass(this.weather.wind.direction) + ' ' +
                    this.weather.wind.speed.toFixed(1) + ' km/h '
                );
            }

            if (this.weather.wind.gust && (this.weather.wind.gust>0)) {
                weatherString += Marker.makeListItem('Gusts', this.weather.wind.gust.toFixed(1) + ' km/h');
            }
        }

        if (this.weather.rain && (this.weather.rain.day>0)) {
            weatherString += Marker.makeListItem('Rain',
                this.weather.rain.hour.toFixed(0) + ' mm/h, ' +
                this.weather.rain.day.toFixed(0) + ' mm/day'
//                    this.weather.rain.sincemidnight + ' mm since midnight'
            );
        }

        if (this.weather.snowfall) {
            weatherString += Marker.makeListItem('Snow', this.weather.snowfall.toFixed(1) + ' cm');
        }

        weatherString += '</p>';
    }

    if (this.device) {
        detailsString += Marker.makeListItem('Device', this.device.manufacturer?
          this.device.device + ' by ' + this.device.manufacturer : this.device
        );
    }

    if (this.height) {
        detailsString += Marker.makeListItem('Height', this.height.toFixed(0) + ' m');
    }

    if (this.power) {
        detailsString += Marker.makeListItem('Power', this.power + ' W');
    }

    if (this.gain) {
        detailsString += Marker.makeListItem('Gain', this.gain + ' dB');
    }

    if (this.directivity) {
        detailsString += Marker.makeListItem('Direction', this.directivity);
    }

    if (this.icao) {
        detailsString += Marker.makeListItem('ICAO', Marker.linkify(this.icao, modes_url));
    }

    if (this.aircraft) {
        detailsString += Marker.makeListItem('Aircraft', Marker.linkify(this.aircraft, flight_url));
    }

    if (this.origin) {
        detailsString += Marker.makeListItem('Origin', this.origin);
    }

    if (this.destination) {
        detailsString += Marker.makeListItem('Destination', this.destination);
    }

    // Combine course and speed if both present
    if (this.course && this.speed) {
        detailsString += Marker.makeListItem('Course',
            Marker.degToCompass(this.course) + ' ' +
            this.speed.toFixed(1) + ' km/h'
        );
    } else {
        if (this.course) {
            detailsString += Marker.makeListItem('Course', Marker.degToCompass(this.course));
        }
        if (this.speed) {
            detailsString += Marker.makeListItem('Speed', this.speed.toFixed(1) + ' km/h');
        }
    }

    // Combine altitude and vertical speed
    if (this.altitude) {
        var alt = this.altitude.toFixed(0) + ' m';
        if (this.vspeed > 0) alt += ' &UpperRightArrow;' + this.vspeed + ' m/m';
        else if (this.vspeed < 0) alt += ' &LowerRightArrow;' + (-this.vspeed) + ' m/m';
        detailsString += Marker.makeListItem('Altitude', alt);
    }

    if (detailsString.length > 0) {
        detailsString = '<p>' + Marker.makeListTitle('Details') + detailsString + '</p>';
    }

    if (receiverMarker) {
        distance = ' at ' + Marker.distanceKm(receiverMarker.position, this.position) + ' km';
    }

    if (this.hops && this.hops.length > 0) {
        var hops = this.hops.toString().split(',');
        hops.forEach(function(part, index, hops) {
            hops[index] = Marker.linkify(part);
        });

        hopsString = '<p align="right"><i>via ' + hops.join(', ') + '&nbsp;</i></p>';
    }

    // Linkify title based on what it is (vessel, flight, mode-S code, or else)
    var linkEntity = null;
    var url = null;
    switch (this.mode) {
        case 'HFDL':
        case 'VDL2':
        case 'ADSB':
        case 'ACARS':
            if (this.flight) {
                name = this.flight;
                url  = flight_url;
            } else if (this.aircraft) {
                name = this.aircraft;
                url  = flight_url;
            } else {
                url = modes_url;
            }
            break;
        case 'AIS':
            url = vessel_url;
            break;
        default:
            linkEntity = name.replace(new RegExp('-.*$'), '');
            url = callsign_url;
            break;
    }

    return '<h3>' + Marker.linkify(name, url, linkEntity) + distance + '</h3>'
        + '<div align="center">' + timeString + ' using ' + this.mode
        + ( this.band ? ' on ' + this.band : '' ) + '</div>'
        + commentString + weatherString + detailsString + hopsString;
};