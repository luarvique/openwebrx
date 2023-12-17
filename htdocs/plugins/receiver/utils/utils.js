// This is the utils plugin
// It provides function wrapping method
// and some events for the rest plugins

// Disable CSS loading for this plugin
Plugins.utils.no_css = true;

// Utils plugin version
Plugins.utils._version = 0.1;

/**
 * Wrap an existing function with before and after callbacks.
 * @param {string} name The name of function to wrap with before and after callbacks.
 * @param {function(orig, thisArg, args):boolean} before_cb Callback before original. Return true to call the original.
 * @param {function(result):void} after_cb Callback after original, will receive the result of original
 * @param {object} obj [optional] Object to look for function into. Default is 'window'
 * @description
 *   - Before Callback:
 *     - Params:
 *       - orig: Original function (in case you want to call it, you have to return false to prevent second calling)
 *       - thisArg: local 'this' for the original function
 *       - args: arguments passed to the original function
 *     - Returns: Boolean. Return false to prevent execution of original function and the after callback.
 *   - After Callback:
 *     - Params:
 *       - res: Result of the original function
 *
 * @example
 * // Using before and after callbacks.
 * Plugins.utils.wrap_func('sdr_profile_changed',
 *   function (orig, thisArg, args) { // before callback
 *     console.log(orig.name);
 *     if (something_bad)
 *       console.log('This profile is disabled by proxy function');
 *       return false; // return false to prevent the calling of the original function and the after_cb()
 *     }
 *     return true; // always return true, to call the original function
 *   },
 *   function (res) { // after callback
 *     console.log(res);
 *   }
 * );
 *
 * @example
 * // Using only before callback and handle original.
 * Plugins.utils.wrap_func('sdr_profile_changed',
 *   function (orig, thisArg, args) { // before callback
 *     // if we need to call the original in the middle of our work
 *     do_something_before_original();
 *     var res = orig.apply(thisArg, args);
 *     do_something_after_original(res);
 *     return false; // to prevent calling the original and after_cb
 *   },
 *   function (res) { // after callback
 *     // ignored
 *   }
 * );
 *
 */
Plugins.utils.wrap_func = function (name, before_cb, after_cb, obj = window) {
  if (typeof obj[name] !== "function") {
    console.error("Cannot wrap non existing function: '" + obj + '.' + name + "'");
    return false;
  }

  var fn_original = obj[name];
  var proxy = new Proxy(obj[name], {
    apply: function (target, thisArg, args) {
      if (before_cb(target, thisArg, args))
        after_cb(fn_original.apply(thisArg, args));
    }
  });
  obj[name] = proxy;
}





// Init utils plugin
Plugins.utils.init = function () {

  // trigger some events
  var send_events_for = {
    'sdr_profile_changed': { // function name to proxy.
      name: 'profile_changed', // [optional] event name (prepended with 'event:'). Default is function name.
      data: function () { // [optional] data to send with the event (should be function).
        return $('#openwebrx-sdr-profiles-listbox').find(':selected').text()
      }
    },
    'on_ws_recv': {
      handler: function (orig, thisArg, args) { // if handler exist, it will replace the before_cb
        if (typeof args[0].data === 'string' && args[0].data.substr(0, 16) !== "CLIENT DE SERVER") {
          try {
            var json = JSON.parse(args[0].data);
            $(document).trigger('server:' + json.type + ":before", [json['value']]);
          } catch (e) {}
        }
        orig.apply(thisArg, args); // we handle original function here
        if (typeof json === 'object')
          $(document).trigger('server:' + json.type + ":after", [json['value']]);
        return false; // do not call the after_cb
      }
    },
  }

  $.each(send_events_for, function (key, obj) {
    Plugins.utils.wrap_func(key,
      (typeof (obj.handler) === 'function') ?
      obj.handler : function () {
        return true;
      },
      function (res) {
        var ev_data;
        var ev_name = key;
        if (typeof (obj.name) === 'string') ev_name = obj.name;
        if (typeof (obj.data) === 'function') ev_data = obj.data(res);
        $(document).trigger('event:' + ev_name, [ev_data]);
      }
    );
  });

  var interval = setInterval(function () {
    if (typeof (clock) === 'undefined') return;
    clearInterval(interval);
    $(document).trigger('event:owrx_initialized');
  }, 10);

  return true;
}
