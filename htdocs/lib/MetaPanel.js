function MetaPanel(el) {
    this.el = el;
    this.modes = [];
}

MetaPanel.prototype.update = function(data) {
};

MetaPanel.prototype.isSupported = function(data) {
    return this.modes.includes(data.protocol);
};

MetaPanel.prototype.clear = function() {
    this.el.find(".openwebrx-meta-slot").removeClass("active").removeClass("sync");
};

function DmrMetaSlot(el) {
    this.el = $(el);
    this.clear();
}

DmrMetaSlot.prototype.update = function(data) {
    this.el[data['sync'] ? "addClass" : "removeClass"]("sync");
    if (data['sync'] && data['sync'] === "voice") {
        this.setId(data['additional'] && data['additional']['callsign'] || data['talkeralias'] || data['source']);
        this.setName(data['additional'] && data['additional']['fname']);
        this.setMode(['group', 'direct'].includes(data['type']) ? data['type'] : undefined);
        this.setTarget(data['target']);
        this.setLocation(data['lat'], data['lon'], this.getCallsign(data));
        this.el.addClass("active");
    } else {
        this.clear();
    }
};

DmrMetaSlot.prototype.getCallsign = function(data) {
    if ('additional' in data) {
        return data['additional']['callsign'];
    }
    if ('talkeralias' in data) {
        var matches = /^([A-Z0-9]+)(\s.*)?$/.exec(data['talkeralias']);
        if (matches) return matches[1];
    }
};

DmrMetaSlot.prototype.setId = function(id) {
    if (this.id === id) return;
    this.id = id;
    this.el.find('.openwebrx-dmr-id .dmr-id').text(id || '');
}

DmrMetaSlot.prototype.setName = function(name) {
    if (this.name === name) return;
    this.name = name;
    this.el.find('.openwebrx-dmr-name').text(name || '');
};

DmrMetaSlot.prototype.setMode = function(mode) {
    if (this.mode === mode) return;
    this.mode = mode;
    var classes = ['group', 'direct'].filter(function(c){
        return c !== mode;
    });
    this.el.removeClass(classes.join(' ')).addClass(mode);
}

DmrMetaSlot.prototype.setTarget = function(target) {
    if (this.target === target) return;
    this.target = target;
    this.el.find('.openwebrx-dmr-target').text(target || '');
}

DmrMetaSlot.prototype.setLocation = function(lat, lon, callsign) {
    var hasLocation = lat && lon && callsign && callsign != '';
    if (hasLocation === this.hasLocation && this.callsign === callsign) return;
    this.hasLocation = hasLocation; this.callsign = callsign;
    var html = '';
    if (hasLocation) {
        html = '<a class="openwebrx-maps-pin" href="map?callsign=' + encodeURIComponent(callsign) + '" target="_blank"><svg viewBox="0 0 20 35"><use xlink:href="static/gfx/svg-defs.svg#maps-pin"></use></svg></a>';
    }
    this.el.find('.openwebrx-dmr-id .location').html(html);
}

DmrMetaSlot.prototype.clear = function() {
    this.setId();
    this.setName();
    this.setMode();
    this.setTarget();
    this.setLocation();
    this.el.removeClass("active");
};

function DmrMetaPanel(el) {
    MetaPanel.call(this, el);
    this.modes = ['DMR'];
    this.slots = this.el.find('.openwebrx-meta-slot').toArray().map(function(el){
        return new DmrMetaSlot(el);
    });
}

DmrMetaPanel.prototype = new MetaPanel();

DmrMetaPanel.prototype.update = function(data) {
    if (!this.isSupported(data)) return;
    if (data['slot']) {
        var slot = this.slots[data['slot']];
        slot.update(data);
    } else {
        this.clear();
    }
}

DmrMetaPanel.prototype.clear = function() {
    MetaPanel.prototype.clear.call(this);
    this.el.find(".openwebrx-dmr-timeslot-panel").removeClass("muted");
    this.slots.forEach(function(slot) {
        slot.clear();
    });
};

