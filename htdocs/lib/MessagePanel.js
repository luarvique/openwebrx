function MessagePanel(el) {
    this.el = el;
    this.render();
    this.initClearButton();
}

MessagePanel.prototype.supportsMessage = function(message) {
    return false;
};

MessagePanel.prototype.render = function() {
};

MessagePanel.prototype.pushMessage = function(message) {
};

// Automatic clearing is not enabled by default.
// Call this method from the constructor to enable.
MessagePanel.prototype.initClearTimer = function() {
    var me = this;
    if (me.removalInterval) clearInterval(me.removalInterval);
    me.removalInterval = setInterval(function () {
        me.clearMessages(250);
    }, 15000);
};

// Clear all currently shown messages.
MessagePanel.prototype.clearMessages = function(toRemain) {
    var $elements = $(this.el).find('tbody tr');
    // limit to 1000 entries in the list since browsers get laggy at some point
    var toRemove = $elements.length - toRemain;
    if (toRemove <= 0) return;
    $elements.slice(0, toRemove).remove();
};

// Add CLEAR button to the message list.
MessagePanel.prototype.initClearButton = function() {
    var me = this;
    me.clearButton = $(
        '<div class="openwebrx-button">Clear</div>'
    );
    me.clearButton.css({
        position: 'absolute',
        top: '10px',
        right: '10px'
    });
    me.clearButton.on('click', function() {
        me.clearMessages(0);
    });
    $(me.el).append(me.clearButton);
};

// Scroll to the bottom of the message list.
MessagePanel.prototype.scrollToBottom = function() {
    var $t = $(this.el).find('tbody');
    $t.scrollTop($t[0].scrollHeight);
};

function WsjtMessagePanel(el) {
    MessagePanel.call(this, el);
    this.initClearTimer();
    this.qsoModes = ['FT8', 'JT65', 'JT9', 'FT4', 'FST4', 'Q65', 'MSK144'];
    this.beaconModes = ['WSPR', 'FST4W'];
    this.modes = [].concat(this.qsoModes, this.beaconModes);
}

WsjtMessagePanel.prototype = Object.create(MessagePanel.prototype);

WsjtMessagePanel.prototype.supportsMessage = function(message) {
    return this.modes.indexOf(message['mode']) >= 0;
};

WsjtMessagePanel.prototype.render = function() {
    $(this.el).append($(
        '<table>' +
            '<thead><tr>' +
                '<th class="time">UTC</th>' +
                '<th class="decimal">dB</th>' +
                '<th class="decimal">DT</th>' +
                '<th class="decimal freq">Freq</th>' +
                '<th class="message">Message</th>' +
            '</tr></thead>' +
            '<tbody></tbody>' +
        '</table>'
    ));
};

WsjtMessagePanel.prototype.pushMessage = function(msg) {
    var $b = $(this.el).find('tbody');
    var linkedmsg = msg['msg'];
    var matches;

    if (this.qsoModes.indexOf(msg['mode']) >= 0) {
        matches = linkedmsg.match(/^(.*?)([A-Z0-9\/]+)\s([A-Z0-9\/]+)\s(([A-R]{2}[0-9]{2})|(R?[+\-]?[0-9]{2})|(RRR))$/);
        if (matches) {
            var destination = matches[2]!=='CQ' && matches[2]!=='DX' && matches[2]!=='TEST'?
                Utils.linkifyCallsign(matches[2]) : matches[2];
            var locator = matches[5] && matches[5]!=='RR73'?
                Utils.linkifyLocator(matches[5]) : matches[4];
            linkedmsg = Utils.htmlEscape(matches[1]) + destination
                + ' ' + Utils.linkifyCallsign(matches[3])
                + ' ' + locator;
        } else {
            linkedmsg = Utils.htmlEscape(linkedmsg);
        }
    } else if (this.beaconModes.indexOf(msg['mode']) >= 0) {
        matches = linkedmsg.match(/([A-Z0-9]+)\s([A-R]{2}[0-9]{2})\s([0-9]+)/);
        if (matches) {
            linkedmsg = Utils.linkifyCallsign(matches[1])
                + ' ' + Utils.linkifyLocator(matches[2])
                + ' ' + Utils.htmlEscape(matches[3]);
        } else {
            linkedmsg = Utils.htmlEscape(linkedmsg);
        }
    }
    $b.append($(
        '<tr data-timestamp="' + msg['timestamp'] + '">' +
        '<td class="time">' + Utils.HHMMSS(msg['timestamp']) + '</td>' +
        '<td class="decimal">' + msg['db'] + '</td>' +
        '<td class="decimal">' + msg['dt'] + '</td>' +
        '<td class="decimal freq">' + msg['freq'] + '</td>' +
        '<td class="message" style="font-family:monospace;">' + linkedmsg + '</td>' +
        '</tr>'
    ));
    this.scrollToBottom();
}

