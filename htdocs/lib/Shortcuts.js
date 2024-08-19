//
// Handle keyboard shortcuts
//

function Shortcuts() {}

Shortcuts.init = function(target) {
    var that = this;
    target.addEventListener('keydown', function(e) { that.handleKey(e); });

    this.overlay = jQuery('<div id="ks-overlay"></div>');
    this.overlay.hide();
    this.overlay.appendTo(target);

    this.overlay.html(`
    <div class="ks-title">Keyboard shortcuts</div>
    <div class="ks-subtitle">Hide this help with '?'.</div>
    <div class="ks-separator"></div>
    <div class="ks-content">

      <div class="ks-item">
        <div class="ks-item-txt">tune frequency</div>
        <div class="ks-item-kbd">${this.keycap('ArrowLeft')}|${this.keycap('ArrowRight')}</div>
      </div>
      <div class="ks-item">
        <div class="ks-item-txt">zoom waterfall</div>
        <div class="ks-item-kbd">${this.keycap('ArrowUp')}|${this.keycap('ArrowDown')}</div>
      </div>
      <div class="ks-item">
        <div class="ks-item-txt">select modulation</div>
        <div class="ks-item-kbd">(${this.keycap('Control')}+)${this.keycap('0')}..${this.keycap('9')}</div>
      </div>

      <div class="ks-item">
        <div class="ks-item-txt">change tuning step</div>
        <div class="ks-item-kbd">${this.keycap('[')}|${this.keycap(']')}</div>
      </div>
      <div class="ks-item">
        <div class="ks-item-txt">change volume</div>
        <div class="ks-item-kbd">${this.keycap('Control')}+${this.keycap('ArrowUp')}|${this.keycap('ArrowDown')}</div>
      </div>
      <div class="ks-item">
        <div class="ks-item-txt">mute/unumte sound</div>
        <div class="ks-item-kbd">${this.keycap('Space')}</div>
      </div>

      <div class="ks-item">
        <div class="ks-item-txt">auto-set squelch</div>
        <div class="ks-item-kbd">${this.keycap('A')}</div>
      </div>
      <div class="ks-item">
        <div class="ks-item-txt">change squelch level</div>
        <div class="ks-item-kbd">${this.keycap('Control')}+${this.keycap('ArrowLeft')}|${this.keycap('ArrowRight')}</div>
      </div>
      <div class="ks-item">
        <div class="ks-item-txt">disable squelch</div>
        <div class="ks-item-kbd">${this.keycap('D')}</div>
      </div>

      <div class="ks-item">
        <div class="ks-item-txt">toggle noise reduction</div>
        <div class="ks-item-kbd">${this.keycap('N')}</div>
      </div>
      <div class="ks-item">
        <div class="ks-item-txt">adjust bandpass offset</div>
        <div class="ks-item-kbd">${this.keycap('Shift')}+${this.keycap('ArrowLeft')}|${this.keycap('ArrowRight')}</div>
      </div>
      <div class="ks-item">
        <div class="ks-item-txt">adjust bandpass width</div>
        <div class="ks-item-kbd">${this.keycap('Shift')}+${this.keycap('ArrowUp')}|${this.keycap('ArrowDown')}</div>
      </div>

      <div class="ks-item">
        <div class="ks-item-txt">toggle scanner</div>
        <div class="ks-item-kbd">${this.keycap('S')}</div>
      </div>
      <div class="ks-item">
        <div class="ks-item-txt">adjust waterfall min level</div>
        <div class="ks-item-kbd">${this.keycap(',')}|${this.keycap('.')}</div>
      </div>
      <div class="ks-item">
        <div class="ks-item-txt">adjust waterfall max level</div>
        <div class="ks-item-kbd">${this.keycap('<')}|${this.keycap('>')}</div>
      </div>

      <div class="ks-item">
        <div class="ks-item-txt">auto-set colors once</div>
        <div class="ks-item-kbd">${this.keycap('Z')}</div>
      </div>
      <div class="ks-item">
        <div class="ks-item-txt">auto-set colors</div>
        <div class="ks-item-kbd">${this.keycap('X')}</div>
      </div>
      <div class="ks-item">
        <div class="ks-item-txt">set default colors</div>
        <div class="ks-item-kbd">${this.keycap('C')}</div>
      </div>

      <div class="ks-item">
        <div class="ks-item-txt">toggle recorder</div>
        <div class="ks-item-kbd">${this.keycap('R')}</div>
      </div>
      <div class="ks-item">
        <div class="ks-item-txt">toggle spectrum</div>
        <div class="ks-item-kbd">${this.keycap('V')}</div>
      </div>
      <div class="ks-item">
        <div class="ks-item-txt">toggle bandplan</div>
        <div class="ks-item-kbd">${this.keycap('B')}</div>
      </div>

      <div class="ks-item">
        <div class="ks-item-txt">open map</div>
        <div class="ks-item-kbd">${this.keycap('M')}</div>
      </div>
      <div class="ks-item">
        <div class="ks-item-txt">open files browser</div>
        <div class="ks-item-kbd">${this.keycap('F')}</div>
      </div>
      <div class="ks-item">
        <div class="ks-item-txt">open documentation</div>
        <div class="ks-item-kbd">${this.keycap('H')}</div>
      </div>
    </div>
    `);
};

