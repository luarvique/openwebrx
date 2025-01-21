#!/bin/bash
set -euxo pipefail
export MAKEFLAGS="-j12"

case `uname -m` in
    arm*)
        PLATFORM=armhf
        ;;
    aarch64*)
        PLATFORM=aarch64
        ;;
    x86_64*)
        PLATFORM=amd64
        ;;
esac

echo "+ Init..."
apt update
apt install -y --no-install-recommends wget gpg ca-certificates auto-apt-proxy udev

echo "+ Install S6 services..."
wget https://github.com/just-containers/s6-overlay/releases/download/v1.21.8.0/s6-overlay-${PLATFORM}.tar.gz
tar xzf s6-overlay-${PLATFORM}.tar.gz -C /
rm s6-overlay-${PLATFORM}.tar.gz
cp -a /files/services/sdrplay /etc/services.d/
sed -ri 's/^python3 openwebrx.py/openwebrx/' /run.sh

echo "+ Add repos and update..."
wget -O - https://luarvique.github.io/ppa/openwebrx-plus.gpg | gpg --dearmor -o /etc/apt/trusted.gpg.d/openwebrx-plus.gpg
echo "deb [signed-by=/etc/apt/trusted.gpg.d/openwebrx-plus.gpg] https://luarvique.github.io/ppa/debian ./" > /etc/apt/sources.list.d/openwebrx-plus.list
wget -O - https://repo.openwebrx.de/debian/key.gpg.txt | gpg --dearmor -o /usr/share/keyrings/openwebrx.gpg
echo "deb [signed-by=/usr/share/keyrings/openwebrx.gpg] https://repo.openwebrx.de/debian/ bullseye main" > /etc/apt/sources.list.d/openwebrx.list
apt update

echo "+ Install OpenWebRX, Soapy modules and some libs..."
DEBIAN_FRONTEND=noninteractive apt install -y openwebrx soapysdr-module-all libsoapysdr-dev libpulse0 libfaad2 libopus0 soapysdr-module-sdrplay3 airspyhf alsa-utils libpopt0 libiio0 libad9361-0 libhidapi-hidraw0 libhidapi-libusb0 dump1090-fa-minimal libliquid2d csdr-eti python3-csdr-eti dablin
