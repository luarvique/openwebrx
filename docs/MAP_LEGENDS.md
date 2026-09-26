# Receiver-coordinate picker and visible-layer legends

## Receiver coordinates in General settings

**Settings → General settings → Receiver coordinates** now uses Leaflet 1.9.4
and OpenStreetMap tiles. This embedded picker is always OSM, independent of the
main map engine and the Google API key. The latitude/longitude form fields and
stored `receiver_gps` setting are unchanged; their accessible labels now identify
each coordinate separately. The picker does not read or publish the Google key.

Edit either number, click the map, or drag the receiver marker. Numeric edits move
the marker; clicks/drags update the numbers. Merely loading, panning, zooming or
resizing the preview does **not** overwrite saved coordinates. Click/drag selections
are rounded to six decimal places; existing numeric precision is retained until
edited. Repeated-world longitudes are normalized into the server's accepted range.

The preview uses a pinned public Leaflet CDN and normal OSM tile requests with
attribution, normal caching and browser Referer behavior. Neither requires a key.
If the library cannot load, the page shows **Retry map preview** and numeric entry
still works. A tile failure also leaves numeric entry available. No address search,
geocoder, browser-location prompt or automatic GPS change is introduced.

## Collapsible legend in the Leaflet map

The **Legend** control appears in the **upper-right corner** of the Leaflet map.
Click its heading, or focus it and press Enter/Space, to expand/collapse it. Its
expanded state is remembered in browser storage when storage is available. The
body scrolls and is sized for smaller screens. The existing lower-left layer,
radio-feature and color controls remain separate.

Legends follow the selected basemap and enabled overlays, actual map attachment,
nonzero opacity, applicable zoom/scale limits, and loaded vector features in the
current view. Turning a layer off removes its legend. Switching basemaps replaces
the background's legend entry. The separate Google map client is unchanged.

| Source | Legend behavior |
| --- | --- |
| ArcGIS **map** service | Reads service layer metadata and `/legend?f=json`; filters selected sublayers, group descendants, default visibility when no IDs were selected, and reported scale limits. Displays provider symbols and labels. |
| WMS | Requests `GetLegendGraphic` separately for each selected layer/style, with current scale. At most ten sublayer legends are displayed. Support depends on the provider; not every WMS implements this operation. |
| ArcGIS **feature**, WFS, GeoJSON, completed WPS result | Builds point/line/area swatches from the **actual Leaflet styling** of already-loaded features intersecting the view. It does not falsely display a service's class-break renderer when that renderer is not used by this client. No additional feature query or WPS execution is made for the legend. |
| XYZ, TMS, WMTS, other raster sources | Uses the optional **Legend image URL** when configured; otherwise explicitly reports that no automatic legend is supplied. WMTS capabilities legend discovery is not implemented. |
| Built-in free weather | IEM-maintained color ramps for NEXRAD, MRMS hourly precipitation and GOES imagery; NOAA advisories use the ArcGIS legend endpoint automatically. |

**Visibility is not pixel-level legend filtering.** Server-rendered raster images
usually cannot tell the client which classes actually occur in the current pixels.
Their keys may contain classes outside the viewport, or a complete range where only
part of the range is currently visible. Vector visibility uses feature bounding-box
intersection (point locations for points), not exact clipping/occlusion. Raster keys
show original colors before opacity, night shading or overlapping-layer blending.

The default vector renderer is currently uniform Leaflet styling. This change adds
matching geometric swatches, **not** an ArcGIS renderer import, classified styling
engine, raster-value inspector, or automatic field-based categorization.

## Custom legend images

Under **Settings → Map settings**, each custom raster layer now has:

- **Legend image URL (optional; overrides automatic raster legend)**: a complete
  anonymous HTTP(S) image URL, not a tile template or an HTML page. Use HTTPS when
  the receiver is served over HTTPS. A supplied image overrides WMS/ArcGIS map
  legend discovery for that layer.
