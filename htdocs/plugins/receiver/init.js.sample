// Receiver plugins initialization.
// everything after '//' is a comment.

// !!! IMPORTANT !!! More information about the plugins can be found here:
// https://0xaf.github.io/openwebrxplus-plugins/

// uncomment the next line to enable plugin debugging in browser console.
// Plugins._enable_debug = true;

// base URL for remote plugins
const rp_url = 'https://0xaf.github.io/openwebrxplus-plugins/receiver';

// First load the utils, needed for most plugins
Plugins.load(rp_url + '/utils/utils.js').then(async function () {
	// to load local plugins use a plugin folder name directly
	//Plugins.load('example');

	// otherwise, you can load the remote plugins like this:

	// Load the notification plugin, used by some plugins. await to ensure it is loaded before the rest.
	await Plugins.load(rp_url + '/notify/notify.js');

	Plugins.load(rp_url + '/colorful_spectrum/colorful_spectrum.js');
	Plugins.load(rp_url + '/connect_notify/connect_notify.js');
});
