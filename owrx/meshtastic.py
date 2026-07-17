from owrx.toolbox import TextParser
from owrx.color import ColorCache
from owrx.reporting import ReportingEngine
from owrx.map import Map, LatLngLocation
from owrx.bands import Bandplan, Band
from owrx.storage import Storage
from datetime import datetime, timezone, timedelta
from owrx.config import Config

import threading
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
    logger.warning("Meshtastic package not installed, payload decoding disabled. Install with: 'apt install python3-meshtastic' OR 'pip install meshtastic'")

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

def getSymbolData(symbol, table):
    return {"symbol": symbol, "table": table, "index": ord(symbol) - 33, "tableindex": ord(table) - 33}

def _expand_short_psk(index):
    key = bytearray(DEFAULT_KEY)
    key[-1] = (key[-1] + index - 1) & 0xFF
    return bytes(key)

def _resolve_key(raw_key):
    raw = raw_key.strip()
    if raw.lower() in ["default", "aq=="]:
        return _expand_short_psk(1)
    candidate = raw[2:] if raw.lower().startswith("0x") else raw
    candidate = candidate.replace(":", "").replace("-", "")
    if len(candidate) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in candidate):
        key = bytes.fromhex(candidate)
    else:
        key = base64.b64decode(raw, validate=True)
    if len(key) == 1:
        return _expand_short_psk(key[0])
    elif len(key) in [16, 32]:
        return key
    elif 1 < len(key) < 16:
        return key + b"\x00" * (16 - len(key))
    elif 16 < len(key) < 32:
        return key + b"\x00" * (32 - len(key))
    else:
        raise ValueError(f"Unsupported key length: {len(key)}")


class MeshtasticCache():
    CACHE_FILENAME = "meshtastic.json"
    CACHE_SAVE_INTERVAL = 60 * 60
    CACHE_TTL = 7 * 24 * 60 * 60

    sharedInstance = None
    creationLock = threading.Lock()

    # Return a global instance of the Meshtastic node cache.
    @staticmethod
    def getSharedInstance():
        with MeshtasticCache.creationLock:
            if MeshtasticCache.sharedInstance is None:
                MeshtasticCache.sharedInstance = MeshtasticCache()
        return MeshtasticCache.sharedInstance

    def __init__(self):
        self.fileName  = Storage.getFilePath(self.CACHE_FILENAME)
        self.lastSave  = time.monotonic()
        self.cacheLock = threading.RLock()
        self.nodeCache = self.loadNodeCache(self.fileName)

    def loadNodeCache(self, fileName: str):
        with self.cacheLock:
            try:
                with open(fileName, "r") as f:
                    nodes = json.load(f)
                    now   = time.monotonic()
                    return { int(k): v for k, v in nodes.items() if now - v["seen"] < self.CACHE_TTL }
            except Exception as e:
                logger.error("Failed loading node cache from '%s': %s", fileName, e)
        return {}

    def saveNodeCache(self, fileName: str, data) -> bool:
        with self.cacheLock:
            try:
                with open(fileName, "w") as f:
                    json.dump(data, f)
                    return True
            except Exception as e:
                logger.error("Failed saving node cache to '%s': %s", fileName, e)
        return False

    def getNode(self, node: int):
        with self.cacheLock:
            return self.nodeCache[node] if node in self.nodeCache else None

    def cacheNode(self, node: int, data):
        with self.cacheLock:
            # Our current time
            now = time.monotonic()
            # Collect cacheable fields
            updates = {}
            for key in ["lat", "lon", "altitude", "long_name", "short_name", "role", "hw_model", "is_licensed"]:
                if key in data:
                    updates[key] = data[key]
            # Update cached node information
            if updates:
                if node in self.nodeCache:
                    self.nodeCache[node].update(updates)
                else:
                    self.nodeCache[node] = updates
                # Save last-seen timestamp
                self.nodeCache[node]["seen"] = now
            # If it is time to save...
            if now - self.lastSave >= self.CACHE_SAVE_INTERVAL:
                self.saveNodeCache(self.fileName, self.nodeCache)
                self.lastSave = now


class MeshtasticLocation(LatLngLocation):
    def __init__(self, lat, lon, data):
        super().__init__(lat, lon)
        self.data = { k: v for k, v in data.items() if k in [
            "symbol", "altitude", "nickName", "longName", "device", "role",
            "weather", "battery", "uptime", "channelUse", "airtimeUse"
        ]}
        # Using same TTL as other semi-static map objects
        pm  = Config.get()
        ttl = pm["map_position_retention_time"]
        self.data["ttl"] = data["timestamp"] + ttl * 1000

    def __dict__(self):
        res = super().__dict__()
        res.update(self.data)
        return res


