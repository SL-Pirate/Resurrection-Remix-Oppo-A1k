# Installation scope and recovery

This repository records a successful device-specific bring-up. It is **not a universal one-click installer**. A complete unattended clean-room rebuild and fresh-device installation have not been tested. The boot/recovery repack scripts preserve the original workspace layout and require documented, locally supplied intermediate inputs.

## Required preparation

Verify CPH1923 / OP486C, stock CPH1923EX_11_A.43, board 2739 and HX8394F panel before considering these exact images. Preserve your own original boot, recovery, LK/LK2, vbmeta, DTBO, partition table and modem/calibration partitions. Never substitute another phone's NVRAM/NVDATA, persist/protect data or identity-bearing backups. Keep a working recovery route and a verified backup before a firmware write.

The tested process used MediaTek BootROM access through MTKClient to back up partitions and recover from failed boots, an unlocked bootloader, and disabled AVB verification. ADB works only after Android/recovery exposes it; it is not the BootROM interface. Unlocking and the RR installation erased userdata. The no-FBE overlay does not migrate encrypted data.

## Tested final partition roles

| Partition | Content |
| --- | --- |
| `lk` | Custom final boot-menu image |
| `lk2` | Original stock image retained |
| `boot` | Standard v1 Magisk/no-FBE fix1 image |
| `recovery` | Standalone TWRP fix1 image |
| `system` | RR 8.7.3 ARM64 AB vanilla/no-su GSI |
| `vbmeta` | Verification disabled for this unlocked setup |
| `vendor`, `odm`, modem partitions, `dtbo` | Original stock content retained |

No preloader or GPT rewrite is part of the final port. Do not flash intermediate images marked RAM-ONLY, UNTESTED, experimental or rejected. Fastboot transfer progress is not Android boot progress. TWRP's Install Image function needs the correct partition target, not a filesystem directory.

## Telephony overlay payload

The release `.tar.gz` is a **module directory backup**, not a TWRP flashable ZIP or Magisk installer ZIP. Extract it on the host. With working Magisk root, copy its directory to `/data/adb/modules/op486c_telephony_fix`, retaining the directory structure, readable file modes and executable directory modes. Label its `system` subtree `u:object_r:system_file:s0`, then reboot. The payload contains `module.prop`, `system/priv-app/TeleService/TeleService.apk` and `.replace` to hide old oat files. Confirm the installed APK hash against the release manifest. The original system APK remains intact.

The telephony patch is pinned to the exact RR APK in `manifests/telephony.json`; applying it to an unrelated Android build is not supported.

After installation, validate root, Enforcing status, recovery access, cameras/audio/Wi-Fi, SIM registration, calls and data. Dual-SIM success here is user-reported with two cards; individual per-card combinations were not exhaustively logged.
