# Map client configuration and custom GIS layers

## Where to configure it

Open **Settings → Map settings** (`/settings/map`). This authenticated settings page
replaces the Map settings section formerly under General settings. Existing keys
(`map_type`, `google_maps_api_key`, `openweathermap_api_key`, marker/call retention
and position-report preferences) are reused. No settings-file migration is needed.
Receiver coordinates and GPS updates remain under General because they describe
the receiver, not the initial map view.

**Map engine** and **basemap** are different:

- **OpenStreetMap, etc. (Leaflet)** is the extensible client. It supports the GIS
  adapters, weather catalog and custom basemap selector described below.
- **Google Maps** remains an optional separate client. It requires a Google browser
  API key; restrict that key to the receiver's domain. Turning Google off, or having
  no key, makes `/map?type=google` fall back to Leaflet. Google does not gain the
  Leaflet-only custom layers/weather catalog.

Checkboxes control the map client, Google availability, custom starting view,
receiver marker, day/night overlay, each built-in basemap, each free weather option,
OpenWeatherMap, seamarks, Maidenhead and each custom layer. No basemap is a valid
choice. Initial coordinates/zoom and receiver-marker/day-night settings work in both
clients. Callsign/locator links can still recenter the map.

After applying settings, **reload existing map pages**. The server publishes a
validated snapshot when a map page loads. Browser basemap/overlay choices are saved
per settings revision; changing map settings resets those choices to the new defaults.
Weather checkboxes on the settings page make providers available, not automatically
visible. Visitors turn overlays on in the map legend. The legend scrolls when needed.

Hiding the receiver marker or disabling the web page is a display setting, **not**
a privacy/access-control boundary for other receiver data or WebSocket endpoints.

## Adding layers without writing JSON

Choose **Add layer**, enter a name, select the service type and supply its URL.
For OGC services, enter the exact layer/type identifier from the service's
GetCapabilities response. Use the per-layer **Available to visitors** checkbox to
include/exclude a configured layer without deleting it.

Mark a layer **Use as a basemap** to put it in the basemap dropdown. Then select it
under **Default basemap** to make it the initial background. Otherwise it is an
overlay with its own visitor checkbox and an optional **Overlay initially visible**
setting. Up to 50 custom layers can be configured. Layer IDs remain stable when names
or URLs change. All entries, including disabled ones, must be valid before saving.

Opacity ranges from 0 to 1; use 1 for an opaque background. Attribution is plain
text; supply the credit required by the service owner. Refresh is disabled at 0;
otherwise the minimum is 60 seconds and maximum is 86400 seconds. Native tile zoom
controls upsampling for XYZ/WMTS sources; the map itself supports zoom 0–22.