class MeshtasticParser(TextParser):
    DEDUP_TTL = 60
    DEDUP_MAX = 4096

    def __init__(self, service: bool = False) -> None:
        super().__init__(filePrefix="MHTC", service=service)
        self.colors = ColorCache()
        self.band   = None
        self.seen   = {}
        self.key    = _resolve_key("AQ==")

    def setDialFrequency(self, frequency: int) -> None:
        super().setDialFrequency(frequency)
        self.band = Bandplan.getSharedInstance().findBand(frequency)

    # Parse Meshtastic message received by LoraRX
    def parse(self, msg: bytes):
        # Try parsing JSON, drop out if failed (not JSON)
        try:
            data = json.loads(msg)
        except Exception:
            return None
        # Meshtastic packet must have payload and valid CRC
        if "payload" not in data or "crc" not in data or data["crc"] < 1:
            return None
        # Try parsing Meshtastic packer
        try:
            return self.parsePacket(base64.b64decode(data["payload"]))
        except Exception as e:
            logger.error("Initial parse failed: %s", e)
        # Could not parse
        return None

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

        #logger.info("Parsing %d-byte packet from !%08x to !%08x", len(data), src, dst)

        # Drop duplicates
        if self.isDuplicatePacket(src, packet_id):
            return None

        # Parse rest of header
        hop_limit    = flags & 0x07
        hop_start    = (flags >> 5) & 0x07
        want_ack     = bool(flags & 0x08)
        via_mqtt     = bool(flags & 0x10)
        channel_hash = data[13]
        next_hop     = data[14]
        relay_node   = data[15]

        # Place header data into the output
        out = {
            "mode":      "Meshtastic",
            "timestamp": round(datetime.now(timezone.utc).timestamp() * 1000),
            "comment":   f"{len(data)} bytes, hop {hop_start-hop_limit}/{hop_start}",
            "dst":       dst,
            "src":       src,
            "color":     self.colors.getColor(src),
            "symbol":    getSymbolData(",", "M"),
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
                logger.error("Decrypt/decode failed for !%08x: %s", src, e)

        # Annotate src address with cached information
        cached = MeshtasticCache.getSharedInstance().getNode(src)
        if cached:
            for key, field in [
                ("short_name", "nickName"), ("long_name", "longName"),
                ("role", "role"), ("hw_model", "device"),
                ("lat", "lat"), ("lon", "lon"), ("altitude", "altitude")
                ]:
                if key in cached:
                    out[field] = cached[key]

        # Annotate dst address with cached information
        cached = MeshtasticCache.getSharedInstance().getNode(dst)
        if dst != 0xFFFFFFFF and cached:
            for key, field in [("short_name", "dstNickName"), ("long_name", "dstLongName")]:
                if key in cached:
                    out[field] = cached[key]

        # Update map marker
        if "lat" in out and "lon" in out:
            loc = MeshtasticLocation(out["lat"], out["lon"], out)
            Map.getSharedInstance().updateLocation(f"!{src:08x}", loc, "Meshtastic", self.band)

        # Report received packet
        ReportingEngine.getSharedInstance().spot(out)

        # Done
        #logger.info(f"Decoded: {out}")
        return out

    #
    # Parse decrypted Meshtastic payload
    #
    def parsePayload(self, out, port, payload):
        #logger.info("Parsing payload for port %d", port)

        # Add port number and name
        out["port"] = port
        out["type"] = portnums_pb2.PortNum.Name(port)

        # For text messages, add text
        if port in [1, 7]:
            out["message"] = payload.decode("utf-8", errors="replace")
            return

        # If no protobuf decoder for the port, drop out
        if port not in APP_PROTO_DECODERS:
            return

        try:
            msg = APP_PROTO_DECODERS[port]()
            msg.ParseFromString(payload)
            data = MessageToDict(msg, preserving_proto_field_name=True)
            out["data"] = data

            if port == 3: # POSITION_APP
                if "latitude_i" in data:
                    out["lat"] = int(data["latitude_i"]) / 10000000
                if "longitude_i" in data:
                    out["lon"] = int(data["longitude_i"]) / 10000000
                if "altitude" in data:
                    out["altitude"] = int(data["altitude"])
                MeshtasticCache.getSharedInstance().cacheNode(out["src"], out)
            elif port == 4: # NODEINFO_APP
                MeshtasticCache.getSharedInstance().cacheNode(out["src"], data)
            elif port == 5: # ROUTING_APP
                if data.get("error_reason") == "NONE":
                    del data["error_reason"] # skip anoying messages
            elif port == 8: # WAYPOINT_APP
                if "name" in data and "latitude_i" in data and "longitude_i" in data:
                    out["waypoint"] = {
                        "name" : data["name"],
                        "lat"  : int(data["latitude_i"]) / 10000000,
                        "lon"  : int(data["longitude_i"]) / 10000000
                    }
            elif port == 67: # TELEMETRY_APP
                if "device_metrics" in data:
                    metrics = data["device_metrics"]
                    if "voltage" in metrics:
                        out["battery"] = metrics["voltage"]
                    if "uptime_seconds" in metrics:
                        out["uptime"] = metrics["uptime_seconds"]
                    if "channel_utilization" in metrics:
                        out["channelUse"] = metrics["channel_utilization"]
                    if "air_util_tx" in metrics:
                        out["airtimeUse"] = metrics["air_util_tx"]
                if "environment_metrics" in data:
                    metrics = data["environment_metrics"]
                    weather = {}
                    if "temperature" in metrics:
                        weather["temperature"] = metrics["temperature"]
                    if "relative_humidity" in metrics:
                        weather["humidity"] = metrics["relative_humidity"]
                    if "barometric_pressure" in metrics:
                        weather["barometricpressure"] = metrics["barometric_pressure"]
                    if weather:
                        out["weather"] = weather

        except Exception as e:
            logger.error("Payload parsing failed for !%08x: %s", out["src"], e)