Shortcuts.moveSlider = function(slider, delta) {
    var $control = $(slider);
    if (!$control.prop('disabled')) {
        $control.val(parseInt($control.val()) + delta).change();
    }
};

Shortcuts.moveSelector = function(selector, steps) {
    var $control = $(selector);
    if (!$control.prop('disabled')) {
        var max = $(selector + ' option').length;
        var n = $control.prop('selectedIndex') + steps;
        n = n < 0? n + max : n >= max? n - max : n;
        $control.prop('selectedIndex', n).change();
    }
};

Shortcuts.handleKey = function(event) {
    // Do not handle shortcuts when focused on a text or numeric input
    var on_input = !!($('input:focus').length && ($('input:focus')[0].type === 'text' || $('input:focus')[0].type === 'number'));
    if (on_input) return;

    switch (event.key) {
        case 'ArrowLeft':
            if (event.ctrlKey) {
                // CTRL+LEFT: Decrease squelch
                this.moveSlider('#openwebrx-panel-receiver .openwebrx-squelch-slider', -1);
            } else if (event.shiftKey) {
                // SHIFT+LEFT: Shift bandpass left
                var demodulators = getDemodulators();
                for (var i = 0; i < demodulators.length; i++) {
                    demodulators[i].moveBandpass(
                        demodulators[i].low_cut - 50,
                        demodulators[i].high_cut - 50
                    );
                }
            } else {
                // LEFT: Tune down
                tuneBySteps(-1);
            }
            break;

        case 'ArrowRight':
            if (event.ctrlKey) {
                // CTRL+RIGHT: Increase squelch
                this.moveSlider('#openwebrx-panel-receiver .openwebrx-squelch-slider', 1);
            } else if (event.shiftKey) {
                // SHIFT+RIGHT: Shift bandpass right
                var demodulators = getDemodulators();
                for (var i = 0; i < demodulators.length; i++) {
                    demodulators[i].moveBandpass(
                        demodulators[i].low_cut + 50,
                        demodulators[i].high_cut + 50
                    );
                }
            } else {
                // RIGHT: Tune up
                tuneBySteps(1);
            }
            break;

        case 'ArrowUp':
            if (event.ctrlKey) {
                // CTRL+UP: Increase volume
                this.moveSlider('#openwebrx-panel-volume', 1);
            } else if (event.shiftKey) {
                // SHIFT+UP: Make bandpass wider
                var demodulators = getDemodulators();
                for (var i = 0; i < demodulators.length; i++) {
                    demodulators[i].moveBandpass(
                        demodulators[i].low_cut - 50,
                        demodulators[i].high_cut + 50
                    );
                }
            } else {
                // UP: Zoom in
                zoomInOneStep();
            }
            break;

        case 'ArrowDown':
            if (event.ctrlKey) {
                // CTRL+DOWN: Decrease volume
                this.moveSlider('#openwebrx-panel-volume', -1);
            } else if (event.shiftKey) {
                // SHIFT+DOWN: Make bandpass narrower
                var demodulators = getDemodulators();
                for (var i = 0; i < demodulators.length; i++) {
                    demodulators[i].moveBandpass(
                        demodulators[i].low_cut + 50,
                        demodulators[i].high_cut - 50
                    );
                }
            } else {
                // DOWN: Zoom out
                zoomOutOneStep();
            }
            break;

        case '1': case '2': case '3': case '4': case '5':
        case '6': case '7': case '8': case '9': case '0':
            // 0-9, ctrl+0-9: Select modulation
            var $modes = $('.openwebrx-demodulator-button');
            var n = parseInt(event.key);
            n = n > 0? n - 1 : 9;
            if (event.ctrlKey) n += 10;
            if (n < $modes.length) $modes[n].click();
            break;

        case '[': case '{':
            // [: Decrease tuning step
            this.moveSelector('#openwebrx-tuning-step-listbox', -1);
            break;

        case ']': case '}':
            // ]: Increase tuning step
            this.moveSelector('#openwebrx-tuning-step-listbox', 1);
            break;

        case 'a':
            // A: Set squelch automatically
            $('.openwebrx-squelch-auto').click();
            break;

        case 's':
            // S: Toggle scanner
            if (event.ctrlKey) return; // leave it to the browser
            toggleScanner();
            break;

        case 'd':
            // D: Turn off squelch
            if (event.ctrlKey) return; // leave it to the browser
            var $squelchControl = $('#openwebrx-panel-receiver .openwebrx-squelch-slider');
            if (!$squelchControl.prop('disabled')) {
                $squelchControl.val($squelchControl.attr('min')).change();
            }
            break;

        case 'z':
            // Z: Set waterfall colors automatically
            $('#openwebrx-waterfall-colors-auto').click();
            break;

        case 'x':
            // X: Continuously auto-set waterfall colors
            $('#openwebrx-waterfall-colors-auto').triggerHandler('contextmenu');
            break;

        case 'c':
            // C: Set default waterfall colors
            $('#openwebrx-waterfall-colors-default').click();
            break;

        case 'v':
            // V: Toggle spectrum display
            UI.toggleSpectrum();
            break;

        case 'b':
            // B: Toggle bandplan display
            UI.toggleBandplan();
            break;

        case ' ':
            // SPACE: Mute/unmute sound
            UI.toggleMute();
            break;

        case 'n':
            // N: Toggle noise reduction
            if (event.ctrlKey) return; // leave it to the browser
            UI.toggleNR();
            break;

        case 'r':
            // R: Toggle recorder
            if (event.ctrlKey) return; // leave it to the browser
            UI.toggleRecording();
            break;

        case '<':
            // SHIFT+<: Decrease waterfall max level
            this.moveSlider('#openwebrx-waterfall-color-max', -1);
            break;

        case ',':
            // <: Decrease waterfall min level
            this.moveSlider('#openwebrx-waterfall-color-min', -1);
            break;

        case '>':
            // SHIFT+>: Increase waterfall max level
            this.moveSlider('#openwebrx-waterfall-color-max', 1);
            break;

        case '.':
            // >: Increase waterfall min level
            this.moveSlider('#openwebrx-waterfall-color-min', 1);
            break;

       case 'f':
            // F: Open file browser
            if (event.ctrlKey) return; // leave it to the browser
            $('a.button[target="openwebrx-files"]')[0].click();
            break;

       case 'h':
            // H: Open documentation
            if (event.ctrlKey) return; // leave it to the browser
            $('a.button[target="openwebrx-help"]')[0].click();
            break;

       case 'm':
            // M: Open map
            $('a.button[target="openwebrx-map"]')[0].click();
            break;

        case '/': case '?':
            Shortcuts.overlay.slideToggle(100);
            break;

        default:
            // Key not handled, pass it on
            return;
    }

    // Key handled, prevent default operation
    event.preventDefault();
};

