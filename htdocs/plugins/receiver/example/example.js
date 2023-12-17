/*
 * example UI plugin for OpenWebRx+
 */

// Disable CSS loading for this plugin
Plugins.example.no_css = true;

// Init function of the plugin
Plugins.example.init = function () {

  // Check if utils plugin is loaded
  if (!Plugins.isLoaded('utils', 0.1)) {
    console.error('Example plugin depends on "utils >= 0.1".');
    return false;
  }

  // Listen to profile change and print the new profile name to console.
  // NOTE: you cannot manipulate the data in events, you will need to wrap the original
  // function if you want to manipulate data.
  $(document).on('event:profile_changed', function (e, data) {
    console.log('profile change event: ' + data);
  });

  // Another events:
  // event:owrx_initialized - called when OWRX is initialized

  // Server events are triggered when server sends data over the WS
  // All server events have suffix ':before' or ':after', based on the original functoin call.
  // :before events are before the original function call,
  // :after events are after the original function call.
  // Some interesting server events:
  // server:config - server configuration
  // server:bookmarks - the bookmarks from server
  // server:clients - clients number change
  // server:profiles - sdr profiles
  // server:features - supported features


  // Modify an existing OWRX function with utils plugin.
  // See utils.js for documentation on wrap method.
  // This will wrap profile changing function
  Plugins.utils.wrap_func(
    // function to wrap around
    'sdr_profile_changed',

    // before callback, to be run before the original function
    // orig = original function
    // thisArg = thisArg for the original function
    // args = the arguments for the original function
    // If you call the original function here (in the before_cb), always return false,
    // so the wrap_func() will not call it later again.
    // example of calling the original function: orig.apply(thisArg, args);
    function (orig, thisArg, args) {
      console.log("Before callback for: " + orig.name);

      // check if newly selected profile is the PMR profile
      if ($('#openwebrx-sdr-profiles-listbox').find(':selected').text() === "[RTL] 446 PMR") {
        // prevent changing to this profile
        console.log('This profile is disabled by proxy function');

        // restore the previous selected profile
        $('#openwebrx-sdr-profiles-listbox').val(currentprofile.toString());

        // return false to prevent execution of original function
        return false;
      }

      // return true to allow execution of original function
      return true;
    },

    // after callback, to be run after the original function,
    // but only if the before callback returns true
    // res = result of the original function, if any
    function (res) {
      console.log('profile changed.');
    }
  );

  // this example will do the same (stop profile changing), but using another method
  // replace the "onchange" handler of the profiles selectbox
  // and call the original function "sdr_profile_changed"
  $('#openwebrx-sdr-profiles-listbox')[0].onchange = function (e) {

    // check the index of the selected profile (0 is the first profile in the list)
    if (e.target.options.selectedIndex === 0) {
      // prevent changing to this profile
      console.log('This profile is disabled by onchange.');

      // restore the previous profile
      $('#openwebrx-sdr-profiles-listbox').val(currentprofile.toString());
      e.preventDefault();
      e.stopPropagation();
      return false;
    }

    // otherwise, call the original function
    sdr_profile_changed();
  };

  // this example will manipulate bookmarks data when the server sends the bookmarks
  // We will wrap the bookmarks.replace_bookmarks() function, once OWRX is initialized.
  // We cannot wrap the replace_bookmarks() function before the bookmarks object is created.
  // So we wait for OWRX to initialize and then wrap the function.
  $(document).on('event:owrx_initialized', function () {

    // Call the wrap method of utils plugin
    Plugins.utils.wrap_func(

      // function to wrap
      'replace_bookmarks',

      // before callback
      function (orig, thisArg, args) {

        // check if the bookmarks are "server bookmarks"
        if (args[1] === 'server') {

          // check if we have array of bookmarks (will be empty if the profile has no bookmarks to show)
          if (typeof (args[0]) === 'object' && args[0].length)

            // replace the name of the first bookmark
            args[0][0].name = 'replaced';
        }

        // now call the original function
        orig.apply(thisArg, args);

        // and return false, so the wrap_func() will not call the original for second time
        return false;
      },

      // after callback
      function (res) {
        /* not executed because the before function returns false always */
      },

      // this is the object, where the repalce_boomarks() function should be found
      bookmarks
    );
  });



  // return true for plugin init()
  return true;
} // end of init function
