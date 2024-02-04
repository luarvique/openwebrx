#!/bin/bash
set -euxo pipefail
export MAKEFLAGS="-j12"

function cmakebuild() {
  cd $1
  if [[ ! -z "${2:-}" ]]; then
    git checkout $2
  fi
  if [[ -f ".gitmodules" ]]; then
    git submodule update --init
  fi
  mkdir build
  cd build
  cmake ${CMAKE_ARGS:-} ..
  make
  make install
  cd ../..
  rm -rf $1
}

export MARCH=native
case `uname -m` in
    arm*)
        #SDRPLAY_BINARY=SDRplay_RSP_API-ARM32-3.07.2.run
        SDRPLAY_BINARY=SDRplay_RSP_API-Linux-3.14.0.run
        ;;
    aarch64*)
        #SDRPLAY_BINARY=SDRplay_RSP_API-ARM64-3.07.1.run
        SDRPLAY_BINARY=SDRplay_RSP_API-Linux-3.14.0.run
        ;;
    x86_64*)
        SDRPLAY_BINARY=SDRplay_RSP_API-Linux-3.07.2.run
        export MARCH=x86-64
        ;;
esac


echo "+ Install dev packages..."
BUILD_PACKAGES="git cmake make patch wget sudo gcc g++ libusb-1.0-0-dev libsoapysdr-dev debhelper cmake libprotobuf-dev protobuf-compiler libcodecserver-dev build-essential xxd qt5-qmake libpulse-dev libfaad-dev libopus-dev libfftw3-dev  pkg-config libglib2.0-dev libconfig++-dev libliquid-dev libairspyhf-dev libpopt-dev libiio-dev libad9361-dev libhidapi-dev libasound2-dev qtmultimedia5-dev  libqt5serialport5-dev qttools5-dev qttools5-dev-tools libboost-all-dev libfftw3-dev libreadline-dev libusb-1.0-0-dev libudev-dev asciidoctor gfortran libhamlib-dev libsndfile1-dev libliquid-dev autoconf build-essential automake"
apt-get -y install --no-install-recommends $BUILD_PACKAGES

echo "+ Install SDRPlay..."
wget --no-http-keep-alive https://www.sdrplay.com/software/$SDRPLAY_BINARY
sh $SDRPLAY_BINARY --noexec --target sdrplay
patch --verbose -Np0 < /files/sdrplay/install-lib.`uname -m`.patch
cd sdrplay
mkdir -p /etc/udev/rules.d
./install_lib.sh
cd ..
rm -rf sdrplay
rm $SDRPLAY_BINARY

echo "+ Install redsea (RDS)"
git clone https://github.com/windytan/redsea.git
pushd redsea
./autogen.sh && ./configure && make && make install
popd

echo "+ Install PerseusSDR..."
git clone https://github.com/Microtelecom/libperseus-sdr.git
cd libperseus-sdr
# latest from master as of 2020-09-04
git checkout c2c95daeaa08bf0daed0e8ada970ab17cc264e1b
sed -i 's/-march=native/-march='${MARCH}'/g' configure.ac
./bootstrap.sh
./configure
make
make install
ldconfig /etc/ld.so.conf.d
cd ..
rm -rf libperseus-sdr

echo "+ Install AirSpyHF+..."
git clone https://github.com/pothosware/SoapyAirspyHF.git
cmakebuild SoapyAirspyHF 5488dac5b44f1432ce67b40b915f7e61d3bd4853


echo "+ Install RockOProg..."
git clone https://github.com/0xAF/rockprog-linux
cd rockprog-linux
make
cp rockprog /usr/local/bin/
cd ..
rm -rf rockprog-linux

echo "+ Install PlutoSDR..."
git clone https://github.com/pothosware/SoapyPlutoSDR.git
cmakebuild SoapyPlutoSDR 93717b32ef052e0dfa717aa2c1a4eb27af16111f

echo "+ Install FCDPP..."
git clone https://github.com/pothosware/SoapyFCDPP.git
cmakebuild SoapyFCDPP soapy-fcdpp-0.1.1

echo "+ Install FreeDV..."
git clone https://github.com/drowe67/codec2.git
cd codec2
mkdir build
cd build
cmake ..
make
make install
install -m 0755 src/freedv_rx /usr/local/bin
cd ../..
rm -rf codec2

echo "+ Install wsjtx..."
WSJT_DIR=wsjtx-2.6.1
WSJT_TGZ=${WSJT_DIR}.tgz
wget https://downloads.sourceforge.net/project/wsjt/${WSJT_DIR}/${WSJT_TGZ}
tar xfz ${WSJT_TGZ}
patch -Np0 -d ${WSJT_DIR} < /files/wsjtx/wsjtx-hamlib.patch
mv /files/wsjtx/wsjtx.patch ${WSJT_DIR}
cmakebuild ${WSJT_DIR}
rm ${WSJT_TGZ}

echo "+ Install ACARSDEC..."
git clone https://github.com/szpajder/libacars.git
cmakebuild libacars v2.1.4

git clone https://github.com/TLeconte/acarsdec.git
sed -i 's/-march=native/-march='${MARCH}'/g' acarsdec/CMakeLists.txt
cmakebuild acarsdec

echo "+ Install HFDL..."
git clone https://github.com/szpajder/dumphfdl.git
cmakebuild dumphfdl v1.4.1

git clone https://github.com/szpajder/dumpvdl2.git
cmakebuild dumpvdl2

echo "+ Install Dream (DRM)..."
wget https://downloads.sourceforge.net/project/drm/dream/2.1.1/dream-2.1.1-svn808.tar.gz
tar xvfz dream-2.1.1-svn808.tar.gz
pushd dream
patch -Np0 < /files/dream/dream.patch
qmake CONFIG+=console
make
make install
popd
rm -rf dream
rm dream-2.1.1-svn808.tar.gz


echo "+ Clean..."
SUDO_FORCE_REMOVE=yes apt-get -y purge --autoremove $BUILD_PACKAGES systemd udev dbus
apt-get clean
rm -rf /var/lib/apt/lists/*
rm -rf /files
