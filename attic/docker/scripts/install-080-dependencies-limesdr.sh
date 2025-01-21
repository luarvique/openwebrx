#!/usr/bin/env bash
set -euo pipefail

cd /tmp

STATIC_PACKAGES="libusb-1.0-0 libatomic1"
BUILD_PACKAGES="git libusb-1.0-0-dev cmake make gcc g++"

if [[ -z ${1:-} ]]; then
  apt-get update
  apt-get -y install --no-install-recommends $STATIC_PACKAGES $BUILD_PACKAGES

  SIMD_FLAGS=""
  if [[ 'x86_64' == `uname -m` ]] ; then
      SIMD_FLAGS="-DDEFAULT_SIMD_FLAGS=SSE3"
  fi

  git clone https://github.com/myriadrf/LimeSuite.git
  cd LimeSuite
  # latest from master as of 2020-09-04
  git checkout 9526621f8b4c9e2a7f638b5ef50c45560dcad22a
  mkdir builddir
  cd builddir
  cmake .. -DENABLE_EXAMPLES=OFF -DENABLE_DESKTOP=OFF -DENABLE_LIME_UTIL=OFF -DENABLE_QUICKTEST=OFF -DENABLE_OCTAVE=OFF -DENABLE_GUI=OFF -DCMAKE_CXX_STANDARD_LIBRARIES="-latomic" ${SIMD_FLAGS}
  make
  make install
  cd ../..
  rm -rf LimeSuite
fi

if [[ -z ${FULL_BUILD:-} || ${1:-} == 'clean' ]]; then
  echo "Cleaning from $0"
  apt-get -y purge --autoremove $BUILD_PACKAGES
  if [[ -z ${FULL_BUILD:-} ]]; then
    apt-get clean
    rm -rf /var/lib/apt/lists/*
  fi
fi