| Service type | URL / required identifiers | Implemented behavior and limits |
| --- | --- | --- |
| ArcGIS map service | `https://host/arcgis/rest/services/Example/MapServer` or `/MapServer/0`; optional comma-separated sublayer IDs | Tiled `/export` requests with `bboxSR=3857`, `imageSR=3857`, PNG32 and transparency. Explicit IDs override a numbered URL. Service must support dynamic map export. |
| ArcGIS feature service | `.../FeatureServer`, `.../FeatureServer/0`, or queryable `.../MapServer/0` | Viewport queries return WGS84 GeoJSON. IDs are requested first, then fetched in batches of 100. A root URL without explicit IDs discovers up to 10 nongroup layers. Supply numeric IDs to select particular layers. Query and GeoJSON output must be supported. |
| WMS | Service endpoint plus one or more layer names | WMS 1.1.1 (default) or 1.3.0, EPSG:3857, PNG or JPEG. Use PNG for transparency. Styles are optional. GetCapabilities query parameters are removed before GetMap requests. |
| WMTS | KVP endpoint, exact layer ID and tile matrix set | WMTS 1.0.0, **Web Mercator XYZ-compatible matrices only**. Supply an optional matrix-ID prefix, e.g. `EPSG:3857:`. This is not an arbitrary matrix-set/projection implementation. REST tile templates can instead use XYZ. |
| WFS | Endpoint plus exact feature type name | WFS 1.0.0, 1.1.0 or 2.0.0 with **GeoJSON output**. No GML/XML parsing or reprojection. Longitude-first EPSG:4326 is requested for 1.0; CRS84 for 1.1/2.0. The current viewport is queried and antimeridian crossings are split. Services must accept the requested CRS and output format. |
| XYZ / TMS | URL containing `{z}`, `{x}`, `{y}`; optional `{s}` / `{r}` | Web Mercator tile grid. `{s}` uses a/b/c unless an existing built-in specifies otherwise. TMS reverses Y. Native zoom limits allow upsampling without requesting unsupported higher-resolution tiles. |
| GeoJSON | URL returning a WGS84 FeatureCollection or Feature | Reads the whole response, subject to size/feature limits. Useful for a previously generated WPS result. Coordinates must be longitude/latitude, not projected eastings/northings. |
| WPS | Endpoint, process identifier, literal inputs and output identifier | **Synchronous WPS 1.0 GET Execute returning raw GeoJSON only.** Enter inputs as `name=value;name=value`; default output ID is `result`. Output MIME type defaults to `application/json`. It is not a tiled map protocol or a general WPS workflow editor. |

### WPS is deliberately manual

Enabling a WPS overlay executes a process on another server. It cannot be an
automatically visible layer or basemap and cannot auto-refresh. Saved browser
preferences do not execute it on page load. Turning its checkbox on explicitly
executes it; the error recovery button says **Execute again**. Requests do not use
the browser cache. WPS 2.0, asynchronous job polling, complex/reference-input
configuration, XML result parsing and output negotiation are not implemented.
For those workflows, execute the process elsewhere and add its completed GeoJSON
result as an ordinary layer (which can be a basemap).

## Free, anonymous weather catalog

These are **latest-available / near-real-time** public services, not instantaneous
or guaranteed-available feeds. They do not require an API key or paid subscription
at the documented endpoints. Service terms, coverage, latency and availability can
change. Do not use them for aviation navigation, warnings delivery or safety-critical
decisions. The map's retrieval timestamp is **not an observation timestamp**.

| Layer | Coverage | Visible-layer refresh |
| --- | --- | --- |
| IEM NEXRAD radar | USA, where radar data is available | 5 minutes |
| NOAA watches, warnings and advisories | USA | 5 minutes |
| IEM MRMS accumulated precipitation, past hour | USA | 5 minutes |
| GOES East infrared, channel 13 | Full disk, Americas / Atlantic side | 10 minutes |
| GOES West infrared, channel 13 | Full disk, Americas / Pacific side | 10 minutes |
| GOES East visible, channel 2 | Full disk; daylight only | 10 minutes |
| GOES West visible, channel 2 | Full disk; daylight only | 10 minutes |

The old HTTP-only IEM radar entry is replaced by HTTPS. Free layers remain available
whether or not an OpenWeatherMap key is configured. The existing OpenWeatherMap
clouds/precipitation options are separately opt-in and still require that provider's
key/terms. Stadia basemaps are retained but still require registration.

Provider references used to configure the catalog:

- IEM OGC services, layer identifiers, CRS and caching documentation:
  <https://mesonet.agron.iastate.edu/ogc/>
- NOAA warning service metadata (CurrentWarnings 0, WatchesWarnings 1):
  <https://mapservices.weather.noaa.gov/eventdriven/rest/services/WWA/watch_warn_adv/MapServer?f=pjson>
- NOAA GIS services: <https://www.weather.gov/gis/>

The precise URLs/layer identifiers and refresh intervals live in
`owrx/mapconfig.py:WEATHER_LAYERS`, so they can be maintained in one place.

## Network, resource and security behavior

