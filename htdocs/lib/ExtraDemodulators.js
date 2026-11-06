//
// Additional audio-only demodulators, running alongside the main one
// (server-side demodulator ids 1 and up)
//

function ExtraDemodulator(id, offset_frequency, modulation) {
    var self = this;
    this.id = id;
    this.color = ExtraDemodulators.getColor(id);

    this.demodulator = new Demodulator(offset_frequency, modulation);
    this.demodulator.id = id;
    this.demodulator.envelope.color = this.color;

    this.audio = audioEngine.createChannel();

    this.el = this.render();
    $('#openwebrx-extra-demods').append(this.el);

    var displayEl = this.el.find('.webrx-actual-freq');
    this.frequencyDisplay = displayEl.tuneableFrequencyDisplay();
    displayEl.on('frequencychange', function(event, freq) {
        self.demodulator.set_offset_frequency(freq - center_freq - self.getCwDelta());
    });
    this.demodulator.on('frequencychange', function() { self.updateFrequency(); });

    this.el.on('change', '.openwebrx-extra-demod-mode', function() {
        self.setModulation($(this).val());
    });
    this.el.on('click', '.openwebrx-extra-demod-squelch-icon', function() {
        self.autoSquelch();
    });
    this.el.on('input change', '.openwebrx-squelch-slider', function() {
        self.demodulator.setSquelch(parseInt($(this).val()));
    });
    this.el.on('input change', '.openwebrx-extra-demod-volume', function() {
        self.setVolume($(this).val());
    });
    this.el.on('click', '.openwebrx-extra-demod-mute', function() {
        self.toggleMute();
    });
    this.el.on('click', '.openwebrx-extra-demod-close', function() {
        ExtraDemodulators.remove(self.id);
    });

    this.volume = 100;
    this.setVolume(this.volume);
    this.updateModeControls();
    this.updateFrequency();
    this.demodulator.start();
}

ExtraDemodulator.prototype.render = function() {
    var modulation = this.demodulator.get_modulation();
    var options = ExtraDemodulators.getAvailableModes().map(function(m) {
        return '<option value="' + m.modulation + '"' + (m.modulation === modulation ? ' selected' : '') + '>' +
            m.name + '</option>';
    }).join('');

    return $(
        '<div class="openwebrx-extra-demod" style="border-left-color: ' + this.color + ';">' +
            '<div class="openwebrx-panel-line openwebrx-panel-flex-line openwebrx-extra-demod-header">' +
                '<span class="openwebrx-extra-demod-label" style="color: ' + this.color + ';">#' + this.id + '</span>' +
                '<div class="webrx-actual-freq"></div>' +
                '<div title="Remove demodulator" class="openwebrx-button openwebrx-extra-demod-close">&times;</div>' +
            '</div>' +
            '<div class="openwebrx-panel-line openwebrx-panel-flex-line">' +
                '<select class="openwebrx-extra-demod-mode" title="Mode">' + options + '</select>' +
                '<span class="openwebrx-extra-demod-level" title="Signal level"></span>' +
            '</div>' +
            '<div class="openwebrx-panel-line openwebrx-panel-flex-line">' +
                '<div title="Mute on/off" class="openwebrx-button openwebrx-slider-button openwebrx-extra-demod-mute">' +
                    '<svg class="unmuted" viewBox="0 0 80 80"><use xlink:href="static/gfx/svg-defs.svg#speaker"></use></svg>' +
                    '<svg class="muted" viewBox="0 0 80 80"><use xlink:href="static/gfx/svg-defs.svg#speaker-muted"></use></svg>' +
                '</div>' +
                '<input title="Volume" class="openwebrx-panel-slider openwebrx-extra-demod-volume" type="range" min="0" max="150" value="100" step="1">' +
            '</div>' +
            '<div class="openwebrx-panel-line openwebrx-panel-flex-line">' +
                '<div title="Auto-set squelch level" class="openwebrx-button openwebrx-slider-button openwebrx-extra-demod-squelch-icon">' +
                    '<svg viewBox="0 0 80 80"><use xlink:href="static/gfx/svg-defs.svg#squelch"></use></svg>' +
                '</div>' +
                '<input title="Squelch" class="openwebrx-squelch-slider openwebrx-panel-slider" type="range" min="-150" max="0" value="' + this.demodulator.getSquelch() + '" step="1">' +
            '</div>' +
        '</div>'
    );
};