function YsfMetaPanel(el) {
    MetaPanel.call(this, el);
    this.modes = ['YSF'];
    this.clear();
}

YsfMetaPanel.prototype = new MetaPanel();

YsfMetaPanel.prototype.update = function(data) {
    if (!this.isSupported(data)) return;
    this.setMode(data['mode']);

    if (data['mode'] && data['mode'] !== "") {
        this.setSource(data['source']);
        this.setLocation(data['lat'], data['lon'], data['source']);
        this.setUp(data['up']);
        this.setDown(data['down']);
        if (data['mode'].indexOf('data') < 0) {
            this.el.find(".openwebrx-meta-slot").addClass("active");
        }
    } else {
        this.clear();
    }
};

YsfMetaPanel.prototype.clear = function() {
    MetaPanel.prototype.clear.call(this);
    this.setMode();
    this.setSource();
    this.setLocation();
    this.setUp();
    this.setDown();
};

YsfMetaPanel.prototype.setMode = function(mode) {
    if (this.mode === mode) return;
    this.mode = mode;
    this.el.find('.openwebrx-ysf-mode').text(mode || '');
};

YsfMetaPanel.prototype.setSource = function(source) {
    if (this.source === source) return;
    this.source = source;
    this.el.find('.openwebrx-ysf-source .callsign').text(source || '');
};

YsfMetaPanel.prototype.setLocation = function(lat, lon, callsign) {
    var hasLocation = lat && lon && callsign && callsign != '';
    if (hasLocation === this.hasLocation && this.callsign === callsign) return;
    this.hasLocation = hasLocation; this.callsign = callsign;
    var html = '';
    if (hasLocation) {
        html = '<a class="openwebrx-maps-pin" href="map?callsign=' + encodeURIComponent(callsign) + '" target="_blank"><svg viewBox="0 0 20 35"><use xlink:href="static/gfx/svg-defs.svg#maps-pin"></use></svg></a>';
    }
    this.el.find('.openwebrx-ysf-source .location').html(html);
};

YsfMetaPanel.prototype.setUp = function(up) {
    if (this.up === up) return;
    this.up = up;
    this.el.find('.openwebrx-ysf-up').text(up || '');
};

YsfMetaPanel.prototype.setDown = function(down) {
    if (this.down === down) return;
    this.down = down;
    this.el.find('.openwebrx-ysf-down').text(down || '');
}

function DStarMetaPanel(el) {
    MetaPanel.call(this, el);
    this.modes = ['DSTAR'];
    this.clear();
}

DStarMetaPanel.prototype = new MetaPanel();

DStarMetaPanel.prototype.update = function(data) {
    if (!this.isSupported(data)) return;

    if (data['sync'] && data['sync'] == 'voice') {
        this.el.find(".openwebrx-meta-slot").addClass("active");
        this.setOurCall(data['ourcall']);
        this.setYourCall(data['yourcall']);
        this.setDeparture(data['departure']);
        this.setDestination(data['destination']);
        this.setMessage(data['message']);
        this.setLocation(data['lat'], data['lon'], data['ourcall']);
    } else {
        this.clear();
    }
};

DStarMetaPanel.prototype.setOurCall = function(ourcall) {
    if (this.ourcall === ourcall) return;
    this.ourcall = ourcall;
    this.el.find('.openwebrx-dstar-ourcall .callsign').text(ourcall || '');
};

DStarMetaPanel.prototype.setYourCall = function(yourcall) {
    if (this.yourcall === yourcall) return;
    this.yourcall = yourcall;
    this.el.find('.openwebrx-dstar-yourcall').text(yourcall || '');
};

DStarMetaPanel.prototype.setDeparture = function(departure) {
    if (this.departure === departure) return;
    this.departure = departure;
    this.el.find('.openwebrx-dstar-departure').text(departure || '');
};

DStarMetaPanel.prototype.setDestination = function(destination) {
    if (this.destination === destination) return;
    this.destination = destination;
    this.el.find('.openwebrx-dstar-destination').text(destination || '');
};

DStarMetaPanel.prototype.setMessage = function(message) {
    if (this.message === message) return;
    this.message = message;
    this.el.find('.openwebrx-dstar-message').text(message || '');
}

