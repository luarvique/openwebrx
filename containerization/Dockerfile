FROM debian:trixie-slim AS builder

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3-pip \
        python3-setuptools \
    && rm -rf /var/lib/apt/lists/*

COPY . /usr/src/openwebrx
RUN python3 -m pip install --break-system-packages --no-cache-dir --no-deps /usr/src/openwebrx


FROM debian:trixie-slim

ARG DEBIAN_FRONTEND=noninteractive
ARG OPENWEBRX_FULL=0

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
        gosu \
        python3 \
        python3-packaging \
        soapysdr-module-all \
        tini \
    && curl -fsSL https://luarvique.github.io/ppa/openwebrx-plus.gpg -o /tmp/openwebrx-plus.gpg \
    && gpg --batch --dearmor --output /usr/share/keyrings/openwebrx-plus.gpg /tmp/openwebrx-plus.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/openwebrx-plus.gpg] https://luarvique.github.io/ppa/trixie ./" \
        > /etc/apt/sources.list.d/openwebrx-plus.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        csdr \
        nmux \
        owrx-connector \
        python3-csdr \
    && apt-get purge -y --auto-remove curl gnupg \
    && rm -f /tmp/openwebrx-plus.gpg \
    && groupadd --system openwebrx \
    && useradd --system --gid openwebrx --no-create-home --home-dir /nonexistent openwebrx \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/ /usr/local/
COPY openwebrx.conf bands*.json /usr/share/openwebrx-defaults/
COPY bookmarks.d /usr/share/openwebrx-defaults/bookmarks.d
COPY containerization/entrypoint.sh /usr/local/bin/openwebrx-entrypoint

RUN chmod 0755 /usr/local/bin/openwebrx-entrypoint \
    && ldconfig

WORKDIR /

VOLUME ["/etc/openwebrx", "/var/lib/openwebrx"]
EXPOSE 8073

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/openwebrx-entrypoint"]
CMD ["openwebrx"]

# Add the decoder-rich package set only when requested. OPENWEBRX_FULL=0 is
# the default sparse image and does not rely on Docker build-target support.
RUN if [ "$OPENWEBRX_FULL" = "1" ]; then \
        apt-get update \
        && apt-get install -y --no-install-recommends \
            acarsdec \
            alsa-utils \
            aprs-symbols \
            codec2 \
            codecserver \
            csdr-skimmer \
            dablin \
            direwolf \
            dumphfdl \
            dump1090-fa-minimal \
            dump978-fa-minimal \
            dumpvdl2 \
            dxlaprs-lora \
            imagemagick \
            js8call \
            lame \
            libhamlib-utils \
            multimon-ng \
            nrsc5 \
            python3-csdr-eti \
            python3-digiham \
            python3-js8py \
            python3-meshtastic \
            python3-paho-mqtt \
            python3-pycryptodome \
            redsea \
            rtl-433 \
            rtl-sdr \
            satdump \
            soapysdr-tools \
            sonde-decoders \
            wsjtx \
        && sed -i 's/from distutils.version import StrictVersion/from packaging.version import Version as StrictVersion/' \
            /usr/lib/python3/dist-packages/js8py/version.py; \
    fi \
    && rm -rf /var/lib/apt/lists/*
