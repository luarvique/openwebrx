//
// Plugins Support Functions
//

function Plugin() {}

// Add extension button to invoke plugin
Plugin.addButton = function(id, title, handler) {
    var $stack = $('#openwebrx-panel-extensions');
    if (!$stack) return false;

    var $button = $(
      '<div class="openwebrx-button openwebrx-extension-button"'
    + ' id="plugin-button-' + Utils.htmlEscape(id) + '">'
    + Utils.htmlEscape(title)
    + '</div>');

    if (handler) $button.click(handler);
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
    if ($window.length > 0) return true;

    var $page = $('#webrx-page-container');
    if (!$page) return false;

    var $window = $(
      '<div class="openwebrx-extension-window openwebrx-dialog" id="plugin-window-' + id + '">'
    + '  <div class="openwebrx-extension-header">'
    + '    <span>' + Utils.htmlEscape(title) + '</span>'
    + '    <div class="openwebrx-button openwebrx-extension-close">✕</div>'
    + '  </div>'
    + '  <div class="openwebrx-extension-body">' + content + '</div>'
    + '</div>');

    var $header = $window.find('.openwebrx-extension-header');
    var $close  = $window.find('.openwebrx-extension-close');

    let dragging = false, offsetX = 0, offsetY = 0;

    $close.click((e) => { $window.hide(); });

    $header.on('mousedown', (e) => {
        dragging = true;
        offsetX = e.clientX - e.currentTarget.parentElement.offsetLeft;
        offsetY = e.clientY - e.currentTarget.parentElement.offsetTop;
        e.preventDefault();
    });

    $header.on('mousemove', (e) => {
        if (!dragging) return;
        e.currentTarget.parentElement.style.left = (e.clientX - offsetX) + 'px';
        e.currentTarget.parentElement.style.top = (e.clientY - offsetY) + 'px';
    });

    $header.on('mouseup', () => { dragging = false; });

    $page.append($window);
    return true;
};
