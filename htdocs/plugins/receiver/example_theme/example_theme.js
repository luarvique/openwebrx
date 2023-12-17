/*
 * example plugin, creating a new theme for OpenWebRx+
 */

// Add new entry in the Theme selectbox
$('#openwebrx-themes-listbox').append(
  $('<option>').val(
    // give it a value. you will need this for the css styles
    "eye-piercer"
  ).text(
    // lets name it
    'Eye-Piercer'
  )
);
