//
// User Interface functions
//

function UI() {}

// We start with these values
UI.theme = 'default';
UI.wfTheme = null;
UI.frame = false;
UI.opacity = 100;
UI.volume = -1;
UI.volumeMuted = -1;
UI.nrThreshold = -20;
UI.nrEnabled = false;
UI.wheelSwap = false;
UI.spectrum = false;
UI.bandplan = false;

// Foldable UI sections and their initial states
UI.sections = {
    'modes'   : true,
    'controls': true,
    'settings': false,
    'display' : true
};

// Load UI settings from local storage.
UI.loadSettings = function() {
    this.setTheme(LS.has('ui_theme')? LS.loadStr('ui_theme') : 'default');
    this.setOpacity(LS.has('ui_opacity')? LS.loadInt('ui_opacity') : 100);
    this.toggleFrame(LS.has('ui_frame')? LS.loadBool('ui_frame') : false);
    this.toggleWheelSwap(LS.has('ui_wheel')? LS.loadBool('ui_wheel') : false);
    this.toggleSpectrum(LS.has('ui_spectrum')? LS.loadBool('ui_spectrum') : false);
    this.toggleBandplan(LS.has('ui_bandplan')? LS.loadBool('ui_bandplan') : false);
    this.setWfTheme(LS.has('wf_theme')? LS.loadStr('wf_theme') : 'default');
    this.setNR(LS.has('nr_threshold')? LS.loadInt('nr_threshold') : 0);
    this.toggleNR(LS.has('nr_enabled')? LS.loadBool('nr_enabled') : false);

    // Toggle UI sections
    for (section in this.sections) {
        var id = 'openwebrx-section-' + section;
        var el = document.getElementById(id);
        if (el) this.toggleSection(el,
            LS.has(id)? LS.loadBool(id) : this.sections[section]
        );
    }
};

// Load audio settings from local storage.
UI.loadAudioSettings = function() {
    // Must have running audio engine
    if (!audioEngine.isStarted()) return;

    // Get volume and mute
    var volume = LS.has('volume')? LS.loadInt('volume') : 100;
    var muted  = LS.has('volumeMuted')? LS.loadInt('volumeMuted') : -1;
    if (muted >= 0) {
        if (this.volumeMuted >= 0) {
            this.volumeMuted = muted;
        } else {
            this.volume = muted;
            this.toggleMute(true);
        }
    } else {
        if (this.volumeMuted < 0) {
            this.setVolume(volume);
        } else {
            this.volumeMuted = volume;
            this.toggleMute(false);
        }
    }
}

//
// Modulation Controls
//

UI.getDemodulatorPanel = function() {
    return $('#openwebrx-panel-receiver').demodulatorPanel();
};

UI.getDemodulator = function() {
    return this.getDemodulatorPanel().getDemodulator();
}

UI.getModulation = function() {
    var mode1 = this.getDemodulator().get_secondary_demod();
    var mode2 = this.getDemodulator().get_modulation();
    return !!mode1? mode1 : !mode2? '' : mode2;
};

UI.getUnderlying = function() {
    var mode1 = this.getDemodulator().get_secondary_demod();
    var mode2 = this.getDemodulator().get_modulation();
    return !mode1? '' : !mode2? '' : mode2;
};

UI.setModulation = function(mode, underlying) {
    this.getDemodulatorPanel().setMode(mode, underlying);
};

//
// Frequency Controls
//

UI.getOffsetFrequency = function(x) {
    if (typeof(x) === 'undefined') {
        // No argument: return currently tuned offset
        return this.getDemodulator().get_offset_frequency();
    } else {
        // Pointer position: return offset under pointer
        // Use rounded absolute frequency to get offset
        return this.getFrequency(x) - center_freq;
    }
};

UI.getFrequency = function(x) {
    if (typeof(x) === 'undefined') {
        // No argument: return currently tuned frequency
        return center_freq + this.getOffsetFrequency();
    } else {
        // Pointer position: return frequency under pointer
        x = x / canvas_container.clientWidth;
        x = center_freq + (bandwidth * x) - (bandwidth / 2);
        return tuning_step>0?
            Math.round(x / tuning_step) * tuning_step : Math.round(x);
    }
};