- **Legend description / units (plain text, optional)**: a short caption such as
  `Radar reflectivity (dBZ)` or `Accumulated rainfall (mm)`. This is also available
  for vector layers. No HTML is interpreted.

Leave these blank to use automatic behavior. Existing saved custom layers acquire
empty values without a settings-file migration. Disabled layer URLs are not included
in the new public map configuration. Legend URLs must not contain passwords, common
API-key/token query parameters, URL fragments, or tile-template placeholders.

The legend does not transform units or recolor imagery. Built-in captions explicitly
identify radar reflectivity in dBZ, the IEM hourly precipitation ramp in inches,
GOES channel 13 brightness temperature in kelvin, and channel 2 visible reflectance.

## Failure isolation and resource limits

Requests originate in the visitor's browser, with **no server-side proxy**. ArcGIS
JSON endpoints must permit CORS from the receiver's origin. Images use browser
image-loading rules. A provider failure produces a local **Retry legend** button;
it does not remove the map layer or interrupt decoded aircraft updates.

Legend JSON uses the layer adapter's 20-second timeout and 5 MiB response limit.
At most four metadata requests run concurrently; a small five-minute cache avoids
repeated downloads. ArcGIS output is capped at 256 symbols per legend. Inline
ArcGIS symbols accept raster image formats, not executable HTML or inline SVG.
Remote labels and captions are inserted as DOM text. External image loading has a
20-second error fallback; arbitrary image dimensions/response bytes remain subject
to normal browser image decoding rather than the JSON response-byte cap.

Closing the legend, hiding the tab, removing a layer or disposing the map cancels
pending legend work. Late responses cannot recreate removed entries. The legend
never executes or re-executes WPS processes. It only reflects layers the map already
has. Provider keys may refresh after five minutes while the legend is open; the
weather imagery's own refresh behavior remains unchanged.

## Tests and live acceptance checks

Dependency-free checks from the repository root:

```sh
python3 -m unittest discover -s tests -p 'test_map_followup.py' -v
node --test tests/map_legend.test.js
```

Chromium DOM integration checks (development-only `playwright` and Chromium needed):

```sh
python3 tests/browser_map_followup.py
```

The browser suite uses **test doubles for Leaflet and external requests** and runs
the real picker, layer manager, legend, editor and DOM. It verifies coordinate
synchronization, error recovery, layer visibility, keyboard collapse, late-response
cancellation, mobile sizing and safe text handling. It does not prove live Leaflet
rendering, Google behavior, public-provider availability/CORS, or an SDR deployment.
No new production npm or Python package dependency is introduced.

After updating the branch and restarting the installed application as usual, hard
reload both settings and map pages so previously cached scripts are not reused.

1. With the Google key blank, open General settings. Confirm OSM tiles load; enter
   coordinates, click, drag, save, then reopen to verify persistence. Pan without
   selecting a point and confirm the numbers do not change.
2. Enable IEM radar, MRMS precipitation, GOES and NOAA advisories individually. Open
   **Legend**, verify actual provider symbols/units and check any CORS/network errors.
3. Add a numbered ArcGIS map sublayer and a WMS layer/style; compare each legend with
   the service metadata and map. Test a custom image URL and an unavailable URL.
4. Switch basemaps, disable overlays, pan/zoom through vector features, collapse the
   legend with the keyboard, and check that aircraft updates and existing controls
   continue to work.

## Provider/API references

- Leaflet: <https://leafletjs.com/reference.html>
- OSM tile usage: <https://operations.osmfoundation.org/policies/tiles/>
- ArcGIS map-service legend: <https://developers.arcgis.com/rest/services-reference/enterprise/legend-map-service/>
- WMS GetLegendGraphic: <https://docs.geoserver.org/stable/en/user/services/wms/get_legend_graphic/index.html>
- IEM OGC services/ramps: <https://mesonet.agron.iastate.edu/ogc/>
- IEM NEXRAD mosaic/reflectivity ramp: <https://mesonet.agron.iastate.edu/docs/nexrad_mosaic/>
