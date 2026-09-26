#!/usr/bin/env python3
"""Validate installed artifacts before accepting a source-build success stamp."""
import argparse
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from owrx.feature_probes import soapy_registry, acars_version, run_probe

FACTORIES = {
    "soapyrtlsdr": "rtlsdr", "soapyafedri": "afedri",
    "soapyairspy": "airspy", "soapyairspyhf": "airspyhf",
    "soapybladerf": "bladerf", "soapyelad": "elad",
    "soapyfcdpp": "fcdpp", "soapyhackrf": "hackrf",
    "soapyhydra": "hydrasdr", "soapyiqfile": "iqfile",
    "limesuite": "lime", "soapymalahit": "malahitrr",
    "soapymiri": "soapymiri", "soapypluto": "plutosdr",
    "radioberry": "radioberry", "extio_sddc": "sddc",
    "soapysdrplay": "sdrplay", "soapyremote": "remote",
    "soapysx": "sx", "soapyuhd": "uhd",
}


def cli_output(executable, option="-h"):
    if not executable.is_file():
        raise RuntimeError(f"not installed: {executable}")
    result = subprocess.run(
        [str(executable), option], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=15, check=False, text=True, errors="replace",
    )
    # These command-line tools use either 0 or 1 for their help option.
    # Loader failures (127), signals, and timeouts are not successes.
    if result.returncode not in (0, 1) or not result.stdout.strip():
        raise RuntimeError(f"{executable.name} help failed ({result.returncode}): {result.stdout}")
    return result.stdout


def validate(component, prefix, model="tiny"):
    if component in FACTORIES:
        factories, probe = soapy_registry()
        factory = FACTORIES[component]
        if factory not in factories:
            raise RuntimeError(f"{component}: factory {factory!r} is not registered/loadable\n{probe.error}\n{probe.output}")
    elif component == "acarsdec":
        output = cli_output(prefix / "bin/acarsdec")
        version = acars_version(output)
        if not version or tuple(map(int, version.split("."))) < (4, 0):
            raise RuntimeError(f"ACARS version must be >= 4.0; installed banner:\n{output}")
    elif component == "tetrarx":
        cli_output(prefix / "bin/tetrarx")
    elif component == "sddc_connector":
        output = cli_output(prefix / "bin/sddc_connector", "--version")
        if not re.search(r"^sddc_connector version ", output, re.M):
            raise RuntimeError(f"unexpected SDDC connector version output:\n{output}")
    elif component == "whisper":
        cli_output(prefix / "bin/whisper-server", "--help")
        if model != "none":
            path = prefix / "share/whisper" / f"ggml-{model}.bin"
            if not path.is_file() or not path.stat().st_size:
                raise RuntimeError(f"Whisper model missing: {path}")
    elif component == "codecserver":
        cli_output(prefix / "bin/codecserver", "--version")
    elif component == "codecserver-mbelib":
        # Merely finding a plugin file is not enough: verify ABI dependencies load.
        library = prefix / "lib/codecserver/libmbelib.so"
        result = run_probe((sys.executable, "-c", "import ctypes, sys; ctypes.CDLL(sys.argv[1])", str(library)))
        if result.returncode != 0:
            raise RuntimeError(f"AMBE plugin is not loadable: {library}\n{result.error}\n{result.output}")
    # Other components retain their existing recipe-specific checks.


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component")
    parser.add_argument("prefix", type=Path)
    parser.add_argument("model", nargs="?", default="tiny")
    args = parser.parse_args()
    try:
        validate(args.component, args.prefix, args.model)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
