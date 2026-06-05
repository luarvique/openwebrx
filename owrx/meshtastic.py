from owrx.toolbox import TextParser
from owrx.reporting import ReportingEngine
from owrx.map import Map, LatLngLocation
from owrx.bands import Bandplan, Band
from owrx.storage import Storage
from datetime import datetime, timezone, timedelta

import base64
import json
import logging
import time

logger = logging.getLogger(__name__)


DEFAULT_KEY = bytes([
    0xD4, 0xF1, 0xBB, 0x3A,
    0x20, 0x29, 0x07, 0x59,
    0xF0, 0xBC, 0xFF, 0xAB,
    0xCF, 0x4E, 0x69, 0x01,
])


# Import decryption library if available
try:
    from Cryptodome.Cipher import AES
    from Cryptodome.Util import Counter
    _aes_available = True
except ImportError:
    _aes_available = False
    logger.warning("PyCryptodome not installed, decryption disabled. Install with: 'apt install python3-pycryptodome' OR 'pip install pycryptodome'")

# Import ProtoBuf and Meshtastic libraries if available
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
    logger.warning("Meshtastic package not installed, payload decoding disabled. No Debian package available, install with: 'pip install meshtastic'")

# Create a mapping from packet types to decoders
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
        if isinstance(metrics, dict):
            parts = []
            for key, label, unit in fields:
                if key in metrics:
                    parts.append(f"{label}={metrics[key]}{unit}")
            return f"{section}: " + ", ".join(parts) if parts else section
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


class MeshtasticLocation(LatLngLocation):
    def __init__(self, lat, lon, data):
        super().__init__(lat, lon)
        self.data = data

    def getTTL(self) -> timedelta:
        return timedelta(hours=4)

    def __dict__(self):
        res = super().__dict__()
        res["ttl"] = round((datetime.now(timezone.utc) + self.getTTL()).timestamp() * 1000)
        res.append(data)
        return res