DStarMetaPanel.prototype.clear = function() {
    MetaPanel.prototype.clear.call(this);
    this.setOurCall();
    this.setYourCall();
    this.setDeparture();
    this.setDestination();
    this.setMessage();
    this.setLocation();
};

DStarMetaPanel.prototype.setLocation = function(lat, lon, callsign) {
    var hasLocation = lat && lon && callsign && callsign != '';
    if (hasLocation === this.hasLocation && this.callsign === callsign) return;
    this.hasLocation = hasLocation; this.callsign = callsign;
    var html = '';
    if (hasLocation) {
        html = '<a class="openwebrx-maps-pin" href="map?callsign=' + encodeURIComponent(callsign) + '" target="_blank"><svg viewBox="0 0 20 35"><use xlink:href="static/gfx/svg-defs.svg#maps-pin"></use></svg></a>';
    }
    this.el.find('.openwebrx-dstar-ourcall .location').html(html);
};

function NxdnMetaPanel(el) {
    MetaPanel.call(this, el);
    this.modes = ['NXDN'];
    this.clear();
}

NxdnMetaPanel.prototype = new MetaPanel();

NxdnMetaPanel.prototype.update = function(data) {
    if (!this.isSupported(data)) return;

    if (data['sync'] && data['sync'] === 'voice') {
        this.el.find(".openwebrx-meta-slot").addClass("active");
        this.setSource(data['additional'] && data['additional']['callsign'] || data['source']);
        this.setName(data['additional'] && data['additional']['fname']);
        this.setDestination(data['destination']);
        this.setMode(['conference', 'individual'].includes(data['type']) ? data['type'] : undefined);
    } else {
        this.clear();
    }
};

NxdnMetaPanel.prototype.setSource = function(source) {
    if (this.source === source) return;
    this.source = source;
    this.el.find('.openwebrx-nxdn-source').text(source || '');
};

NxdnMetaPanel.prototype.setName = function(name) {
    if (this.name === name) return;
    this.name = name;
    this.el.find('.openwebrx-nxdn-name').text(name || '');
};

NxdnMetaPanel.prototype.setDestination = function(destination) {
    if (this.destination === destination) return;
    this.destination = destination;
    this.el.find('.openwebrx-nxdn-destination').text(destination || '');
};

NxdnMetaPanel.prototype.setMode = function(mode) {
    if (this.mode === mode) return;
    this.mode = mode;

    var modes = ['individual', 'conference'];
    var classes = modes.filter(function(c){
        return c !== mode;
    });
    this.el.find('.openwebrx-meta-slot').removeClass(classes.join(' ')).addClass(mode);
};

NxdnMetaPanel.prototype.clear = function() {
    MetaPanel.prototype.clear.call(this);
    this.setMode();
    this.setSource();
    this.setName();
    this.setDestination();
};

function M17MetaPanel(el) {
    MetaPanel.call(this, el);
    this.modes = ['M17'];
    this.clear();
}

M17MetaPanel.prototype = new MetaPanel();

M17MetaPanel.prototype.update = function(data) {
    if (!this.isSupported(data)) return;

    if (data['sync'] && data['sync'] === 'voice') {
        this.el.find(".openwebrx-meta-slot").addClass("active");
        this.setSource(data['source']);
        this.setDestination(data['destination']);
    } else {
        this.clear();
    }
};

M17MetaPanel.prototype.setSource = function(source) {
    if (this.source === source) return;
    this.source = source;
    this.el.find('.openwebrx-m17-source').text(source || '');
};

M17MetaPanel.prototype.setDestination = function(destination) {
    if (this.destination === destination) return;
    this.destination = destination;
    this.el.find('.openwebrx-m17-destination').text(destination || '');
};

M17MetaPanel.prototype.clear = function() {
    MetaPanel.prototype.clear.call(this);
    this.setSource();
    this.setDestination();
};

function WfmMetaPanel(el) {
    MetaPanel.call(this, el);
    this.modes = ['WFM'];
    this.enabled = false;
    this.timeout = false;
    this.clear();
}

