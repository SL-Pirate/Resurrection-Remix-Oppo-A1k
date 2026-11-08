#!/usr/bin/env python3
"""Test the actual proposed LK menu action code with memory-only stubs.

Run only on the build host (this invokes its C compiler):
  python3 test-rescue-storage-menu.py PATH_TO_PATCHED_SOURCE_ROOT
No phone access. --emit-only writes generated C files without compiling.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile


def extract_function(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    for pos in range(opening, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[start:pos + 1] + "\n"
    raise ValueError(f"Unterminated function: {signature}")


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source_root", type=Path)
parser.add_argument("--cc", default="cc")
parser.add_argument("--emit-only", type=Path)
args = parser.parse_args()
source = (args.source_root / "app/mt_boot/fastboot.c").read_text()
enum_start = source.index("enum oppo_fastboot_ui_action {")
selection = source[enum_start:source.index("static volatile bool oppo_fastboot_command_active", enum_start)]
array_start = source.index("static const char * const oppo_fastboot_ui_actions[] = {")
labels = source[array_start:source.index("};", array_start) + 2]
actions = extract_function(source, "static void oppo_fastboot_ui_run_action(")
whitelist = extract_function(source, "static bool oppo_rescue_fastboot_command_allowed(")

prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#define OPPO_PREVENT_BOOTLOADER_RELOCK
#define CRITICAL 0
#define PART_NOT_EXIST (-1)
#define dprintf lk_dprintf
typedef enum { NORMAL_BOOT = 0, RECOVERY_BOOT = 2 } BOOTMODE;
static bool oppo_fastboot_relock_guard_tripped;
static bool exists, clear_ok;
static int clear_calls, rtc_recovery_calls, rtc_fastboot_calls;
static int boot_calls, boot_mode, exit_calls, reset_calls, poweroff_calls;
static bool rtc_recovery, rtc_fastboot;
static char status[128];
static void lk_dprintf(int level, const char *fmt, ...) { (void)level; (void)fmt; }
static void oppo_fastboot_enforce_unlocked_state(const char *where) { (void)where; }
static void oppo_fastboot_ui_show_status(const char *message) {
    snprintf(status, sizeof(status), "%s", message);
}
static int partition_exists(const char *name) {
    assert(!strcmp(name, "misc")); return exists ? 0 : PART_NOT_EXIST;
}
static bool recovery_clear_bootloader_cmd(void) { clear_calls++; return clear_ok; }
static void Set_Clr_RTC_PDN1_bit13(bool value) {
    rtc_fastboot_calls++; rtc_fastboot = value;
}
static void Set_RTC_Recovery_Mode(bool value) {
    rtc_recovery_calls++; rtc_recovery = value;
}
static void oppo_fastboot_ui_boot_storage(BOOTMODE mode) { boot_calls++; boot_mode = mode; }
static void oppo_fastboot_ui_prepare_exit(void) { exit_calls++; }
static void mtk_arch_reset(int bypass_power_key) { assert(bypass_power_key == 1); reset_calls++; }
static void mt_power_off(void) { poweroff_calls++; }
static void reset_state(void) {
    exists = clear_ok = true;
    oppo_fastboot_relock_guard_tripped = false;
    clear_calls = rtc_recovery_calls = rtc_fastboot_calls = 0;
    boot_calls = exit_calls = reset_calls = poweroff_calls = 0;
    boot_mode = -1;
    rtc_recovery = rtc_fastboot = true;
    status[0] = '\0';
}
static void assert_no_action(void) {
    assert(boot_calls == 0 && clear_calls == 0 && exit_calls == 0);
    assert(reset_calls == 0 && poweroff_calls == 0);
    assert(rtc_recovery_calls == 0 && rtc_fastboot_calls == 0);
}
'''
tests = r'''

int main(void) {
    unsigned int action;
    const unsigned int storage_actions[] = {OPPO_FASTBOOT_UI_START, OPPO_FASTBOOT_UI_RECOVERY};
    const char *allow[] = {"getvar:all", "fetch:expdb", "download:00001000",
        "boot", "reboot", "poweroff", "flashing unlock", "flash:boot",
        "flash:recovery", "flash:dtbo", "flash:lk2"};
    const char *deny[] = {"continue", "erase:userdata", "flash:lk",
        "flash:preloader", "flash:seccfg", "flash:super", "reboot-recovery",
        "oem format", "flashing lock", "flash:recovery_extra"};
    for (action = 0; action < sizeof(allow) / sizeof(allow[0]); action++)
        assert(oppo_rescue_fastboot_command_allowed(allow[action]));
    for (action = 0; action < sizeof(deny) / sizeof(deny[0]); action++)
        assert(!oppo_rescue_fastboot_command_allowed(deny[action]));
    assert(oppo_fastboot_ui_selected == OPPO_FASTBOOT_UI_START);
#if defined(OPPO_RESCUE_FASTBOOT) && defined(OPPO_RESCUE_STORAGE_MENU)
    assert(!strcmp(oppo_fastboot_ui_actions[OPPO_FASTBOOT_UI_START], "START RR (MAGISK)"));
    assert(!strcmp(oppo_fastboot_ui_actions[OPPO_FASTBOOT_UI_RECOVERY], "TWRP RECOVERY"));
#else
    assert(!strcmp(oppo_fastboot_ui_actions[OPPO_FASTBOOT_UI_START], "START"));
    assert(!strcmp(oppo_fastboot_ui_actions[OPPO_FASTBOOT_UI_RECOVERY], "RECOVERY MODE"));
#endif
    for (action = 0; action < sizeof(storage_actions) / sizeof(storage_actions[0]); action++) {
        reset_state(); oppo_fastboot_ui_run_action(storage_actions[action]);
#if defined(OPPO_RESCUE_FASTBOOT) && !defined(OPPO_RESCUE_STORAGE_MENU)
        assert_no_action(); assert(strstr(status, "RESCUE MODE"));
#else
        assert(boot_calls == 1 && clear_calls == 1);
        assert(boot_mode == (storage_actions[action] == OPPO_FASTBOOT_UI_START ? NORMAL_BOOT : RECOVERY_BOOT));
        assert(rtc_fastboot_calls == 1 && !rtc_fastboot);
        assert(rtc_recovery_calls == 1 && !rtc_recovery);
#endif
#ifdef OPPO_RESCUE_STORAGE_MENU
        reset_state(); clear_ok = false;
        oppo_fastboot_ui_run_action(storage_actions[action]);
        assert(clear_calls == 1 && boot_calls == 0 && exit_calls == 0);
        assert(reset_calls == 0 && poweroff_calls == 0);
        assert(rtc_recovery_calls == 0 && rtc_fastboot_calls == 0);
        assert(strstr(status, "BCB clear failed"));
        reset_state(); exists = false;
        oppo_fastboot_ui_run_action(storage_actions[action]);
        assert_no_action(); assert(strstr(status, "BCB clear failed"));
#endif
    }
    for (action = 0; action < OPPO_FASTBOOT_UI_ACTION_COUNT; action++) {
        reset_state(); oppo_fastboot_relock_guard_tripped = true;
        oppo_fastboot_ui_run_action(action); assert_no_action();
    }
    reset_state(); oppo_fastboot_ui_run_action(OPPO_FASTBOOT_UI_RESTART_BOOTLOADER);
    assert(exit_calls == 1 && reset_calls == 1 && boot_calls == 0 && clear_calls == 0);
    assert(rtc_fastboot_calls == 1 && rtc_fastboot);
    assert(rtc_recovery_calls == 1 && !rtc_recovery);
    reset_state(); oppo_fastboot_ui_run_action(OPPO_FASTBOOT_UI_POWER_OFF);
    assert(exit_calls == 1 && poweroff_calls == 1 && boot_calls == 0 && clear_calls == 0);
    puts("PASS: Start default, normal/recovery dispatch, both BCB guards, relock guard, power actions, unchanged USB whitelist");
    return 0;
}
'''

profiles = {
    "rescue-menu": "#define OPPO_RESCUE_FASTBOOT\n#define OPPO_RESCUE_STORAGE_MENU\n",
    "rescue-original": "#define OPPO_RESCUE_FASTBOOT\n",
    "normal-original": "",
}


def generate_and_run(work, compile_tests):
    work.mkdir(parents=True, exist_ok=True)
    for name, defines in profiles.items():
        test_source = work / (name + ".c")
        test_source.write_text(defines + prefix + selection + labels + actions + whitelist + tests)
        if compile_tests:
            executable = work / name
            subprocess.run([args.cc, "-std=c99", "-Wall", "-Wextra", "-Werror",
                            "-O0", str(test_source), "-o", str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
            print(f"PASS profile: {name}", flush=True)
        else:
            print(f"Generated without compilation: {test_source}")


if args.emit_only:
    generate_and_run(args.emit_only, False)
else:
    with tempfile.TemporaryDirectory(prefix="lk-storage-menu-test-") as work:
        generate_and_run(Path(work), True)
