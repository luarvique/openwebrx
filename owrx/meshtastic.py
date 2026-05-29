from owrx.map import Map, LatLngLocation
from owrx.bands import Bandplan
from owrx.storage import Storage
from datetime import timedelta

import base64
import json
import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

try:
    from Cryptodome.Cipher import AES
    from Cryptodome.Util import Counter
    _aes_available = True
except ImportError:
    _aes_available = False
    logger.warning("Meshtastic: pycryptodome not installed, decryption disabled. Install with: apt install python3-pycryptodome  OR  pip install pycryptodome")

try:
    from google.protobuf.json_format import MessageToDict
    from meshtastic.protobuf import (
        admin_pb2,
        atak_pb2,
        mesh_pb2,
        paxcount_pb2,
        portnums_pb2,
        powermon_pb2,
        remote_hardware_pb2,
        storeforward_pb2,
        telemetry_pb2,
    )
    _protobuf_available = True
except ImportError:
    _protobuf_available = False
    logger.warning("Meshtastic: meshtastic package not installed, payload decoding disabled. No Debian package available, install with: pip install meshtastic")


DEFAULT_KEY = bytes([
    0xD4, 0xF1, 0xBB, 0x3A,
    0x20, 0x29, 0x07, 0x59,
    0xF0, 0xBC, 0xFF, 0xAB,
    0xCF, 0x4E, 0x69, 0x01,
])

if _protobuf_available:
    APP_PROTO_DECODERS = {
        2:  remote_hardware_pb2.HardwareMessage,
        3:  mesh_pb2.Position,
        4:  mesh_pb2.User,
        5:  mesh_pb2.Routing,
        6:  admin_pb2.AdminMessage,
        8:  mesh_pb2.Waypoint,
        12: mesh_pb2.KeyVerification,
        32: mesh_pb2.StatusMessage,
        34: paxcount_pb2.Paxcount,
        35: mesh_pb2.StoreForwardPlusPlus,
        65: storeforward_pb2.StoreAndForward,
        67: telemetry_pb2.Telemetry,
        70: mesh_pb2.RouteDiscovery,
        71: mesh_pb2.NeighborInfo,
        72: atak_pb2.TAKPacket,
        74: powermon_pb2.PowerStressMessage,
    }


def _expand_short_psk(index):
    key = bytearray(DEFAULT_KEY)
    key[-1] = (key[-1] + index - 1) & 0xFF
    return bytes(key)


def _resolve_key(raw_key):
    raw = raw_key.strip()
    if raw.lower() in ("default", "aq=="):
        return _expand_short_psk(1)
    candidate = raw[2:] if raw.lower().startswith("0x") else raw
    candidate = candidate.replace(":", "").replace("-", "")
    if len(candidate) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in candidate):
        key = bytes.fromhex(candidate)
    else:
        key = base64.b64decode(raw, validate=True)
    if len(key) == 1:
        return _expand_short_psk(key[0])
    if len(key) in (16, 32):
        return key
    if 1 < len(key) < 16:
        return key + b"\x00" * (16 - len(key))
    if 16 < len(key) < 32:
        return key + b"\x00" * (32 - len(key))
    raise ValueError(f"Unsupported key length: {len(key)}")


def _portnum_name(portnum):
    if not _protobuf_available:
        return f"PORTNUM_{portnum}"
    try:
        return portnums_pb2.PortNum.Name(portnum)
    except Exception:
        return f"UNKNOWN_{portnum}"


def _proto_to_dict(message):
    return MessageToDict(message, preserving_proto_field_name=True)


def _append_metric(metrics, key, label, parts, unit=""):
    value = metrics.get(key)
    if value is not None:
        parts.append(f"{label}={value}{unit}")


