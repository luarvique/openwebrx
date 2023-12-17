/*
 * Plugin: sort profiles by name.
 */

// do not load CSS for this plugin
Plugins.sort_profiles.no_css = true;

// Initialize the plugin
Plugins.sort_profiles.init = function () {

  // Catch the event, when server sends us the profiles.
  $(document).on('server:profiles:after', function (e, data) {
    var sel = $('#openwebrx-sdr-profiles-listbox');

    // if the list is empty, return
    if (!sel[0] || !sel[0].length)
      return;

    var selected = sel.val();
    var list = sel.find('option');

    // sort the list of options, alphanumeric and ignorring the case
    list.sort(function (a, b) {
      return $(a).text()
        .localeCompare(
          $(b).text(), undefined, {
            numeric: true,
            sensitivity: 'base'
          }
        );
    });

    // now reset the list and fill it with the new sorted one
    sel.html('').append(list);

    // set the selected profile from our cached value
    sel.val(selected);
  });

  // return true to validate plugin load
  return true;
}
