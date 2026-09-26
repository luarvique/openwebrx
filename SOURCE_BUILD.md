# Linux source build

OpenWebRX+ can be built directly from source on Linux without producing or installing the project's Debian/RPM packages.

The host-native builder is:

```bash
./build-linux.sh
```

The default `full` profile builds OpenWebRX+ into a private prefix at `~/.local/openwebrx-source`, creates a Python virtual environment there, clones dependencies into `.build-linux/src`, applies compatibility fixes in those disposable clones, installs dependencies into the private prefix, installs the current OpenWebRX+ checkout in editable mode, and runs a feature report.

## Commands

```bash
./build-linux.sh build
./build-linux.sh run
./build-linux.sh doctor
./build-linux.sh feature-report
./build-linux.sh env
./build-linux.sh clean
./build-linux.sh uninstall
```

Profiles:

```bash
./build-linux.sh --profile core build
./build-linux.sh --profile decoders build
./build-linux.sh --profile receivers build
./build-linux.sh --profile full build
```

The build is resumable. Successful components are stamped under `.build-linux/state`; rerunning the command skips those components. Use `--force` to rebuild them.

## Supported Linux distributions

The builder contains system-package adapters for:

- openSUSE / Tumbleweed (`zypper`)
- Debian / Ubuntu (`apt`)
- Fedora / RHEL-family (`dnf`)
- Arch-family (`pacman`)

On other Linux systems use `--no-system-packages` after installing development prerequisites manually.

## Dependency integration

Third-party source repositories are cloned into the disposable `.build-linux/src` tree. OpenWebRX+-specific compatibility changes are applied by `build-linux.sh`; users do not need forks of those dependencies.

The current integration includes the compatibility work required by contemporary rolling Linux distributions, including:

- RTL-SDR automatic kernel-driver detachment.
- CodecServer C++17 and modern Protobuf imported-target integration.
- PyCSDR development headers installed under the private prefix for PyCSDR-ETI.
- JS8Py migration away from removed `pkg_resources`.
- Current FlightAware Dump1090 and Dump978 source builds.
- Decoder and receiver families represented by current OpenWebRX+ feature/source definitions.

Dependencies with known stable integration revisions are pinned in the script. `--latest` switches dependency checkouts to their configured upstream branch heads for compatibility testing.

## Optional and external prerequisites

A full OpenWebRX+ feature matrix includes components with substantial or externally controlled prerequisites. By default, failures in optional components are recorded and the build continues. The final `doctor` and `feature-report` output show what is available. Use `--strict` to make optional build failures fatal.

Examples:

- SDRplay requires the vendor SDRplay API v3 before the open SoapySDRPlay3 wrapper can be built.
- The CUDA SDDC connector requires an installed CUDA toolkit/`nvcc`; the Soapy path is attempted separately.
- Some hardware backends are architecture-specific, such as Radioberry on Raspberry Pi.
- Large suites such as WSJT-X, JS8Call, Dream, UHD, and LimeSuite may require distribution-specific development packages beyond the common prerequisite set.

Build logs are saved under:

```text
.build-linux/logs/
```

## Private install layout

By default:

```text
~/.local/openwebrx-source/
├── bin/
├── lib/
├── include/
├── share/
├── etc/openwebrx/
├── var/
└── venv/
```

The builder writes `env.sh` into the prefix. The `run` command sets the source-build environment automatically.

Override the prefix with:

```bash
./build-linux.sh --prefix /desired/path build
```

or with `OWRX_PREFIX`.

## Verification

`doctor` checks installed commands and SoapySDR information. `feature-report` initializes the OpenWebRX core configuration and runs the application's own `FeatureDetector`, avoiding differences between the build script's assumptions and the current OpenWebRX+ source.

The objective is that missing capabilities are explicit rather than discovered only when a mode or receiver is selected in the UI.
