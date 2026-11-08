# Release assets

The seven tested artifacts below are committed in [assets/](../assets/), each below 100 MB. You can download them directly from Git or optionally attach copies to a GitHub release. The large upstream RR GSI remains outside Git.

| Included in `assets/` | Size (MiB) | Purpose |
| --- | ---: | --- |
| `boot-magisk-31.1-OP486C-nofbe-fix1.img` | 32.00 | BOOT; tested normal Android startup |
| `twrp-3.7.0_9-OP486C-bringup1-fix1.img` | 32.00 | RECOVERY; standalone TWRP |
| `lk-OP486C-final-menu.bin` | 1.00 | LK primary only; stock LK2 retained |
| `vbmeta-OP486C-disable-verification.img` | 8.00 | AVB configuration used by unlocked setup |
| `OP486C-telephony-module-payload-v1.tar.gz` | 4.06 | op486c_telephony_fix: module payload backup, NOT a flashable/installable ZIP |
| `OP486C-zram-module-payload-v1.tar.gz` | 0.00 | op486c_zram: module payload backup, NOT a flashable/installable ZIP |
| `OP486C-btop-module-payload-v1.tar.gz` | 1.09 | op486c_btop: module payload backup, NOT a flashable/installable ZIP |

Checksums are included as [assets/SHA256SUMS](../assets/SHA256SUMS). If mirroring assets into a release, attach that file too. Core device images and the telephony payload belong together; btop and swap are optional. See [installation notes](INSTALLATION.md) for payload layout and prerequisites. The tarballs are directory payloads, not recovery flash packages.

The only large upstream download is `RR-8.7.3-system-arm64-ab-vanilla-nosu-userdebug.img.xz` (781.03 MiB). Prefer [the upstream download](https://downloads.sourceforge.net/project/resurrection-remix-q-gsi/compressed/system-arm64-ab-vanilla-nosu-userdebug.img.xz). If you choose to mirror it, use that completed `.img.xz`, not the `.part`, chunk directory, or expanded raw image. The upstream XZ expands to an Android sparse system image; the separately verified raw system SHA-256 is `017669590688b0d359329c41200b17a70d8209db0eef782d1fdf4390f654293f`.

Published hashes and exact byte counts are in [release-assets.json](../manifests/release-assets.json). Hashes identify the tested files; they are not authenticity signatures.

Never attach full stock backups, NVRAM/NVDATA, protect/persist partitions, GPT dumps, seccfg, para, expdb, userdata, radio/crash logs, private keys or local access details. Exclude all RAM-ONLY, UNTESTED, experimental and rejected images.

Firmware derivatives retain upstream/vendor licensing obligations. See [third-party notices](../THIRD_PARTY_NOTICES.md). The source tree does not imply that every binary is cleared for public redistribution.