$.fn.wsjtMessagePanel = function(){
    if (!this.data('panel')) {
        this.data('panel', new WsjtMessagePanel(this));
    }
    return this.data('panel');
};

function PacketMessagePanel(el) {
    MessagePanel.call(this, el);
    this.initClearTimer();
}

PacketMessagePanel.prototype = Object.create(MessagePanel.prototype);

PacketMessagePanel.prototype.supportsMessage = function(message) {
    return (message['mode'] === 'APRS') || (message['mode'] === 'AIS');
};

PacketMessagePanel.prototype.render = function() {
    $(this.el).append($(
        '<table>' +
            '<thead><tr>' +
                '<th class="time">UTC</th>' +
                '<th class="callsign">Callsign</th>' +
                '<th class="coord">Coord</th>' +
                '<th class="message">Comment</th>' +
            '</tr></thead>' +
            '<tbody></tbody>' +
        '</table>'
    ));
};

PacketMessagePanel.prototype.pushMessage = function(msg) {
    var $b = $(this.el).find('tbody');

    if (msg.type && msg.type === 'thirdparty' && msg.data) {
        msg = msg.data;
    }

    var source = msg.source;
    if (msg.type) {
        if (msg.type === 'nmea') {
            // Do not show AIS-specific stuff for now
            return;
        }
        if (msg.type === 'item') {
            source = msg.item;
        }
        if (msg.type === 'object') {
            source = msg.object;
        }
    }

    var timestamp = msg.timestamp? Utils.HHMMSS(msg.timestamp) : '';

    var link = '';
    var classes = [];
    var styles = {};
    var overlay = '';
    var stylesToString = function (s) {
        return $.map(s, function (value, key) {
            return key + ':' + value + ';'
        }).join('')
    };
    if (msg.symbol) {
        classes.push('aprs-symbol');
        classes.push('aprs-symboltable-' + (msg.symbol.table === '/' ? 'normal' : 'alternate'));
        styles['background-position-x'] = -(msg.symbol.index % 16) * 15 + 'px';
        styles['background-position-y'] = -Math.floor(msg.symbol.index / 16) * 15 + 'px';
        if (msg.symbol.table !== '/' && msg.symbol.table !== '\\') {
            var s = {};
            s['background-position-x'] = -(msg.symbol.tableindex % 16) * 15 + 'px';
            s['background-position-y'] = -Math.floor(msg.symbol.tableindex / 16) * 15 + 'px';
            overlay = '<div class="aprs-symbol aprs-symboltable-overlay" style="' + stylesToString(s) + '"></div>';
        }
    } else if (msg.lat && msg.lon) {
        classes.push('openwebrx-maps-pin');
        overlay = '<svg viewBox="0 0 20 35"><use xlink:href="static/gfx/svg-defs.svg#maps-pin"></use></svg>';
    }
    var attrs = [
        'class="' + classes.join(' ') + '"',
        'style="' + stylesToString(styles) + '"'
    ].join(' ');
    if (msg.lat && msg.lon) {
        link = Utils.linkToMap(source, overlay, attrs);
    } else {
        link = '<div ' + attrs + '>' + overlay + '</div>'
    }

    // Compose comment
    var comment = msg.comment || msg.message || '';
    if (comment !== '') {
        // Escape all special characters
        comment = Utils.htmlEscape(comment);
    } else if (msg.country) {
        // Add country flag and name in lieu of comment
        comment = Lookup.cdata2country([msg.ccode, msg.country]);
    } else if (msg.mode === 'AIS') {
        // Get country flag and name from the MMSI
        comment = Lookup.mmsi2country(source);
    }

    // Linkify source based on what it is (vessel or HAM callsign)
    source = msg.mode === 'AIS'?
        Utils.linkifyVessel(source) : Utils.linkifyCallsign(source);

    $b.append($(
        '<tr>' +
        '<td class="time">' + timestamp + '</td>' +
        '<td class="callsign">' + source + '</td>' +
        '<td class="coord">' + link + '</td>' +
        '<td class="message">' + comment + '</td>' +
        '</tr>'
    ));
    this.scrollToBottom();
};

