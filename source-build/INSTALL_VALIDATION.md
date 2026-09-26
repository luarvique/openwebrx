# Optional-component installation validation

`feature-report` measures software availability, not whether a radio is connected
or receiving usable RF. Receiver plugins are accepted only when SoapySDR's live
factory registry reports them; a `.so` filename alone is not sufficient.

## Rebuild the existing installation

Use the same prefix and work directory as the original build. For an installation
in `~/.local/openwebrx-dev`, after updating the `linux-source-build` branch:

```sh
export OWRX_PREFIX="$HOME/.local/openwebrx-dev"
./build-linux.sh --profile full build
./build-linux.sh feature-report
./build-linux.sh failures
./build-linux.sh diagnostics
```

Do not use `clean` or `--force` for this repair. The builder now revalidates the
installed artifacts before trusting a cached success. Missing executables,
unloadable Soapy factories, missing Whisper models, and an unloadable AMBE module
cause the affected component to be retried. Repository-owned patch contents are
included in success stamps, so a changed dependency patch also triggers a rebuild.
The first build with patch-aware stamps will rebuild previously stamped patched
dependencies. Existing unpatched, valid components retain their cache entries.

Build failures and prerequisite skips are retained across profile runs. A retry
replaces only that component's previous status, and a successful retry clears its
old failure/skip. A failed strict build is recorded before the script exits.
`failures` is a build-attempt log, not a substitute for `feature-report`.

## Components that can legitimately remain unavailable

| Feature | Required external prerequisite |
| --- | --- |
| `sdrplay` | Vendor SDRplay API v3, installed under the user's license terms. |
| `radioberry` | Supported ARM/aarch64 Raspberry Pi platform and hardware. |
| native `sddc` | CUDA toolkit with `nvcc`; this is distinct from `sddc_soapy`. |
| `speech` | A downloaded model and a model-ready local Whisper server, or a configured external service. `OWRX_WHISPER_MODEL=none` does not download a local model. |

The CPU Soapy SDDC target must build its plugin, not silently omit it when the
SoapySDR development package is missing. That requirement is stored as a patch
under `build/patches/extio_sddc/` and applied by the existing patch mechanism.

TETRA's existing source provider is a mutable HTTP directory on port 8025.
Retrieval now honors configured proxies, limits per-request waits/retries, and
checks required source files before compilation. Failed retrieval or compilation
remains a failure; it is never relabeled PASS. A complete native TETRA rebuild
still needs to be verified on the target host. The existing compatibility and
Makefile adjustments are not evidence of a successful decoder build.

## Offline regression checks

```sh
bash -n build-linux.sh
python3 -m unittest discover -s test/source_build -v
```

Tests cover all 20 Soapy component/factory mappings, cached and post-install
validation, failure/skip persistence, ACARS version provenance, malformed Whisper
health responses, and private-service ownership. With a C++ compiler installed,
a small native test applies the repository's DigiHAM patch to a temporary source
fixture and connects to a private Unix socket. This is not a full dependency build,
AMBE audio-decoding test, speech-transcription test, or hardware acceptance test.