def _telemetry_summary(data):
    sections = [
        ("device_metrics", [
            ("battery_level", "bat", "%"), ("voltage", "v", "V"),
            ("channel_utilization", "ch_util", "%"), ("air_util_tx", "air_tx", "%"),
            ("uptime_seconds", "uptime", "s"),
        ]),
        ("power_metrics", [
            ("ch1_voltage", "v1", "V"), ("ch1_current", "i1", "A"),
            ("ch2_voltage", "v2", "V"), ("ch2_current", "i2", "A"),
        ]),
        ("environment_metrics", [
            ("temperature", "temp", "C"), ("relative_humidity", "rh", "%"),
            ("barometric_pressure", "press", "hPa"), ("gas_resistance", "gas", ""),
            ("iaq", "iaq", ""),
        ]),
        ("air_quality_metrics", [
            ("pm10_standard", "pm10", ""), ("pm25_standard", "pm25", ""),
            ("pm100_standard", "pm100", ""), ("aqi", "aqi", ""),
        ]),
        ("health_metrics", [
            ("heart_bpm", "bpm", ""), ("spo2", "spo2", "%"),
        ]),
    ]
    for section, fields in sections:
        metrics = data.get(section)
        if not isinstance(metrics, dict):
            continue
        parts = []
        for key, label, unit in fields:
            _append_metric(metrics, key, label, parts, unit)
        if parts:
            return f"{section}: " + ", ".join(parts)
        return section
    return None


def _nodeinfo_summary(data):
    parts = []
    for key, label in [("long_name", "name"), ("short_name", "short"),
                       ("id", "id"), ("hw_model", "hw"), ("role", "role")]:
        value = data.get(key)
        if value:
            parts.append(f"{label}={value}")
    return ", ".join(parts) if parts else None


def _routing_summary(data):
    parts = []
    for key, label in [("error_reason", "error"), ("request_id", "req"),
                       ("reply_id", "reply"), ("snr_towards", "snr"),
                       ("route", "route"), ("relay_node", "relay"),
                       ("route_back", "route_back"), ("want_ack", "want_ack")]:
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        parts.append(f"{label}={value}")
    if parts:
        return ", ".join(parts)
    if data:
        return f"fields={','.join(list(data.keys())[:4])}"
    return None


def _summarize_fields(data, preferred=None, limit=4):
    if not isinstance(data, dict) or not data:
        return None
    preferred = preferred or []
    parts = []
    used = set()

    def append_part(label, value):
        if value is None:
            return
        if isinstance(value, str):
            text = value if len(value) <= 32 else f"{value[:29]}..."
            parts.append(f"{label}={text}")
        elif isinstance(value, list):
            if value:
                parts.append(f"{label}_count={len(value)}")
        elif isinstance(value, dict):
            if value:
                parts.append(f"{label}_keys={len(value)}")
        else:
            parts.append(f"{label}={value}")

    for key, label in preferred:
        used.add(key)
        append_part(label, data.get(key))
        if len(parts) >= limit:
            break
    if len(parts) < limit:
        for key in data:
            if key in used:
                continue
            append_part(key, data.get(key))
            if len(parts) >= limit:
                break
    return ", ".join(parts) if parts else f"fields={','.join(list(data.keys())[:4])}"


def _decode_app_payload(portnum, payload_bytes):
    if portnum in (1, 7):
        try:
            text = payload_bytes.decode("utf-8")
        except Exception:
            text = payload_bytes.decode("utf-8", errors="replace")
        return {"type": "text", "summary": text, "data": text}

    cls = APP_PROTO_DECODERS.get(portnum)
    if cls is None:
        return None

    try:
        msg = cls()
        msg.ParseFromString(payload_bytes)
        data = _proto_to_dict(msg)
        summary = None

        if portnum == 3:
            lat_i = data.get("latitude_i")
            lon_i = data.get("longitude_i")
            alt = data.get("altitude")
            if lat_i is not None and lon_i is not None:
                lat = int(lat_i) / 1e7
                lon = int(lon_i) / 1e7
                summary = f"lat={lat:.6f},lon={lon:.6f}" + (f",alt={alt}" if alt is not None else "")
        elif portnum == 4:
            summary = _nodeinfo_summary(data)
        elif portnum == 5:
            summary = _routing_summary(data)
        elif portnum == 6:
            summary = _summarize_fields(data, [("set_owner", "owner"), ("set_config", "config"),
                                               ("reboot_seconds", "reboot")])
        elif portnum == 8:
            name = data.get("name")
            lat_i = data.get("latitude_i")
            lon_i = data.get("longitude_i")
            parts = []
            if name:
                parts.append(f"name={name}")
            if lat_i is not None and lon_i is not None:
                parts.append(f"lat={int(lat_i)/1e7:.6f},lon={int(lon_i)/1e7:.6f}")
            summary = ", ".join(parts) if parts else _summarize_fields(data)
        elif portnum == 67:
            summary = _telemetry_summary(data)
        elif portnum == 70:
            summary = _summarize_fields(data, [("route", "route"), ("route_back", "route_back")])
        elif portnum == 71:
            summary = _summarize_fields(data, [("node_id", "node"), ("neighbors", "neighbors")])
        elif portnum == 72:
            summary = _summarize_fields(data, [("contact", "contact"), ("group", "group")])

        if not summary:
            summary = _summarize_fields(data)

        return {"type": "protobuf", "summary": summary, "data": data}
    except Exception:
        return None