Requests go **directly from the visitor's browser to the configured service**.
There is no server-side fetch/proxy, credential broker, JSONP or remote-HTML popup.
A private-network endpoint only works for visitors whose browsers can reach it.
Vector/metadata endpoints must allow the receiver's origin through CORS. On an
HTTPS receiver, HTTP custom services are rejected as mixed content. Raster images
use the normal browser image-loading rules.

Custom URLs are public configuration. Do not put secrets, tokens or passwords in
them; embedded URL credentials and common API-key/token query parameters are
rejected. Authenticated ArcGIS/OGC sessions and OAuth token acquisition are outside
this implementation. Dedicated existing Google/OpenWeatherMap browser-key settings
remain separate. Only enabled custom URLs are included in the new public payload.

Vector JSON requests omit credentials, have a 20-second timeout and a 5 MiB response
limit, and revalidate cached content. Features are capped at 2000 by default,
configurable from 1 to 10000. More than 200000 coordinates in one decoded response
are rejected. Attribute popups use DOM text, not HTML. Explicitly projected CRS metadata and out-of-range or malformed coordinates
are rejected rather than silently placed in the wrong location.

Feature limits and known server truncation produce a visible **results may be
incomplete** warning. WFS results are bounded, not exhaustively paged through an
arbitrarily large dataset. Pan/zoom to narrow the query, raise the configured cap
carefully, or use a server-rendered map service for large datasets. ArcGIS services
with exceptionally small server transfer limits may require a narrower query or
server-side adjustment; warnings do not claim all features were returned.

Viewport requests are debounced and aborted when superseded. Removing a layer
cancels its vector request; late responses cannot resurrect it. Failed refreshes
retain the last successful data with an error message. Each provider fails
independently; aircraft/other decoded markers are managed separately. Custom
background/overlay panes stay below radio markers. Only active layers auto-refresh,
and hidden tabs skip refresh ticks. Returning to a visible tab refreshes overdue
layers. Tile-refresh query buckets avoid permanently reusing old imagery URLs.

Invalid map configuration fails closed for optional providers and displays a
configuration warning. An unavailable provider is not silently replaced by an
unconfigured external service. Choose another enabled basemap or None.

## Development and validation

Production code adds no npm package or Python dependency. New static files are
included by the existing recursive `htdocs` package-data rule. Reinstall/restart
using the same method used for this source checkout, then reload map pages.

Run the dependency-free unit/syntax suite with Python 3 and Node 18 or later:

```sh
./tests/run-map-client-tests.sh
```

Optional browser tests require the Python Playwright package and Chromium:

```sh
./tests/run-map-client-tests.sh --browser --chromium /usr/bin/chromium
```

Tests cover configuration/defaults, legacy PropertyLayer coordinates, validation,
JSON escaping, URL construction, antimeridian extents, bounds/limits, cancellation,
out-of-order responses, lazy activation, refresh control and failure isolation.
The headless tests exercise the real editor DOM and real map initialization/update
handlers **with stubbed Leaflet and GIS services**, including continuing ADS-B
updates after a custom layer fails. They do not certify live provider imagery,
Google API authorization or an end-to-end SDR deployment.

Before deploying, check representative live services from the receiver's origin:

1. Save/reload map settings, then restart the receiver and verify persistence.
2. Test the Google fallback and both clients' initial view/receiver/night switches.
3. Add a known ArcGIS sublayer, WMS, WFS and WMTS using their advertised parameters;
   verify alignment against an existing basemap and test a custom default basemap.
4. Enable each regional weather layer in its coverage area; check tile errors,
   attribution, data freshness and visible-only refresh.
5. Confirm decoded aircraft, popups, locator grids, call lines and legend filtering
   on the actual receiver while switching layers, panning and reconnecting.

Protocol references:
<https://developers.arcgis.com/rest/services-reference/enterprise/export-map/>,
<https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/>,
<https://www.ogc.org/standards/wps/>.
