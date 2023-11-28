/*
 * example UI plugin for OpenWebRx+
 */

$(document).on('uiplugins_initialized', () => { console.log('handle some event') });


// this is an example on how to proxy a function (run code "around" the func)
// i.e. call your code before and after the function
sdr_profile_changed_original = sdr_profile_changed;
var proxy = new Proxy(function sdr_profile_changed() { }, {
  apply: function (target, thisArg, argumentsList) {
    console.log('%s was called', target.name);
    if ($('#openwebrx-sdr-profiles-listbox').find(':selected').text() == "Profile Name" ) {
      console.log('This profile is disabled');
      return;
    }
    sdr_profile_changed_original();
  }
});
sdr_profile_changed = proxy;

// this will do the same (stop profile changing), but using another method
// we change the "onchange" handler of the profiles selectbox
// and call the original function "sdr_profile_changed"
$('#openwebrx-sdr-profiles-listbox')[0].onchange = function (e) {
  if (e.target.options.selectedIndex === 0) {
    console.log('This profile is disabled.');
    e.preventDefault();
    e.stopPropagation();
    return false;
  }
  sdr_profile_changed();
};

