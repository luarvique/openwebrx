#!/bin/sh
# Developer tests only: Node is not a new runtime dependency of OpenWebRX+.
set -eu
cd "$(dirname "$0")/.."
"${PYTHON:-python3}" -m unittest discover -s tests -p 'test_mapconfig.py' -v
for script in htdocs/lib/MapLayers.js htdocs/lib/settings/MapSettings.js htdocs/map-leaflet.js htdocs/map-google.js; do
    node --check "$script"
done
node --test tests/map_layers.test.js
if [ "${1:-}" = "--browser" ]; then
    shift
    "${PYTHON:-python3}" tests/browser_map_smoke.py "$@"
fi
