#!/usr/bin/env bash
set -euxo pipefail

cd /tmp

STATIC_PACKAGES="libusb-1.0-0 libudev1"
BUILD_PACKAGES="git make gcc autoconf automake libtool libusb-1.0-0-dev xxd"

export MARCH=native
case `uname -m` in
    x86_64*)
        export MARCH=x86-64
        ;;
esac



if [[ -z ${1:-} ]]; then
  apt-get update
  apt-get -y install --no-install-recommends $STATIC_PACKAGES $BUILD_PACKAGES

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
fi

if [[ -z ${FULL_BUILD:-} || ${1:-} == 'clean' ]]; then
  echo "Cleaning from $0"
  apt-get -y purge --autoremove $BUILD_PACKAGES
  if [[ -z ${FULL_BUILD:-} ]]; then
    apt-get clean
    rm -rf /var/lib/apt/lists/*
  fi
fi