// volume on the same 0-150 scale as the main volume slider
ExtraDemodulator.prototype.setVolume = function(x) {
    this.volume = Math.min(150, Math.max(0, Math.round(parseFloat(x))));
    this.audio.setVolume(UI.volumeToGain(this.volume));
};

// like the main panel: muting drops the slider to 0 and locks it, unmuting restores the previous volume
ExtraDemodulator.prototype.toggleMute = function() {
    var muted = !this.audio.isMuted();
    this.audio.setMuted(muted);
    this.el.find('.openwebrx-extra-demod-mute')[muted ? 'addClass' : 'removeClass']('muted');
    this.el.find('.openwebrx-extra-demod-volume')
        .val(muted ? 0 : this.volume)
        .prop('disabled', muted);
};

ExtraDemodulator.prototype.getCwDelta = function() {
    return this.demodulator.get_modulation() === 'cw' ? UI.getCwOffset() : 0;
};

ExtraDemodulator.prototype.getFrequency = function() {
    return center_freq + this.demodulator.get_offset_frequency();
};

ExtraDemodulator.prototype.updateFrequency = function() {
    this.frequencyDisplay.setFrequency(this.getFrequency() + this.getCwDelta());
};

ExtraDemodulator.prototype.setModulation = function(modulation) {
    var demod = this.demodulator;
    var mode = Modes.findByModulation(modulation);
    if (!mode || demod.get_modulation() === modulation) return;

    demod.modulation = modulation;
    demod.ifRate = mode.ifRate;
    demod.filter = new Filter(demod);
    var bp = UI.loadBandpass(modulation) || (modulation === 'cw' ? UI.getCwBandpass() : mode.bandpass);
    if (bp) {
        demod.setBandpass(bp);
    } else {
        demod.disableBandpass();
    }

    this.updateModeControls();
    this.updateFrequency();
};

ExtraDemodulator.prototype.updateModeControls = function() {
    var squelch = this.squelchAvailable();
    this.el.find('.openwebrx-squelch-slider').prop('disabled', !squelch);
    this.el.find('.openwebrx-extra-demod-squelch-icon')[squelch ? 'removeClass' : 'addClass']('disabled');
};

ExtraDemodulator.prototype.squelchAvailable = function() {
    var mode = Modes.findByModulation(this.demodulator.get_modulation());
    return !!(mode && mode.squelch);
};

// same as the main panel: put the squelch just above the current signal level
ExtraDemodulator.prototype.autoSquelch = function() {
    if (!this.squelchAvailable() || this.levelDb === undefined) return;
    var $slider = this.el.find('.openwebrx-squelch-slider');
    var level = Math.round(this.levelDb + UI.getDemodulatorPanel().getSquelchMargin());
    level = Math.min(Math.max(level, Number($slider.attr('min'))), Number($slider.attr('max')));
    $slider.val(level);
    this.demodulator.setSquelch(level);
    setSquelchSliderBackground(this.levelDb, $slider);
};

ExtraDemodulator.prototype.setLevel = function(level) {
    var db = getLogSmeterValue(level);
    if (isFinite(db)) this.levelDb = db;
    this.el.find('.openwebrx-extra-demod-level').text(isFinite(db) ? Math.round(db) + ' dB' : '');
    if (isFinite(db)) setSquelchSliderBackground(db, this.el.find('.openwebrx-squelch-slider'));
};

ExtraDemodulator.prototype.setTuningPrecision = function(precision) {
    this.frequencyDisplay.setTuningPrecision(precision);
};

ExtraDemodulator.prototype.destroy = function(notifyServer) {
    if (notifyServer) this.demodulator.stop();
    this.demodulator.started = false;
    this.audio.close();
    this.el.remove();
};