UI.setOffsetFrequency = function(offset) {
    return this.getDemodulator().set_offset_frequency(offset);
};

UI.setFrequency = function(freq) {
    return this.setOffsetFrequency(freq - center_freq);
};

UI.tuneBookmark = function(b) {
    // Bookmark must have frequency and modulation
    if (!b || !b.frequency || !b.modulation) return false;

    //console.log("TUNE: " + b.name + " at " + b.frequency + ": " + b.modulation);

    // Tune to the bookmark frequency
    var freq = b.modulation === 'cw'? b.frequency - 800 : b.frequency;
    UI.setFrequency(freq, b.modulation);
    UI.setModulation(b.modulation, b.underlying);

    // Done
    return true;
};

//
// Volume Controls
//

// Set audio volume in 0..150 range.
UI.setVolume = function(x) {
    // Must have running audio engine
    if (!audioEngine.isStarted()) return;

    x = Math.min(150, Math.max(0, Math.round(parseFloat(x))));
    if (this.volume != x) {
        this.volume = x;
        LS.save('volume', x);
        $('#openwebrx-panel-volume').val(x)
        if (audioEngine) {
            // Map 0-150 to -55..+5db gain
            gain = x > 0? Math.pow(10, ((x / 2.5) - 55) / 20) : 0;
            audioEngine.setVolume(gain);
        }
    }
};

// Toggle audio muting.
UI.toggleMute = function(on) {
    // Must have running audio engine
    if (!audioEngine.isStarted()) return;

    // If no argument given, toggle mute
    var toggle = typeof(on) === 'undefined';
    var $muteButton = $('.openwebrx-mute-button');
    var $volumePanel = $('#openwebrx-panel-volume');

    if ((this.volumeMuted >= 0) && (toggle || !on)) {
        this.setVolume(this.volumeMuted);
        this.volumeMuted = -1;
        $muteButton.removeClass('muted');
        $volumePanel.prop('disabled', false);
        LS.save('volumeMuted', this.volumeMuted);
    } else if (toggle || on) {
        this.volumeMuted = this.volume;
        this.setVolume(0);
        $muteButton.addClass('muted');
        $volumePanel.prop('disabled', true);
        LS.save('volumeMuted', this.volumeMuted);
    }
};

//
// Noise Reduction Controls
//

// Set noise reduction threshold in decibels.
UI.setNR = function(x) {
    x = Math.round(parseFloat(x));
    if (this.nrThreshold != x) {
        this.nrThreshold = x;
        LS.save('nr_threshold', x);
        $('#openwebrx-panel-nr').attr('title', 'Noise reduction level (' + x + ' dB)').val(x);
        this.updateNR();
    }
};

// Toggle noise reduction function.
UI.toggleNR = function(on) {
    var $nrPanel = $('#openwebrx-panel-nr');

    // If no argument given, toggle NR
    this.nrEnabled = !!(typeof(on)==='undefined'? $nrPanel.prop('disabled') : on);

    LS.save('nr_enabled', this.nrEnabled);
    $nrPanel.prop('disabled', !this.nrEnabled);
    this.updateNR();
}

// Send changed noise reduction parameters to the server.
UI.updateNR = function() {
    ws.send(JSON.stringify({
        'type': 'connectionproperties',
        'params': {
            'nr_enabled': this.nrEnabled,
            'nr_threshold': this.nrThreshold
        }
    }));
}

//
// Audio Recording Controls
//

UI.toggleRecording = function(on) {
    // If no argument given, toggle audio recording
    var toggle = typeof(on) === 'undefined';

    var $recButton = $('.openwebrx-record-button');

    if ($recButton.is(':visible')) {
        if (audioEngine.recording && (toggle || !on)) {
            audioEngine.stopRecording();
            $recButton.css('animation-name', '');
        } else if (toggle || on) {
            audioEngine.startRecording();
            $recButton.css('animation-name', 'openwebrx-record-animation');
        }
    }
};

