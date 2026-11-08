# Publication validation

- Consolidated LK patch applies cleanly to the pinned upstream file versions and reproduces all 109 selected final source files byte-for-byte.
- Boot-menu actual-source regression tests pass for three profiles on the build host.
- Calculated modem-option export tests pass, including alternate values, malformed buffers and overflow handling.
- Python, shell and JSON syntax and relative Markdown links checked.
- Git contains text source/configuration only; no binary payloads, device identifier, local host paths, private signing material or files above 100 MB found by the publication scan.
- Firmware/module checksums and sizes recorded separately.

These checks do not establish a clean-room rebuild of every firmware artifact. Device behavior and user-confirmed hardware results are recorded in README.md. No extra phone write was needed to prepare this repository.
