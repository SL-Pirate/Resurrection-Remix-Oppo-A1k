# Secure screen lock: repaired compatibility issues

Status: **pattern enrollment, locking and unlocking work, including after reboot**, confirmed by the user on 2026-11-09. ADB independently confirmed a new boot, completed Android startup, the patched library hash, and the restored security-storage directory. PIN/password modes were not separately confirmed. **Userdata encryption remains disabled** (`ro.crypto.state=unsupported`); this repair does not enable FBE or establish that encryption is working.

## Symptoms and causes

Initially, Settings reported that the screen lock had already changed and asked the user to try again. Trustonic could not create `/data/vendor/mcRegistry/TbStorage/Store_0.tf` because its parent directory was missing. Stock `/vendor/etc/init/tee.rc` creates `/data/vendor/mcRegistry` for `unencrypted`, FBE-encrypted or FDE startup, but none of those triggers covers this GSI's `unsupported` crypto state.

Creating the missing parent with stock ownership/mode and restoring its SELinux label removed the warning, but enrollment still did not take effect. This directory repair alone was **not** a complete fix.

After reboot, `system_server` repeatedly crashed in `SyntheticPasswordCrypto.decryptBlob`, called by `tryDeriveAuthTokenForUnsecuredPrimaryUser`. The exception was `Failed to decrypt blob`, with keystore error **-62 (KEY_REQUIRES_UPGRADE)**. Launcher and System UI subsequently reported `DeadSystemException`; replacing or clearing the launcher would not address the cause.

RR's PHH `fixSPL()` rewrites version-property references in vendor Keymaster libraries and selected VNDK libraries. It missed the loaded **VNDK28** `/system/lib64/vndk-28/libsoftkeymasterdevice.so`. Vendor code was using the stock-compatible Android 9 properties, while this library still referenced the Android 10 GSI properties. Logs showed repeated key upgrades without resolving the error. Aligning the missing library's property references stopped the framework crash loop; subsequent user tests confirmed working pattern enrollment and unlock.

## Repair

The `op486c_keymaster_compat` Magisk module:

1. Creates `/data/vendor/mcRegistry` only if absent, using mode `0775`, owner `system:system`, and `restorecon` (observed label `u:object_r:mobicore_data_file:s0`). The Trustonic service creates its own child storage. Existing security state is not removed or reset.
2. Overlays the exact tested 64-bit VNDK28 library with two equal-length string replacements: `ro.build.version.release` → `ro.keymaster.xxx.release`, and `ro.build.version.security_patch` → `ro.keymaster.xxx.security_patch`.
3. Waits for PHH's version properties and the vendor Keymaster service, then restarts `vendor.keymaster-3-0` and the running keystore service once. This ensures the corrected properties/library are loaded. The wait is bounded to 90 seconds.

The system partition's original library remains unchanged. No credential database, synthetic-password blob, Gatekeeper state or keystore entry was deleted by the repair. Private local backups of those states and the original library were saved and checked before the library test. They are **not** included in this repository or its assets.

## Reproduce and install

Use `scripts/patch_keymaster.py ORIGINAL_LIBRARY NEW_OUTPUT` with the exact original library. It verifies the original hash, both unique strings, and the resulting hash, and refuses to overwrite an existing output.

- Original SHA-256: `338a4e6ceb00f5f8d30bb77013a6d2c7748c53e00eba1a1d7917c28a180f8c89`
- Patched SHA-256: `ee61b394cf60807faf7369ac529d9363355e4e1c88b10a58dccfcbb4d860f560`
- Both libraries: 202,584 bytes.

Put the output at `modules/keymaster/system/lib64/vndk-28/libsoftkeymasterdevice.so`. The supplied asset contains the complete tested module directory. Like the other module tarballs, it is a **directory payload backup, not a Magisk installer ZIP or TWRP flash package**. Install its root directory as `/data/adb/modules/op486c_keymaster_compat`, with directories and both shell scripts executable, ordinary files readable, and the library labeled `u:object_r:system_lib_file:s0`. Back up current security state locally before modifying an existing installation. Do not use another device's credential backup.

## Recovery and limitations

Keep ADB/TWRP recovery access and the original library. Disabling this module and rebooting restores the original system library, but **can reintroduce the synthetic-password crash loop now that credentials exist**. Treat this as a rollback mechanism, not a recommendation to test removal casually. From TWRP, an empty `/data/adb/modules/op486c_keymaster_compat/disable` file disables the overlay. Do not delete lock-settings, keystore, or Trustonic files as a generic fix.

This repair is pinned to this RR/vendor configuration. Hardware-backed attestation, all keystore algorithms, PIN/password enrollment and FBE remain outside the validated result. Fixing screen-lock authentication does not encrypt user files or make this old Android/vendor stack security-current.