//
// Scanner Controls
//

UI.toggleScanner = function(on) {
    // If no argument given, toggle scanner
    if (typeof(on) === 'undefined') on = !scanner.isRunning();

    // Do not change scanner state if not needed
    if (scanner.isRunning() == on) return;

    // Start or stop scanner as needed
    if (on) scanner.start(); else scanner.stop();

    // Get current scanner state
    on = scanner.isRunning();

    // Update UI elements
    var $scanButton = $('.openwebrx-squelch-auto');
    $scanButton.css('animation-name', on? 'openwebrx-scan-animation' : '');
    if (on) {
        $scanButton.addClass('highlighted');
    } else {
        $scanButton.removeClass('highlighted');
    }
};

//
// Look & Feel Controls
//

UI.toggleSection = function(el, on) {
    // If no argument given, toggle section
    var toggle = typeof(on) === 'undefined';

    var next_el = el.nextElementSibling;
    if (next_el) {
        if ((next_el.classList.contains('closed')) && (toggle || on)) {
            el.innerHTML = el.innerHTML.replace('\u25B4', '\u25BE');
            next_el.classList.remove('closed');
            LS.save(el.id, true);
        } else if (toggle || !on) {
            el.innerHTML = el.innerHTML.replace('\u25BE', '\u25B4');
            next_el.classList.add('closed');
            LS.save(el.id, false);
        }
    }
};

// Show or hide spectrum display
UI.toggleSpectrum = function(on) {
    // If no argument given, toggle spectrum
    if (typeof(on) === 'undefined') on = !this.spectrum;

    this.spectrum = on;
    LS.save('ui_spectrum', on);
    if (spectrum) spectrum.toggle(on);
};

// Show or hide bandplan display
UI.toggleBandplan = function(on) {
    // If no argument given, toggle bandplan
    if (typeof(on) === 'undefined') on = !this.bandplan;

    if (this.bandplan != on) {
        this.bandplan = on;
        LS.save('ui_bandplan', on);
        $('#openwebrx-bandplan-checkbox').attr('checked', on);
        if (bandplan) bandplan.toggle(on);
    }
};

// Show or hide frame around receiver and other panels.
UI.toggleFrame = function(on) {
    // If no argument given, toggle frame
    if (typeof(on) === 'undefined') on = !this.frame;

    if (this.frame != on) {
        this.frame = on;
        LS.save('ui_frame', on);
        $('#openwebrx-frame-checkbox').attr('checked', on);

        var border = on ? '2px solid white' : '2px solid transparent';
        $('#openwebrx-panel-receiver').css( 'border', border);
        $('#openwebrx-dialog-bookmark').css('border', border);
//        $('#openwebrx-digimode-canvas-container').css('border', border);
//        $('.openwebrx-message-panel').css('border', border);
    }
};

// Get current mouse wheel function
UI.getWheelSwap = function() {
    return this.wheelSwap;
};

// Set mouse wheel function (zooming when swapped)
UI.toggleWheelSwap = function(on) {
    // If no argument given, toggle wheel swap
    if (typeof(on) === 'undefined') on = !this.wheelSwap;

    if (this.wheelSwap != on) {
        this.wheelSwap = on;
        LS.save('ui_wheel', on);
        $('#openwebrx-wheel-checkbox').attr('checked', on);
    }
};

// Set user interface opacity in 10..100% range.
UI.setOpacity = function(x) {
    // Limit opacity to 10..100% range
    x = x<10? 10 : x>100? 100 : x;

    if (this.opacity != x) {
        this.opacity = x;
        LS.save('ui_opacity', x);
        $('.openwebrx-panel').css('opacity', x/100);
        $('#openwebrx-opacity-slider')
            .attr('title', 'Opacity (' + Math.round(x) + '%)')
            .val(x);
    }
};

