FROM debian:bullseye-slim
ARG VERSION
LABEL OpenWebRX+ with All Receivers and Demodulators
ARG MAKEFLAGS

ADD docker/files /files

COPY docker/deb_based/install-owrxp.sh docker/scripts/run.sh /
RUN /install-owrxp.sh
COPY docker/deb_based/install-owrxp-extra.sh /
RUN /install-owrxp-extra.sh

ENV S6_CMD_ARG0="/run.sh"
ENTRYPOINT ["/init"]

WORKDIR /

VOLUME /etc/openwebrx
VOLUME /var/lib/openwebrx

CMD []

EXPOSE 8073
