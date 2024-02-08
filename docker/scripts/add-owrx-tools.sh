#!/bin/bash
set -euxo pipefail

function cmakebuild() {
  cd $1
  if [[ ! -z "${2:-}" ]]; then
    git checkout $2
  fi
  mkdir build
  cd build
  cmake ${CMAKE_ARGS:-} ..
  make
  make install
  cd ../..
  rm -rf $1
}

cd /tmp

STATIC_PACKAGES="libfftw3-bin libprotobuf23 libsamplerate0 libicu67 libudev1"
BUILD_PACKAGES="git autoconf automake libtool libfftw3-dev pkg-config cmake make gcc g++ libprotobuf-dev protobuf-compiler libsamplerate-dev libicu-dev libpython3-dev libudev-dev"
apt-get update
apt-get -y install --no-install-recommends $STATIC_PACKAGES $BUILD_PACKAGES

git clone https://github.com/jketterl/js8py.git
pushd js8py
# latest develop as of 2022-11-30 (structured callsign data)
#git checkout f7e394b7892d26cbdcce5d43c0b4081a2a6a48f6
git checkout 0.1.2
python3 setup.py install
popd
rm -rf js8py

git clone https://github.com/luarvique/csdr.git
cmakebuild csdr master

git clone https://github.com/luarvique/pycsdr.git
cd pycsdr
git checkout master
./setup.py install install_headers
cd ..
rm -rf pycsdr

git clone https://github.com/jketterl/codecserver.git
mkdir -p /usr/local/etc/codecserver
cp codecserver/conf/codecserver.conf /usr/local/etc/codecserver
cmakebuild codecserver 0.2.0

git clone https://github.com/jketterl/digiham.git
cmakebuild digiham 0.6.1

git clone https://github.com/jketterl/pydigiham.git
cd pydigiham
git checkout 0.6.1
./setup.py install
cd ..
rm -rf pydigiham

git clone https://github.com/luarvique/csdr-eti.git
cmakebuild csdr-eti

git clone https://github.com/luarvique/pycsdr-eti.git
cd pycsdr-eti
./setup.py install install_headers
cd ..
rm -rf pycsdr-eti

apt-get -y purge --autoremove $BUILD_PACKAGES
apt-get clean
rm -rf /var/lib/apt/lists/*
