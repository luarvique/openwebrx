#!/bin/bash

#
# This script will check out and build all the latest OpenWebRX+
# packages in the BUILD_DIR folder, placing .deb files into
# OUTPUT_DIR folder.
#

set -euo pipefail

GIT_CSDR=https://github.com/luarvique/csdr.git
GIT_PYCSDR=https://github.com/luarvique/pycsdr.git
GIT_OWRXCONNECTOR=https://github.com/luarvique/owrx_connector.git
GIT_CODECSERVER=https://github.com/jketterl/codecserver.git
GIT_DIGIHAM=https://github.com/jketterl/digiham.git
GIT_PYDIGIHAM=https://github.com/jketterl/pydigiham.git
GIT_CSDR_ETI=https://github.com/luarvique/csdr-eti.git
GIT_PYCSDR_ETI=https://github.com/luarvique/pycsdr-eti.git
GIT_JS8PY=https://github.com/jketterl/js8py.git
GIT_REDSEA=https://github.com/luarvique/redsea.git
GIT_SOAPYSDRPLAY3=https://github.com/luarvique/SoapySDRPlay3.git
GIT_OPENWEBRX=https://github.com/luarvique/openwebrx.git

BUILD_DIR=./owrx-build/`uname -m`
OUTPUT_DIR=./owrx-output/`uname -m`

if [ "${1:-}" == "--ask" ]; then
	echo;read -n1 -p "Build csdr? [yN] " ret
	[[ "$ret" == [Yy]* ]] && BUILD_CSDR=y || BUILD_CSDR=n
	echo;read -n1 -p "Build pycsdr? [yN] " ret
	[[ "$ret" == [Yy]* ]] && BUILD_PYCSDR=y || BUILD_PYCSDR=n
	echo;read -n1 -p "Build owrxconnector? [yN] " ret
	[[ "$ret" == [Yy]* ]] && BUILD_OWRXCONNECTOR=y || BUILD_OWRXCONNECTOR=n
	echo;read -n1 -p "Build codecserver? [yN] " ret
	[[ "$ret" == [Yy]* ]] && BUILD_CODECSERVER=y || BUILD_CODECSERVER=n
	echo;read -n1 -p "Build digiham? [yN] " ret
	[[ "$ret" == [Yy]* ]] && BUILD_DIGIHAM=y || BUILD_DIGIHAM=n
	echo;read -n1 -p "Build pydigiham? [yN] " ret
	[[ "$ret" == [Yy]* ]] && BUILD_PYDIGIHAM=y || BUILD_PYDIGIHAM=n
	echo;read -n1 -p "Build csdr-eti? [yN] " ret
	[[ "$ret" == [Yy]* ]] && BUILD_CSDR_ETI=y || BUILD_CSDR_ETI=n
	echo;read -n1 -p "Build pycsdr-eti? [yN] " ret
	[[ "$ret" == [Yy]* ]] && BUILD_PYCSDR_ETI=y || BUILD_PYCSDR_ETI=n
	echo;read -n1 -p "Build js8py? [yN] " ret
	[[ "$ret" == [Yy]* ]] && BUILD_JS8PY=y || BUILD_JS8PY=n
	echo;read -n1 -p "Build Redsea? [yN] " ret
	[[ "$ret" == [Yy]* ]] && BUILD_REDSEA=y || BUILD_REDSEA=n
	echo;read -n1 -p "Build SoapySDRPlay3? [yN] " ret
	[[ "$ret" == [Yy]* ]] && BUILD_SOAPYSDRPLAY3=y || BUILD_SOAPYSDRPLAY3=n
	echo;read -n1 -p "Build OpenWebRX+? [Yn] " ret
	[[ "$ret" == [Nn]* ]] && BUILD_OWRX=n || BUILD_OWRX=y
	echo;read -n1 -p "Clean the Output folder? [yN] " ret
	[[ "$ret" == [Yy]* ]] && CLEAN_OUTPUT=y || CLEAN_OUTPUT=n
