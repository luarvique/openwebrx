//
// Utility functions
//

function Utils() {}

Utils.fm_url = 'https://www.google.com/search?q={}+FM';
Utils.callsign_url = null;
Utils.sonde_url = null;
Utils.vessel_url = null;
Utils.flight_url = null;
Utils.icao_url = null;
Utils.receiver_pos = null;

// Set receiver position
Utils.setReceiverPos = function(pos) {
    if (pos.lat && pos.lon) this.receiver_pos = pos;
};

// Get receiver position
Utils.getReceiverPos = function() {
    return this.receiver_pos;
};

// Set URL for linkifying callsigns
Utils.setCallsignUrl = function(url) {
    this.callsign_url = url;
};

// Set URL for linkifying radiosonde IDs
Utils.setSondeUrl = function(url) {
    this.sonde_url = url;
};

// Set URL for linkifying AIS vessel IDs
Utils.setVesselUrl = function(url) {
    this.vessel_url = url;
};

// Set URL for linkifying flight and aircraft IDs
Utils.setFlightUrl = function(url) {
    this.flight_url = url;
};

// Set URL for linkifying ICAO aircraft IDs
Utils.setIcaoUrl = function(url) {
    this.icao_url = url;
};

// Escape HTML code
Utils.htmlEscape = function(input) {
    return $('<div/>').text(input).html();
};

// Print frequency (in Hz) in a nice way
Utils.printFreq = function(freq) {
    if (isNaN(parseInt(freq))) {
        return freq;
    } else if (freq >= 30000000) {
        return '' + (freq / 1000000.0) + 'MHz';
    } else if (freq >= 10000) {
        return '' + (freq / 1000.0) + 'kHz';
    } else {
        return '' + freq + 'Hz';
    }
}

// Change frequency as required by given modulation
Utils.offsetFreq = function(freq, mod) {
    switch(mod) {
        case 'cw':
            return freq - UI.getCwOffset();
        case 'fax':
            return freq - 1900;
        case 'cwdecoder':
        case 'rtty450':
        case 'rtty170':
        case 'rtty85':
        case 'bpsk31':
        case 'bpsk63':
        case 'sitorb':
        case 'navtex':
        case 'dsc':
            return freq - 1000;
    }

    return freq;
}

// Wrap given callsign or other ID into a clickable link.
Utils.linkify = function(id, url = null, content = null, tip = null) {
    // If no specific content, use the ID itself
    if (content == null) content = id;

    // Compose tooltip
    var tipText = tip? ' title="' + tip + '"'  : '';

    // Must have valid ID and lookup URL
    if ((id == '') || (url == null) || (url == '')) {
        return tipText? '<div' + tipText + '>' + content + '</div>'  : content;
    } else {
        return '<a target="callsign_info"' + tipText + ' href="' +
            url.replaceAll('{}', id) + '">' + content + '</a>';
    }
};

// Linkify name by mode
Utils.linkifyByMode = function(mode, name) {
    switch (mode) {
        case 'SONDE': return this.linkifySonde(name);
        case 'AIS':   return this.linkifyVessel(name);
        case 'HDR':   return this.linkifyFM(name);
    }

    // Default is HAM callsign
    return this.linkifyCallsign(name);
};

// Create link to an FM station
Utils.linkifyFM = function(name) {
    return this.linkify(name, this.fm_url);
};

// Create link to a callsign, with country tooltip, etc.
Utils.linkifyCallsign = function(callsign) {
    // Strip callsign of modifiers
    var id = callsign.replace(/[-/].*$/, '');
    // Add country name as a tooltip
    return this.linkify(id, this.callsign_url, callsign, Lookup.call2cname(id));
};

// Create link to a radiosonde
Utils.linkifySonde = function(id) {
    return this.linkify(id, this.sonde_url, id);
};

// Create link to a maritime vessel, with country tooltip, etc.
Utils.linkifyVessel = function(mmsi) {
    // Add country name as a tooltip
    return this.linkify(mmsi, this.vessel_url, mmsi, Lookup.mmsi2cname(mmsi));
};

// Create link to a flight or an aircraft
Utils.linkifyFlight = function(flight, content = null) {
    return this.linkify(flight, this.flight_url, content);
};

// Create link to a MODE-S ICAO ID
Utils.linkifyIcao = function(icao, content = null) {
    return this.linkify(icao, this.icao_url, content);
};

// Create link to tune OWRX to the given frequency and modulation.
Utils.linkifyFreq = function(freq, mod) {
    return '<a target="openwebrx-rx" href="/#freq='
        + freq + ',mod=' + mod + '">' + Utils.printFreq(freq) + '</a>';
};

// Create link to a map locator
Utils.linkifyLocator = function(locator) {
    return '<a target="openwebrx-map" href="map?locator='
        + encodeURIComponent(locator) + '">' + locator + '</a>';
}

// Linkify given content so that clicking them opens the map with
// the info bubble.
Utils.linkToMap = function(id, content = null, attrs = "") {
    if (id) {
        return '<a ' + attrs + ' href="map?callsign='
            + encodeURIComponent(id) + '" target="openwebrx-map">'
            + (content != null? content  : id) + '</a>';
    } else if (content != null) {
        return '<div ' + attrs + '>' + content + '</div>';
    } else {
        return '';
    }
};