$.fn.packetMessagePanel = function() {
    if (!this.data('panel')) {
        this.data('panel', new PacketMessagePanel(this));
    }
    return this.data('panel');
};

PocsagMessagePanel = function(el) {
    MessagePanel.call(this, el);
    this.initClearTimer();
}

PocsagMessagePanel.prototype = Object.create(MessagePanel.prototype);

PocsagMessagePanel.prototype.supportsMessage = function(message) {
    return message['mode'] === 'Pocsag';
};

PocsagMessagePanel.prototype.render = function() {
    $(this.el).append($(
        '<table>' +
            '<thead><tr>' +
                '<th class="address">Address</th>' +
                '<th class="message">Message</th>' +
            '</tr></thead>' +
            '<tbody></tbody>' +
        '</table>'
    ));
};

PocsagMessagePanel.prototype.pushMessage = function(msg) {
    var $b = $(this.el).find('tbody');
    $b.append($(
        '<tr>' +
            '<td class="address">' + msg.address + '</td>' +
            '<td class="message">' + Utils.htmlEscape(msg.message) + '</td>' +
        '</tr>'
    ));
    this.scrollToBottom();
};

$.fn.pocsagMessagePanel = function() {
    if (!this.data('panel')) {
        this.data('panel', new PocsagMessagePanel(this));
    }
    return this.data('panel');
};

PageMessagePanel = function(el) {
    MessagePanel.call(this, el);
    this.initClearTimer();
}

PageMessagePanel.prototype = Object.create(MessagePanel.prototype);

PageMessagePanel.prototype.supportsMessage = function(message) {
    return (message['mode'] === 'FLEX') || (message['mode'] === 'POCSAG');
};

PageMessagePanel.prototype.render = function() {
    $(this.el).append($(
        '<table>' +
            '<thead><tr>' +
                '<th class="address">CapCode</th>' +
                '<th class="mode">Mode</th>' +
                '<th class="timestamp">Time</th>' +
            '</tr></thead>' +
            '<tbody></tbody>' +
        '</table>'
    ));
};

PageMessagePanel.prototype.pushMessage = function(msg) {
    // Get color from the message, default to white
    var color = msg.hasOwnProperty('color')? msg.color : '#FFF';

    // Get channel from the message (FLEX only)
    var channel = msg.hasOwnProperty('channel')? '/' + msg.channel : '';


    // Append message header (address, time, etc)
    var $b = $(this.el).find('tbody');
    $b.append($(
        '<tr>' +
            '<td class="address">' + msg.address + '</td>' +
            '<td class="mode">' + msg.mode + msg.baud + channel + '</td>' +
            '<td class="timestamp" style="text-align:right;">' + Utils.HHMMSS(msg.timestamp) + '</td>' +
        '</tr>'
    ).css('background-color', color).css('color', '#000'));

    // Append message body (text)
    if (msg.hasOwnProperty('message')) {
        $b.append($(
            '<tr><td class="message" colspan="3">' +
            Utils.htmlEscape(msg.message) +
            '</td></tr>'
        ));
    }

    // Jump list to the last received message
    this.scrollToBottom();
};

$.fn.pageMessagePanel = function() {
    if (!this.data('panel')) {
        this.data('panel', new PageMessagePanel(this));
    }
    return this.data('panel');
};

HfdlMessagePanel = function(el) {
    MessagePanel.call(this, el);
    this.initClearTimer();
    this.modes = ['HFDL', 'VDL2', 'ADSB', 'ACARS'];
}

HfdlMessagePanel.prototype = Object.create(MessagePanel.prototype);

HfdlMessagePanel.prototype.supportsMessage = function(message) {
    return this.modes.indexOf(message['mode']) >= 0;
};

HfdlMessagePanel.prototype.render = function() {
    $(this.el).append($(
        '<table>' +
            '<thead><tr>' +
                '<th class="timestamp">Time</th>' +
                '<th class="flight">Flight</th>' +
                '<th class="aircraft">Aircraft</th>' +
                '<th class="data">Data</th>' +
            '</tr></thead>' +
            '<tbody></tbody>' +
        '</table>'
    ));
};