class MeshtasticParser(TextParser):
    CACHE_FILENAME = "meshtastic.json"
    CACHE_SAVE_INTERVAL = 60 * 60
    DEDUP_TTL = 60
    DEDUP_MAX = 4096

    def __init__(self, service: bool = False) -> None:
        super().__init__(filePrefix="MHTC", service=service)
        self.fileName = Storage.getFilePath(self.CACHE_FILENAME)
        self.lastSave = time.monotonic()
        self.nodes = self.loadNodeCache(self.fileName)
        self.band = None
        self.seen = {}
        self.key  = _resolve_key("AQ==")

    def setDialFrequency(self, frequency: int) -> None:
        super().setDialFrequency(frequency)
        self._band = Bandplan.getSharedInstance().findBand(frequency)

    def loadNodeCache(fileName: str):
        try:
            with open(fileName, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.debug("Failed loading node cache from '%s': %s", fileName, e)
        return {}

    def saveNodeCache(fileName: str, data) -> boolean:
        try:
            with open(fileName, "w") as f:
                json.dump(data, f)
                return True
        except Exception as e:
            logger.debug("Failed saving node cache to '%s': %s", fileName, e)
        return False

    def cacheNode(node: int, data):
        with self.nodes:
            # Our current time
            now = time.monotonic()
            # Collect cacheable fields
            updates = {}
            for key in ("lat", "lon", "alt", "long_name", "short_name", "role", "hw_model", "is_licensed"):
                if key in data:
                    update[key] = data[key]
            # Update cached node information
            if updates:
                if node in self.nodes:
                    self.nodes[node].update(updates)
                else:
                    self.nodes[node] = updates
                # Save last-seen timestamp
                self.nodes[node]["seen"] = now
            # If it is time to save...
            if now - self.lastSave >= CACHE_SAVE_INTERVAL:
                self.saveNodeCache(self.FileName, self.nodes)
                self.lastSave = now

    # Parse Meshtastic message received by LoraRX
    def parse(self, msg: bytes):
        try:
            # Try parsing JSON
            data = json.loads(msg)
            # Meshtastic packet must have payload and valid CRC
            if "payload" in data and "crc" in data and data["crc"] >= 1:
                return self.parsePacket(base64.b64decode(data["payload"]))
        except Exception as e:
            logger.error("Exception parsing message: %s", str(e))
        # Message could not be parsed
        msg = msg.decode("utf-8", errors="replace")
        logger.info("Failed parsing message: '%s'", msg)
        return msg + "\n"

    # Return TRUE if we got a duplicate packet, else FALSE
    def isDuplicatePacket(self, src: int, packetId: int) -> bool:
        now = time.monotonic()
        key = (src, packetId)
        if key in self.seen and now - self.seen[key] < self.DEDUP_TTL:
            return True
        self.seen[key] = now
        if len(self.seen) > self.DEDUP_MAX:
            cutoff = now - self.DEDUP_TTL
            self.seen = { k: v for k, v in self.seen.items() if v > cutoff }
        return False

    #
    # Parse Meshtastic packet (header + payload)
    #
    def parsePacket(self, data: bytes):
        # Must have 16-byte header
        if len(data) < 16:
            return None

        # Parse header
        dst       = int.from_bytes(data[0:4], "little")
        src       = int.from_bytes(data[4:8], "little")
        packet_id = int.from_bytes(data[8:12], "little")
        flags     = data[12]

        # Drop duplicates
        if self.isDuplicatePacket(src, packet_id):
            return None

        # Place header data into the output
        out = {
            "mode":         "Meshtastic",
            "timestamp":    round(datetime.now(timezone.utc).timestamp() * 1000),
            "dst":          dst,
            "src":          src,
            "packet_id":    packet_id,
            "hop_limit":    flags & 0x07,
            "hop_start":    (flags >> 5) & 0xE0,
            "want_ack":     bool(flags & 0x08),
            "via_mqtt":     bool(flags & 0x10),
            "channel_hash": data[13],
            "next_hop":     data[14],
            "relay_node":   data[15],
        }

        # Add reception frequency, if known
        if self.frequency:
            out["freq"] = self.frequency

        # If packet has data and we can decrypt it...
        if _aes_available and _protobuf_available and len(data) > 16:
            try:
                # Prepare decryption engine
                prefix = packet_id.to_bytes(8, "little") + src.to_bytes(4, "little")
                ctr    = Counter.new(32, prefix=prefix, initial_value=0)
                cipher = AES.new(self.key, AES.MODE_CTR, counter=ctr)

                # Decrypt and parse packet data
                parsed = mesh_pb2.Data()
                parsed.ParseFromString(cipher.decrypt(data[16:]))
                self.parsePayload(out, int(parsed.portnum), parsed.payload)

            except Exception as e:
                logger.debug("Decrypt/decode failed for !%08x: %s", out["src"], e)

        # Annotate src address with cached names/role/hw_model (if known)
        if src in self.nodes:
            for key, field in (
                ("short_name", "src_short_name"), ("long_name", "src_long_name"),
                ("role", "src_role"), ("hw_model", "src_hw_model")
                ):
                if key in self.nodes[src]:
                    out[field] = self.nodes[src][key]

        # Annotate dst address with cached names/role/hw_model (if known)
        if dst != 0xFFFFFFFF and dst in self.nodes:
            for key, field in (("short_name", "dst_short_name"), ("long_name", "dst_long_name")):
                if key in self.nodes[dst]:
                    out[field] = self.nodes[dst][key]

        # Update map marker
        if "lat" in out and "lon" in out:
            loc = MeshtasticLocation(out["lat"], out["lon"], out)
            Map.getSharedInstance().updateLocation(f"!{src:08x}", loc, "Meshtastic", self._band)

        # Report received packet
        ReportingEngine.getSharedInstance().spot(out)

        # Done
        return out

    #
    # Parse decrypted Meshtastic payload
    #
    def parsePayload(self, out, port, payload):
        # Add port number and name
        out["port"]      = port
        out["port_name"] = portnums_pb2.PortNum.Name(port)

        # For text messages, add text
        if port in (1, 7):
            try:
                out["message"] = payload.decode("utf-8")
            except Exception:
                out["message"] = payload.decode("utf-8", errors="replace")
            return

        cls = APP_PROTO_DECODERS.get(port)
        if cls is None:
            return

        try:
            msg = cls()
            msg.ParseFromString(payload)
            data = MessageToDict(msg, preserving_proto_field_name=True)
            out["data"] = data

            if port == 3:
                if "latitude_i" in data:
                    out["lat"] = int(data["latitude_i"]) / 10000000
                if "longitude_i" in data:
                    out["lon"] = int(data["longitude_i"]) / 10000000
                if "altitude" in data:
                    out["alt"] = int(data["altitude"])
                self.cacheNode(src, out)
            elif port == 4:
                out["comment"] = _nodeinfo_summary(data)
                self.cacheNode(src, data)
            elif port == 5:
                out["comment"] = _routing_summary(data)
            elif port == 6:
                out["comment"] = _summarize_fields(data, [("set_owner", "owner"), ("set_config", "config"), ("reboot_seconds", "reboot")])
            elif port == 8:
                if "name" in data and "latitude_i" in data and "longitude_i" in data:
                    out["waypoint"] = {
                        "name" : data["name"],
                        "lat"  : int(data["latitude_i"]) / 10000000,
                        "lon"  : int(data["longitude_i"]) / 10000000
                    }
                else:
                    out["comment"] = _summarize_fields(data)
            elif port == 67:
                out["comment"] = _telemetry_summary(data)
            elif port == 70:
                out["comment"] = _summarize_fields(data, [("route", "route"), ("route_back", "route_back")])
            elif port == 71:
                out["comment"] = _summarize_fields(data, [("node_id", "node"), ("neighbors", "neighbors")])
            elif port == 72:
                out["comment"] = _summarize_fields(data, [("contact", "contact"), ("group", "group")])
            else:
                out["comment"] = _summarize_fields(data)

    except Exception:
        logger.debug("Payload parsing failed for !%08x: %s", out["src"], e)
        return None
