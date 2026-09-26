#!/usr/bin/env bash
# Host-native Linux source builder for OpenWebRX+.
# Builds OpenWebRX+ and source-buildable receiver/decoder dependencies into
# a private prefix. It does not create or install OpenWebRX .deb/.rpm packages.
set -Eeuo pipefail
IFS=$'\n\t'

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${OWRX_PREFIX:-$HOME/.local/openwebrx-source}"
WORK="${OWRX_BUILD_ROOT:-$ROOT/.build-linux}"
SRC="$WORK/src"; BLD="$WORK/build"; STATE="$WORK/state"; LOG="$WORK/logs"
VENV="${OWRX_VENV:-$PREFIX/venv}"
CONF="${OWRX_CONFIG_FILE:-$PREFIX/etc/openwebrx/openwebrx.conf}"
DATA="${OWRX_DATA_DIR:-$PREFIX/var/lib/openwebrx}"
TMP="${OWRX_TMP_DIR:-$PREFIX/var/tmp}"
PROFILE="${OWRX_PROFILE:-full}"
INSTALL_SYS="${OWRX_INSTALL_SYSTEM_DEPS:-1}"
STRICT="${OWRX_STRICT_OPTIONAL:-0}"
LATEST="${OWRX_LATEST:-0}"
FORCE="${OWRX_FORCE:-0}"
PYTHON="${OWRX_PYTHON:-python3}"
JOBS="${OWRX_JOBS:-$(command -v nproc >/dev/null && nproc || echo 2)}"
GENERATOR="${OWRX_CMAKE_GENERATOR:-$(command -v ninja >/dev/null && echo Ninja || echo 'Unix Makefiles')}"

info(){ printf '\033[1;34m[INFO]\033[0m %s\n' "$*"; }
ok(){ printf '\033[1;32m[ OK ]\033[0m %s\n' "$*"; }
warn(){ printf '\033[1;33m[WARN]\033[0m %s\n' "$*" >&2; }
die(){ printf '\033[1;31m[FAIL]\033[0m %s\n' "$*" >&2; exit 1; }

declare -A URL REF BRANCH
dep(){ URL["$1"]="$2"; REF["$1"]="$3"; BRANCH["$1"]="${4:-}"; }

# Locked integration revisions. OWRX_LATEST=1 switches to the named branch.
dep fftw https://github.com/FFTW/fftw3.git 7184fc796279cfa70e4ba62519ac2938054584e6 master
dep rtl-sdr https://github.com/osmocom/rtl-sdr.git 797f8143266d983c56d8f35d2d442527529dd8a5 master
dep soapysdr https://github.com/pothosware/SoapySDR.git 1551ea0d39ce546b32a15808b9b1241018a89fc8 master
dep soapyrtlsdr https://github.com/pothosware/SoapyRTLSDR.git 6ca357c15cbf676ff30eb8eb445d1e1eac17c136 master
dep csdr https://github.com/luarvique/csdr.git f26b52071c4a127fc8193d058c249cac57585de4 master
dep pycsdr https://github.com/luarvique/pycsdr.git 42a5ab3ca48953e65441c4ed7fbd63f030f5afa8 master
dep owrx_connector https://github.com/luarvique/owrx_connector.git bca362707131289f91441c8080fd368fdc067b6d develop
dep codecserver https://github.com/jketterl/codecserver.git 8caf36aab936c5587fa404572b2c59c6ab7d4339 master
dep digiham https://github.com/luarvique/digiham.git beec78229edb8e049f8b82729498def952b79cc1 master
dep pydigiham https://github.com/luarvique/pydigiham.git 9ab0f239130d3f0aea5ac15d4b209ed7db2b88be master
dep csdr-eti https://github.com/luarvique/csdr-eti.git a52651366276c382fbe87131d44c37642de65e7f develop
dep pycsdr-eti https://github.com/luarvique/pycsdr-eti.git 0bd15e1af1f8f232a2c8e9c4b623e146066113bb develop
dep js8py https://github.com/jketterl/js8py.git f7e394b7892d26cbdcce5d43c0b4081a2a6a48f6 develop
dep liquid-dsp https://github.com/jgaeddert/liquid-dsp.git master master
dep redsea https://github.com/windytan/redsea.git 7555c9f6259d50718697ee8c9f218ea012c6892c master
dep libacars https://github.com/luarvique/libacars.git 392ab0e5913d973f37e4bacfedb2c2e6921ae3fd master
dep acarsdec https://github.com/luarvique/acarsdec.git dfd62e2c1a3c12866c9bb5d8c51437a5589dbb9d master
dep dumpvdl2 https://github.com/luarvique/dumpvdl2.git 5843a3aa7532eeb69e30ecd4c8fbd16d8834604d master
dep dumphfdl https://github.com/luarvique/dumphfdl.git 17e40b29db13031167d56278bd3ec51fdc3639ec master
dep dump1090 https://github.com/flightaware/dump1090.git 0339a57b89cd6e61856cbb13ae342c31ae7be5ac master
dep dump978 https://github.com/flightaware/dump978.git f40aa9a0d2d0a0067c0c628b44ba316f7049b8ce master
dep nrsc5 https://github.com/luarvique/nrsc5.git 7a458e4fdc88022bc620d298152a30490d5376ee master
dep multimon-ng https://github.com/luarvique/multimon-ng.git b5a9515a91c0163314566e486458ff9900f3e59b master
dep csdr-skimmer https://github.com/luarvique/csdr-skimmer.git b1dc9e3d573bfe05c2532bb45f69d2d3c7d9b51e main
dep rtl_433 https://github.com/merbanan/rtl_433.git 7649730330f1fb00d572bc595e33d2bd605068bb master
dep direwolf https://github.com/wb2osz/direwolf.git eda1383f5fa9d8ba3cb27f99db1d2c79494404c9 master
dep codec2 https://github.com/drowe67/codec2.git 310777b1c6f1af0bc7c72f5b32f80f6fd9136962 main
dep m17 https://github.com/mobilinkd/m17-cxx-demod.git 9b8cec24d3f8d5e9f7f6e9c23661439e32343d6b master
dep msk144 https://github.com/alexander-sholohov/msk144decoder.git 761d0b3a61cde664d4c25b1c6ff1d9c0e395af23 main
dep dablin https://github.com/Opendigitalradio/dablin.git 96ae480f7ff6c20c9c3cdbcc35c80cf88f5ab750 master
dep aprs-symbols https://github.com/hessu/aprs-symbols.git master master
dep wsjtx https://github.com/WSJTX/wsjtx.git v3.0.2 master
dep js8call https://github.com/js8call/js8call.git v2.3.1 main
dep dream https://github.com/wwek/dream.git v2.2.4 main
dep rade https://github.com/peterbmarks/radae_decoder.git baff453880f89bbfb7cb28f3caa8cb6b83410ee4 main
dep hamlib https://github.com/Hamlib/Hamlib.git 50b2a9310edc4a481d8a6ef10e948ea8554f97f9 master
dep sonde-decoders https://github.com/projecthorus/radiosonde_auto_rx.git 53d03c72ad18ce4357c0cedd1f4acf2bf1efb36e master
dep satdump https://github.com/SatDump/SatDump.git f3d82adbfe04e57c596b93479d687f4b830ee26c master
dep whisper https://github.com/ggml-org/whisper.cpp.git d09f61a708f3487afa956ff578e60eae5e7a233c master
dep dxlaprs https://github.com/oe5hpm/dxlAPRS.git 10bec72314d8fbefc3316054bf737e0bfc06e3fa master
dep fdkaac https://github.com/mstorsjo/fdk-aac.git 7c83d08002332b2730c845eec3497e6bf585dd28 master

