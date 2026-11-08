# Boot and maintenance

Every startup opens the custom LK menu. Volume Up cycles selections; Power confirms. Select **START RR (MAGISK)** for Android or **TWRP RECOVERY** for recovery, then release all keys. The menu shows a startup acknowledgement; the image can remain on screen until Android draws. Allow roughly one to two minutes for startup.

Do not relock the bootloader with this custom unsigned configuration.

## Magisk

The tested BOOT ramdisk intentionally retains `RECOVERYMODE=true` for legacy-SAR routing. Magisk **Direct Install** can therefore choose RECOVERY instead of BOOT and overwrite the separate TWRP setup. Updating root needs explicit file-only patching, verification that the no-FBE overlay and routing are preserved, and installation of the verified image to BOOT. App-only updates are separate.

## Modules and rollback

- `op486c_telephony_fix`: guards the nonnumeric modem ID crash; supplied as an overlay payload. Disable in Magisk and reboot to restore the original system APK.
- `op486c_zram`: starts compressed swap, and storage swap if `/data/adb/op486c-storage.swap` already exists. Disable and reboot to stop both. The inactive swapfile can then be removed to reclaim 4 GiB. The service never allocates the file itself.
- `op486c_btop`: exposes `/sbin/btop`. Run `su`, then `btop`. Grant the terminal root in Magisk if needed. GPU monitoring is disabled in this upstream build. Configuration is `/data/adb/op486c-btop/btop.conf`.

If a module blocks Android startup, use working TWRP to create an empty `disable` file in `/data/adb/modules/<module-id>/`, then reboot. Unencrypted userdata was readable in the tested recovery.

The source-only `modules/btop` directory requires the upstream ARM64 binary and its private C++ runtime before installation. The source-only telephony module requires the rebuilt APK. Do not install incomplete directories as working modules.