HfdlMessagePanel.prototype.pushMessage = function(msg) {
    var bcolor = msg.color?  msg.color : '#000';
    var fcolor = msg.color?  '#000' : '#FFF';
    var data   = msg.type?   msg.type : '';

    // Only linkify ICAO-compliant flight IDs
    var flight =
      !msg.flight? ''
    : !msg.flight.match(/^[A-Z]{3}[0-9]+[A-Z]*$/)? msg.flight
    : Utils.linkifyFlight(msg.flight);

    var aircraft =
      msg.aircraft? Utils.linkifyFlight(msg.aircraft)
    : msg.icao?     Utils.linkifyIcao(msg.icao)
    : '';

    var tstamp =
      msg.msgtime?   '<b>' + msg.msgtime + '</b>'
    : msg.timestamp? Utils.HHMMSS(msg.timestamp)
    : '';

    // Add location, altitude, speed, etc
    var data = '';
    if (msg.lat && msg.lon) {
        data += '@' + msg.lat.toFixed(4) + ',' + msg.lon.toFixed(4);
    }
    if (msg.altitude)    data += ' &UpArrowBar;' + msg.altitude + 'ft';
    if (msg.vspeed>0)    data += ' &UpperRightArrow;' + msg.vspeed + 'ft/m';
    if (msg.vspeed<0)    data += ' &LowerRightArrow;' + (-msg.vspeed) + 'ft/m';
    if (msg.speed)       data += ' &rightarrow;' + msg.speed + 'kt';
    if (msg.origin)      data += ' &lsh;' + msg.origin;
    if (msg.destination) data += ' &rdsh;' + msg.destination;

    // If no location data in the message, use message type as data
    if (!data.length && msg.type) data = msg.type;

    // Make data point to the map
    if (data.length && msg.mapid) data = Utils.linkToMap(msg.mapid, data);

    // Append report
    var $b = $(this.el).find('tbody');
    $b.append($(
        '<tr>' +
            '<td class="timestamp">' + tstamp + '</td>' +
            '<td class="flight">' + flight + '</td>' +
            '<td class="aircraft">' + aircraft + '</td>' +
            '<td class="data" style="text-align:left;">' + data + '</td>' +
        '</tr>'
    ).css('background-color', bcolor).css('color', fcolor));

    // Append messsage if present
    if (msg.message) {
        $b.append($(
            '<tr><td class="message" colspan="4">' + Utils.htmlEscape(msg.message) + '</td></tr>'
        ));
    }

    // Jump list to the last received message
    this.scrollToBottom();
};

$.fn.hfdlMessagePanel = function() {
    if (!this.data('panel')) {
        this.data('panel', new HfdlMessagePanel(this));
    }
    return this.data('panel');
};

AdsbMessagePanel = function(el) {
    MessagePanel.call(this, el);
    this.clearButton.css('display', 'none');
}

AdsbMessagePanel.prototype = Object.create(MessagePanel.prototype);

AdsbMessagePanel.prototype.supportsMessage = function(message) {
    return message['mode'] === 'ADSB-LIST';
};

AdsbMessagePanel.prototype.render = function() {
    $(this.el).append($(
        '<table>' +
            '<thead><tr>' +
                '<th class="flight">Flight</th>' +
                '<th class="aircraft">Aircraft</th>' +
                '<th class="squawk">Squawk</th>' +
                '<th class="distance">Dist</th>' +
                '<th class="altitude">Alt&nbsp;(ft)</th>' +
                '<th class="speed">Speed&nbsp;(kt)</th>' +
                '<th class="rssi">Signal</th>' +
            '</tr></thead>' +
            '<tbody></tbody>' +
        '</table>'
    ));
};

