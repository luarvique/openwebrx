#!/bin/sh
# Container initialization for persistent configuration and application data.
set -eu

config_dir=/etc/openwebrx
data_dir=/var/lib/openwebrx
defaults_dir=/usr/share/openwebrx-defaults

mkdir -p "$config_dir/openwebrx.conf.d" "$config_dir/bookmarks.d" "$config_dir/markers.d" "$data_dir"

if [ ! -f "$config_dir/openwebrx.conf" ]; then
    cp "$defaults_dir/openwebrx.conf" "$config_dir/openwebrx.conf"
fi

for bands_file in "$defaults_dir"/bands*.json; do
    target="$config_dir/$(basename "$bands_file")"
    if [ ! -f "$target" ]; then
        cp "$bands_file" "$target"
    fi
done

for bookmark_file in "$defaults_dir"/bookmarks.d/*.json; do
    target="$config_dir/bookmarks.d/$(basename "$bookmark_file")"
    if [ ! -f "$target" ]; then
        cp "$bookmark_file" "$target"
    fi
done

# Bind mounts are commonly created as root. OpenWebRX writes its dynamic
# settings, users, bookmarks, recordings, and decoded images to data_dir.
chown -R openwebrx:openwebrx "$data_dir"

if [ -n "${OPENWEBRX_ADMIN_USER:-}" ] && [ -n "${OPENWEBRX_ADMIN_PASSWORD:-}" ]; then
    if ! gosu openwebrx openwebrx admin --silent hasuser "$OPENWEBRX_ADMIN_USER"; then
        OWRX_PASSWORD="$OPENWEBRX_ADMIN_PASSWORD" \
            gosu openwebrx openwebrx admin --noninteractive adduser "$OPENWEBRX_ADMIN_USER"
    fi
fi

if [ "$#" -eq 0 ]; then
    set -- openwebrx
fi

# SDR device nodes retain their host ownership and permissions when /dev is
# bind-mounted. Running the receiver as root is therefore required for a
# reliable out-of-the-box hardware setup across hosts with different udev
# rules and group IDs. This container is already privileged by Compose.
exec "$@"
