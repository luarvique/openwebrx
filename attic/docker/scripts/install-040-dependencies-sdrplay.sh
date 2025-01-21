#!/bin/bash
set -euxo pipefail

function cmakebuild() {
  cd $1
  if [[ ! -z "${2:-}" ]]; then
    git checkout $2
  fi
  mkdir build
  cd build
  cmake ..
  make
  make install
  cd ../..
  rm -rf $1
}

cd /tmp

STATIC_PACKAGES="libusb-1.0.0 udev"
BUILD_PACKAGES="git cmake make patch wget sudo gcc g++ libusb-1.0-0-dev"

if [[ -z ${1:-} ]]; then
  apt-get update
  apt-get -y install --no-install-recommends $STATIC_PACKAGES $BUILD_PACKAGES

  ARCH=$(uname -m)

  case $ARCH in
    x86_64)
      #BINARY=SDRplay_RSP_API-Linux-3.07.1.run
      BINARY=SDRplay_RSP_API-Linux-3.14.0.run
      BRANCH=master
      ;;
    armv*)
      BINARY=SDRplay_RSP_API-ARM32-3.07.2.run
      BRANCH=0.8.7
      ;;
    aarch64)
      #BINARY=SDRplay_RSP_API-ARM64-3.07.1.run
      BINARY=SDRplay_RSP_API-Linux-3.14.0.run
      BRANCH=master
      ;;
  esac

  wget --no-http-keep-alive https://www.sdrplay.com/software/$BINARY
  sh $BINARY --noexec --target sdrplay
  patch --verbose -Np0 < /install-lib.$ARCH.patch

  cd sdrplay
  ./install_lib.sh
  cd ..
  rm -rf sdrplay
  rm $BINARY
  mkdir -p /usr/local/bin
  mv /opt/sdrplay_api/sdrplay_apiService /usr/local/bin/ || true

  #git clone https://github.com/pothosware/SoapySDRPlay3.git
  # latest from master as of 2021-06-19 (reliability fixes)
  #cmakebuild SoapySDRPlay3 a869f25364a1f0d5b16169ff908aa21a2ace475d
  git clone https://github.com/luarvique/SoapySDRPlay3
  cmakebuild SoapySDRPlay3 $BRANCH
fi

if [[ -z ${FULL_BUILD:-} || ${1:-} == 'clean' ]]; then
  echo "Cleaning from $0"
  SUDO_FORCE_REMOVE=yes apt-get -y purge --autoremove $BUILD_PACKAGES
  if [[ -z ${FULL_BUILD:-} ]]; then
    apt-get clean
    rm -rf /var/lib/apt/lists/*
  fi
fi