AdsbMessagePanel.prototype.pushMessage = function(msg) {
    // Must have list of aircraft
    if (!msg.aircraft) return;

    // Create new table body
    var body = '';
    var odd = false;
    msg.aircraft.forEach(entry => {
        // Signal strength
        var rssi = entry.rssi? entry.rssi + '&nbsp;dB' : '';

        // Flight identificators
        var flight =
          entry.flight? Utils.linkifyFlight(entry.flight)
        : '';
        var aircraft =
          entry.aircraft? Utils.linkifyFlight(entry.aircraft)
        : entry.icao?     Utils.linkifyIcao(entry.icao)
        : '';

        // Altitude and climb / descent
        var alt  = entry.altitude? '' + entry.altitude : '';
        if (entry.vspeed) {
            var vspeed = entry.vspeed;
            vspeed = vspeed>0? vspeed + '&uarr;' : (-vspeed) + '&darr;';
            alt    = vspeed + '&nbsp'.repeat(6 - alt.length) + alt;
        }

        // Speed and direction
        var speed = entry.speed? '' + entry.speed : '';
        if (entry.course) {
            var dir = Utils.degToCompass(entry.course);
            speed = dir + '&nbsp'.repeat(5 - speed.length) + speed;
        }

        // Replace squawk with emergency status, if present
        var squawk = entry.squawk? entry.squawk : '';
        if (entry.emergency && (entry.emergency!=='NONE')) {
            squawk = '<div style="color:white;background-color:red;"><b>&nbsp;'
                + entry.emergency + '&nbsp;</b></div>';
        }

        // Compute distance to the receiver
        var distance = '';
        var receiver_pos = Utils.getReceiverPos();
        if (receiver_pos && entry.lat && entry.lon) {
            var id = entry.icao?     entry.icao
                   : entry.aircraft? entry.aircraft
                   : entry.flight?   entry.flight
                   : null;

            distance = Utils.distanceKm(entry, receiver_pos) + '&nbsp;km';
            if (id) distance = Utils.linkToMap(id, distance);
        }

        body += '<tr style="background-color:' + (odd? '#E0FFE0':'#FFFFFF') + ';">'
            + '<td class="flight">'   + flight   + '</td>'
            + '<td class="aircraft">' + aircraft + '</td>'
            + '<td class="squawk">'   + squawk   + '</td>'
            + '<td class="distance">' + distance + '</td>'
            + '<td class="altitude">' + alt      + '</td>'
            + '<td class="speed">'    + speed    + '</td>'
            + '<td class="rssi">'     + rssi     + '</td>'
            + '</tr>\n';
        odd = !odd;
    });

    // Assign new table body
    $(this.el).find('tbody').html(body);
};

$.fn.adsbMessagePanel = function() {
    if (!this.data('panel')) {
        this.data('panel', new AdsbMessagePanel(this));
    }
    return this.data('panel');
};

DscMessagePanel = function(el) {
    MessagePanel.call(this, el);
    this.initClearTimer();
}

DscMessagePanel.prototype = Object.create(MessagePanel.prototype);

DscMessagePanel.prototype.supportsMessage = function(message) {
    return message['mode'] === 'DSC';
};

DscMessagePanel.prototype.render = function() {
    $(this.el).append($(
        '<table>' +
            '<thead><tr>' +
                '<th class="timestamp">UTC</th>' +
                '<th class="src">From</th>' +
                '<th class="dst">To</th>' +
                '<th class="data">Data</th>' +
            '</tr></thead>' +
            '<tbody></tbody>' +
        '</table>'
    ));
};

DscMessagePanel.prototype.pushMessage = function(msg) {
    var bcolor = msg.color? msg.color : '#000';
    var fcolor = msg.color? '#000' : '#FFF';
    var src    = msg.src? Utils.linkifyVessel(msg.src) : '';
    var dst    = msg.dst? Utils.linkifyVessel(msg.dst) : '';
    var data   = (
      (msg.category? ' ' + msg.category : '')
    + (msg.format?   ' ' + msg.format : '')
    + (msg.eos?      ' ' + msg.eos : '')
    + (!msg.ecc && !msg.data? ' ?' : '')
    ).trim().toUpperCase();

    // Format timestamp
    var timestamp =
      msg.time?      '<b>' + msg.time + '</b>'
    : msg.timestamp? Utils.HHMMSS(msg.timestamp)
    : '';

    // Format debugging data
    var symbols = '';
    if (msg.data) {
        symbols = msg.data.replace(
            /(.*)\|(.*)/, ' $1<span style="opacity:0.5;"> | $2 &hellip;</span>'
        );
    }

    // Combine remaining attributes into a message
    var message = (
      (msg.distress? ' ' + msg.distress : '')
    + (msg.id?     ' SHIP ' + Utils.linkifyVessel(msg.id) : '')
    + (msg.loc?    ' AT ' + msg.loc : '')
    + (msg.num?    ' DIAL ' + msg.num : '')
    + (msg.rxfreq? ' RX ' + Utils.printFreq(msg.rxfreq) : '')
    + (msg.txfreq? ' TX ' + Utils.printFreq(msg.txfreq) : '')
    + symbols
    ).trim();

    // Append report
    var $b = $(this.el).find('tbody');
    $b.append($(
        '<tr>' +
            '<td class="timestamp">' + timestamp + '</td>' +
            '<td class="src">' + src + '</td>' +
            '<td class="dst">' + dst + '</td>' +
            '<td class="data" style="text-align:left;">' + data + '</td>' +
        '</tr>'
    ).css('background-color', bcolor).css('color', fcolor));

    // Append messsage if present
    if (message) {
        $b.append($(
            '<tr><td class="message" colspan="4">' + message + '</td></tr>'
        ));
    }

    // Jump list to the last received message
    this.scrollToBottom();
};