WfmMetaPanel.prototype = new MetaPanel();

WfmMetaPanel.prototype.update = function(data) {
    if (!this.isSupported(data)) return;
    var me = this;

    // automatically clear metadata panel when no RDS data is received for more than ten seconds
    if (this.timeout) clearTimeout(this.timeout);
    this.timeout = setTimeout(function(){
        me.clear();
    }, 10000);

    if ('pi' in data && data.pi !== this.pi) {
        this.clear();
        this.pi = data.pi;
    }

    var $el = $(this.el);

    if ('ps' in data) {
        this.ps = data.ps;
    }

    if ('prog_type' in data) {
        $el.find('.rds-prog_type').text(data['prog_type']);
    }

    if ('callsign' in data) {
        this.callsign = data.callsign;
    } else if ('callsign_uncertain' in data) {
        this.callsign = data.callsign_uncertain + '?';
    }

    if ('pi' in data) {
        this.pi = data.pi
    }

    if ('clock_time' in data) {
        var date = new Date(Date.parse(data.clock_time));
        $el.find('.rds-clock').text(date.toLocaleString([], {dateStyle: 'short', timeStyle: 'short'}));
    }

    if ('radiotext_plus' in data) {
        // prefer displaying radiotext plus over radiotext
        this.radiotext_plus = this.radiotext_plus || {
            item_toggle: -1,
            news: []
        };

        var tags = {};
        if ('tags' in data.radiotext_plus) {
            tags = Object.fromEntries(data.radiotext_plus.tags.map(function (tag) {
                return [tag['content-type'], tag['data']]
            }));
        }

        if (data.radiotext_plus.item_toggle !== this.radiotext_plus.item_toggle) {
            this.radiotext_plus.item_toggle = data.radiotext_plus.item_toggle;
            this.radiotext_plus.item = '';
        }

        this.radiotext_plus.item_running = !!data.radiotext_plus.item_running;

        if ('item.artist' in tags && 'item.title' in tags) {
            this.radiotext_plus.item = tags['item.artist'] + ' - ' + tags['item.title'];
        } else {
            var items = Object.entries(tags).filter(function (e) {
                return e[0].startsWith("item.")
            })
            if (items.length) {
                this.radiotext_plus.item = items.map(function (e) {
                    return e[0].substr(5, 1).toUpperCase() + e[0].substr(6) + ': ' + e[1];
                }).join('; ');
            }
        }

        if ('programme.now' in tags) {
            this.radiotext_plus.programme = tags['programme.now'];
        }

        if ('programme.homepage' in tags) {
            this.radiotext_plus.homepage = tags['programme.homepage'];
        }

        if ('stationname.long' in tags) {
            this.long_stationname = tags['stationname.long'];
        }

        if ('stationname.short' in tags) {
            this.short_stationname = tags['stationname.short'];
        }

        if ('info.news' in tags) {
            var n = tags['info.news'];
            var i = this.radiotext_plus.news.indexOf(n);
            if (i >= 0) {
                this.radiotext_plus.news.splice(i, 1);
            }
            this.radiotext_plus.news.push(n);
            // limit the number of items
            this.radiotext_plus.news = this.radiotext_plus.news.slice(-5);
        }

        if ('info.weather' in tags) {
            this.radiotext_plus.weather = tags['info.weather'];
        }
    }

    if ('radiotext' in data && !this.radiotext_plus) {
        this.radiotext = data.radiotext;
    }

    if (this.radiotext_plus) {
        $el.find('.rds-radiotext').empty();
        if (this.radiotext_plus.item_running) {
            $el.find('.rds-rtplus-item').text(this.radiotext_plus.item || '');
        } else {
            $el.find('.rds-rtplus-item').empty();
        }
        $el.find('.rds-rtplus-programme').text(this.radiotext_plus.programme || '');
        $el.find('.rds-rtplus-news').empty().html(this.radiotext_plus.news.map(function(n){
            return $('<li>').text(n);
        }));
        $el.find('.rds-rtplus-weather').text(this.radiotext_plus.weather || '');
        if (this.radiotext_plus.homepage) {
            var url = this.radiotext_plus.homepage;
            // prefix with a protcol if not present. we'll assume https, should be generally available these days.
            if (url.indexOf('://') < 0) url = 'https://' + url;
            // avoid updating the link if not necessary since that would prevent the user from clicking it
            if ($el.find('.rds-rtplus-homepage a').attr('href') !== url) {
                var link = $('<a href="' + url + '" target="_blank"></a>').text(this.radiotext_plus.homepage);
                $el.find('.rds-rtplus-homepage').html(link);
            }
        }
    } else {
        $el.find('.rds-radiotext-plus .autoclear').empty();
        $el.find('.rds-radiotext').text(this.radiotext || '');
    }

    $el.find('.rds-stationname').text(this.long_stationname || this.ps);
    $el.find('.rds-callsign').text(this.short_stationname || this.callsign);
    $el.find('.rds-identifier').text('PI:' + this.pi);
};

