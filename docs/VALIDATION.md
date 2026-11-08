# Publication validation

- Consolidated LK patch applies cleanly to the pinned upstream file versions and reproduces all 109 selected final source files byte-for-byte.
- Boot-menu actual-source regression tests pass for three profiles on the build host.
- Calculated modem-option export tests pass, including alternate values, malformed buffers and overflow handling.
- Python, shell and JSON syntax and relative Markdown links checked.
- Initial source publication was scanned for device identifiers, local host paths and private signing material.
- Seven explicitly selected tested binary assets were subsequently added at the owner's request. Each is below 100 MB and matches the recorded SHA-256 and size; device dumps and private logs remain excluded.
- Firmware/module checksums and sizes recorded separately.

These checks do not establish a clean-room rebuild of every firmware artifact. Device behavior and user-confirmed hardware results are recorded in README.md. No extra phone write was needed to prepare this repository.
