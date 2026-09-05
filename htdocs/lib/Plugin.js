//
// Plugins Support Functions
//

function Plugin() {}

// Add plugin button to invoke plugin
Plugin.addButton = function(id, title, handler) {
    var $stack = $('#openwebrx-panel-plugins');
    if (!$stack) return false;

    var $button = $(
      '<div class="openwebrx-button openwebrx-plugin-button"'
    + ' id="plugin-button-' + Utils.htmlEscape(id) + '">'
    + Utils.htmlEscape(title)
    + '</div>');

    if (handler) $button.on('click', handler);
    $stack.append($button);
    return true;
};

Plugin.toggleWindow = function(id, on) {
    var $window = $('#plugin-window-' + id);
    if (!$window) return;

    if (typeof(on) === 'undefined')
        on = !$window.is(':visible');

    if (on) $window.show(); else $window.hide();
}

Plugin.addWindow = function(id, title, content) {
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
    if (LS.has(name + '_x')) $window.css('left',   LS.loadStr(name + '_x') + 'px');
    if (LS.has(name + '_y')) $window.css('top',    LS.loadStr(name + '_y') + 'px');
    if (LS.has(name + '_w')) $window.css('width',  LS.loadStr(name + '_w') + 'px');
    if (LS.has(name + '_h')) $window.css('height', LS.loadStr(name + '_h') + 'px');

    var $header = $window.find('.openwebrx-plugin-header');
    var $close  = $window.find('.openwebrx-plugin-close');
    var $body   = $window.find('.openwebrx-plugin-body');

    let dragging = false, offsetX = 0, offsetY = 0;

    $close.on('click', (e) => { $window.hide(); });

    $window.on('mouseup', (e) => {
        var name = 'plugin_' + id;
        LS.save(name + '_w', e.currentTarget.clientWidth);
        LS.save(name + '_h', e.currentTarget.clientHeight);
    });

    $header.on('mousedown', (e) => {
        dragging = true;
        offsetX = e.clientX - e.currentTarget.parentElement.offsetLeft;
        offsetY = e.clientY - e.currentTarget.parentElement.offsetTop;
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!dragging) return;
        $window.css('left', (e.clientX - offsetX) + 'px');
        $window.css('top', (e.clientY - offsetY) + 'px');
        var name = 'plugin_' + id;
        LS.save(name + '_x', e.clientX - offsetX);
        LS.save(name + '_y', e.clientY - offsetY);
    });

    document.addEventListener('mouseup', () => { dragging = false; });

    $page.append($window);
    return $body[0];
};