WfmMetaPanel.prototype.isSupported = function(data) {
    return this.modes.includes(data.mode);
};

WfmMetaPanel.prototype.setEnabled = function(enabled) {
    if (enabled === this.enabled) return;
    this.enabled = enabled;
    if (enabled) {
        $(this.el).removeClass('disabled').html(
            '<div class="rds-container">' +
                '<div class="rds-top-line">' +
                    '<span class="rds-callsign rds-autoclear"></span>' +
                    '<span class="rds-identifier rds-autoclear"></span>' +
                '</div>' +
                '<div class="rds-stationname rds-autoclear"></div>' +
                '<div class="rds-radiotext rds-autoclear"></div>' +
                '<div class="rds-radiotext-plus">' +
                    '<div class="rds-rtplus-programme rds-autoclear"></div>' +
                    '<div class="rds-rtplus-item rds-autoclear"></div>' +
                    '<ul class="rds-rtplus-news rds-autoclear"></ul>' +
                    '<div class="rds-rtplus-weather rds-autoclear"></div>' +
                    '<div class="rds-rtplus-homepage rds-autoclear"></div>' +
                '</div>' +
                '<div class="rds-bottom-line">' +
                    '<span class="rds-prog_type rds-autoclear"></span>' +
                    '<span class="rds-clock rds-autoclear"></span>' +
                '</div>' +
            '</div>'
        );
    } else {
        $(this.el).addClass('disabled').emtpy()
    }
};

WfmMetaPanel.prototype.clear = function() {
    $(this.el).find('.rds-autoclear').empty();
    this.pi = '';
    this.ps = '';
    this.callsign = '';
    this.long_stationname = '';
    this.short_stationname = '';

    this.radiotext = '';
    this.radiotext_plus = false;
};

function HdrMetaPanel(el) {
    MetaPanel.call(this, el);
    this.modes = ['HDR'];
    this.frequency = -1;

    // Create info panel
    var $container = $(
        '<div class="hdr-container">' +
            '<div class="hdr-top-line">' +
                '<select id="hdr-program-id" class="hdr-selector"></select>' +
                '<span class="hdr-identifier"></span>' +
            '</div>' +
            '<div class="hdr-station"></div>' +
            '<div class="hdr-message"></div>' +
            '<div id="hdr-logo" class="hdr-image"></div>' +
            '<div class="hdr-title"></div>' +
            '<div class="hdr-artist"></div>' +
            '<div class="hdr-album"></div>' +
            '<div class="hdr-bottom-line">' +
                '<span class="hdr-genre"></span>' +
            '</div>' +
        '</div>'
    );

    $(this.el).append($container);

    var $select = $('#hdr-program-id');
    $select.hide();
    $select.on("change", function() {
        var id = parseInt($(this).val());
        UI.getDemodulator().setAudioServiceId(id);
    });
}

HdrMetaPanel.prototype = new MetaPanel();

