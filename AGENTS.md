# Development notes

## Modbus RTU decoder

- Run `python3 -m unittest discover -s test -t .` for the Python suite and
  `python3 -m unittest -v test.modbus.test_modbus` for the decoder regressions.
- Protocol tests need no SDR hardware or pycsdr. Eight audio tests require
  CSDR/PyCSDR with native `FskUartDecoder`; they explicitly skip when unavailable.
  Acceptance requires running these tests with the real native dependency.
- Keep real repeated ADUs and write echo responses. Parallel UART copies refer
  to the same character start sample; wall-clock proximity is not an identity.
- FSK/UART DSP belongs to CSDR, exposed as `pycsdr.modules.FskUartDecoder`.
  Its native module and ModbusStreamDecoder share the line format
  `bits comma-separated-start-samples hex-bytes`.
- Import the optional native decoder inside the Modbus chain constructor and
  gate the mode with `csdr_fsk_uart`; older PyCSDR must still start other modes.
- Reserve space for the maximum 256-byte RTU ADU plus eight leading junk bytes.
  Register responses must have an even byte count; request/response pairing must
  check the requested quantity before assigning register or coil addresses.