else
	# build all by default
	BUILD_OWRX=y
	BUILD_CSDR=y
	BUILD_PYCSDR=y
	BUILD_OWRXCONNECTOR=y
	BUILD_SOAPYSDRPLAY3=y
	BUILD_CODECSERVER=y
	BUILD_DIGIHAM=y
	BUILD_PYDIGIHAM=y
	BUILD_CSDR_ETI=y
	BUILD_PYCSDR_ETI=y
	BUILD_JS8PY=y
	BUILD_REDSEA=y
	CLEAN_OUTPUT=y
fi

#
# Update build targets based on dependencies
#
if [ "${BUILD_OWRX:-}" == "y" ]; then
	BUILD_PYCSDR=y
	BUILD_OWRXCONNECTOR=y
fi
if [ "${BUILD_PYCSDR_ETI:-}" == "y" ]; then
	BUILD_CSDR_ETI=y
fi
if [ "${BUILD_PYDIGIHAM:-}" == "y" ]; then
	BUILD_DIGIHAM=y
fi
if [ "${BUILD_DIGIHAM:-}" == "y" ]; then
	BUILD_CODECSERVER=y
fi
if [ "${BUILD_PYCSDR:-}" == "y" ] || [ "${BUILD_OWRXCONNECTOR:-}" == "y" ] || [ "${BUILD_CSDR_ETI:-}" == "y" ]; then
	BUILD_CSDR=y
fi

echo ======================================
echo "Building:"
echo "csdr: $BUILD_CSDR"
echo "pycsdr: $BUILD_PYCSDR"
echo "owrx connector: $BUILD_OWRXCONNECTOR"
echo "codec server: $BUILD_CODECSERVER"
echo "digiham: $BUILD_DIGIHAM"
echo "pydigiham: $BUILD_PYDIGIHAM"
echo "csdr-eti: $BUILD_CSDR_ETI"
echo "pycsdr-eti: $BUILD_PYCSDR_ETI"
echo "js8py: $BUILD_JS8PY"
echo "redsea: $BUILD_REDSEA"
echo "SoapySDRPlay3: $BUILD_SOAPYSDRPLAY3"
echo "OpenWebRx: $BUILD_OWRX"
echo "Clean OUTPUT folder: $CLEAN_OUTPUT"
echo ======================================

if [ "${1:-}" == "--ask" ]; then
	read -p "Press [ENTER] to continue, or CTRL-C, to exit."
fi

rm -rf ${BUILD_DIR}
if [ "${CLEAN_OUTPUT:-}" == "y" ]; then
	rm -rf ${OUTPUT_DIR}
fi

mkdir -p ${BUILD_DIR} ${OUTPUT_DIR}
pushd ${BUILD_DIR}

if [ "${BUILD_CSDR:-}" == "y" ]; then
	echo "##### Building CSDR... #####"
	git clone -b master "$GIT_CSDR"
	pushd csdr
	if [ `gcc -dumpversion` -gt 10 ]; then
		# fix armhf builds on gcc>=11 (bookworm)
		sed -i 's/-march=armv7-a /-march=armv7-a+fp /g' CMakeLists.txt
	fi
	dpkg-buildpackage -us -uc
	popd
	# PyCSDR, CSDR-ETI, and OWRX-Connector depend on the latest CSDR
	sudo dpkg -i csdr*.deb libcsdr*.deb nmux*.deb
fi

if [ "${BUILD_PYCSDR:-}" == "y" ]; then
	echo "##### Building PyCSDR... #####"
	git clone -b master "$GIT_PYCSDR"
	pushd pycsdr
	dpkg-buildpackage -us -uc
	popd
	# OpenWebRX build depends on the latest PyCSDR
	sudo dpkg -i python3-csdr*.deb
fi

if [ "${BUILD_OWRXCONNECTOR:-}" == "y" ]; then
	echo "##### Building OWRX-Connector... #####"
	git clone -b master "$GIT_OWRXCONNECTOR"
	pushd owrx_connector
	dpkg-buildpackage -us -uc
	popd
	# Not installing OWRX-Connectors here since there are no
	# further build steps depending on it
	#sudo dpkg -i *connector*.deb
fi

if [ "${BUILD_CODECSERVER:-}" == "y" ]; then
	echo "##### Building CodecServer... #####"
	git clone -b master "$GIT_CODECSERVER"
	pushd codecserver
	dpkg-buildpackage -us -uc
	popd
	# Digiham depends on libcodecserver-dev
	sudo dpkg -i libcodecserver_*.deb codecserver_*.deb libcodecserver-dev_*.deb