HdrMetaPanel.prototype.update = function(data) {
    if (!this.isSupported(data)) return;

    // If there is an image, display it and do not parse further
    if ('image' in data && 'data' in data) {
        $('#hdr-logo').html(
            '<img src="data:image/png;base64,' + data.data + '">'
        );
        return;
    }

    // Clear logo image when frequency changes
    if (data.frequency != this.frequency) {
        this.frequency = data.frequency;
        $('#hdr-logo').html('');
    }

    // Convert FCC ID to hexadecimal
    var fcc_id = '';
    if ('fcc_id' in data) {
        fcc_id = data.fcc_id.toString(16).toUpperCase();
        fcc_id = '0x' + ('0000' + fcc_id).slice(-4);
        fcc_id = ('country' in data?  data.country + ':' : '') + fcc_id;
    }

    // Update panel
    var $el = $(this.el);
    $el.find('.hdr-identifier').text(fcc_id);
    $el.find('.hdr-station').text(data.station || '');
    $el.find('.hdr-message').text(data.alert || data.message || data.slogan || '');
    $el.find('.hdr-title').text(data.title || '');
    $el.find('.hdr-artist').text(data.artist || '');
    $el.find('.hdr-genre').text(data.genre || '');
    $el.find('.hdr-album').text(data.album || '');

    // Update program selector
    var $select = $('#hdr-program-id');
    if (data.audio_services && data.audio_services.length) {
        $select.html(data.audio_services.map(function(pgm) {
            var selected = data.program == pgm.id? ' selected' : '';
            return '<option value="' + pgm.id + '"' + selected + '>P' +
                (pgm.id + 1) + ' - ' + pgm.name + '</option>';
        }).join());
        $select.show();
    } else {
        $select.html('');
        $select.hide();
    }
};

HdrMetaPanel.prototype.isSupported = function(data) {
    return this.modes.includes(data.mode);
};

function DabMetaPanel(el) {
    MetaPanel.call(this, el);
    var me = this;
    this.modes = ['DAB'];
    this.service_id = 0;
    this.$select = $('<select id="dab-service-id"></select>');
    this.$select.on("change", function() {
        me.service_id = parseInt($(this).val());
        UI.getDemodulator().setAudioServiceId(me.service_id);
    });
    var $container = $(
        '<div class="dab-container">' +
            '<div class="dab-auto-clear dab-ensemble-id"></div>' +
            '<div class="dab-auto-clear dab-ensemble-label"></div>' +
            '<div class="dab-auto-clear dab-timestamp"></div>' +
            '<label for="dab-service-id">DAB Programme:</label>' +
        '</div>'
    );
    $container.append(this.$select);
    $(this.el).append($container);
    this.clear();
    this.programmeTimeout = false;
};

DabMetaPanel.prototype = new MetaPanel();

DabMetaPanel.prototype.isSupported = function(data) {
    return this.modes.includes(data.mode);
};

DabMetaPanel.prototype.update = function(data) {
    if (!this.isSupported(data)) return;

    if ('ensemble_id' in data) {
        $(this.el).find('.dab-ensemble-id').text('0x' + data.ensemble_id.toString(16));
    }

    if ('ensemble_label' in data) {
        $(this.el).find('.dab-ensemble-label').text(data.ensemble_label);
    }

    if ('timestamp' in data) {
        var date = new Date(data.timestamp * 1000);
        $(this.el).find('.dab-timestamp').text(date.toLocaleString([], {dateStyle: 'short', timeStyle: 'medium'}));
    }

    if ('programmes' in data) {
        var options = Object.entries(data.programmes).map(function(e) {
            return '<option value="' + e[0] + '">' + e[1] + '</option>';
        });
        this.$select.html(
            options.join('') +
            '<option value="" disabled selected hidden>Loading...</option>'
        );

        var me = this;
        if (this.programmeTimeout) clearTimeout(this.programmeTimeout);
        this.programmeTimeout = setTimeout(function() {
            // user has selected a programme to play. don't interfere.
            me.$select.val(this.service_id);
            if (me.$select.val()) return;
            me.$select.val(me.$select.find('option:first').val()).change();
        }, 1000);
    }
};