def _parse_data_message(decrypted_bytes):
    try:
        data_msg = mesh_pb2.Data()
        data_msg.ParseFromString(decrypted_bytes)
        payload = data_msg.payload
        portnum = int(data_msg.portnum)
        decoded = _decode_app_payload(portnum, payload)
        return {
            "portnum": portnum,
            "portnum_name": _portnum_name(portnum),
            "payload_decoded": decoded,
        }
    except Exception:
        return None


def _decrypt_payload(key, src, packet_id, encrypted):
    iv_prefix = packet_id.to_bytes(8, "little") + src.to_bytes(4, "little")
    ctr = Counter.new(32, prefix=iv_prefix, initial_value=0)
    cipher = AES.new(key, AES.MODE_CTR, counter=ctr)
    return cipher.decrypt(encrypted)


class MeshtasticLocation(LatLngLocation):
    def __init__(self, lat: float, lon: float, alt: int | None = None, src: str | None = None,
                 hop_limit: int | None = None, hop_start: int | None = None, summary: str | None = None,
                 long_name: str | None = None, short_name: str | None = None,
                 role: str | None = None, hw_model: str | None = None):
        super().__init__(lat, lon)
        self.alt:        int | None = alt
        self.src:        str | None = src
        self.hop_limit:  int | None = hop_limit
        self.hop_start:  int | None = hop_start
        self.summary:    str | None = summary
        self.long_name:  str | None = long_name
        self.short_name: str | None = short_name
        self.role:       str | None = role
        self.hw_model:   str | None = hw_model

    def getTTL(self) -> timedelta:  # type: ignore[override]
        return timedelta(hours=4)

    def __dict__(self):  # type: ignore[override]
        res: dict[str, object] = super().__dict__()  # type: ignore[assignment]
        if self.alt is not None:
            res["altitude"] = self.alt
        if self.src is not None:
            res["src"] = self.src
        if self.hop_limit is not None:
            res["hop_limit"] = self.hop_limit
        if self.hop_start is not None:
            res["hop_start"] = self.hop_start
        if self.summary is not None:
            res["summary"] = self.summary
        if self.long_name is not None:
            res["long_name"] = self.long_name
        if self.short_name is not None:
            res["short_name"] = self.short_name
        if self.role is not None:
            res["role"] = self.role
        if self.hw_model is not None:
            res["hw_model"] = self.hw_model
        return res


