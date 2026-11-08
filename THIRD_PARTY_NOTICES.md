# Third-party sources and licensing

This is a mixed-origin integration project, not a blanket relicensing of RR, Android, LK, MediaTek, OPPO or bundled utilities. Existing source headers and licenses continue to apply. No private signing material or complete vendor firmware is included in Git.

| Component | Source / provenance |
| --- | --- |
| LK base | https://github.com/svoboda18/lk at `37ec8bcbc4361c0e267617f517d154656804c17a` |
| OPPO A1k LK port | https://github.com/calan152/oppo-a1k-lk at `85dafe8efffac84f601d32b6a086f0cd4ab512c1` |
| OPPO kernel / panel lineage | https://github.com/oppo-source/A1k-9.0-kernel-source and https://github.com/Frostleaft07/kernel_source_OP486C |
| TWRP | https://github.com/TeamWin/android_bootable_recovery; exact source revisions in the pinned manifest |
| RR GSI | https://sourceforge.net/projects/resurrection-remix-q-gsi/ |
| Magisk | https://github.com/topjohnwu/Magisk, v31.1 |
| Termux btop and libc++ | https://github.com/termux/termux-packages; btop 1.4.8 ARM64 and libc++ 30 ARM64 |
| APK tooling | https://github.com/iBotPeaches/Apktool, v2.11.1 |
| Android development certificate | AOSP platform_build `android-10.0.0_r47`, `target/product/security/platform.x509.pem` |

The LK base carries MIT terms, while imported vendor and kernel-derived files have their own notices. Kernel-derived panel code retains the source headers. Public verification-key constants in target source are not private signing keys. The consolidated patch includes upstream port changes and this handset's changes; it does not claim exclusive authorship.

Stock kernel/DTB and vendor inputs are not rebuilt by this project. Publishing binary firmware derivatives requires appropriate redistribution rights and applicable corresponding-source obligations; a source reference alone is not a claim that those obligations are satisfied. Prefer upstream links for unchanged RR, Magisk and Termux downloads. The release inventory distinguishes tested technical artifacts from a redistribution clearance.

No single LICENSE is asserted for the entire collection. New repository glue and documentation have not been assigned a separate blanket license by the repository owner; choose one explicitly if you want to grant additional reuse rights. Upstream notices remain applicable regardless.
