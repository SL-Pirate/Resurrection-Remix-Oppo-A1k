# Resurrection Remix for OPPO A1k

Unofficial **OPPO A1k CPH1923 / OP486C** bring-up using Resurrection Remix **8.7.3 (Android 10)**, TWRP **3.7.0_9**, Magisk **31.1**, and a custom Little Kernel boot menu. This is a device integration and repair project around an existing RR GSI, not a new build of the RR Android source tree.

Tested on one 2 GB handset with stock **CPH1923EX_11_A.43**, board ID **2739**, and the **HX8394F 720×1560** display. Other A1k panel/firmware variants are not validated.

## Verified results

| Feature | Result |
| --- | --- |
| RR startup / Magisk root | Working after reboot; SELinux Enforcing |
| TWRP | Display, touch, root ADB, internal storage and SD card work |
| Wi-Fi, front/rear camera previews, flash, speaker | User confirmed |
| Light/proximity sensors | Runtime events observed |
| Cellular | Calls, mobile data and incoming SMS confirmed by user |
| Dual SIM | User tested with two SIMs and confirmed operation |
| btop 1.4.8 | Live monitoring works and survives reboot |
| Swap | 1 GiB LZ4 zRAM + 4 GiB storage swap, verified after reboot |
| Bluetooth, GPS, outgoing SMS | Not explicitly tested |

**Userdata encryption is disabled** by the tested early-init fstab overlay. The stock vendor/kernel stack remains in use. GApps are not included or tested. This Android/vendor combination is old and is not a current security-maintained release.

## Start here

- [Build and source provenance](docs/BUILD.md)
- [Installation scope and recovery](docs/INSTALLATION.md)
- [What broke and what fixed it](docs/TECHNICAL_NOTES.md)
- [Boot menu and maintenance](docs/MAINTENANCE.md)
- [Files to attach to a release](docs/RELEASE_ASSETS.md)
- [Third-party sources and licensing](THIRD_PARTY_NOTICES.md)

The repository contains source patches, the TWRP device tree, module scripts, recorded artifact hashes, and the seven tested binary assets in [assets/](assets/). Each included asset is below 100 MB. The large RR GSI, original packages, private logs, device backups, toolchains and signing keys remain outside Git. No command in this README flashes a device.

This is an independent project, not an official OPPO, Resurrection Remix, TeamWin or Magisk release. The measured results apply to the exact tested configuration, not every phone sold as an A1k.
