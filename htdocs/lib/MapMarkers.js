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
        'ACARS'     : '#800000',
        'HFDL'      : '#004000',
        'VDL2'      : '#000080',
        'ADSB'      : '#000000'
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

    // Load saved shown/hidden status, by type
    for (type in this.symbols) {
        if (LS.has('marker-' + type)) {
            this.enabled[type] = LS.loadBool('marker-' + type);
        }
    }
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
    // If state not supplied, toggle existing state
    if (typeof(onoff) === 'undefined') onoff = !this.isEnabled(type);

    // Keep track of each feature table being show or hidden
    LS.save('marker-' + type, onoff);
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

MarkerManager.prototype.remove = function(id) {
    if (id in this.markers) {
        this.markers[id].setMap();
        delete this.markers[id];
    }
};

MarkerManager.prototype.ageAll = function() {
    var now = new Date().getTime();
    var data = this.markers;
    $.each(data, function(id, x) {
        if (x.ttl && now >= x.ttl)
            this.remove(id);
        else if (x.lastseen && !x.age(now - x.lastseen))
            this.remove(id);
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

// Set marker's opacity based on the supplied age. Returns TRUE
// if the marker should still be visible, FALSE if it has to be
// removed.
Marker.prototype.age = function(age) {
    if(age <= retention_time) {
        this.setMarkerOpacity(Utils.getOpacityScale(age));
        return true;
    } else {
        this.setMap();
        return false;
    }
};

// Remove visual marker element from its parent, if that element exists.
Marker.prototype.remove = function() {
    if (this.div) {
        if (this.div.parentNode && this.div.parentNode.removeChild)
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
    this.ttl      = update.location.ttl;
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

FeatureMarker.prototype.getSize = function() {
    return [this.symWidth, this.symHeight];
};

FeatureMarker.prototype.getInfoHTML = function(name, receiverMarker = null) {
    var nameString    = this.url? Utils.linkify(name, this.url) : name;
    var commentString = this.comment? '<div align="center">' + Utils.htmlEscape(this.comment) + '</div>' : '';
    var detailsString = '';
    var scheduleString = '';
    var distance = '';

    // If it is a repeater, its name is a callsign
    if(!this.url && this.freq) {
        nameString = Utils.linkifyCallsign(name);
    }

    if (this.altitude) {
        detailsString += Utils.makeListItem('Altitude', this.altitude.toFixed(0) + ' m');
    }

    if (this.device) {
        detailsString += Utils.makeListItem('Device', this.device.manufacturer?
            this.device.device + ' by ' + this.device.manufacturer : this.device
        );
    }

    if (this.antenna) {
        detailsString += Utils.makeListItem('Antenna', Utils.truncate(this.antenna, 24));
    }

    if (this.freq) {
        detailsString += Utils.makeListItem('Frequency', Utils.linkifyFreq(
            this.freq, this.mmode? this.mmode:'fm'
        ));
    }

    if (this.mmode) {
        detailsString += Utils.makeListItem('Modulation', this.mmode.toUpperCase());
    }

    if (!this.comment && this.status && this.updated) {
        commentString = '<div align="center">' + this.status
            + ', last updated on ' + this.updated + '</div>';
    } else {
        if (this.status) {
            detailsString += Utils.makeListItem('Status', this.status);
        }
        if (this.updated) {
            detailsString += Utils.makeListItem('Updated', this.updated);
        }
    }

    var moreDetails = this.detailsData;
    if (typeof moreDetails === 'object') {
        Object.keys(moreDetails).sort().forEach(function (k, i) {
            detailsString += Utils.makeListItem(k.charAt(0).toUpperCase() + k.slice(1), moreDetails[k]);
        });
    }

    if (this.schedule) {
        for (var j=0 ; j<this.schedule.length ; ++j) {
            var freq = this.schedule[j].freq;
            var mode = this.schedule[j].mode;
            var tune = Utils.offsetFreq(freq, mode);

            var name = ('0000' + this.schedule[j].time1).slice(-4)
                + '&#8209;' + ('0000' + this.schedule[j].time2).slice(-4)
                + '&nbsp;&nbsp;' + this.schedule[j].name;

            scheduleString += Utils.makeListItem(name, Utils.linkifyFreq(
                this.schedule[j].freq, mode? mode : 'am'
            ));
        }
    }

    if (detailsString.length > 0) {
        detailsString = '<div>' + Utils.makeListTitle('Details') + detailsString + '</div>';
    }

    if (scheduleString.length > 0) {
        scheduleString = '<div>' + Utils.makeListTitle('Schedule') + scheduleString + '</div>';
    }

    if (receiverMarker) {
        distance = ' at ' + Utils.distanceKm(receiverMarker.position, this.position) + ' km';
    }

    return '<h3>' + nameString + distance + '</h3>'
        + commentString + detailsString + scheduleString;
};

//
// APRS Marker
//     Represents APRS transmitters, as well as AIS (vessels).
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
    // APRS, AIS
    this.weather  = update.location.weather;
    this.altitude = update.location.altitude;
    this.height   = update.location.height;
    this.power    = update.location.power;
    this.gain     = update.location.gain;
    this.device   = update.location.device;
    this.directivity = update.location.directivity;

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

AprsMarker.prototype.getSize = function() {
    return [24, 24];
};

AprsMarker.prototype.getInfoHTML = function(name, receiverMarker = null) {
    var timeString = moment(this.lastseen).fromNow();
    var commentString = '';
    var weatherString = '';
    var detailsString = '';
    var messageString = '';
    var hopsString = '';
    var distance = '';

    if (this.comment) {
        commentString += '<div>' + Utils.makeListTitle('Comment') + '<div>'
            + Utils.htmlEscape(this.comment) + '</div></div>';
    }

    if (this.weather) {
        weatherString += '<div>' + Utils.makeListTitle('Weather');

        if (this.weather.temperature) {
            weatherString += Utils.makeListItem('Temperature', this.weather.temperature.toFixed(1) + ' oC');
        }

        if (this.weather.humidity) {
            weatherString += Utils.makeListItem('Humidity', this.weather.humidity + '%');
        }

        if (this.weather.barometricpressure) {
            weatherString += Utils.makeListItem('Pressure', this.weather.barometricpressure.toFixed(1) + ' mbar');
        }

        if (this.weather.wind) {
            if (this.weather.wind.speed && (this.weather.wind.speed>0)) {
                weatherString += Utils.makeListItem('Wind',
                    Utils.degToCompass(this.weather.wind.direction) + ' ' +
                    this.weather.wind.speed.toFixed(1) + ' km/h '
                );
            }

            if (this.weather.wind.gust && (this.weather.wind.gust>0)) {
                weatherString += Utils.makeListItem('Gusts', this.weather.wind.gust.toFixed(1) + ' km/h');
            }
        }

        if (this.weather.rain && (this.weather.rain.day>0)) {
            weatherString += Utils.makeListItem('Rain',
                this.weather.rain.hour.toFixed(0) + ' mm/h, ' +
                this.weather.rain.day.toFixed(0) + ' mm/day'
//                    this.weather.rain.sincemidnight + ' mm since midnight'
            );
        }

        if (this.weather.snowfall) {
            weatherString += Utils.makeListItem('Snow', this.weather.snowfall.toFixed(1) + ' cm');
        }

        weatherString += '</div>';
    }

    if (this.device) {
        detailsString += Utils.makeListItem('Device', this.device.manufacturer?
          this.device.device + ' by ' + this.device.manufacturer : this.device
        );
    }

    if (this.height) {
        detailsString += Utils.makeListItem('Height', this.height.toFixed(0) + ' m');
    }

    if (this.power) {
        detailsString += Utils.makeListItem('Power', this.power + ' W');
    }

    if (this.gain) {
        detailsString += Utils.makeListItem('Gain', this.gain + ' dB');
    }

    if (this.directivity) {
        detailsString += Utils.makeListItem('Direction', this.directivity);
    }

    // Combine course and speed if both present
    if (this.course && this.speed) {
        detailsString += Utils.makeListItem('Course',
            Utils.degToCompass(this.course) + ' ' +
            this.speed.toFixed(1) + ' km/h'
        );
    } else {
        if (this.course) {
            detailsString += Utils.makeListItem('Course', Utils.degToCompass(this.course));
        }
        if (this.speed) {
            detailsString += Utils.makeListItem('Speed', this.speed.toFixed(1) + ' km/h');
        }
    }

    if (this.altitude) {
        detailsString += Utils.makeListItem('Altitude', this.altitude.toFixed(0) + ' m');
    }

    if (this.mode === 'AIS') {
        var country = Utils.mmsi2country(name);
        if (country) {
            detailsString += Utils.makeListItem('Country', Utils.truncate(country, 24));
        }
    }

    // Linkify title based on what it is (vessel or HAM callsign)
    var title = this.mode === 'AIS'?
      Utils.linkifyVessel(name) : Utils.linkifyCallsign(name);

    if (detailsString.length > 0) {
        detailsString = '<div>' + Utils.makeListTitle('Details') + detailsString + '</div>';
    }

    if (receiverMarker) {
        distance = ' at ' + Utils.distanceKm(receiverMarker.position, this.position) + ' km';
    }

    if (this.hops && this.hops.length > 0) {
        var hops = this.hops.toString().split(',');
        hops.forEach(function(part, index, hops) {
            hops[index] = Utils.linkifyCallsign(part);
        });

        hopsString = '<div style="text-align:right;padding-top:1em;"><i>via '
            + hops.join(', ') + '&nbsp;</i></div>';
    }

    // Linkify title based on what it is (vessel or HAM callsign)
    var title = this.mode === 'AIS'?
      Utils.linkifyVessel(name) : Utils.linkifyCallsign(name);

    // Combine everything into info box contents
    return '<h3>' + title + distance + '</h3>'
        + '<div align="center">' + timeString + ' using '
        + this.mode + ( this.band ? ' on ' + this.band : '' ) + '</div>'
        + commentString + weatherString + detailsString
        + messageString + hopsString;
};

//
// Aircraft Marker
//     Represents aircraft reported by various aeronautic services,
//     such as HFDL, ACARS, VDL2, and ADSB.
// Derived classes have to implement:
//     setMarkerOpacity()
//

function AircraftMarker() {
    this.scale = 0.5;
}

AircraftMarker.prototype = new Marker();

AircraftMarker.prototype.update = function(update) {
    this.lastseen = update.lastseen;
    this.mode     = update.mode;
    this.comment  = update.location.comment;
    this.ttl      = update.location.ttl;
    // HFDL, ACARS, VDL2, ADSB
    this.altitude = update.location.altitude;
    this.aircraft = update.location.aircraft;
    this.destination = update.location.destination;
    this.origin   = update.location.origin;
    this.flight   = update.location.flight;
    this.icao     = update.location.icao;
    this.vspeed   = update.location.vspeed;
    this.squawk   = update.location.squawk;
    this.rssi     = update.location.rssi;
    this.msglog   = update.location.msglog;

    // Implementation-dependent function call
    this.setMarkerPosition(update.callsign, update.location.lat, update.location.lon);

    // Age locator
    this.age(new Date().getTime() - update.lastseen);
};

AircraftMarker.prototype.draw = function() {
    var div = this.div;
    var overlay = this.overlay;
    if (!div || !overlay) return;

    if (this.symbol) {
        div.style.background = 'url(static/gfx/adsb-72.png)';
        div.style['background-size'] = '576px 792px';
        div.style['background-position-x'] = -this.symbol.x * 72 + 'px';
        div.style['background-position-y'] = -this.symbol.y * 72 + 'px';
    }

    // If aircraft is flying at a significant altitude...
    if (this.altitude > 1000) {
        // r = elevation, a = rotation, <x,y> = shadow offset
        var r = Math.round(this.altitude / 2000);
        var a = - Math.PI * (this.course? this.course - 45 : -45) / 180;
        var x = r * Math.cos(a);
        var y = r * Math.sin(a);
        div.style.filter = 'drop-shadow(' + x + 'px ' + y + 'px 0.5px rgba(0,0,0,0.5))';
    } else {
        div.style.filter = 'none';
    }

    div.style.transform = 'scale(' + this.scale + ')';

    if (this.course) {
        div.style.transform += ' rotate(' + this.course + 'deg)';
    }

    if (this.symbol && this.symbol.table !== '/' && this.symbol.table !== '\\') {
        overlay.style.display = 'block';
        overlay.style['background-position-x'] = -this.symbol.x * 72 + 'px';
        overlay.style['background-position-y'] = -this.symbol.y * 72 + 'px';
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

AircraftMarker.prototype.create = function() {
    var div = this.div = document.createElement('div');

    div.style.position = 'absolute';
    div.style.cursor = 'pointer';
    div.style.width = '72px';
    div.style.height = '72px';

    var overlay = this.overlay = document.createElement('div');
    overlay.style.width = '72px';
    overlay.style.height = '72px';
    overlay.style.background = 'url(static/gfx/adsb-72.png)';
    overlay.style['background-size'] = '576px 792px';
    overlay.style.display = 'none';

    div.appendChild(overlay);

    return div;
};

AircraftMarker.prototype.getAnchorOffset = function() {
    return [0, -36 * this.scale];
};

AircraftMarker.prototype.getSize = function() {
    return [72, 72];
};

AircraftMarker.prototype.getInfoHTML = function(name, receiverMarker = null) {
    var timeString = moment(this.lastseen).fromNow();
    var commentString = '';
    var detailsString = '';
    var messageString = '';
    var distance = '';

    if (this.comment) {
        commentString += '<div>' + Utils.makeListTitle('Comment') + '<div>'
            + Utils.htmlEscape(this.comment) + '</div></div>';
    }

    if (this.msglog) {
        var msglog = $.map(this.msglog, function(x, _) {
            return Utils.htmlEscape(x);
        });
        messageString += '<div>' + Utils.makeListTitle('Messages')
            + '<pre class="openwebrx-map-console">' + msglog.join('\n<hr>')
            + '</pre></div>';
    }

    if (this.icao) {
        detailsString += Utils.makeListItem('ICAO', Utils.linkify(this.icao, modes_url));
    }

    if (this.aircraft) {
        detailsString += Utils.makeListItem('Aircraft', Utils.linkify(this.aircraft, flight_url));
    }

    if (this.squawk) {
        detailsString += Utils.makeListItem('Squawk', this.squawk);
    }

    if (this.origin) {
        detailsString += Utils.makeListItem('Origin', this.origin);
    }

    if (this.destination) {
        detailsString += Utils.makeListItem('Destination', this.destination);
    }

    // Combine course and speed if both present
    if (this.course && this.speed) {
        detailsString += Utils.makeListItem('Course',
            Utils.degToCompass(this.course) + ' ' +
            this.speed.toFixed(1) + ' kt'
        );
    } else {
        if (this.course) {
            detailsString += Utils.makeListItem('Course', Utils.degToCompass(this.course));
        }
        if (this.speed) {
            detailsString += Utils.makeListItem('Speed', this.speed.toFixed(1) + ' kt');
        }
    }

    // Combine altitude and vertical speed
    if (this.altitude) {
        var alt = this.altitude.toFixed(0) + ' ft';
        if (this.vspeed > 0) alt += ' &UpperRightArrow;' + this.vspeed + ' ft/m';
        else if (this.vspeed < 0) alt += ' &LowerRightArrow;' + (-this.vspeed) + ' ft/m';
        detailsString += Utils.makeListItem('Altitude', alt);
    }

    if (this.rssi) {
        detailsString += Utils.makeListItem('RSSI', this.rssi + ' dB');
    }

    if (detailsString.length > 0) {
        detailsString = '<div>' + Utils.makeListTitle('Details') + detailsString + '</div>';
    }

    if (receiverMarker) {
        distance = ' at ' + Utils.distanceKm(receiverMarker.position, this.position) + ' km';
    }

    // Linkify title based on what it is (flight, aircraft, ICAO code)
    var text = this.flight? this.flight : this.aircraft? this.aircraft : name;
    var url  = null;
    if (this.flight && this.flight.match(/^[A-Z]{3}[0-9]+[A-Z]*$/)) {
        name = this.flight;
        url  = flight_url;
    } else if(this.aircraft) {
        name = this.aircraft;
        url  = flight_url;
    } else if(name.match(/^[0-9A-F]{6}$/)) {
        url  = modes_url;
    }

    return '<h3>' + Utils.linkify(name, url, text) + distance + '</h3>'
        + '<div align="center">' + timeString + ' using ' + this.mode + '</div>'
        + commentString + detailsString + messageString;
};