// Set user interface theme.
UI.setTheme = function(theme) {
    // Do not set twice
    if (this.theme === theme) return;

    // Save current theme name
    this.theme = theme;
    LS.save('ui_theme', theme);

    // Set selector
    var lb = $('#openwebrx-themes-listbox');
    lb.val(theme);

    // Remove existing theme
    var opts = lb[0].options;
    for(j=0 ; j<opts.length ; j++) {
        $('body').removeClass('theme-' + opts[j].value);
    }
    $('body').removeClass('has-theme');

    // Apply new theme
    if (theme && (theme != '') && (theme != 'default')) {
        $('body').addClass('theme-' + theme);
        $('body').addClass('has-theme');
    }
};

// Set waterfall color theme.
UI.setWfTheme = function(theme) {
    // Theme name must be valid
    if (!(theme in this.wfThemes)) return;

    // Do not set twice
    if (this.wfTheme === theme) return;

    // Save current theme name
    this.wfTheme = theme;
    LS.save('wf_theme', theme);

    // Set selector
    $('#openwebrx-wf-themes-listbox').val(theme);

    // Set new colors in the waterfall
    Waterfall.setTheme(this.wfThemes[theme]);
};

// Set default waterfall color theme.
UI.setDefaultWfTheme = function(colors) {
    // Update default waterfall theme with new colors
    this.wfThemes['default'] = colors;

    // If default theme currently used, update waterfall
    if (this.wfTheme === 'default') {
        this.wfTheme = null;
        this.setWfTheme('default');
    }
};

