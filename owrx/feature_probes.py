"""Bounded, hardware-independent probes shared by source-build diagnostics.

A plugin filename is NOT evidence that the plugin loaded. Only an entry in
SoapySDR's live factory registry may enable a receiver type.
"""
from dataclasses import dataclass
import re
import subprocess
from typing import Optional, Tuple

_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_FACTORIES = re.compile(r"^\s*Available factories\.{3}[ \t]*(.*)$", re.I | re.M)
_VERSION = re.compile(r"\bAcarsdec\s+v?([0-9]+(?:\.[0-9]+)*)(?=[\s+\-]|$)", re.I)


@dataclass(frozen=True)
class ProbeResult:
    argv: Tuple[str, ...]
    returncode: Optional[int]
    output: str
    error: str = ""


def run_probe(argv, timeout=15):
    """Capture diagnostics without touching hardware, opening stdin or a shell."""
    args = tuple(argv)
    try:
        process = subprocess.run(
            args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, errors="replace",
            timeout=timeout, check=False,
        )
        return ProbeResult(args, process.returncode, process.stdout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        output = getattr(exc, "stdout", "") or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return ProbeResult(args, None, output, str(exc))


def parse_soapy_factories(output):
    """None means unrecognised output; an empty set means an empty registry."""
    match = _FACTORIES.search(_ANSI.sub("", output))
    if match is None:
        return None
    return frozenset(item.strip().casefold() for item in match.group(1).split(",") if item.strip())


def soapy_registry():
    """Query the loaded registry once, never enumerate/open physical devices."""
    result = run_probe(("SoapySDRUtil", "--info"))
    if result.returncode != 0:
        return frozenset(), result
    factories = parse_soapy_factories(result.output)
    if factories is None:
        result = ProbeResult(result.argv, result.returncode, result.output,
                             "SoapySDRUtil did not report an Available factories line")
        return frozenset(), result
    return factories, result


def acars_version(output):
    """Accept a semantic version, never turn an opaque git hash into a version."""
    match = _VERSION.search(_ANSI.sub("", output))
    return match.group(1) if match else None


def acars_probe():
    result = run_probe(("acarsdec", "-h"), timeout=5)
    # acarsdec's help deliberately exits with status 1 in some releases.
    if result.returncode not in (0, 1):
        return None, result
    return acars_version(result.output), result