$.fn.dscMessagePanel = function() {
    if (!this.data('panel')) {
        this.data('panel', new DscMessagePanel(this));
    }
    return this.data('panel');
};

IsmMessagePanel = function(el) {
    MessagePanel.call(this, el);
    this.initClearTimer();
    // These are basic message attributes
    this.basicInfo = ['mode', 'id', 'model', 'timestamp', 'freq', 'color'];
}

IsmMessagePanel.prototype = Object.create(MessagePanel.prototype);

IsmMessagePanel.prototype.supportsMessage = function(message) {
    return message['mode'] === 'ISM';
};

IsmMessagePanel.prototype.render = function() {
    $(this.el).append($(
        '<table>' +
            '<thead><tr>' +
                '<th class="address">ID</th>' +
                '<th class="device">Device</th>' +
                '<th class="timestamp">Time</th>' +
            '</tr></thead>' +
            '<tbody></tbody>' +
        '</table>'
    ));
};

IsmMessagePanel.prototype.formatAttr = function(msg, key) {
    return('<td class="attr" colspan="2">' +
        '<div style="border-bottom:1px dotted;">' +
        '<span style="float:left;">' + key + '</span>' +
        '<span style="float:right;">' + msg[key] + '</span>' +
        '</div></td>'
    );
};

IsmMessagePanel.prototype.pushMessage = function(msg) {
    // Get basic information, assume white color if missing
    var address = msg.hasOwnProperty('id')? msg.id : '???';
    var device  = msg.hasOwnProperty('model')? msg.model : '';
    var tstamp  = msg.hasOwnProperty('timestamp')? Utils.HHMMSS(msg.timestamp) : '';
    var color   = msg.hasOwnProperty('color')? msg.color : '#FFF';

    // Append message header (address, time, etc)
    var $b = $(this.el).find('tbody');
    $b.append($(
        '<tr>' +
            '<td class="address">' + address + '</td>' +
            '<td class="device">' + device + '</td>' +
            '<td class="timestamp" style="text-align:right;" colspan="2">' + tstamp + '</td>' +
        '</tr>'
    ).css('background-color', color).css('color', '#000'));

    // Append attributes in pairs, skip basic information
    var last = null;
    for (var key in msg) {
        if (this.basicInfo.indexOf(key) < 0) {
            var cell = this.formatAttr(msg, key);
            if (!last) {
                last = cell;
            } else {
                $b.append($('<tr>' + last + cell + '</tr>'));
                last = null;
            }
        }
    }

    // Last row
    if (last) $b.append($('<tr>' + last + '<td class="attr"/></tr>'));

    // Jump list to the last received message
    this.scrollToBottom();
};

$.fn.ismMessagePanel = function() {
    if (!this.data('panel')) {
        this.data('panel', new IsmMessagePanel(this));
    }
    return this.data('panel');
};

SstvMessagePanel = function(el) {
    MessagePanel.call(this, el);
    this.initClearTimer();
}

SstvMessagePanel.prototype = Object.create(MessagePanel.prototype);

SstvMessagePanel.prototype.supportsMessage = function(message) {
    return message['mode'] === 'SSTV';
};

SstvMessagePanel.prototype.render = function() {
    $(this.el).append($(
        '<table>' +
            '<thead><tr>' +
                '<th class="message">TV</th>' +
            '</tr></thead>' +
            '<tbody></tbody>' +
        '</table>'
    ));
};