class MeshtasticParser:
    _DEDUP_TTL:           int = 60
    _DEDUP_MAX:           int = 4096
    _CACHE_SAVE_INTERVAL: int = 60

    def __init__(self) -> None:
        self._key:              bytes = _resolve_key("AQ==")
        from owrx.bands import Band
        self._band:             Band | None = None
        self._seen:             dict[tuple[int, int], float] = {}
        self._cache_file:       str   = Storage.getFilePath("meshtastic_nodes.json")
        self._cache_dirty:      bool  = False
        self._cache_last_saved: float = 0.0
        self._node_cache:       dict[str, dict[str, str | int | float | bool | None]] = self._load_node_cache()

    def setDialFrequency(self, frequency: int) -> None:
        self._band = Bandplan.getSharedInstance().findBand(frequency)

    def _is_duplicate(self, src: int, packet_id: int) -> bool:
        now = time.monotonic()
        key = (src, packet_id)
        if key in self._seen and now - self._seen[key] < self._DEDUP_TTL:
            return True
        self._seen[key] = now
        if len(self._seen) > self._DEDUP_MAX:
            cutoff = now - self._DEDUP_TTL
            self._seen = {k: v for k, v in self._seen.items() if v > cutoff}
        return False

    def parsePayload(self, out: dict[str, object], data: bytes):
        # crc: 1=OK, 0=error, -1=no CRC. Meshtastic always uses CRC.
        if int(out.get("crc", 1)) < 1:  # type: ignore[arg-type]
            logger.debug("Meshtastic: dropped packet with crc=%d", out.get("crc"))
            return None

        dest      = int.from_bytes(data[0:4], "little")
        src       = int.from_bytes(data[4:8], "little")
        packet_id = int.from_bytes(data[8:12], "little")

        if self._is_duplicate(src, packet_id):
            return

        flags      = data[12]
        chan_hash  = data[13]
        next_hop   = data[14]
        relay_node = data[15]
        encrypted  = data[16:]

        hop_limit = flags & 0x07
        want_ack  = bool(flags & 0x08)
        via_mqtt  = bool(flags & 0x10)
        hop_start = (flags >> 5) & 0x07

        mesh = {
            "dest":         f"{dest:08x}",
            "src":          f"{src:08x}",
            "packet_id":    f"{packet_id:08x}",
            "hop_limit":    hop_limit,
            "hop_start":    hop_start,
            "want_ack":     want_ack,
            "via_mqtt":     via_mqtt,
            "channel_hash": f"{chan_hash:02x}",
            "next_hop":     f"{next_hop:02x}",
            "relay_node":   f"{relay_node:02x}",
        }

        meshtastic_data = None

        if _aes_available and encrypted:
            try:
                decrypted = _decrypt_payload(self._key, src, packet_id, encrypted)
                if _protobuf_available:
                    meshtastic_data = _parse_data_message(decrypted)
                    if meshtastic_data:
                        mesh["portnum"]      = meshtastic_data["portnum"]
                        mesh["portnum_name"] = meshtastic_data["portnum_name"]
                        decoded = meshtastic_data.get("payload_decoded") or {}
                        mesh["summary"] = decoded.get("summary", "")
                        mesh["data"]    = (decoded.get("data") or {})
                        if meshtastic_data["portnum"] == 4:
                            self._update_node_cache(src, mesh["data"])  # type: ignore[arg-type]
            except Exception as e:
                logger.debug("Meshtastic decrypt/decode failed for %s: %s", mesh["src"], e)

        # Annotate src/dest with cached names/role/hw_model (if known)
        src_hex  = f"{src:08x}"
        dest_hex = f"{dest:08x}"
        for key, field in (("short_name", "src_short_name"), ("long_name", "src_long_name"),
                           ("role", "src_role"), ("hw_model", "src_hw_model")):
            val = self._cache_str(src_hex, key)
            if val:
                mesh[field] = val
        if dest != 0xFFFFFFFF:
            for key, field in (("short_name", "dest_short_name"), ("long_name", "dest_long_name")):
                val = self._cache_str(dest_hex, key)
                if val:
                    mesh[field] = val

        out["mode"] = "Meshtastic"
        out["timestamp"] = round(datetime.now(timezone.utc).timestamp() * 1000)
        out["meshtastic"] = mesh

        self._update_map(out, src, meshtastic_data)

        # Update last_heard after all per-packet data is cached, so a flush triggered
        # here always sees the complete entry (including any freshly cached position).
        self._touch_last_heard(src)

    def _load_node_cache(self) -> dict[str, dict[str, str | int | float | bool | None]]:
        try:
            with open(self._cache_file, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data  # type: ignore[return-value]
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return {}

    def _mark_cache_dirty(self) -> None:
        self._cache_dirty = True
        if time.monotonic() - self._cache_last_saved >= self._CACHE_SAVE_INTERVAL:
            self._flush_node_cache()

    def _flush_node_cache(self) -> None:
        if not self._cache_dirty:
            return
        try:
            with open(self._cache_file, "w") as f:
                json.dump(self._node_cache, f, indent=2)
            self._cache_dirty = False
            self._cache_last_saved = time.monotonic()
            logger.debug("Meshtastic: node cache saved (%d entries)", len(self._node_cache))
        except Exception:
            logger.exception("Meshtastic: failed to save node cache")

    def _cache_str(self, src_hex: str, key: str) -> str | None:
        val = self._node_cache.get(src_hex, {}).get(key)
        return str(val) if val is not None else None

    def _update_node_cache(self, src: int, data: dict[str, object]) -> None:
        src_hex = f"{src:08x}"
        entry: dict[str, str | int | float | bool | None] = dict(self._node_cache.get(src_hex, {}))
        for key in ("long_name", "short_name", "role", "hw_model", "is_licensed"):
            val = data.get(key)
            if val is not None and val != "":
                entry[key] = str(val) if not isinstance(val, bool) else val
        node_id_val = data.get("id")
        if node_id_val:
            entry["node_id"] = str(node_id_val)
        entry["last_heard"] = round(datetime.now(timezone.utc).timestamp() * 1000)
        self._node_cache[src_hex] = entry
        logger.debug("Meshtastic: cached node %s: %s", src_hex, entry)
        self._mark_cache_dirty()

    def _touch_last_heard(self, src: int) -> None:
        src_hex = f"{src:08x}"
        entry: dict[str, str | int | float | bool | None] = dict(self._node_cache.get(src_hex, {}))
        entry["last_heard"] = round(datetime.now(timezone.utc).timestamp() * 1000)
        self._node_cache[src_hex] = entry
        self._mark_cache_dirty()

    def _node_display_name(self, src_hex: str) -> str | None:
        return self._cache_str(src_hex, "long_name") or self._cache_str(src_hex, "short_name")

    def _update_map(self, out, src, meshtastic_data):
        if not meshtastic_data or meshtastic_data.get("portnum") != 3:
            return
        decoded = (meshtastic_data.get("payload_decoded") or {}).get("data") or {}
        lat_i = decoded.get("latitude_i")
        lon_i = decoded.get("longitude_i")
        if lat_i is None or lon_i is None:
            return
        lat = int(lat_i) / 1e7
        lon = int(lon_i) / 1e7
        alt     = decoded.get("altitude")
        src_hex = f"{src:08x}"
        node_id = f"!{src_hex}"

        # Cache position in node entry
        entry: dict[str, str | int | float | bool | None] = dict(self._node_cache.get(src_hex, {}))
        entry["lat"] = lat
        entry["lon"] = lon
        if alt is not None:
            entry["alt"] = int(alt)
        entry["last_heard"] = round(datetime.now(timezone.utc).timestamp() * 1000)
        self._node_cache[src_hex] = entry
        self._mark_cache_dirty()

        hop_limit = out.get("meshtastic", {}).get("hop_limit")
        hop_start = out.get("meshtastic", {}).get("hop_start")
        summary   = out.get("meshtastic", {}).get("summary") or ""
        loc = MeshtasticLocation(lat, lon,
                                 alt=int(alt) if alt is not None else None,
                                 src=src_hex,
                                 hop_limit=hop_limit,
                                 hop_start=hop_start,
                                 summary=summary,
                                 long_name=self._cache_str(src_hex, "long_name"),
                                 short_name=self._cache_str(src_hex, "short_name"),
                                 role=self._cache_str(src_hex, "role"),
                                 hw_model=self._cache_str(src_hex, "hw_model"))
        Map.getSharedInstance().updateLocation(node_id, loc, "Meshtastic", self._band)
        out["lat"] = lat
        out["lon"] = lon
        if alt is not None:
            out["altitude"] = int(alt)
