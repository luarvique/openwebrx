//
// Plugin Support Functions
//

function Plugins() {}

//
// Add plugin invocation button.
//

Plugins.addButton = function(id, title, handler = null, color = null) {
    var $stack = $('#openwebrx-panel-plugins');
    if (!$stack) return null;

    var $button = $(
      '<div class="openwebrx-button openwebrx-plugin-button"'
    + ' id="plugin-button-' + Utils.htmlEscape(id) + '">'
    + Utils.htmlEscape(title)
    + '</div>');

    if (color)   $button.css('background', color);
    if (handler) $button.on('click', handler);

    $stack.append($button);
    return $button[0];
};

//
// Add a floating resizable window.
//

Plugins.toggleWindow = function(id, on) {
    var $window = $('#plugin-window-' + id);
    if (!$window) return;

    if (typeof(on) === 'undefined')
        on = !$window.is(':visible');

    if (on) $window.show(); else $window.hide();
}

Plugins.addWindow = function(id, title, content = '') {
    id = Utils.htmlEscape(id);
    var $window = $('#plugin-window-' + id);
    if ($window.length > 0) return $window[0];

    var $page = $('#webrx-page-container');
    if (!$page) return null;

    var $window = $(
      '<div class="openwebrx-plugin-window" id="plugin-window-' + id + '">'
    + '  <div class="openwebrx-plugin-header openwebrx-button">'
    + '    <span>' + Utils.htmlEscape(title) + '</span>'
    + '    <div class="openwebrx-plugin-close openwebrx-button">✕</div>'
    + '  </div>'
    + '  <div class="openwebrx-plugin-body">' + content + '</div>'
    + '</div>');

    var name = 'plugin_' + id;
    if (LS.has(name + '_x')) $window.css('left',   LS.loadStr(name + '_x'));
    if (LS.has(name + '_y')) $window.css('top',    LS.loadStr(name + '_y'));
    if (LS.has(name + '_w')) $window.css('width',  LS.loadStr(name + '_w'));
    if (LS.has(name + '_h')) $window.css('height', LS.loadStr(name + '_h'));

    var $header = $window.find('.openwebrx-plugin-header');
    var $close  = $window.find('.openwebrx-plugin-close');

    let dragging = false, offsetX = 0, offsetY = 0;

    $close.on('click touchend', (e) => { $window.hide(); });

    $window.on('mouseup touchend', (e) => {
        var name = 'plugin_' + id;
        LS.save(name + '_w', e.currentTarget.style.width);
        LS.save(name + '_h', e.currentTarget.style.height);
        LS.save(name + '_x', e.currentTarget.style.left);
        LS.save(name + '_y', e.currentTarget.style.top);
    });

    $header.on('mousedown touchstart', (e) => {
        if (dragging) return;
        dragging = true;

        $('[id^="plugin-window-"]').css('z-index', 110);
        $window.css('z-index', 111);

        if (e.targetTouches) {
            var t = e.targetTouches.item(0);
            offsetX = t.clientX;
            offsetY = t.clientY;
        } else {
            offsetX = e.clientX;
            offsetY = e.clientY;
        }

        offsetX -= e.currentTarget.parentElement.offsetLeft;
        offsetY -= e.currentTarget.parentElement.offsetTop;
        e.preventDefault();
    });

    $(document).on('mousemove touchmove', (e) => {
        if (!dragging) return;

        var t = e.targetTouches? e.targetTouches.item(0) : e;
        $window.css('left', (t.clientX - offsetX) + 'px');
        $window.css('top', (t.clientY - offsetY) + 'px');
    });

    $(document).on('mouseup touchend touchcancel', (e) => {
        dragging = false;
    });

    $window.hide();
    $page.append($window);
    return $window[0];
};

//
// Add a receiver panel section.
//

Plugins.toggleSection = function(id, on) {
    var $section = $('#plugin-section-' + id);
    if (!$section) return;
    UI.toggleSection($section[0]);
}

Plugins.addSection = function(id, title, content = '') {
    id = 'plugin-section-' + Utils.htmlEscape(id);

    var $section = $(
      '<div id="' + id + '" class="openwebrx-section-divider" onclick="UI.toggleSection(this);">'
    + '&blacktriangledown;&nbsp;' + Utils.htmlEscape(title) + '</div>'
    + '<div class="openwebrx-section">' + content + '</div>');

    $section.insertBefore('#openwebrx-section-settings');
    UI.toggleSection($section[0], LS.has(id)? LS.loadBool(id) : false);
    return $section[0].nextElementSibling;
};

//
// Sample map plugin that lives inside a floating window.
//

function MapPlugin() {}

MapPlugin.myname = 'map';
MapPlugin.iframe = null;

MapPlugin.init = function() {
    Plugins.addButton(this.myname, 'MAP', this.create);
};

MapPlugin.create = function() {
    if (MapPlugin.iframe == null) {
        var content = '<iframe src="/map" style="position:relative;top:0;left:0;width:100%;height:100%;border:none;"></iframe>';
        var iframe = Plugins.addWindow(MapPlugin.myname, 'Map', content).querySelector('iframe');
        MapPlugin.iframe = iframe;

        iframe.addEventListener('load', () => {
            var doc = iframe.contentDocument || iframe.contentWindow.document;
            doc.querySelector('.webrx-top-bar').style.display = 'none';
        });
    }

    Plugins.toggleWindow(MapPlugin.myname);
}