SstvMessagePanel.prototype.pushMessage = function(msg) {
    var $b = $(this.el).find('tbody');
    if(msg.hasOwnProperty('message')) {
        // Append a new debug message text
// See service log for debug output instead
//        $b.append($('<tr><td class="message">' + msg.message + '</td></tr>'));
//        this.scrollToBottom();
    }
    else if(msg.width>0 && msg.height>0 && !msg.hasOwnProperty('line')) {
        var f = msg.frequency>0? ' at ' + Math.floor(msg.frequency/1000) + 'kHz' : '';
        var h = '<div>' + msg.timestamp + ' ' + msg.width + 'x' + msg.height +
            ' ' + msg.sstvMode + f + '</div>';
        var c = '<div onclick="Utils.saveCanvas(\'' + msg.filename + '\');">' +
            '<canvas class="frame" id="' + msg.filename +
            '" width="' + msg.width + '" height="' + msg.height +
            '"></canvas></div>';
        // Append a new canvas
        $b.append($('<tr><td class="message">' + h + c + '</td></tr>'));
        $b.scrollTop($b[0].scrollHeight);
        // Save canvas context and dimensions for future use
        this.ctx    = $(this.el).find('canvas').get(-1).getContext("2d");
        this.width  = msg.width;
        this.height = msg.height;
    }
    else if(msg.width>0 && msg.height>0 && msg.line>=0 && msg.hasOwnProperty('pixels')) {
        // Will copy pixels to img
        var pixels = atob(msg.pixels);
        var img = this.ctx.createImageData(msg.width, 1);
        // Convert BMP BGR pixels into HTML RGBA pixels
        for (var x = 0; x < msg.width; x++) {
            img.data[x*4 + 0] = pixels.charCodeAt(x*3 + 2);
            img.data[x*4 + 1] = pixels.charCodeAt(x*3 + 1);
            img.data[x*4 + 2] = pixels.charCodeAt(x*3 + 0);
            img.data[x*4 + 3] = 0xFF;
        }
        // Render scanline
        this.ctx.putImageData(img, 0, msg.line);
    }
};

$.fn.sstvMessagePanel = function() {
    if (!this.data('panel')) {
        this.data('panel', new SstvMessagePanel(this));
    }
    return this.data('panel');
};

FaxMessagePanel = function(el) {
    MessagePanel.call(this, el);
    this.initClearTimer();
}

FaxMessagePanel.prototype = Object.create(MessagePanel.prototype);

FaxMessagePanel.prototype.supportsMessage = function(message) {
    return message['mode'] === 'Fax';
};

FaxMessagePanel.prototype.render = function() {
    $(this.el).append($(
        '<table>' +
            '<thead><tr>' +
                '<th class="message">Fax</th>' +
            '</tr></thead>' +
            '<tbody></tbody>' +
        '</table>'
    ));
};

FaxMessagePanel.prototype.pushMessage = function(msg) {
    var $b = $(this.el).find('tbody');
    if(msg.hasOwnProperty('message')) {
        // Append a new debug message text
// See service log for debug output instead
//        $b.append($('<tr><td class="message">' + msg.message + '</td></tr>'));
//        this.scrollToBottom();
    }
    else if(msg.width>0 && msg.height>0 && !msg.hasOwnProperty('line')) {
        var f = msg.frequency>0? ' at ' + Math.floor(msg.frequency/1000) + 'kHz' : '';
        var h = '<div>' + msg.timestamp + ' ' + msg.width + 'x' + msg.height +
            ' ' + msg.faxMode + f + '</div>';
        var c = '<div onclick="Utils.saveCanvas(\'' + msg.filename + '\');">' +
            '<canvas class="frame" id="' + msg.filename +
            '" width="' + msg.width + '" height="' + msg.height +
            '"></canvas></div>';
        // Append a new canvas
        $b.append($('<tr><td class="message">' + h + c + '</td></tr>'));
        this.scrollToBottom();
        // Save canvas context and dimensions for future use
        this.ctx    = $(this.el).find('canvas').get(-1).getContext("2d");
        this.width  = msg.width;
        this.height = msg.height;
    }
    else if(msg.width>0 && msg.height>0 && msg.line>=0 && msg.ended) {
        const canvas  = $(this.el).find('canvas').get(-1);
        const image   = this.ctx.getImageData(0, 0, canvas.width, canvas.height);
        canvas.height = msg.line;
        this.height   = msg.line;
        this.ctx.putImageData(image, 0, 0);
    }
    else if(msg.width>0 && msg.height>0 && msg.line>=0 && msg.hasOwnProperty('pixels')) {
        // Will copy pixels to img
        var img = this.ctx.createImageData(msg.width, 1);
        var pixels;

        // Unpack RLE-compressed line of pixels
        if(!msg.rle) {
            pixels = atob(msg.pixels);
        } else {
            var rle = atob(msg.pixels);
            pixels = '';
            for(var x=0 ; x<rle.length ; ) {
                var c = rle.charCodeAt(x);
                if(c<128) {
                    pixels += rle.slice(x+1, x+c+2);
                    x += c + 2;
                } else {
                    pixels += rle.slice(x+1, x+2).repeat(c-128+2)
                    x += 2;
                }
            }
        }

        // Convert BMP BGR pixels into HTML RGBA pixels
        if(msg.depth==8) {
            for(var x=0, y=0; x<msg.width; x++) {
                var c = pixels.charCodeAt(x);
                img.data[y++] = c;
                img.data[y++] = c;
                img.data[y++] = c;
                img.data[y++] = 0xFF;
            }
        } else {
            for (var x = 0; x < msg.width; x++) {
                img.data[x*4 + 0] = pixels.charCodeAt(x*3 + 2);
                img.data[x*4 + 1] = pixels.charCodeAt(x*3 + 1);
                img.data[x*4 + 2] = pixels.charCodeAt(x*3 + 0);
                img.data[x*4 + 3] = 0xFF;
            }
        }

        // Render scanline
        this.ctx.putImageData(img, 0, msg.line);
    }
};

