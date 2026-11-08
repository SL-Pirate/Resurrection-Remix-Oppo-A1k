#!/usr/bin/env python3
"""Compile/run real proposed LK helpers with memory-only I/O stubs on the build host.

Usage: python3 test-bcb-preservation.py PATH_TO_PATCHED_SOURCE_ROOT
No device access. A compiler is invoked; do not run on the phone/workstation.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source_root", type=Path)
parser.add_argument("--cc", default="cc")
args = parser.parse_args()
recovery = (args.source_root / "platform/common/recovery.c").read_text()
fdt = (args.source_root / "app/mt_boot/fdt_op.c").read_text()
helpers = recovery[recovery.index("static int mboot_recovery_set_misc("):
                   recovery.index("BOOL recovery_check_command_trigger(")]
early_dtb = fdt[fdt.index("void load_device_tree(void)"):
                fdt.index("int32_t parse_dtbo_tbl(")]

prefix = r'''
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define MTK_EMMC_SUPPORT
#define OPPO_RESCUE_FASTBOOT
#define CFG_DTB_EARLY_LOADER_SUPPORT
#define MISC_PAGES 3
#define MISC_COMMAND_PAGE 1
#define MODULE_NAME "test"
#define INFO 0
#define CRITICAL 1
#define TRUE 1
#define FALSE 0
#define PART_NOT_EXIST -1
#define PROFILING_START(x) ((void)0)
#define PROFILING_END() ((void)0)
#define dprintf lk_dprintf
typedef unsigned char uchar;
typedef int BOOL;
struct misc_message { char command[32], status[32], recovery[1024]; };
static unsigned char disk[6144], before[6144];
static int read_result, write_result, read_calls, write_calls, exists = 1;
static int dtb_calls;
static void lk_dprintf(int level, const char *fmt, ...) { (void)level; (void)fmt; }
static unsigned long get_timer(unsigned long begin) { (void)begin; return 0; }
static int partition_exists(const char *name) {
    assert(!strcmp(name, "misc")); return exists ? 0 : PART_NOT_EXIST;
}
static int mboot_recovery_load_misc(unsigned char *out, unsigned int size) {
    assert(size == sizeof(disk)); read_calls++;
    if (read_result > 0) memcpy(out, disk, (size_t)read_result);
    return read_result;
}
static long partition_write(const char *name, int offset, unsigned char *data, size_t size) {
    assert(!strcmp(name, "misc") && offset == 0 && size == sizeof(disk));
    write_calls++;
    if (write_result > 0) memcpy(disk, data, (size_t)write_result);
    return write_result;
}
static int bldr_load_dtb(const char *name) {
    assert(!strcmp(name, "recovery")); dtb_calls++; return 0;
}
/* Any attempted RTC/BCB access in the rescue early loader fails the test. */
int Check_RTC_Recovery_Mode(void) { assert(0); return 0; }
void Set_RTC_Recovery_Mode(int value) { (void)value; assert(0); }
int unshield_recovery_detection(void) { assert(0); return 0; }
static void reset(void) {
    unsigned i;
    for (i = 0; i < sizeof(disk); i++) disk[i] = (unsigned char)(i * 17 + 29);
    memcpy(before, disk, sizeof(disk));
    read_result = write_result = sizeof(disk);
    read_calls = write_calls = 0; exists = 1;
}
'''
tests = r'''
static void check_command(int (*fn)(void), const char *command) {
    unsigned char expected[32] = {0};
    memcpy(expected, command, strlen(command));
    reset(); assert(fn());
    assert(read_calls == 1 && write_calls == 1);
    assert(!memcmp(disk, expected, sizeof(expected)));
    assert(!memcmp(disk + 32, before + 32, sizeof(disk) - 32));
}
int main(void) {
    const int failures[] = {-EIO, 0, 6143};
    unsigned i;
    check_command(recovery_set_recovery_cmd, "boot-recovery");
    check_command(recovery_set_fastboot_cmd, "boot-fastboot");
    check_command(recovery_clear_bootloader_cmd, "");
    for (i = 0; i < sizeof(failures)/sizeof(failures[0]); i++) {
        reset(); read_result = failures[i];
        assert(!recovery_set_recovery_cmd());
        assert(read_calls == 1 && write_calls == 0);
        assert(!memcmp(disk, before, sizeof(disk)));
        reset(); write_result = failures[i];
        assert(!recovery_set_recovery_cmd());
        assert(read_calls == 1 && write_calls == 1);
    }
    reset(); exists = 0;
    assert(!recovery_clear_bootloader_cmd());
    assert(write_calls == 0 && !memcmp(disk, before, sizeof(disk)));
    reset(); load_device_tree();
    assert(dtb_calls == 1 && read_calls == 0 && write_calls == 0);
    assert(!memcmp(disk, before, sizeof(disk)));
    puts("PASS: command-only updates, unrelated-byte preservation, read/write failures, rescue DTB without BCB/RTC access");
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix="lk-bcb-test-") as work:
    source = Path(work) / "test.c"
    executable = Path(work) / "test"
    source.write_text(prefix + helpers + early_dtb + tests)
    subprocess.run([args.cc, "-std=c99", "-Wall", "-Wextra", "-Werror",
                    "-Wno-pointer-to-int-cast", "-O0", str(source),
                    "-o", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
