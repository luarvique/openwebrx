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
    return $section[0];
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