$.fn.faxMessagePanel = function() {
    if (!this.data('panel')) {
        this.data('panel', new FaxMessagePanel(this));
    }
    return this.data('panel');
};

CwSkimmerMessagePanel = function(el) {
    MessagePanel.call(this, el);
    this.texts = [];

    // CLEAR button clears underlying texts storage
    var me = this;
    this.clearButton.on('click', function() { me.texts = []; });
}

CwSkimmerMessagePanel.prototype = Object.create(MessagePanel.prototype);

CwSkimmerMessagePanel.prototype.supportsMessage = function(message) {
    return message['mode'] === 'CW';
};

CwSkimmerMessagePanel.prototype.render = function() {
    $(this.el).append($(
        '<table width="100%">' +
            '<thead><tr>' +
                '<th class="freq">Freq</th>' +
                '<th class="text">Text</th>' +
            '</tr></thead>' +
            '<tbody></tbody>' +
        '</table>'
    ));
};

CwSkimmerMessagePanel.prototype.pushMessage = function(msg) {
    // Must have some text
    if (!msg.text) return;

    // Clear cache if requested
//    if (msg.changed) this.texts = [];

    // Current time
    var now = Date.now();

    // Modify or add a new entry
    var j = this.texts.findIndex(function(x) { return x.freq >= msg.freq });
    if (j < 0) {
        // Append a new entry
        if (msg.text.trim().length > 0) {
            this.texts.push({ freq: msg.freq, text: msg.text, ts: now });
        }
    } else if (this.texts[j].freq == msg.freq) {
        // Update existing entry
        this.texts[j].text = (this.texts[j].text + msg.text).slice(-64);
        this.texts[j].ts   = now;
    } else {
        // Insert a new entry
        if (msg.text.trim().length > 0) {
            this.texts.splice(j, 0, { freq: msg.freq, text: msg.text, ts: now });
        }
    }

    // Generate table body
    var body = '';
    for (var j = 0 ; j < this.texts.length ; j++) {
        // Limit the lifetime of entries depending on their length
        var cutoff = 5000 * this.texts[j].text.length;
        if (now - this.texts[j].ts >= cutoff) {
            this.texts.splice(j--, 1);
        } else {
            var f = Math.floor(this.texts[j].freq / 100.0) / 10.0;
            body +=
                '<tr style="color:black;background-color:' + (j&1? '#E0FFE0':'#FFFFFF') +
                ';"><td class="freq">' + f.toFixed(1) +
                '</td><td class="text">' + this.texts[j].text + '</td></tr>\n';
        }
    }

    // Assign new table body
    $(this.el).find('tbody').html(body);
};

$.fn.cwskimmerMessagePanel = function() {
    if (!this.data('panel')) {
        this.data('panel', new CwSkimmerMessagePanel(this));
    }
    return this.data('panel');
};