DabMetaPanel.prototype.clear = function() {
    this.service_id = 0;
    $(this.el).find('.dab-auto-clear').empty();
    this.$select.html(
        '<option value="" disabled selected hidden>Loading...</option>'
    );
};

function DrmMetaPanel(el) {
    MetaPanel.call(this, el);
    this.modes = ['DRM'];
    this.frequency = -1;

    // Create info panel
    var $container = $(
        '<div class="drm-container">' +
            '<div class="drm-line">' +
                '<span class="drm-indicator drm-io">IO</span>' +
                '<span class="drm-indicator drm-time">Time</span>' +
                '<span class="drm-indicator drm-frame">Frame</span>' +
                '<span class="drm-indicator drm-fac">FAC</span>' +
                '<span class="drm-indicator drm-sdc">SDC</span>' +
                '<span class="drm-indicator drm-msc">MSC</span>' +
            '</div>' +
            '<div class="drm-separator">' +
                '<span class="drm-left">IF Level</span>' +
                '<span class="drm-right drm-if"></span>' +
                '<span class="drm-left">SNR</span>' +
                '<span class="drm-right drm-snr"></span>' +
            '</div>' +
            '<div class="drm-line">' +
                '<span class="drm-left">Mode</span>' +
                '<span class="drm-right drm-mode"></span>' +
                '<span class="drm-left">Channel</span>' +
                '<span class="drm-right drm-channel"></span>' +
            '</div>' +
            '<div class="drm-line">' +
                '<span class="drm-left">SDC</span>' +
                '<span class="drm-right drm-sdc-qam"></span>' +
                '<span class="drm-left">MSC</span>' +
                '<span class="drm-right drm-msc-qam"></span>' +
            '</div>' +
            '<div class="drm-line">' +
                '<span class="drm-left">ILV</span>' +
                '<span class="drm-right drm-ilv"></span>' +
                '<span class="drm-left">Protect</span>' +
                '<span class="drm-right">' +
                  '<span class="drm-indicator drm-prot-a">A</span>' +
                  '<span class="drm-indicator drm-prot-b">B</span>' +
                '</span>' +
            '</div>' +
            '<div class="drm-separator">' +
                '<span class="drm-audio drm-indicator">Audio</span>' +
                '<span class="drm-data drm-indicator">Data</span>' +
                '<span class="drm-indicator drm-guide">Guide</span>' +
                '<span class="drm-indicator drm-journaline">Journaline</span>' +
                '<span class="drm-indicator drm-slideshow">Slideshow</span>' +
            '</div>' +
            '<div class="drm-line drm-programs">' +
            '</div>' +
        '</div>'
    );

    $(this.el).append($container);
};

DrmMetaPanel.prototype = new MetaPanel();