# Receiver backends supported by current OpenWebRX+.
dep hackrf https://github.com/greatscottgadgets/hackrf.git 7f96cc8e3fa625c4263a71ba8dd44d1f6110e4fa master
dep soapyhackrf https://github.com/pothosware/SoapyHackRF.git master master
dep airspy https://github.com/airspy/airspyone_host.git fc61ab6be57ed61f0e2bdd9c6dfae74cacef57d0 master
dep soapyairspy https://github.com/pothosware/SoapyAirspy.git master master
dep airspyhf https://github.com/airspy/airspyhf.git 24fe8ffcb00b14f827268bbad89ae1392de055e5 master
dep soapyairspyhf https://github.com/pothosware/SoapyAirspyHF.git master master
dep libiio https://github.com/analogdevicesinc/libiio.git b6028fdeef888ab45f7c1dd6e4ed9480ae4b55e3 libiio-v0
dep libad9361 https://github.com/analogdevicesinc/libad9361-iio.git 486e0ad4da422760a8338a8582caf5783691c808 main
dep soapypluto https://github.com/pothosware/SoapyPlutoSDR.git 6d93ba806e4b2d2e1c5c70c9ba82027b37bdb257 master
dep limesuite https://github.com/myriadrf/LimeSuite.git 699d05b7212aa612a9802c219dd6621be88c77db master
dep soapyremote https://github.com/pothosware/SoapyRemote.git master master
dep soapyfcdpp https://github.com/pothosware/SoapyFCDPP.git master master
dep perseus https://github.com/Microtelecom/libperseus-sdr.git master master
dep bladerf https://github.com/Nuand/bladeRF.git master master
dep soapybladerf https://github.com/pothosware/SoapyBladeRF.git master master
dep uhd https://github.com/EttusResearch/uhd.git master master
dep soapyuhd https://github.com/pothosware/SoapyUHD.git master master
dep libmirisdr https://github.com/ericek111/libmirisdr-5.git master master
dep soapymiri https://github.com/ericek111/SoapyMiri.git main main
dep soapyafedri https://github.com/alexander-sholohov/SoapyAfedri.git 86d152cb87f56a16fb05dda2311de88b3fb06918 master
dep soapyiqfile https://github.com/utn-ba-rf-lab/SoapyIQFile.git main main
dep soapymalahit https://github.com/luarvique/SoapyMalahitRR.git 21dd5b2a539b726388b5127150f8b92b3e775d64 main
dep hydrasdr-host https://github.com/hydrasdr/hydrasdr-host.git 16942cbcbde47198abc6b7968c700ed0cbb8cc87 master
dep soapyhydra https://github.com/hydrasdr/SoapyHydraSDR.git 77b6ae2929830e8a01a0e8efa69e44d6ac438cde main
dep soapyelad https://github.com/DisagioDigitale/SoapyELAD.git 52dcf720a3d0a585bfe613a4e7b825dd07008a19 main
dep soapysx https://github.com/tejeez/sxxcvr.git 9705147dd8c189625071f3f163ea56119bda4a05 main
dep radioberry https://github.com/pa3gsb/Radioberry-2.x.git master master
dep soapysdrplay https://github.com/luarvique/SoapySDRPlay3.git master master
dep extio_sddc https://github.com/ik1xpv/ExtIO_sddc.git master master
dep sddc_connector https://github.com/jketterl/sddc_connector.git master master
dep runds_connector https://github.com/jketterl/runds_connector.git 06ca993a3c81ddb0a2581b1474895da07752a9e1 develop
dep hpsdrconnector https://github.com/jancona/hpsdrconnector.git master master
dep rockprog https://github.com/0xAF/rockprog-linux.git abe1440cff90a69e297fe7f3f16866d6555a2058 master

layout(){ mkdir -p "$SRC" "$BLD" "$STATE" "$LOG" "$PREFIX"/{bin,lib,include,share,etc,var} "$(dirname "$CONF")" "$DATA" "$TMP"; }

sudo_run(){ if [[ ${EUID:-$(id -u)} -eq 0 ]]; then "$@"; elif command -v sudo >/dev/null; then sudo "$@"; else die "sudo/root required for system prerequisites"; fi; }