//
// Sample solar weather plugin that lives inside a floating window.
//

function SunPlugin() {}

SunPlugin.myname = 'sun';

SunPlugin.init = function() {
    Plugins.addButton(this.myname, 'SUN', this.create);
};

SunPlugin.create = function() {
    if (SunPlugin.iframe == null) {
        var src = 'https://www.hamqsl.com/solar101vhf.php';
        var content =
          '<center>'
        + '<a href="https://www.hamqsl.com/solar.html" target="_blank">'
        + '<img src="' + src + '"></a></center>';
        var w = Plugins.addWindow(SunPlugin.myname, 'Solar Weather', content);
        var h = w.querySelector('.openwebrx-plugin-header');
        var b = w.querySelector('.openwebrx-plugin-body');
        var i = w.querySelector('img');
        b.style.backgroundColor = 'black';
        w.style.resize = 'none';
        i.addEventListener('load', () => {
            w.style.width = i.naturalWidth + 20 + 'px';
            w.style.height = i.naturalHeight + 20 + h.offsetHeight + 'px';
        });
        setInterval(() => {
            i.src = src + '?t=' + (new Date().getTime());
        }, 15 * 60 * 1000);
    }

    Plugins.toggleWindow(SunPlugin.myname);
}

//
// Add magic key entry to the Settings section.
//

function KeyPlugin() {}

KeyPlugin.myname = 'key';

KeyPlugin.init = function() {
    var settings = document.querySelector('#openwebrx-section-settings');
    if (!settings) return;

    settings = settings.nextElementSibling;
    if (!settings) return;

    settings.insertAdjacentHTML('beforeend',
      '<div class="openwebrx-panel-line" style="display:flex;gap:10px;padding:5px 0px;align-items:center;">'
    + '<label for="magic-key-input" style="flex:none;">Key</label>'
    + '<input type="text" id="magic-key-input" style="flex:1;min-width:0;box-sizing:border-box">'
    + '</div>'
    );

    var input = settings.querySelector('#magic-key-input');
    input.value = UI.getDemodulatorPanel().getMagicKey() || LS.loadStr('magic-key') || '';
    UI.getDemodulatorPanel().setMagicKey(input.value);
    input.addEventListener('change', () => {
        UI.getDemodulatorPanel().setMagicKey(input.value);
        LS.save('magic-key', input.value);
    });
};

//
// Add TRANSMIT button for connected transceivers.
//

function RigPlugin() {}

RigPlugin.myname = 'rig';
RigPlugin.ptt = null;
RigPlugin.tx = false;

RigPlugin.start = function() {
    if (RigPlugin.ptt && !RigPlugin.tx) {
        RigPlugin.ptt.style.background = 'red';
        RigPlugin.ptt.style.color = 'white';
        RigPlugin.tx = true;
        ws.send(JSON.stringify({ 'type': 'txcontrol', 'action': 'start' }));
    }
};

RigPlugin.stop = function() {
    if (RigPlugin.ptt && RigPlugin.tx) {
        RigPlugin.ptt.style.background = 'white';
        RigPlugin.ptt.style.color = 'red';
        RigPlugin.tx = false;
        ws.send(JSON.stringify({ 'type': 'txcontrol', 'action': 'stop' }));
    }
};

RigPlugin.init = function() {
    // Do not initialize twice
    if (RigPlugin.ptt) return;

    var content =
      '<div class="openwebrx-panel-line" style="display:grid;justify-items:center;">'
    + '<input type="button" class="openwebrx-button" value="&#9003; TRANSMIT" '
    + 'style="width:95%;font-size:12pt;font-weight:bold;background:white;color:red;">'
    + '</div>';
    var ptt = Plugins.addSection(this.myname, 'Rig', content).querySelector('input');
    this.ptt = ptt;

    ptt.addEventListener('pointerdown', this.start);
    ptt.addEventListener('pointerleave', this.stop);
    ptt.addEventListener('pointerup', this.stop);

    // When BACKSPACE pressed...
    document.body.addEventListener('keydown', (e) => {
        // Do not push twice
        if (RigPlugin.tx) return;
        // Do not proceed if focused on an input or list selector
        var tag = document.activeElement? document.activeElement.tagName : null;
        if (tag && (tag === 'INPUT' || tag === 'TEXTAREA'))
            return;
        // Simulate pointer-down event on BACKSPACE
        if (e.key.toLowerCase() === 'backspace') {
            ptt.dispatchEvent(new PointerEvent('pointerdown', {
                bubbles: true, cancelable: true, view: window
            }));
        }
    });

    // When any key released...
    document.body.addEventListener('keyup', (e) => {
        // Do not release twice
        if (!RigPlugin.tx) return;
        // Simulate pointer-up event
        ptt.dispatchEvent(new PointerEvent('pointerup', {
            bubbles: true, cancelable: true, view: window
        }));
    });
};