fi

if [ "${BUILD_DIGIHAM:-}" == "y" ]; then
	echo "##### Building DigiHAM... #####"
	git clone -b master "$GIT_DIGIHAM"
	pushd digiham
	dpkg-buildpackage -us -uc
	popd
	# PyDigiHAM build depends on the latest DigiHAM
	sudo dpkg -i *digiham*.deb
fi

if [ "${BUILD_PYDIGIHAM:-}" == "y" ]; then
	echo "##### Building PyDigiHAM... #####"
	git clone -b master "$GIT_PYDIGIHAM"
	pushd pydigiham
	dpkg-buildpackage -us -uc
	popd
	# Not installing PyDigiHAM here since there are no further
	# build steps depending on it
	#sudo dpkg -i python3-digiham*.deb
fi

if [ "${BUILD_CSDR_ETI:-}" == "y" ]; then
	echo "##### Building CSDR-ETI... #####"
	git clone "$GIT_CSDR_ETI"
	pushd csdr-eti
	dpkg-buildpackage -us -uc
	popd
	# PyCSDR-ETI build depends on the latest CSDR-ETI
	sudo dpkg -i libcsdr-eti*.deb
fi

if [ "${BUILD_PYCSDR_ETI:-}" == "y" ]; then
	echo "##### Building PyCSDR-ETI... #####"
	git clone "$GIT_PYCSDR_ETI"
	pushd pycsdr-eti
	dpkg-buildpackage -us -uc
	popd
	# Not installing PyCSDR-ETI here since there are no further
	# build steps depending on it
	#sudo dpkg -i python3-csdr-eti*.deb
fi

if [ "${BUILD_JS8PY:-}" == "y" ]; then
	echo "##### Building JS8Py... #####"
	git clone -b master "$GIT_JS8PY"
	pushd js8py
	dpkg-buildpackage -us -uc
	popd
	# Not installing JS8Py here since there are no further
	# build steps depending on it
	#sudo dpkg -i *js8py*.deb
fi

if [ "${BUILD_REDSEA:-}" == "y" ]; then
	echo "##### Building Redsea... #####"
	git clone -b master "$GIT_REDSEA"
	pushd redsea
	dpkg-buildpackage -us -uc
	popd
	# Not installing Redsea here since there are no further
	# build steps depending on it
	#sudo dpkg -i *redsea*.deb
fi

if [ "${BUILD_SOAPYSDRPLAY3:-}" == "y" ]; then
	echo "##### Building SoapySDRPlay3 ... #####"
	git clone -b master "$GIT_SOAPYSDRPLAY3"
	pushd SoapySDRPlay3
	case $(uname -m) in
		arm*) git checkout 0.8.7 ;;
	esac
	# Debian Bullseye uses SoapySDR v0.7
	HAVE_SOAPY=`apt-cache search libsoapysdr0.7`
	if [ ! -z "${HAVE_SOAPY}" ] ; then
		echo "##### Building SoapySDRPlay3 v0.7 (Debian) ... #####"
		cp debian/control.debian debian/control
		dpkg-buildpackage -us -uc
	fi
	# Ubuntu Jammy uses SoapySDR v0.8
	HAVE_SOAPY=`apt-cache search libsoapysdr0.8`
	if [ ! -z "${HAVE_SOAPY}" ] ; then
		echo "##### Building SoapySDRPlay3 v0.8 (Ubuntu) ... #####"
		cp debian/control.ubuntu debian/control
		dpkg-buildpackage -us -uc
	fi
	popd
fi

if [ "${BUILD_OWRX:-}" == "y" ]; then
	echo "##### Building OpenWebRX... #####"
	git clone -b master "$GIT_OPENWEBRX"
	pushd openwebrx
	dpkg-buildpackage -us -uc
	popd
	# Not installing OpenWebRX here since there are no further
	# build steps depending on it
	#sudo dpkg -i openwebrx*.deb
fi


echo "##### Moving packages to ${OUTPUT_DIR} ... #####"
popd
mv ${BUILD_DIR}/*.deb ${OUTPUT_DIR}
echo "##### ALL DONE! #####"