// Waterfall color themes
UI.wfThemes = {
    'default' : [0x000000, 0xFFFFFF],
    'teejeez' : [0x000000, 0x0000FF, 0x00FFFF, 0x00FF00, 0xFFFF00, 0xFF0000, 0xFF00FF, 0xFFFFFF],
    'ha7ilm'  : [0x000000, 0x2E6893, 0x69A5D0, 0x214B69, 0x9DC4E0, 0xFFF775, 0xFF8A8A, 0xB20000],
    'ocean'   : [0x000000, 0x000965, 0x00E0FF, 0x2EFF00, 0xFFEC00, 0xFF0000],
    'eclipse' : [
        0x000020, 0x000030, 0x000050, 0x000091, 0x1E90FF, 0xFFFFFF, 0xFFFF00, 0xFE6D16,
        0xFF0000, 0xC60000, 0x9F0000, 0x750000, 0x4A0000
    ],
    'turbo'   : [
        0x30123B, 0x311542, 0x33184A, 0x341B51, 0x351E58, 0x36215F, 0x372466, 0x38266C,
        0x392973, 0x3A2C79, 0x3B2F80, 0x3C3286, 0x3D358B, 0x3E3891, 0x3E3A97, 0x3F3D9C,
        0x4040A2, 0x4043A7, 0x4146AC, 0x4248B1, 0x424BB6, 0x434EBA, 0x4351BF, 0x4453C3,
        0x4456C7, 0x4559CB, 0x455BCF, 0x455ED3, 0x4561D7, 0x4663DA, 0x4666DD, 0x4669E1,
        0x466BE4, 0x466EE7, 0x4671E9, 0x4673EC, 0x4676EE, 0x4678F1, 0x467BF3, 0x467DF5,
        0x4680F7, 0x4682F9, 0x4685FA, 0x4587FC, 0x458AFD, 0x448CFE, 0x448FFE, 0x4391FF,
        0x4294FF, 0x4196FF, 0x3F99FF, 0x3E9BFF, 0x3D9EFE, 0x3BA1FD, 0x3AA3FD, 0x38A6FB,
        0x36A8FA, 0x35ABF9, 0x33ADF7, 0x31B0F6, 0x2FB2F4, 0x2DB5F2, 0x2CB7F0, 0x2AB9EE,
        0x28BCEC, 0x26BEEA, 0x25C0E7, 0x23C3E5, 0x21C5E2, 0x20C7E0, 0x1FC9DD, 0x1DCCDB,
        0x1CCED8, 0x1BD0D5, 0x1AD2D3, 0x19D4D0, 0x18D6CD, 0x18D8CB, 0x18DAC8, 0x17DBC5,
        0x17DDC3, 0x17DFC0, 0x18E0BE, 0x18E2BB, 0x19E3B9, 0x1AE5B7, 0x1BE6B4, 0x1DE8B2,
        0x1EE9AF, 0x20EAAD, 0x22ECAA, 0x24EDA7, 0x27EEA4, 0x29EFA1, 0x2CF09E, 0x2FF19B,
        0x32F298, 0x35F394, 0x38F491, 0x3CF58E, 0x3FF68B, 0x43F787, 0x46F884, 0x4AF980,
        0x4EFA7D, 0x51FA79, 0x55FB76, 0x59FC73, 0x5DFC6F, 0x61FD6C, 0x65FD69, 0x69FE65,
        0x6DFE62, 0x71FE5F, 0x75FF5C, 0x79FF59, 0x7DFF56, 0x80FF53, 0x84FF50, 0x88FF4E,
        0x8BFF4B, 0x8FFF49, 0x92FF46, 0x96FF44, 0x99FF42, 0x9CFE40, 0x9FFE3E, 0xA2FD3D,
        0xA4FD3B, 0xA7FC3A, 0xAAFC39, 0xACFB38, 0xAFFA37, 0xB1F936, 0xB4F835, 0xB7F835,
        0xB9F634, 0xBCF534, 0xBFF434, 0xC1F334, 0xC4F233, 0xC6F033, 0xC9EF34, 0xCBEE34,
        0xCEEC34, 0xD0EB34, 0xD2E934, 0xD5E835, 0xD7E635, 0xD9E435, 0xDBE236, 0xDDE136,
        0xE0DF37, 0xE2DD37, 0xE4DB38, 0xE6D938, 0xE7D738, 0xE9D539, 0xEBD339, 0xEDD139,
        0xEECF3A, 0xF0CD3A, 0xF1CB3A, 0xF3C93A, 0xF4C73A, 0xF5C53A, 0xF7C33A, 0xF8C13A,
        0xF9BF39, 0xFABD39, 0xFABA38, 0xFBB838, 0xFCB637, 0xFCB436, 0xFDB135, 0xFDAF35,
        0xFEAC34, 0xFEA933, 0xFEA732, 0xFEA431, 0xFFA12F, 0xFF9E2E, 0xFF9C2D, 0xFF992C,
        0xFE962B, 0xFE932A, 0xFE9028, 0xFE8D27, 0xFD8A26, 0xFD8724, 0xFC8423, 0xFC8122,
        0xFB7E20, 0xFB7B1F, 0xFA781E, 0xF9751C, 0xF8721B, 0xF86F1A, 0xF76C19, 0xF66917,
        0xF56616, 0xF46315, 0xF36014, 0xF25D13, 0xF05B11, 0xEF5810, 0xEE550F, 0xED530E,
        0xEB500E, 0xEA4E0D, 0xE94B0C, 0xE7490B, 0xE6470A, 0xE4450A, 0xE34209, 0xE14009,
        0xDF3E08, 0xDE3C07, 0xDC3A07, 0xDA3806, 0xD83606, 0xD63405, 0xD43205, 0xD23105,
        0xD02F04, 0xCE2D04, 0xCC2B03, 0xCA2903, 0xC82803, 0xC62602, 0xC32402, 0xC12302,
        0xBF2102, 0xBC1F01, 0xBA1E01, 0xB71C01, 0xB41B01, 0xB21901, 0xAF1801, 0xAC1601,
        0xAA1501, 0xA71401, 0xA41201, 0xA11101, 0x9E1001, 0x9B0F01, 0x980D01, 0x950C01,
        0x920B01, 0x8E0A01, 0x8B0901, 0x880801, 0x850701, 0x810602, 0x7E0502, 0x7A0402
    ]
};
