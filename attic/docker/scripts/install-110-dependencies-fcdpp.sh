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

STATIC_PACKAGES="libhidapi-hidraw0 libhidapi-libusb0 libasound2"
BUILD_PACKAGES="git cmake make gcc g++ libhidapi-dev libasound2-dev"

if [[ -z ${1:-} ]]; then
  apt-get update
  apt-get -y install --no-install-recommends $STATIC_PACKAGES $BUILD_PACKAGES

  git clone https://github.com/pothosware/SoapyFCDPP.git
  cmakebuild SoapyFCDPP soapy-fcdpp-0.1.1
fi

if [[ -z ${FULL_BUILD:-} || ${1:-} == 'clean' ]]; then
  echo "Cleaning from $0"
  apt-get -y purge --autoremove $BUILD_PACKAGES
  if [[ -z ${FULL_BUILD:-} ]]; then
    apt-get clean
    rm -rf /var/lib/apt/lists/*
  fi
fi
