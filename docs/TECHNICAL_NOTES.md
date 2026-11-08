# Bring-up findings

## RR stopped at the OPPO logo

Android init reached `vdc --wait cryptfs enablefilecrypto` with the stock vendor fstab forcing FBE. The underlying Keymaster/TEE failure was not conclusively identified. Removing only `fileencryption=aes-256-xts` in a RAM-backed bind-mounted copy allowed startup. The overlay checks exact source and resulting fstab hashes and retains the original vendor file and SELinux label. It does not decrypt existing data. The tested installation used erased userdata and remains unencrypted.

## Normal boot versus recovery boot

The working Magisk ramdisk uses legacy system-as-root routing with `RECOVERYMODE=true`. A recovery-path kernel launch skipped normal modem/SCP initialization. The final BOOT image keeps the tested kernel and ramdisk but has a standard v1 boot header with both recovery DTBO fields zero and the embedded recovery overlay physically removed. Normal startup uses the retained stock DTBO partition. A separate TWRP image occupies RECOVERY.

## Modem was not initialized by custom LK

The custom loader calculated modem options but failed to export them into the final command line. The fix exports the calculated `opt_*` values after the last command-line rebuild and before FDT publication. It does not hardcode modem mode 9. The observed working configuration reports `opt_md1_support=9` and `opt_ps1_rat=Lf/Lt/W/G`.

## RR phone service crashed with an inserted SIM

`PhoneUtils.getPrimaryStackPhoneId()` called `Integer.parseInt()` on MediaTek's logical modem UUID `modem_sys1_ps0`. This crashed `com.android.phone` repeatedly, even though the SIM was READY and the modem was running. The patch catches `NumberFormatException`, skips that identifier, and uses the existing fallback when no numeric primary identifier is available. Numeric identifiers retain their original handling.

The APK was rebuilt with Apktool 2.11.1, using eight build workers. Its manifest and resources were unchanged. Its signer matches the installed public AOSP platform development certificate. Android rejected a normal package update because this is a persistent app; the final repair is a Magisk overlay. After reboot the crash stopped and LTE registration succeeded. The user subsequently tested calls, mobile data, incoming SMS and two SIMs.

## TWRP USB and MTP

Recovery uses the stock MediaTek configfs/musb-hdrc USB path. The MTP fix closes the constructor's descriptor before reopening the legacy MTP device, which permits only one open descriptor. The final fstab and patched MTP library are part of the tested fix1 recovery repack.

## Optional memory setup

The stock kernel supports zRAM but does not expose zswap or zRAM backing-device writeback. The tested arrangement is two independent swap areas: 1 GiB LZ4 zRAM at priority 100 and a fully allocated 4 GiB ext4 swapfile at priority 10. Swappiness remains 60. This is not zswap: existing zRAM pages are not automatically evicted into the storage swapfile. Storage swap is slower and writes to internal flash. Neither swap area adds physical RAM.