install_system_deps(){
  [[ "$INSTALL_SYS" == 1 ]] || return 0
  local pm=""
  command -v zypper >/dev/null && pm=zypper
  [[ -n "$pm" ]] || { command -v apt-get >/dev/null && pm=apt; }
  [[ -n "$pm" ]] || { command -v dnf >/dev/null && pm=dnf; }
  [[ -n "$pm" ]] || { command -v pacman >/dev/null && pm=pacman; }
  [[ -n "$pm" ]] || { warn "Unknown package manager; continuing with prerequisite detection only."; return; }
  info "Installing broad source-build prerequisites with $pm"
  case "$pm" in
    zypper)
      sudo_run zypper --non-interactive refresh
      pkgs=(git cmake make ninja meson gcc gcc-c++ gcc-fortran autoconf automake libtool patch pkgconf python3 python3-devel python3-pip curl wget go
        libusb-1_0-devel fftw3-devel libfftw3_threads3 libsamplerate-devel systemd-devel protobuf-devel libicu-devel boost-devel
        libboost_program_options-devel libboost_filesystem-devel libboost_regex-devel libboost_log-devel libboost_serialization-devel
        libsndfile-devel libao-devel libxml2-devel libconfig-devel libjansson-devel libcurl-devel "pkgconfig(openssl)" ncurses-devel
        alsa-devel libpulse-devel "pkgconfig(sdl2)" "pkgconfig(libmpg123)" libfaad-devel "pkgconfig(hidapi-libusb)" avahi-devel "pkgconfig(zlib)"
        libpcap-devel speexdsp-devel hamlib hamlib-devel ImageMagick lame popt-devel libgpiod-devel volk-devel libpng16-devel armadillo-devel nng-devel libzstd-devel libtiff-devel sqlite3-devel
        libqt5-qtbase-devel libqt5-qtmultimedia-devel libqt5-qtserialport-devel libqt5-qtwebsockets-devel libqt5-qtsvg-devel libqt5-linguist-devel
        qt6-base-devel qt6-multimedia-devel qt6-serialport-devel qt6-websockets-devel cJSON-devel "cmake(Qt5LinguistTools)" "pkgconfig(libpng)")
      ;;
    apt)
      sudo_run apt-get update
      pkgs=(git cmake make ninja-build meson gcc g++ gfortran autoconf automake libtool patch pkg-config python3 python3-dev python3-venv python3-pip curl wget golang
        libusb-1.0-0-dev libfftw3-dev libsamplerate0-dev libudev-dev libprotobuf-dev protobuf-compiler libicu-dev libboost-dev
        libboost-program-options-dev libboost-filesystem-dev libboost-regex-dev libsndfile1-dev libao-dev libxml2-dev libconfig++-dev
        libjansson-dev libcurl4-openssl-dev libssl-dev libncurses-dev libasound2-dev libpulse-dev libsdl2-dev libmpg123-dev libfaad-dev
        libhidapi-dev libavahi-client-dev zlib1g-dev libpcap-dev libspeexdsp-dev libhamlib-dev imagemagick lame)
      ;;
    dnf)
      pkgs=(git cmake make ninja-build meson gcc gcc-c++ gcc-gfortran autoconf automake libtool patch pkgconf-pkg-config python3 python3-devel python3-pip curl wget golang
        libusb1-devel fftw-devel libsamplerate-devel systemd-devel protobuf-devel libicu-devel boost-devel libsndfile-devel libao-devel
        libxml2-devel libconfig-devel jansson-devel libcurl-devel openssl-devel ncurses-devel alsa-lib-devel pulseaudio-libs-devel SDL2-devel
        mpg123-devel faad2-devel hidapi-devel avahi-devel zlib-devel libpcap-devel speexdsp-devel hamlib-devel ImageMagick lame)
      ;;
    pacman)
      sudo_run pacman -Sy --noconfirm
      pkgs=(git cmake make ninja meson gcc autoconf automake libtool patch pkgconf python python-pip curl wget go libusb fftw libsamplerate
        systemd protobuf icu boost libsndfile libao libxml2 libconfig jansson openssl ncurses alsa-lib libpulse sdl2 mpg123 faad2 hidapi avahi
        zlib libpcap speexdsp hamlib imagemagick lame)
      ;;
  esac
  local p
  for p in "${pkgs[@]}"; do
    case "$pm" in
      zypper) sudo_run zypper --non-interactive install --no-recommends "$p" >/dev/null 2>&1 || warn "package unavailable: $p" ;;
      apt) sudo_run apt-get -y install --no-install-recommends "$p" >/dev/null 2>&1 || warn "package unavailable: $p" ;;
      dnf) sudo_run dnf -y install "$p" >/dev/null 2>&1 || warn "package unavailable: $p" ;;
      pacman) sudo_run pacman -S --needed --noconfirm "$p" >/dev/null 2>&1 || warn "package unavailable: $p" ;;
    esac
  done
}

env_setup(){
  layout
  for x in git cmake make "$PYTHON" pkg-config; do command -v "$x" >/dev/null || die "required tool missing: $x"; done
  [[ -x "$VENV/bin/python" ]] || "$PYTHON" -m venv "$VENV"
  export PATH="$VENV/bin:$PREFIX/bin:$PATH"
  export CMAKE_PREFIX_PATH="$PREFIX${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"
  export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig:$PREFIX/lib64/pkgconfig:$PREFIX/share/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
  export LD_LIBRARY_PATH="$PREFIX/lib:$PREFIX/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  export LIBRARY_PATH="$PREFIX/lib:$PREFIX/lib64${LIBRARY_PATH:+:$LIBRARY_PATH}"
  export CPATH="$PREFIX/include${CPATH:+:$CPATH}"
  export CPPFLAGS="-I$PREFIX/include ${CPPFLAGS:-}"
  export CFLAGS="-I$PREFIX/include ${CFLAGS:-}"
  export CXXFLAGS="-I$PREFIX/include ${CXXFLAGS:-}"
  export LDFLAGS="-L$PREFIX/lib -L$PREFIX/lib64 -Wl,-rpath,$PREFIX/lib -Wl,-rpath,$PREFIX/lib64 ${LDFLAGS:-}"
  export CMAKE_BUILD_PARALLEL_LEVEL="$JOBS"
  python -m pip install -q --upgrade pip setuptools wheel packaging
  python -m pip install -q --upgrade paho-mqtt meshtastic pycryptodome mako numpy ruamel.yaml
}

source_prepare(){
  local n="$1" d="$SRC/$1" target resolved
  [[ -d "$d/.git" ]] || git clone "${URL[$n]}" "$d"
  (
    cd "$d"
    git remote set-url origin "${URL[$n]}"
    git fetch --tags --force origin
    git reset --hard
    git clean -fdx
    target="${REF[$n]}"
    [[ "$LATEST" == 1 ]] && target="origin/${BRANCH[$n]}"
    if git rev-parse --verify -q "${target}^{commit}" >/dev/null; then
      resolved="$(git rev-parse "${target}^{commit}")"
    elif git rev-parse --verify -q "origin/${target}^{commit}" >/dev/null; then
      resolved="$(git rev-parse "origin/${target}^{commit}")"
    else
      echo "Unable to resolve dependency ref '$target' for $n" >&2
      return 1
    fi
    git checkout --detach "$resolved" || return 1
    [[ ! -f .gitmodules ]] || { git submodule sync --recursive && git submodule update --init --recursive; } || return 1
    apply_patches "$n"
  )
}

