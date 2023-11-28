/*
 * OpenWebRx+ UI plugin loader
 *
 * You should load your plugins in "ui-plugins/init.js"
 * see the init.js.sample.
 * and check the "plugins/example" folder for example plugin.
 *
 */

// Wait for the page to load, then load the plugins.
$(document).ready(function () {
  UIPlugins.init();
});


function UIPlugins () { }
UIPlugins.loaded = [];
UIPlugins.initialized = false;

// Load plugin
UIPlugins.load = function (name) {
  console.debug('"' + name + '" plugin loading.');
  UIPlugins._load_script(name + "/" + name + ".js")
    .then(
      () => UIPlugins._load_style(name + '/' + name + '.css')
        .then(() => {
          UIPlugins.loaded.push(name)
          console.debug(`"${name}" plugin loaded.`);
        })
        .catch(() => console.warn(`"${name}" script loaded, but css not found.`))
    )
    .catch(
      () => console.debug('"' + name + '" plugin cannot be loaded (does not exist or has errors).')
    );
}

// initialize loading
UIPlugins.init = function (name) {
  console.debug('loading plugins...');
  UIPlugins._load_script('init.js').then(
    () => {
      UIPlugins.initialized = true;
    }
  )
  .catch (
    () => { console.debug('no plugins to load.'); }
  )
}


// utility methods

UIPlugins._load_script = function (name) {
  return new Promise(function (resolve, reject) {
    var script = document.createElement('script');
    script.onload = resolve;
    script.onerror = reject;
    script.src = 'static/ui-plugins/' + name;
    document.head.appendChild(script);
  });
}

UIPlugins._load_style = function (name) {
  return new Promise(function (resolve, reject) {
    var style = document.createElement('link');
    style.onload = resolve;
    style.onerror = reject;
    style.href = 'static/ui-plugins/' + name;
    style.type = 'text/css';
    style.rel = 'stylesheet';
    document.head.appendChild(style);
  });
}