// Print time in hours, minutes, and seconds.
Utils.HHMMSS = function(t) {
    var pad = function (i) { return ('' + i).padStart(2, "0") };

    // Convert timestamps into dates
    if (!(t instanceof Date)) t = new Date(t);

    return pad(t.getUTCHours()) + ':' + pad(t.getUTCMinutes()) + ':' + pad(t.getUTCSeconds());
};

// Snap given frequency to the nearest step.
Utils.snapFrequency = function(freq, step) {
    if (step <= 0) {
        return Math.round(freq);
    } else if (step == 8330) {
        return this.snapAirbandFrequency(freq);
    } else {
        return Math.round(freq / step) * step;
    }
};

// Snap given frequency to the nearest airband frequency,
// with respect to the uneven 8.33kHz step.
Utils.snapAirbandFrequency = function(freq) {
    freq = Math.round(freq);

    var base = Math.floor(freq / 25000.0) * 25000;
    var rem  = freq - base;

    rem = rem < 4165?  0
        : rem < 12500? 8330
        : rem < 20835? 16670
        : 25000;

    return base + rem;
};

// Compute distance, in kilometers, between two latlons. Use receiver
// location if the second latlon is not provided.
Utils.distanceKm = function(p1, p2) {
    // Use receiver location if second latlon not given
    if (p2 == null) p2 = this.receiver_pos;
    // Convert from map objects to latlons
    if ("lng" in p1) p1 = { lat : p1.lat(), lon : p1.lng() };
    if ("lng" in p2) p2 = { lat : p2.lat(), lon : p2.lng() };
    // Earth radius in km
    var R = 6371.0;
    // Convert degrees to radians
    var rlat1 = p1.lat * (Math.PI/180);
    var rlat2 = p2.lat * (Math.PI/180);
    // Compute difference in radians
    var difflat = rlat2 - rlat1;
    var difflon = (p2.lon - p1.lon) * (Math.PI/180);
    // Compute distance
    d = 2 * R * Math.asin(Math.sqrt(
        Math.sin(difflat/2) * Math.sin(difflat/2) +
        Math.cos(rlat1) * Math.cos(rlat2) * Math.sin(difflon/2) * Math.sin(difflon/2)
    ));
    return Math.round(d);
};

// Truncate string to a given number of characters, adding "..." to the end.
Utils.truncate = function(str, count) {
    return str.length > count? str.slice(0, count) + '&mldr;'  : str;
};

// Convert degrees to compass direction.
Utils.degToCompass = function(deg) {
    dir = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
    return dir[Math.floor((deg/22.5) + 0.5) % 16];
};

// Convert Maidenhead locator ID to lat/lon pair.
Utils.loc2latlng = function(id) {
    return [
        (id.charCodeAt(1) - 65 - 9) * 10 + Number(id[3]) + 0.5,
        (id.charCodeAt(0) - 65 - 9) * 20 + Number(id[2]) * 2 + 1.0
    ];
};

// Convert given name to an information section title.
Utils.makeListTitle = function(name) {
    return '<div style="border-bottom:2px solid;padding-top:1em;"><b>' + name + '</b></div>';
};

// Convert given name/value to an information section item.
Utils.makeListItem = function(name, value) {
    return '<div style="display:flex;justify-content:space-between;border-bottom:1px dotted;white-space:nowrap;">'
        + '<span>' + name + '&nbsp;&nbsp;&nbsp;&nbsp;</span>'
        + '<span>' + value + '</span>'
        + '</div>';
};

// Get opacity value in the 0..1 range based on the given age.
Utils.getOpacityScale = function(age) {
    var scale = 1;
    if (age >= retention_time / 2) {
        scale = (retention_time - age) / (retention_time / 2);
    }
    return Math.max(0, Math.min(1, scale));
};

// Save given canvas into a PNG file.
Utils.saveCanvas = function(canvas) {
    // Get canvas by its ID
    var c = document.getElementById(canvas);
    if (c == null) return;

    // Convert canvas to a data blob
    c.toBlob(function(blob) {
        // Create and click a link to the canvas data URL
        var a = document.createElement('a');
        a.href = window.URL.createObjectURL(blob);
        a.style = 'display: none';
        a.download = canvas + ".png";
        document.body.appendChild(a);
        a.click();

        // Get rid of the canvas data URL
        setTimeout(function() {
            document.body.removeChild(a);
            window.URL.revokeObjectURL(a.href);
        }, 0);
    }, 'image/png');
};

//
// Local Storage Access
//

function LS() {}

// Return true of setting exist in storage.
LS.has = function(key) {
    return localStorage && (localStorage.getItem(key)!=null);
};

// Remove item from local storage.
LS.delete = function(key) {
    if (localStorage) localStorage.removeItem(key);
};

// Save named UI setting to local storage.
LS.save = function(key, value) {
    if (localStorage) localStorage.setItem(key, value);
};

// Load named UI setting from local storage.
LS.loadStr = function(key) {
    return localStorage? localStorage.getItem(key) : null;
};

LS.loadInt = function(key) {
    var x = localStorage? localStorage.getItem(key) : null;
    return x!=null? parseInt(x) : 0;
}

LS.loadBool = function(key) {
    var x = localStorage? localStorage.getItem(key) : null;
    return x==='true';
}