apply_patches(){
  local n="$1" d="$SRC/$1" patchdir="$ROOT/build/patches/$1" p
  [[ -d "$patchdir" ]] || return 0
  for p in "$patchdir"/*.patch; do
    [[ -f "$p" ]] || continue
    if (cd "$d" && git apply --check "$p"); then
      (cd "$d" && git apply "$p") || return 1
    elif (cd "$d" && git apply --reverse --check "$p"); then
      :
    else
      echo "Patch no longer applies: $p" >&2
      return 1
    fi
  done
}

patched_dep(){
  local n="$1"
  shift
  source_prepare "$n" || return 1
  apply_patches "$n" || return 1
  cmake_build "$n" "$SRC/$n" "$@"
}

replace_exact(){
  python - "$1" "$2" "$3" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); old=sys.argv[2]; new=sys.argv[3]; data=p.read_text()
if new in data: raise SystemExit(0)
if old not in data: raise SystemExit(f"expected text not found in {p}: {old!r}")
p.write_text(data.replace(old,new))
PY
}

patch_codecserver(){
  local d="$SRC/codecserver"
  replace_exact "$d/CMakeLists.txt" 'set(CMAKE_CXX_STANDARD 11)' $'set(CMAKE_CXX_STANDARD 17)\nset(CMAKE_CXX_STANDARD_REQUIRED ON)'
  replace_exact "$d/CMakeLists.txt" $'include(GNUInstallDirs)\ninclude(FindProtobuf)\n\nfind_package(Threads REQUIRED)\nfind_package(Protobuf 3.0 REQUIRED)' $'include(GNUInstallDirs)\n\nfind_package(Threads REQUIRED)\nfind_package(protobuf CONFIG REQUIRED)'
  cat >"$d/src/lib/proto/CMakeLists.txt" <<'EOF'
file(GLOB CODECSERVER_PROTO_FILES "*.proto")
add_library(codecserver_proto OBJECT ${CODECSERVER_PROTO_FILES})
target_link_libraries(codecserver_proto PUBLIC protobuf::libprotobuf)
protobuf_generate(TARGET codecserver_proto LANGUAGE cpp OUT_VAR CODECSERVER_PROTO_GENERATED_FILES)
set(CODECSERVER_PROTO_HEADERS ${CODECSERVER_PROTO_GENERATED_FILES})
list(FILTER CODECSERVER_PROTO_HEADERS INCLUDE REGEX "\\.pb\\.h$")
install(FILES ${CODECSERVER_PROTO_FILES} DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/codecserver/proto)
install(FILES ${CODECSERVER_PROTO_HEADERS} DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/codecserver/proto)
EOF
  replace_exact "$d/src/lib/CMakeLists.txt" 'target_link_libraries(codecserver PUBLIC ${Protobuf_LIBRARIES})' 'target_link_libraries(codecserver PUBLIC protobuf::libprotobuf)'
  replace_exact "$d/src/lib/Config.cmake.in" 'find_dependency(Protobuf 3.0)' 'find_dependency(protobuf CONFIG)'
}

patch_js8py(){
  local f="$SRC/js8py/js8py/jsc.py"
  replace_exact "$f" 'import pkg_resources' 'from importlib import resources'
  replace_exact "$f" 'with pkg_resources.resource_stream("js8py", "jsc_map.pickle") as f:' 'with resources.files("js8py").joinpath("jsc_map.pickle").open("rb") as f:'
}

cmake_build(){
  local n="$1" sd="$2"; shift 2
  rm -rf "$BLD/$n"
  cmake -S "$sd" -B "$BLD/$n" -G "$GENERATOR" -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_INSTALL_PREFIX="$PREFIX" -DCMAKE_INSTALL_LIBDIR=lib \
    -DCMAKE_INSTALL_RPATH="$PREFIX/lib;$PREFIX/lib64" -DCMAKE_PREFIX_PATH="$PREFIX" "$@" || return 1
  cmake --build "$BLD/$n" --parallel "$JOBS" || return 1
  cmake --install "$BLD/$n" || return 1
}
cmake_dep(){ local n="$1"; shift; source_prepare "$n" || return 1; cmake_build "$n" "$SRC/$n" "$@"; }
pip_dep(){ source_prepare "$1" || return 1; python -m pip install --no-build-isolation --no-cache-dir "$SRC/$1"; }

declare -A BUILD_REV=(
  [fftw]=3
)

stamp(){
  local rev="${BUILD_REV[$1]:-2}"
  printf '%s|latest=%s|v=%s\n' "${REF[$1]:-repo}" "$LATEST" "$rev"
}
donep(){ [[ "$FORCE" != 1 && -f "$STATE/$1.ok" && "$(cat "$STATE/$1.ok")" == "$(stamp "$1")" ]]; }
step(){
  local n="$1" required="$2"; shift 2
  donep "$n" && { ok "$n already built"; return; }
  info "Building $n"; rm -f "$LOG/$n.log"; set +e; ( set -Eeuo pipefail; "$@" ) 2>&1 | tee "$LOG/$n.log"; local rc=${PIPESTATUS[0]}; set -e
  if [[ $rc -eq 0 ]]; then stamp "$n" >"$STATE/$n.ok"; ok "$n"; return; fi
  if [[ "$required" == 1 || "$STRICT" == 1 ]]; then die "$n failed; see $LOG/$n.log"; fi
  warn "$n failed/skipped; see $LOG/$n.log"; echo "$n" >>"$STATE/optional-failures.txt"
}

# Core
b_fftw(){
  source_prepare fftw || return 1
  rm -f "$PREFIX/lib"/libfftw3*.so* "$PREFIX/lib"/libfftw3*.a "$PREFIX/lib/pkgconfig"/fftw3*.pc 2>/dev/null || true
  (
    cd "$SRC/fftw"
    ./bootstrap.sh >/dev/null 2>&1 || autoreconf -fiv
    ./configure --prefix="$PREFIX" --libdir="$PREFIX/lib" --enable-shared --disable-static --enable-threads --disable-fortran
    make -j"$JOBS"
    make install
    make distclean
    ./configure --prefix="$PREFIX" --libdir="$PREFIX/lib" --enable-shared --disable-static --enable-threads --enable-float --disable-fortran
    make -j"$JOBS"
    make install
  ) || return 1

  for lib in "$PREFIX/lib/libfftw3.so.3" "$PREFIX/lib/libfftw3f.so.3"; do
    [[ -e "$lib" ]] || { echo "Missing FFTW library: $lib" >&2; return 1; }
    if ldd -r "$lib" 2>&1 | grep -q "undefined symbol"; then
      echo "FFTW library has unresolved symbols: $lib" >&2
      ldd -r "$lib" >&2 || true
      return 1
    fi
  done
}

b_rtlsdr(){ cmake_dep rtl-sdr -DDETACH_KERNEL_DRIVER=ON -DINSTALL_UDEV_RULES=OFF; }
b_soapy(){ cmake_dep soapysdr -DENABLE_PYTHON=OFF -DENABLE_TESTS=OFF; }
b_pycsdr(){ pip_dep pycsdr; install -d "$PREFIX/include/pycsdr"; for h in pycsdr.hpp reader.hpp writer.hpp source.hpp sink.hpp module.hpp buffer.hpp bufferreader.hpp; do install -m0644 "$SRC/pycsdr/src/$h" "$PREFIX/include/pycsdr/$h"; done; }
b_codecserver(){ source_prepare codecserver; patch_codecserver; cmake_build codecserver "$SRC/codecserver"; install -d "$PREFIX/etc/codecserver"; install -m0644 "$SRC/codecserver/conf/codecserver.conf" "$PREFIX/etc/codecserver/codecserver.conf"; }
b_js8py(){ source_prepare js8py; patch_js8py; python -m pip install --no-build-isolation --no-cache-dir "$SRC/js8py"; }
b_pydigiham(){ source_prepare pydigiham; python -m pip install --no-build-isolation --no-cache-dir "$SRC/pydigiham"; }

# Decoder special cases
b_redsea(){ source_prepare redsea; rm -rf "$BLD/redsea"; meson setup "$BLD/redsea" "$SRC/redsea" --prefix="$PREFIX" --libdir=lib --buildtype=release -Dbuild_tests=false; meson compile -C "$BLD/redsea" -j "$JOBS"; meson install -C "$BLD/redsea"; }
b_dump1090(){ source_prepare dump1090; (cd "$SRC/dump1090"; make clean; make -j"$JOBS" dump1090 RTLSDR=no BLADERF=no HACKRF=no LIMESDR=no SOAPYSDR=no DUMP1090_VERSION="$(git describe --tags --always --dirty)"; install -Dm755 dump1090 "$PREFIX/bin/dump1090"); }
b_dump978(){ source_prepare dump978; (cd "$SRC/dump978"; make clean; make -j"$JOBS" dump978-fa; install -Dm755 dump978-fa "$PREFIX/bin/dump978"); }
b_skimmer(){ source_prepare csdr-skimmer; (cd "$SRC/csdr-skimmer"; make clean || true; make -j"$JOBS" INCDIRS="-I$PREFIX/include" LIBDIRS="-L$PREFIX/lib -L$PREFIX/lib64 -Wl,-rpath,$PREFIX/lib"; install -Dm755 csdr-cwskimmer "$PREFIX/bin/csdr-cwskimmer"; install -Dm755 csdr-rttyskimmer "$PREFIX/bin/csdr-rttyskimmer"); }
b_nrsc5(){ source_prepare nrsc5; cmake_build nrsc5 "$SRC/nrsc5" -DUSE_SYSTEM_FFTW=ON -DUSE_SYSTEM_RTLSDR=ON -DUSE_SYSTEM_LIBUSB=ON -DUSE_SYSTEM_LIBAO=ON -DUSE_FAAD2=ON -DFAAD2_CMAKE_ARGS=-DCMAKE_INSTALL_LIBDIR=lib -DBUILD_CLI=ON; }
b_codec2(){ cmake_dep codec2 -DUNITTEST=OFF; local f; f="$(find "$BLD/codec2" -type f -name freedv_rx -perm -111 | head -1 || true)"; [[ -n "$f" ]] || return 1; install -Dm755 "$f" "$PREFIX/bin/freedv_rx"; }

b_msk144(){
  source_prepare msk144 || return 1
  rm -rf "$BLD/msk144"
  cmake -S "$SRC/msk144" -B "$BLD/msk144" -G "Unix Makefiles"     -DCMAKE_BUILD_TYPE=Release     -DCMAKE_INSTALL_PREFIX="$PREFIX"     -DCMAKE_INSTALL_LIBDIR=lib     -DCMAKE_INSTALL_RPATH="$PREFIX/lib;$PREFIX/lib64"     -DCMAKE_PREFIX_PATH="$PREFIX" || return 1
  cmake --build "$BLD/msk144" --parallel "$JOBS" || return 1
  cmake --install "$BLD/msk144" || return 1
}
b_aprs(){ source_prepare aprs-symbols; rm -rf "$PREFIX/share/aprs-symbols"; mkdir -p "$PREFIX/share/aprs-symbols"; cp -a "$SRC/aprs-symbols/." "$PREFIX/share/aprs-symbols/"; rm -rf "$PREFIX/share/aprs-symbols/.git"; }
b_rade(){ source_prepare rade; cmake_build rade "$SRC/rade" -DBUILD_GUI=OFF; local f; f="$(find "$BLD/rade" -type f -name 'webrx_rade_decode' -perm -111 | head -1 || true)"; [[ -n "$f" ]] || return 1; install -Dm755 "$f" "$PREFIX/bin/webrx_rade_decode"; }
b_hamlib(){ source_prepare hamlib; (cd "$SRC/hamlib"; ./bootstrap || autoreconf -i; ./configure --prefix="$PREFIX" --disable-static CPPFLAGS="$CPPFLAGS" LDFLAGS="$LDFLAGS"; make -j"$JOBS"; make install); }
b_sonde(){ source_prepare sonde-decoders; (cd "$SRC/sonde-decoders/demod/mod"; make clean || true; make -j"$JOBS"; for x in rs41mod dfm09mod m10mod m20mod mts01mod; do install -Dm755 "$x" "$PREFIX/bin/$x"; done); }
b_satdump(){ cmake_dep satdump -DBUILD_GUI=OFF -DBUILD_TESTING=OFF -DBUILD_TOOLS=OFF -DBUILD_OPENCL=OFF -DBUILD_DOCS=OFF -DENABLE_CRASHDUMP=OFF -DENABLE_INSTALL=ON; }
b_whisper(){ cmake_dep whisper -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_EXAMPLES=ON -DWHISPER_BUILD_SERVER=ON -DWHISPER_CURL=OFF; local s; s="$(find "$BLD/whisper" -type f -name 'whisper-server' -perm -111 | head -1 || true)"; [[ -z "$s" ]] || install -Dm755 "$s" "$PREFIX/bin/whisper-server"; }
b_dxlaprs(){ source_prepare dxlaprs; (cd "$SRC/dxlaprs/src"; make clean || true; make lorarx; local f; f="$(find .. -type f -name lorarx -perm -111 | head -1)"; install -Dm755 "$f" "$PREFIX/bin/lorarx"); }
b_fdkaac(){ source_prepare fdkaac; (cd "$SRC/fdkaac"; autoreconf -fiv; ./configure --prefix="$PREFIX" --disable-static; make -j"$JOBS"; make install); }
b_dream(){ source_prepare dream; local qmake; qmake="$(command -v qmake-qt5 || command -v qmake || true)"; [[ -n "$qmake" ]] || return 1; (cd "$SRC/dream"; make distclean >/dev/null 2>&1 || true; "$qmake" CONFIG+=console CONFIG+=fdk-aac dream.pro; make -j"$JOBS"; install -Dm755 dream "$PREFIX/bin/dream"); }

# Receiver special cases
b_hackrf(){ source_prepare hackrf || return 1; cmake_build hackrf "$SRC/hackrf/host" -DINSTALL_UDEV_RULES=OFF; }
b_perseus(){ source_prepare perseus; (cd "$SRC/perseus"; ./bootstrap.sh; ./configure --prefix="$PREFIX" CPPFLAGS="$CPPFLAGS" LDFLAGS="$LDFLAGS"; make -j"$JOBS"; make install); }
b_libad9361(){ source_prepare libad9361 || return 1; cmake_build libad9361 "$SRC/libad9361" -DBUILD_TESTS=OFF -DWITH_DOC=OFF; }
b_soapypluto(){ source_prepare soapypluto || return 1; cmake_build soapypluto "$SRC/soapypluto"; }
b_direwolf(){ source_prepare direwolf || return 1; cmake_build direwolf "$SRC/direwolf" -DINSTALL_UDEV_RULES=OFF; }
b_soapyafedri(){ source_prepare soapyafedri; cmake_build soapyafedri "$SRC/soapyafedri"; }
b_runds(){ source_prepare runds_connector; cmake_build runds_connector "$SRC/runds_connector"; }
b_hydrasdr_host(){ cmake_dep hydrasdr-host -DINSTALL_UDEV_RULES=OFF -DENABLE_SHARED_LIB=ON; }
b_soapyelad(){ source_prepare soapyelad || return 1; cmake_build soapyelad "$SRC/soapyelad/src"; }
b_soapysx(){ source_prepare soapysx || return 1; cmake_build soapysx "$SRC/soapysx/SoapySX" -DINSTALL_PIPEWIRE_CONF=OFF; }
b_bladerf(){ source_prepare bladerf || return 1; cmake_build bladerf "$SRC/bladerf/host" -DBUILD_DOCUMENTATION=OFF -DTREAT_WARNINGS_AS_ERRORS=OFF -DINSTALL_UDEV_RULES=OFF -DINSTALL_SHELL_COMPLETIONS=OFF; }
b_uhd(){ source_prepare uhd || return 1; cmake_build uhd "$SRC/uhd/host" -DPYTHON_EXECUTABLE="$VENV/bin/python" -DPython3_EXECUTABLE="$VENV/bin/python" -DENABLE_PYTHON_API=OFF -DENABLE_EXAMPLES=OFF -DENABLE_TESTS=OFF -DENABLE_MANUAL=OFF -DENABLE_DOXYGEN=OFF; }
b_radioberry(){ case "$(uname -m)" in arm*|aarch64) source_prepare radioberry; cmake_build radioberry "$SRC/radioberry/SBC/rpi-4/SoapyRadioberrySDR";; *) warn "Radioberry skipped on $(uname -m)";; esac; }
b_sdrplay(){ if ! (ldconfig -p 2>/dev/null | grep -qi libsdrplay_api || find /usr /opt -name 'libsdrplay_api.so*' -print -quit 2>/dev/null | grep -q .); then warn "SDRplay vendor API v3 not installed; wrapper skipped"; return 0; fi; cmake_dep soapysdrplay; }
b_sddc(){ command -v nvcc >/dev/null || { warn "CUDA/nvcc unavailable; sddc_connector skipped"; return 0; }; cmake_dep sddc_connector; }
b_hpsdr(){ source_prepare hpsdrconnector; command -v go >/dev/null || return 1; (cd "$SRC/hpsdrconnector"; go build -o "$PREFIX/bin/hpsdrconnector" .); }
b_rockprog(){ source_prepare rockprog || return 1; (cd "$SRC/rockprog"; make clean || true; make -j"$JOBS"; install -Dm755 rockprog "$PREFIX/bin/rockprog"); }

core_plan(){
  step fftw 1 b_fftw
  step rtl-sdr 1 b_rtlsdr
  step soapysdr 1 b_soapy
  step soapyrtlsdr 0 cmake_dep soapyrtlsdr
  step csdr 1 cmake_dep csdr
  step pycsdr 1 b_pycsdr
  step owrx_connector 1 cmake_dep owrx_connector
  step codecserver 0 b_codecserver
  step digiham 0 cmake_dep digiham
  step pydigiham 0 b_pydigiham
  step csdr-eti 0 cmake_dep csdr-eti
  step pycsdr-eti 0 pip_dep pycsdr-eti
  step js8py 0 b_js8py
}

decoders_plan(){
  step liquid-dsp 0 cmake_dep liquid-dsp -DBUILD_EXAMPLES=OFF -DBUILD_AUTOTESTS=OFF -DBUILD_BENCHMARKS=OFF -DBUILD_STATIC_LIBS=OFF
  step redsea 0 b_redsea
  step libacars 0 cmake_dep libacars
  step acarsdec 0 cmake_dep acarsdec -DRTLSDR=OFF -DSOAPYSDR=OFF -DAIRSPY=OFF -DSDRPLAY=OFF -DALSA=OFF -DSNDFILE=ON -DLIBACARS=ON -DMQTT=OFF
  step dumpvdl2 0 cmake_dep dumpvdl2 -DRTLSDR=OFF -DMIRISDR=OFF -DSDRPLAY=OFF -DSDRPLAY3=OFF -DSOAPYSDR=OFF -DETSY_STATSD=OFF -DSQLITE=OFF -DZMQ=OFF
  step dumphfdl 0 cmake_dep dumphfdl -DSOAPYSDR=OFF -DETSY_STATSD=OFF -DSQLITE=OFF -DZMQ=OFF -DRDKAFKA=OFF
  step dump1090 0 b_dump1090
  step dump978 0 b_dump978
  step nrsc5 0 b_nrsc5
  step multimon-ng 0 cmake_dep multimon-ng -DX11_SUPPORT=OFF -DPULSE_AUDIO_SUPPORT=OFF -DSDL3_SCOPE=OFF -DBUILD_GEN_NG=OFF
  step csdr-skimmer 0 b_skimmer
  step rtl_433 0 cmake_dep rtl_433 -DENABLE_SOAPYSDR=AUTO -DENABLE_RTLSDR=AUTO
  step direwolf 0 b_direwolf
  step codec2 0 b_codec2
  step m17 0 cmake_dep m17
  step msk144 0 b_msk144
  step dablin 0 cmake_dep dablin
  step aprs-symbols 0 b_aprs
  step hamlib 0 b_hamlib
  step sonde-decoders 0 b_sonde
  step satdump 0 b_satdump
  step whisper 0 b_whisper
  step dxlaprs 0 b_dxlaprs
  step wsjtx 0 cmake_dep wsjtx -DWSJT_SKIP_MAP65=ON -DWSJT_BUILD_UTILS=OFF -DWSJT_SKIP_MANPAGES=ON
  step js8call 0 cmake_dep js8call
  step fdkaac 0 b_fdkaac
  step dream 0 b_dream
  step rade 0 b_rade
}

receivers_plan(){
  step hackrf 0 b_hackrf; step soapyhackrf 0 cmake_dep soapyhackrf
  step airspy 0 cmake_dep airspy; step soapyairspy 0 cmake_dep soapyairspy
  step airspyhf 0 cmake_dep airspyhf; step soapyairspyhf 0 cmake_dep soapyairspyhf
  step libiio 0 cmake_dep libiio -DWITH_TESTS=OFF -DWITH_EXAMPLES=OFF -DWITH_IIOD=OFF -DWITH_LOCAL_CONFIG=OFF
  step libad9361 0 b_libad9361; step soapypluto 0 b_soapypluto
  step limesuite 0 cmake_dep limesuite -DENABLE_EXAMPLES=OFF -DENABLE_DESKTOP=OFF -DENABLE_QUICKTEST=OFF -DENABLE_OCTAVE=OFF -DENABLE_GUI=OFF
  step soapyremote 0 cmake_dep soapyremote; step soapyfcdpp 0 cmake_dep soapyfcdpp
  step perseus 0 b_perseus
  step bladerf 0 b_bladerf; step soapybladerf 0 cmake_dep soapybladerf
  step uhd 0 b_uhd; step soapyuhd 0 cmake_dep soapyuhd
  step libmirisdr 0 cmake_dep libmirisdr; step soapymiri 0 cmake_dep soapymiri
  step soapyafedri 0 b_soapyafedri; step soapyiqfile 0 cmake_dep soapyiqfile
  step soapymalahit 0 cmake_dep soapymalahit; step hydrasdr-host 0 b_hydrasdr_host; step soapyhydra 0 cmake_dep soapyhydra
  step soapyelad 0 b_soapyelad; step soapysx 0 b_soapysx
  step radioberry 0 b_radioberry; step soapysdrplay 0 b_sdrplay
  step extio_sddc 0 cmake_dep extio_sddc; step sddc_connector 0 b_sddc
  step runds_connector 0 b_runds; step hpsdrconnector 0 b_hpsdr
  step rockprog 0 b_rockprog
}

install_app(){
  python -m pip install --no-build-isolation --editable "$ROOT"
  if [[ ! -f "$CONF" ]]; then
    cat >"$CONF" <<EOF
[core]
data_directory = $DATA
temporary_directory = $TMP
log_level = INFO

[web]
port = 8073
ipv6 = true
bind_address = ::1

[aprs]
symbols_path = $PREFIX/share/aprs-symbols/png
EOF
  fi
  cat >"$PREFIX/env.sh" <<EOF
export OWRX_PREFIX="$PREFIX"
export PATH="$VENV/bin:$PREFIX/bin:\$PATH"
export CMAKE_PREFIX_PATH="$PREFIX\${CMAKE_PREFIX_PATH:+:\$CMAKE_PREFIX_PATH}"
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig:$PREFIX/lib64/pkgconfig:$PREFIX/share/pkgconfig\${PKG_CONFIG_PATH:+:\$PKG_CONFIG_PATH}"
export LD_LIBRARY_PATH="$PREFIX/lib:$PREFIX/lib64\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
EOF
}

check(){ if command -v "$2" >/dev/null 2>&1; then printf '  %-28s PASS  %s\n' "$1" "$(command -v "$2")"; else printf '  %-28s MISS\n' "$1"; fi; }
doctor(){
  env_setup >/dev/null 2>&1 || true
  echo "OpenWebRX+ source-build doctor"; echo "Prefix: $PREFIX"; echo "Binary/module presence (feature-report is authoritative):"; echo
  check openwebrx openwebrx; check rtl_connector rtl_connector; check soapy_connector soapy_connector; check nmux nmux
  echo; echo Decoders:
  check ADSB/dump1090 dump1090; check UAT/dump978 dump978; check HFDL dumphfdl; check VDL2 dumpvdl2; check ACARS acarsdec
  check ISM/rtl_433 rtl_433; check Packet/direwolf direwolf; check FreeDV freedv_rx; check M17 m17-demod; check MSK144 msk144decoder
  check WSJT/jt9 jt9; check WSJT/wsprd wsprd; check JS8 js8; check DRM dream; check RDS redsea; check DAB dablin; check HDRadio nrsc5
  check multimon multimon-ng; check skimmer csdr-rttyskimmer; check radiosonde/rs41 rs41mod; check LoRa/lorarx lorarx; check wxsat/satdump satdump; check rigctl rigctl
  echo; echo Receiver helpers:
  check Airspy airspy_rx; check Perseus perseustest; check RunDS runds_connector; check HPSDR hpsdrconnector; check SDDC sddc_connector; check FiFi/rockprog rockprog
  command -v SoapySDRUtil >/dev/null 2>&1 && { echo; SoapySDRUtil --info 2>/dev/null || true; }
}

check_refs(){
  local n ref
  for n in "${!URL[@]}"; do
    ref="${REF[$n]}"
    # Full commit SHAs are immutable lock entries; symbolic refs must be
    # advertised by the remote. This catches misspelled/nonexistent tags
    # and branches without cloning every dependency.
    if [[ "$ref" =~ ^[0-9a-fA-F]{40}$ ]]; then
      continue
    fi
    info "Checking ref $n -> $ref"
    if ! git ls-remote --exit-code "${URL[$n]}"         "$ref" "refs/heads/$ref" "refs/tags/$ref" "refs/tags/$ref^{}"         | grep -q .; then
      die "Dependency ref does not exist: $n -> $ref (${URL[$n]})"
    fi
  done
  ok "Symbolic dependency refs are valid"
}

check_patches(){
  layout
  local n
  for n in pydigiham direwolf libad9361 nrsc5 rade runds_connector soapyafedri soapypluto; do
    info "Checking patches for $n"
    source_prepare "$n"
    apply_patches "$n"
    (cd "$SRC/$n"; git reset --hard; git clean -fdx)
    ok "$n patches apply"
  done
}

failure_report(){
  echo "Source-build optional failures"
  if [[ ! -s "$STATE/optional-failures.txt" ]]; then
    echo "  none recorded"
    return 0
  fi
  while IFS= read -r n; do
    [[ -n "$n" ]] || continue
    echo
    echo "===== $n ====="
    if [[ -f "$LOG/$n.log" ]]; then
      echo "-- error excerpts --"
      grep -nE 'FAILED:|CMake Error|(^|[^[:alpha:]])error:|fatal:|undefined reference|multiple rules generate|Permission denied|Unable to resolve|Could NOT find|required packages were not found|Package .* not found' "$LOG/$n.log" | head -n 40 || true
      echo "-- final 60 lines --"
      tail -n 60 "$LOG/$n.log"
    else
      echo "No log file: $LOG/$n.log"
    fi
  done < <(sort -u "$STATE/optional-failures.txt")
}

feature_report(){
  env_setup >/dev/null 2>&1
  [[ -f "$CONF" ]] || die "config missing: $CONF"
  (cd "$ROOT"; python - "$CONF" <<'PY'
from pathlib import Path
import sys
from owrx.config.core import CoreConfig
CoreConfig.load(Path(sys.argv[1]))
from owrx.feature import FeatureDetector
fd=FeatureDetector()
for name, entry in sorted(fd.feature_report().items()):
    missing=[k for k,v in entry["requirements"].items() if not v["available"]]
    print(f"{name:28} {'PASS' if entry['available'] else 'MISS'}" + ("" if not missing else "  missing: "+", ".join(missing)))
PY
  )
}

build_all(){
  layout; install_system_deps; env_setup; : >"$STATE/optional-failures.txt"
  case "$PROFILE" in
    core) core_plan ;;
    decoders) core_plan; decoders_plan ;;
    receivers) core_plan; receivers_plan ;;
    full) core_plan; decoders_plan; receivers_plan ;;
    *) die "profile must be full|core|decoders|receivers" ;;
  esac
  install_app; doctor; feature_report || true
  if [[ -s "$STATE/optional-failures.txt" ]]; then warn "Optional failures:"; sort -u "$STATE/optional-failures.txt" >&2; warn "Logs: $LOG"; else ok "Requested source build completed."; fi
  info "Run: $0 run"
}

run_app(){ env_setup >/dev/null 2>&1; [[ -f "$CONF" ]] || die "run build first"; cd "$ROOT"; exec openwebrx -c "$CONF" --debug; }
usage(){ cat <<EOF
Usage: ./build-linux.sh [options] [build|run|doctor|feature-report|failures|check-refs|check-patches|env|clean|uninstall]
  --profile full|core|decoders|receivers
  --prefix PATH
  --latest                 use dependency branch heads instead of locked refs
  --force                  rebuild successful stamped components
  --strict                 optional component failures are fatal
  --no-system-packages     do not call zypper/apt/dnf/pacman

Default: full source build into ~/.local/openwebrx-source.
EOF
}

CMD=build
while [[ $# -gt 0 ]]; do
  case "$1" in
    build|run|doctor|feature-report|failures|check-refs|check-patches|env|clean|uninstall|help) CMD="$1"; shift ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --prefix) PREFIX="$2"; VENV="$PREFIX/venv"; CONF="$PREFIX/etc/openwebrx/openwebrx.conf"; DATA="$PREFIX/var/lib/openwebrx"; TMP="$PREFIX/var/tmp"; shift 2 ;;
    --latest) LATEST=1; shift ;;
    --force) FORCE=1; shift ;;
    --strict) STRICT=1; shift ;;
    --no-system-packages) INSTALL_SYS=0; shift ;;
    -h|--help) CMD=help; shift ;;
    *) die "unknown argument: $1" ;;
  esac
done

case "$CMD" in
  build) build_all ;;
  run) run_app ;;
  doctor) doctor ;;
  feature-report) feature_report ;;
  failures) failure_report ;;
  check-refs) check_refs ;;
  check-patches) check_patches ;;
  env) env_setup >/dev/null 2>&1; cat "$PREFIX/env.sh" ;;
  clean) rm -rf "$WORK" ;;
  uninstall) rm -rf "$PREFIX" "$WORK" ;;
  help) usage ;;
esac
