OpenWebRX+
=========

This is the **improved version** of the OpenWebRX online SDR. The pre-built OpenWebRX+ packages are available from the [package repository](https://luarvique.github.io/ppa/). Pre-built disk images are available from the [Releases page](https://github.com/luarvique/openwebrx/releases). OpenWebRX+ [documentation](https://fms.komkon.org/OWRX/) draft is now available. News, support, and general discussion can be found in the [Telegram channel](https://t.me/openwebrx) and related [chat](https://t.me/openwebrx_chat). Features found in OpenWebRX+ that are not present in the original version:
* AIS, SSTV, FAX, FLEX, POCSAG, HFDL, VDL2, ADSB, ACARS, ISM, RDS, SAM, SITOR-B, RTTY, and CW decoders.
* DTMF, EEA, EIA, CCIR, and several ZVEY SELCALL decoders.
* Background SSTV and FAX decoding with received images browser.
* Built-in chat between receiver users.
* Built-in recorder for received audio.
* Built-in scanner over bookmarks.
* Ability for the admin to see user connections and ban abusive users.
* Adjustable noise filtering based on spectral subtraction.
* Adjustable tuning step.
* Automatically created bookmarks for shortwave broadcasts.
* Automatically created bookmarks for nearby HAM repeaters.
* Waterfall panning and zooming on touchscreen based devices.
* Bandpass control with the scroll wheel.
* Improved tuning in CW mode.
* More reliable SDRPlay devices operation.
* Map shows other public web SDRs from all around the world.
* Map shows shortwave broadcasters from all around the world.
* Map shows aircraft positions received over ADSB, VDL2, HFDL.
* Map shows nearby HAM repeaters.
* Better map information, with distances, APRS paths, weather, etc.
* Support for configurable session timeout, with a policy page.
* HTTPS protocol support (requires certificate).
* Foldable receiver panel with configurable opacity.
* Spectrum display.

Original OpenWebRX
=========

OpenWebRX is a multi-user SDR receiver software with a web interface.

![OpenWebRX](https://www.openwebrx.de/gfx/openwebrx-screenshot.png)

It has the following features:

- [csdr](https://github.com/jketterl/csdr) based demodulators (AM/FM/SSB/CW/BPSK31/BPSK63)
- filter passband can be set from GUI
- it extensively uses HTML5 features like WebSocket, Web Audio API, and Canvas
- it works in Google Chrome, Chromium and Mozilla Firefox
- supports a wide range of [SDR hardware](https://github.com/jketterl/openwebrx/wiki/Supported-Hardware#sdr-devices)
- Multiple SDR devices can be used simultaneously
- [digiham](https://github.com/jketterl/digiham) based demodularors (DMR, YSF, Pocsag, D-Star, NXDN)
- [wsjt-x](https://wsjt.sourceforge.io/) based demodulators (FT8, FT4, WSPR, JT65, JT9, FST4,
  FST4W)
- [direwolf](https://github.com/wb2osz/direwolf) based demodulation of APRS packets
- [JS8Call](http://js8call.com/) support
- [DRM](https://github.com/jketterl/openwebrx/wiki/DRM-demodulator-notes) support
- [FreeDV](https://github.com/jketterl/openwebrx/wiki/FreeDV-demodulator-notes) support
- M17 support based on [m17-cxx-demod](https://github.com/mobilinkd/m17-cxx-demod)

## Setup

The following methods of setting up a receiver are currently available:

- Raspberry Pi SD card images
- Debian repository
- Docker images
- Manual installation

Please checkout the [setup guide on the wiki](https://github.com/jketterl/openwebrx/wiki/Setup-Guide) for more details
on the respective methods.

### Docker Compose

Build and start OpenWebRX+ from this checkout:

```sh
cd containerization
cp .env.example .env
# Edit .env and choose a strong initial administrator password. Keep the
# project name unique if this host runs other Compose applications.
docker compose up -d --build
```

The default sparse image provides the OpenWebRX core, SDR connectors, SoapySDR
drivers, and ordinary audio demodulation. To build the larger full image with
the optional decoder packages from Debian Trixie and the signed OpenWebRX+
Trixie repository, use its standalone Compose file instead:

```sh
docker compose -f docker-compose.full.yaml up -d --build
```

Both Compose files contain the complete runtime configuration and can be used
independently. For direct image builds, the Dockerfile also defaults to sparse;
set `OPENWEBRX_FULL=1` to build the full package set. Run these commands from
the repository root:

```sh
docker build -f containerization/Dockerfile -t openwebrx-plus:sparse .
docker build -f containerization/Dockerfile --build-arg OPENWEBRX_FULL=1 -t openwebrx-plus:full .
```

Legacy Compose installations can use `docker-compose up -d --build` from the
same directory. The Compose file uses the explicit Compose 3.8 schema; older
installations may require a local version adjustment before starting the
service.

Both images are based on Debian 13 (Trixie). The OpenWebRX Python/web
application is installed from this checkout, while CSDR, its Python bindings,
`nmux`, and the SDR connectors come from the signed OpenWebRX+ Trixie
repository.

The full image installs every compatible decoder available from those signed
repositories. A small number of specialized features still require
proprietary hardware, an external service, or software that is not packaged
for Trixie.

The web interface is available at `http://localhost:8073`. Configuration is
persisted in `containerization/runtime/config`, and settings, users, recordings,
and decoded data are persisted in `containerization/runtime/data`. Both directories are
created and initialized automatically on first start.

The Compose service bind-mounts `/dev` and runs privileged as root so USB and
other SDR devices work regardless of host udev group IDs. This grants the
container broad access to host hardware. For a more restricted deployment,
remove `privileged: true` and the `/dev:/dev` mount, then add only the required
device (for example `/dev/bus/usb:/dev/bus/usb`) under `devices:`.

Useful commands:

```sh
docker compose logs -f openwebrx
docker compose down
```

## Community

If you have trouble setting up or configuring your receiver, you have some great idea you want to see implemented, or
you just generally want to have some OpenWebRX-related chat, come visit us over on
[our groups.io group](https://groups.io/g/openwebrx).

If you want to hang out, chat, or get in touch directly with the developers, receiver operators or users, feel free to
drop by in [our Discord server](https://discord.gg/gnE9hPz).

## Usage tips

You can zoom the waterfall display by the mouse wheel. You can also drag the waterfall to pan across it.

The filter envelope can be dragged at its ends and moved around to set the passband.

However, if you hold down the shift key, you can drag the center line (BFO) or the whole passband (PBS).

## Licensing

OpenWebRX is available under Affero GPL v3 license
([summary](https://tldrlegal.com/license/gnu-affero-general-public-license-v3-(agpl-3.0))).

OpenWebRX is also available under a commercial license on request. Please contact me at the address
*&lt;randras@sdr.hu&gt;* for licensing options. 
