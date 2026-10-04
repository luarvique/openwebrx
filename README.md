Key differences between this fork and the base version:
=========

* The minimum required set of packages for installation.
* Sort Bookmarks by Frequency in Admin's UI.
* Reduction in the number of decoder-related freezes during restarts.
* Localizing OSM Map Assets for Traffic Independence and Supply Chain Security.
* Efficient Storage & Intelligent Squelch-Based Audio Splitting.
* ACARS Telemetry Parsing Fix and external UDP logging.
* Numerous minor fixes.

Prerequisites and Dependencies
=========

To install high-performance DSP engines and specialized digital decoders natively via the system package manager, you must first connect the developer's package repository.
👉 **Follow the official repository setup instructions here:** https://fms.komkon.org/OWRX/#InstallGuide
⚠️ **IMPORTANT NOTE FOR USERS:** Follow the guide **ONLY** up to the point of adding the repository for your specific Linux distribution.
**DO NOT install the main `openwebrx` package** from that guide, as it will conflict with this source-built fork. Only the repository configuration is needed.

Install CORE runtime engine (Mandatory for all users)
=========

```bash
sudo apt install -y git python3-pip python3-setuptools python3-requests \
python3-protobuf python3-tabulate python3-paho-mqtt paho-mqtt1.3 \
libowrx-connector owrx-connector codecserver codecserver-driver-all \
codecserver-driver-ambe3k csdr-skimmer libcsdr-eti0 python3-csdr \
libfdk-aac2t64 soapy-connector python3-bleak python3-dbus-fast python3-dotmap \
libaml0t64 libpaho-mqtt1.3 librtaudio7 perl-openssl-defaults
```

Install SDR receiver DRIVERS (Pick only ONE for your hardware)
=========

* 🔹 **For RTL-SDR Dongles (v3, v4, Nooelec, and clones):**
  ```bash
  sudo apt install -y soapysdr0.8-module-rtlsdr rtl-connector rtl-tcp-connector
  ```
* 🔹 **For Airspy Receivers (R2, Mini, HF+):**
  ```bash
  sudo apt install -y soapysdr0.8-module-airspy
  ```
* 🔹 **For SDRplay / MSI2500 clones (RSP1 architecture):**
  ```bash
  sudo apt install -y soapysdr0.8-module-msi2500 libosmosdr0 soapyosmo-common0.8 libmirisdr4
  ```
* 🔹 **For HackRF One Systems:**
  ```bash
  sudo apt install -y soapysdr0.8-module-hackrf
  ```

Install OPTIONAL digital decoders (Install by interest)
=========

Do not populate your system with unused packages. Selectively install decoder blocks based on the radio networks you intend to monitor.

#### ✈️ Aviation Tracking Networks
* **Aircraft text messages via ACARS (VHF) and VDL Mode 2:**
  ```bash
  sudo apt install -y acarsdec dumpvdl2
  ```
* **Aircraft geographic plotting via ADS-B (1090 MHz) and UAT (978 MHz):**
  ```bash
  sudo apt install -y dump1090-fa-minimal dump978-fa-minimal
  ```
* **HF Aviation tracking via HFDL:**
  ```bash
  sudo apt install -y dumphfdl
  ```

#### 📻 Amateur Radio & Telemetry
* **Automated Weather Station (AWS), ISM band sensors, and tire pressure (433/868 MHz):**
  ```bash
  sudo apt install -y rtl-433
  ```
* **Ham radio geolocation grids via APRS packet networks:**
  ```bash
  sudo apt install -y direwolf aprs-symbols multimon-ng python3-js8py libhamlib-utils libhamlib4t64 libdigiham0 python3-digiham
  ```
* **High-altitude weather balloon telemetry (Radiosondes):**
  ```bash
  sudo apt install -y sonde-decoders
  ```
* **Decentralized LoRa mesh endpoints:**
  ```bash
  sudo apt install -y python3-meshtastic
  ```

#### 🛰️ Digital Broadcast Audio
* **Broadcast text capture (RDS FM Data):**
  ```bash
  sudo apt install -y redsea
  ```
* **Digital Terrestrial Radio standards (DAB/DAB+, Shortwave DRM, HD Radio):**
  ```bash
  sudo apt install -y dablin dream nrsc5 codec2 lame
  ```

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

- Debian repository
- Manual installation

Please checkout the [setup guide on the wiki](https://github.com/jketterl/openwebrx/wiki/Setup-Guide) for more details
on the respective methods.

## Usage tips

You can zoom the waterfall display by the mouse wheel. You can also drag the waterfall to pan across it.

The filter envelope can be dragged at its ends and moved around to set the passband.

However, if you hold down the shift key, you can drag the center line (BFO) or the whole passband (PBS).

## Licensing

OpenWebRX is available under Affero GPL v3 license
