# Optional component verification

Run from the checkout, with the same OWRX_PREFIX/OWRX_CONFIG_FILE overrides used to build:

```sh
./build-linux.sh build
./build-linux.sh failures
./build-linux.sh feature-report
./build-linux.sh diagnostics
./build-linux.sh run
```

`failures` records compiler/install failures and also reports external/platform skips. Neither an empty failure list nor `doctor`'s executable presence checks prove feature parity. `feature-report` invokes the actual application probes. `diagnostics` additionally saves raw Soapy/AcarsDec output and the private service log tails to `.build-linux/logs/optional-diagnostics.txt`; JSON feature results are saved beside it. Runtime/diagnostic commands do not install or upgrade Python packages.

## SoapySDR

Only factories reported by a successful `SoapySDRUtil --info` invocation enable a receiver backend. Module filenames do not count: a file can exist while failing to load because of missing libraries or an ABI mismatch. Driver registration is checked without requiring receiver hardware to be connected. The existing feature catalogue and other checks are preserved in `owrx/feature_base.py`; bounded native command parsers are tested separately in `owrx/feature_probes.py`.

## AcarsDec

The integration patch derives the semantic version from the dependency's own `acarsdec.h` and obtains Git metadata with an explicit dependency working directory. It must not report the invoking OpenWebRX checkout's version or treat an opaque Git hash as a numeric AcarsDec version. The detector accepts both stderr/stdout help output, source suffixes and the decoder's help exit status.

## AMBE / CodecServer

The full build includes mbelib and its CodecServer module. A managed local configuration is written under `$PREFIX/var/run/openwebrx-source`, with a private Unix socket in that owner-only directory. Existing non-empty `digital_voice_codecserver` settings are preserved. The user's `$PREFIX/etc/codecserver/codecserver.conf` is not overwritten.

The DigiHAM integration patch makes its Unix socket client honor the supplied path, checks path length, and closes a failed connection. The AMBE feature check is an actual bounded protocol query in a separate Python process, not a check that a socket or executable exists.

`run`, `feature-report`, and `diagnostics` start the managed service when needed and stop only their own child processes. An already-running configured service is not killed. Logs are in `.build-linux/logs/codecserver-runtime.log`.

## Speech

The default build supplies whisper-server and the `tiny` model. Models are runtime data, not source code; the default model hash is checked by the builder. `OWRX_WHISPER_MODEL=none` omits local model downloading. Existing non-empty `speech_url` settings are preserved. An empty setting is populated for the managed loopback server only when the local binary and model are present.

The managed server binds to `127.0.0.1:8074` by default. The source feature report checks HTTP `/health` readiness, not merely whether any process is listening on the port. Runtime logs are in `.build-linux/logs/whisper-runtime.log`. A configured remote speech service is not started or stopped by this integration; its availability still depends on that service.

## External / platform constraints

SDRplay's open adapter still requires the separately installed vendor API. The native SDDC connector requires CUDA/nvcc; the distinct Soapy SDDC path does not become unavailable merely because that native connector is skipped. Radioberry support is built on its supported ARM/Raspberry Pi platform. These are explicit skips, never fabricated successful builds.

The TETRA recipe is retained in the full decoder plan and now runs a bounded `tetrarx -h` smoke check before recording success. Its legacy author-hosted HTTP source is not a commit-pinned Git dependency; this remains an exception to reproducibility, and an inaccessible source host or build failure must remain visible. It has not been RF-tested by the integration unit tests.

## Validation scope

CI runs shell syntax/help checks, the native probe/runtime unit tests, symbolic dependency reference checks, and application of repository-owned patches to pinned source revisions. These tests do not establish that every decoder compiles on every distribution, or that every receiver works with physical hardware. Local feature reports and RF tests remain separate evidence.
