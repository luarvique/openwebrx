# Development notes

## Modbus RTU decoder

- Run `python3 -m unittest discover -s test -t .` for the Python suite and
  `python3 -m unittest -v test.modbus.test_modbus` for the decoder regressions.
- The pure Python tests need no SDR hardware or pycsdr. A passing unit suite
  does not establish end-to-end DSP or live receiver behavior.
- Keep real repeated ADUs and write echo responses. Parallel UART copies refer
  to the same character start sample; wall-clock proximity is not an identity.
- FskUartDecoder retains its `(dataBits, bytes)` output by default. The timed
  mode adds per-character start samples. FskUartModule and ModbusStreamDecoder
  share the line format `bits comma-separated-start-samples hex-bytes`.
- Reserve space for the maximum 256-byte RTU ADU plus eight leading junk bytes.
  Register responses must have an even byte count; request/response pairing must
  check the requested quantity before assigning register or coil addresses.