var ExtraDemodulators = {
    // the server-side limit, counting the main demodulator
    maxDemodulators: 1,
    items: {},
    centerFrequency: null,
    tuningPrecision: null,

    // modes without secondary demodulators or metadata, since those would need the global panels
    supportedModes: ['nfm', 'am', 'sam', 'lsb', 'usb', 'cw', 'wfm'],

    getColor: function(id) {
        // the main demodulator uses the first color
        var colors = Demodulator.colors.slice(1);
        return colors[(id - 1) % colors.length];
    },

    getAvailableModes: function() {
        var supported = this.supportedModes;
        return Modes.getModes().filter(function(m) {
            return supported.indexOf(m.modulation) >= 0;
        });
    },

    getDemodulators: function() {
        var items = this.items;
        return Object.keys(items).sort(function(a, b) { return a - b; }).map(function(id) {
            return items[id].demodulator;
        });
    },

    count: function() {
        return Object.keys(this.items).length;
    },

    canAdd: function() {
        // +1 for the main demodulator
        return this.count() + 1 < this.maxDemodulators;
    },

    nextId: function() {
        var id = 1;
        while (id in this.items) id++;
        return id;
    },

    add: function() {
        var main = UI.getDemodulator();
        var modes = this.getAvailableModes();
        if (!this.canAdd() || !main || !bandwidth || !modes.length) return null;

        // start next to the main demodulator, so the envelopes don't overlap
        var bp = main.getBandpass();
        var width = (bp.low_cut !== null && bp.high_cut !== null) ? Math.abs(bp.high_cut - bp.low_cut) : 10000;
        var step = Math.max(width * 2, 5000) * (this.count() + 1);
        var offset = main.get_offset_frequency() + step;
        if (offset > bandwidth / 2) offset = main.get_offset_frequency() - step;
        if (offset < -bandwidth / 2) offset = 0;

        var modulation = main.get_modulation();
        if (!modes.some(function(m) { return m.modulation === modulation; })) modulation = modes[0].modulation;

        var id = this.nextId();
        var item = new ExtraDemodulator(id, offset, modulation);
        if (this.tuningPrecision !== null) item.setTuningPrecision(this.tuningPrecision);
        this.items[id] = item;
        this.update();
        return item;
    },

    remove: function(id, notifyServer) {
        var item = this.items[id];
        if (!item) return;
        delete this.items[id];
        item.destroy(notifyServer !== false);
        this.update();
    },

    removeAll: function(notifyServer) {
        var self = this;
        Object.keys(this.items).forEach(function(id) {
            self.remove(id, notifyServer);
        });
    },

    // redraw envelopes, panel visibility and the add button state
    update: function() {
        toggle_panel('openwebrx-panel-extra-demods', this.count() > 0);
        $('.openwebrx-add-demod-button')
            .css('display', this.maxDemodulators > 1 ? '' : 'none')
            .toggleClass('disabled', !this.canAdd());
        var range = get_visible_freq_range();
        if (range) mkenvelopes(range);
    },

    configure: function(config) {
        if ('max_demodulators_per_client' in config) {
            this.maxDemodulators = config['max_demodulators_per_client'];
            this.update();
        }
        if ('tuning_precision' in config) {
            var precision = this.tuningPrecision = config['tuning_precision'];
            $.each(this.items, function(id, item) { item.setTuningPrecision(precision); });
        }
    },

    // demodulator offsets are relative to the center frequency, so keep them on their absolute frequency
    setCenterFrequency: function(freq) {
        var previous = this.centerFrequency;
        this.centerFrequency = freq;
        if (previous === null || previous === freq) return;
        var self = this;
        $.each($.extend({}, this.items), function(id, item) {
            var offset = previous + item.demodulator.get_offset_frequency() - freq;
            if (Math.abs(offset) > bandwidth / 2) {
                self.remove(id);
            } else {
                item.demodulator.set_offset_frequency(offset);
                item.updateFrequency();
            }
        });
    },

    handleMessage: function(json) {
        var item = this.items[json.demod];
        switch (json.type) {
            case 'smeter':
                if (item) item.setLevel(json.value);
                break;
            case 'demodulator_error':
                divlog('Demodulator #' + json.demod + ': ' + json.value, true);
                this.remove(json.demod);
                break;
            default:
                // secondary demodulator output and metadata are not supported for additional demodulators
                break;
        }
    },

    pushAudio: function(id, data, hd) {
        var item = this.items[id];
        if (item) item.audio.push(data, hd);
    }
};