DrmMetaPanel.prototype.update = function(data) {
    if (!this.isSupported(data)) return;

    // Update panel
    var $el = $(this.el);
    this.setIndicator('io', data.status.io);
    this.setIndicator('time', data.status.time);
    this.setIndicator('frame', data.status.frame);
    this.setIndicator('fac', data.status.fac);
    this.setIndicator('sdc', data.status.sdc);
    this.setIndicator('msc', data.status.msc);

    this.setIndicator('guide', data.media.program_guide);
    this.setIndicator('journaline', data.media.journaline);
    this.setIndicator('slideshow', data.media.slideshow);

    this.setIndicator('prot-a', data.coding && data.coding.protection_a > 0? 1:0);
    this.setIndicator('prot-b', data.coding && data.coding.protection_b > 0? 1:0);
    this.setIndicator('audio', data.services && data.services.audio > 0? 1:0);
    this.setIndicator('data', data.services && data.services.data > 0? 1:0);

    this.setText('if', '' + data.signal.if_level_db + 'dB');
    this.setText('snr', '' + data.signal.snr_db + 'dB');

    if (data.drm_mode) {
        var mode = ['A', 'B', 'C', 'D'][data.drm_mode.robustness] || '?';
        var bw = ['4.5kHz', '5kHz', '9kHz', '10kHz', '18kHz', '20kHz'][data.drm_mode.bandwidth] || '?';
        var ilv = ['Short', 'Long'][data.drm_mode.interleaver] || '?';
        this.setText('mode', mode);
        this.setText('channel', bw);
        this.setText('ilv', 'ilv');
    } else {
        this.setText('mode', '-');
        this.setText('channel', '-');
        this.setText('ilv', '-');
    }

    if (data.coding) {
        var sdc = ['4-QAM', '16-QAM'][data.coding.sdc_qam] || '?';
        var msc = ['16-QAM', '64-QAM'][data.coding.msc_qam] || '?';
        this.setText('sdc-qam', sdc);
        this.setText('msc-qam', msc);
    } else {
        this.setText('sdc-qam', '-');
        this.setText('msc-qam', '-');
    }

    var programs = '';
    if (data.service_list) {
        programs += '';
        for (var j = 0 ; j < data.service_list.length ; j++) {
            var entry = data.service_list[j];
            var codec = ['AAC', 'OPUS', 'RESERVED', 'xHE-AAC'][entry.audio_coding] || 'UNKNOWN';
            var country = entry.country? entry.country.name : '';
            var language = entry.language? entry.language.name : '';
            var id = parseInt(entry.id).toString(16).toUpperCase();
            var type = entry.is_audio? entry.audio_mode.toUpperCase() : 'DATA';

            programs +=
                '<div class="drm-program">' +
                    '<div style="color:yellow;"><b>' + entry.label + '</b> (' + id + ')</div>' +
                    '<div>' +
                        '<span class="drm-label">Type:&nbsp;</span>' +
                        '<span class="drm-value">' + type + '</span>' +
                        ' | <span class="drm-label">Codec:&nbsp;</span>' +
                        '<span class="drm-value">' + codec + '</span>' +
                        ' | <span class="drm-label">Bitrate:&nbsp;</span>' +
                        '<span class="drm-value">' + entry.bitrate_kbps + ' kbps</span>' +
                        ' | <span class="drm-label">Protection:&nbsp;</span>' +
                        '<span class="drm-value">' + entry.protection_mode + '</span>';

            if (entry.country) {
                programs +=
                        ' | <span class="drm-label">Country:&nbsp;</span>' +
                        '<span class="drm-value">' + entry.country.name + '</span>';

            }

            if (entry.language) {
                programs +=
                        ' | <span class="drm-label">Language:&nbsp;</span>' +
                        '<span class="drm-value">' + entry.language.name + '</span>';

            }

            programs += '</div></div>';
        }
    }

    $el.find('.drm-programs').html(programs);
};

DrmMetaPanel.prototype.isSupported = function(data) {
    return this.modes.includes(data.mode);
};

DrmMetaPanel.prototype.setText = function(name, text) {
    $(this.el).find('.drm-' + name).text(text);
};

DrmMetaPanel.prototype.setIndicator = function(name, value, text = null) {
    var $el = $(this.el).find('.drm-' + name);

    // Remove all color
    $el.removeClass('drm-error');
    $el.removeClass('drm-off');
    $el.removeClass('drm-on');

    // Set new color based on the value
    if (value > 0) {
        $el.addClass('drm-on');
    } else if (value == 0) {
        $el.addClass('drm-off');
    } else {
        $el.addClass('drm-error');
    }

    // Set new text, if given
    if (text != null) $el.text(text);
};

MetaPanel.types = {
    dmr: DmrMetaPanel,
    ysf: YsfMetaPanel,
    dstar: DStarMetaPanel,
    nxdn: NxdnMetaPanel,
    m17: M17MetaPanel,
    wfm: WfmMetaPanel,
    dab: DabMetaPanel,
    hdr: HdrMetaPanel,
    drm: DrmMetaPanel
};

$.fn.metaPanel = function() {
    return this.map(function() {
        var $self = $(this);
        if (!$self.data('metapanel')) {
            var matches = /^openwebrx-panel-metadata-([a-z0-9]+)$/.exec($self.prop('id'));
            var constructor = matches && MetaPanel.types[matches[1]] || MetaPanel;
            $self.data('metapanel', new constructor($self));
        }
        return $self.data('metapanel');
    });
};