Shortcuts.keycap = function(key) {
    var keymap = {
        ',': ', <b style="font-size: 0.7rem">comma</b>',
        '.': '. <b style="font-size: 0.7rem">dot</b>',
        ';': '; <b style="font-size: 0.7rem">semicolon</b>',
        '\'': '\' <b style="font-size: 0.7rem">apostrophe</b>',
        'SHIFT': '&#8679; Shift',
        'CONTROL': '&#8963; Ctrl',
        'COMMAND': '&#8984; Cmd',
        'META': '&#8984; Meta',
        'ALT': '&#8997; Alt',
        'OPTION': '&#8997; Opt',
        'ENTER': '&crarr; Enter',
        'RETURN': '&crarr; Enter',
        'DELETE': '&#8998; Del',
        'BACKSPACE': '&#9003; BS',
        'ESCAPE': '&#9099; ESC',
        'ARROWRIGHT': '&rarr;',
        'ARROWLEFT': '&larr;',
        'ARROWUP': '&uarr;',
        'ARROWDOWN': '&darr;',
        'PAGEUP': '&#8670; PgUp',
        'PAGEDOWN': '&#8671; PgDn',
        'HOME': '&#8598; Home',
        'END': '&#8600; End',
        'TAB': '&#8677; Tab',
        'SPACE': '&#9251; Space',
        'INTERVAL': '&#9251; Space',
    };

    var k = keymap[key.toUpperCase()] || key.toUpperCase();

    return `<button class="kbc-button kbc-button-sm" title="${key}"><b>${k}</b></button>`;
};
