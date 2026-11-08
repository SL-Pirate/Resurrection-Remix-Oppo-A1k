#!/usr/bin/env python3
"""Compile actual LK functions on the build host only; never talks to a device.

Usage: python3 test-modem-export.py LK_SOURCE [PATCHED_TWO_FILE_OVERLAY]
"""
from pathlib import Path
import hashlib
import re
import socket
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
overlay = Path(sys.argv[2]) if len(sys.argv) > 2 else root
mt = (overlay/'app/mt_boot/mt_boot.c').read_text()
tel = (overlay/'platform/common/md/ccci_ld_md_tel.c').read_text()
ba = (root/'app/mt_boot/bootargs.c').read_text()

def function(text, signature):
    start = text.index(signature)
    brace = text.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end] + '\n'

hook = mt.index('\tif (g_boot_mode == NORMAL_BOOT && ccci_append_tel_fo_setting)')
filter_call = mt.index('\toppo_force_minimal_normal_cmdline();')
publish = mt.index('\tret = fdt_setprop_string(fdt, offset, "bootargs", (char *)cmdline_get());')
assert filter_call < hook < publish
assert mt.count('\t\tccci_append_tel_fo_setting((char *)cmdline_get());') == 1
assert '#include <bootargs.h>' in tel

parts = [function(ba, s) for s in [
    'static inline void validate_cmdline_boundary(',
    'char *cmdline_get(void)',
    'const char *cmdline_chosen_bootargs_get(void)',
    'bool cmdline_append(const char *append_string)',
    'bool cmdline_overwrite(const char *overwrite_string)',
]]
parts += [function(mt, s) for s in [
    'static bool oppo_cmdline_is_space(',
    'static bool oppo_cmdline_token_eq(',
    'static bool oppo_cmdline_token_has_prefix(',
]]
start = mt.index('static bool oppo_minimal_cmdline_token_matches(')
end = mt.index('\n#endif', mt.index('static void oppo_force_minimal_normal_cmdline(void)\n{', start))
parts += [mt[start:end], function(tel, 'static int add_opt_setting_to_buf('), function(tel, 'void ccci_append_tel_fo_setting(')]
prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#define CMDLINE_LEN 2048
#define CMDLINE_OVERFLOW_STR "cmdline overflow"
#define SN_BUF_LEN 64
#define CRITICAL 0
#define dprintf(...) ((void)0)
#define pal_log_err(...) ((void)0)
#define video_printf(...) ((void)0)
#define ALWAYS_LOG(...) printf(__VA_ARGS__)
#define enter_critical_section() ((void)0)
#define exit_critical_section() ((void)0)
#define NORMAL_BOOT 0
static char g_cmdline[CMDLINE_LEN];
static char g_chosen_bootargs[CMDLINE_LEN];
static char *cmdline_tail = g_cmdline;
static char *cmdline_end = g_cmdline + CMDLINE_LEN;
static int g_boot_mode = NORMAL_BOOT;
static unsigned int boot_time;
static char sn_buf[SN_BUF_LEN + 1] = "fixture-serial";
static unsigned long get_timer(unsigned long unused) { (void)unused; return 1234; }
static char *s_g_local_cmd_line_buf;
static int s_g_local_cmd_line_buf_size;
static int s_g_curr_opt_buf_offset;
static jmp_buf panic_target;
static int expect_panic;
static void panic(const char *message) {
    if (expect_panic) longjmp(panic_target, 1);
    fprintf(stderr, "unexpected panic: %s\n", message); abort();
}
'''
main = r'''
static char options[1024];
static void reset(void) {
    memset(options, 0, sizeof(options));
    s_g_local_cmd_line_buf = options;
    s_g_local_cmd_line_buf_size = sizeof(options);
    s_g_curr_opt_buf_offset = 0;
    g_chosen_bootargs[0] = '\0';
    g_boot_mode = NORMAL_BOOT;
    cmdline_overwrite("root=/dev/ram skip_initramfs androidboot.serialno=fixture-serial");
}
static void put(const char *name, const char *value) {
    assert(add_opt_setting_to_buf((char *)name, (char *)value) == 0);
}
static void run_boot_tail(void) {
    oppo_force_minimal_normal_cmdline();
    if (g_boot_mode == NORMAL_BOOT) ccci_append_tel_fo_setting(cmdline_get());
}
int main(void) {
    reset();
    /* All eight values recorded in the stock device's evidence/getprop.txt. */
    put("opt_md1_support", "9"); put("opt_md3_support", "0");
    put("opt_c2k_lte_mode", "0"); put("opt_lte_support", "1");
    put("opt_c2k_support", "0"); put("opt_ps1_rat", "Lf/Lt/W/G");
    put("opt_using_default", "1"); put("opt_eccci_c2k", "1");
    run_boot_tail();
    assert(strstr(g_cmdline, "androidboot.opt_md1_support=9"));
    assert(strstr(g_cmdline, "androidboot.opt_md3_support=0"));
    assert(strstr(g_cmdline, "androidboot.opt_ps1_rat=Lf/Lt/W/G"));
    assert(strstr(g_cmdline, "androidboot.opt_eccci_c2k=1"));
    assert(strstr(g_cmdline, "root=PARTUUID="));
    assert(!strstr(g_cmdline, "root=/dev/ram"));
    assert(!strstr(g_cmdline, "skip_initramfs"));
    printf("PASS stock options and normal root preserved; cmdline %zu/%d bytes\n", strlen(g_cmdline), CMDLINE_LEN);
    reset(); put("opt_md1_support", "13"); put("opt_ps1_rat", "Lt/T/G");
    put("product.hardware.sku", "dsds"); run_boot_tail();
    assert(strstr(g_cmdline, "androidboot.opt_md1_support=13"));
    assert(!strstr(g_cmdline, "androidboot.opt_md1_support=9"));
    assert(strstr(g_cmdline, "androidboot.opt_ps1_rat=Lt/T/G"));
    assert(strstr(g_cmdline, "androidboot.product.hardware.sku=dsds"));
    puts("PASS calculated alternative modem/RAT/SKU values exported verbatim");
    reset(); put("opt_md1_support", "0"); run_boot_tail();
    assert(strstr(g_cmdline, "androidboot.opt_md1_support=0"));
    puts("PASS disabled modem remains zero, no invented fallback");
    reset(); run_boot_tail(); assert(!strstr(g_cmdline, "androidboot.opt_"));
    reset(); s_g_local_cmd_line_buf = NULL; s_g_curr_opt_buf_offset = 10;
    run_boot_tail(); assert(!strstr(g_cmdline, "androidboot.opt_"));
    reset(); put("opt_md1_support", "9"); s_g_local_cmd_line_buf_size = 0;
    run_boot_tail(); assert(!strstr(g_cmdline, "androidboot.opt_"));
    reset(); s_g_curr_opt_buf_offset = sizeof(options) + 1;
    run_boot_tail(); assert(!strstr(g_cmdline, "androidboot.opt_"));
    puts("PASS empty, absent, freed/error and out-of-bounds buffers ignored");
    reset(); memcpy(options, "nonterminated", 13); s_g_curr_opt_buf_offset = 13;
    run_boot_tail(); assert(!strstr(g_cmdline, "androidboot.nonterminated"));
    reset(); memcpy(options, "opt_md1_support\0", 16); s_g_curr_opt_buf_offset = 16;
    run_boot_tail(); assert(!strstr(g_cmdline, "androidboot.opt_"));
    reset(); memcpy(options, "opt_md1_support\0x", 17); s_g_curr_opt_buf_offset = 17;
    run_boot_tail(); assert(!strstr(g_cmdline, "androidboot.opt_"));
    reset(); put("opt_md1_support", "9"); g_boot_mode = 2;
    run_boot_tail(); assert(!strstr(g_cmdline, "androidboot.opt_"));
    puts("PASS malformed name/value bounds and non-normal boot gating");
    reset(); char longvalue[200]; memset(longvalue, '7', 199); longvalue[199] = '\0';
    put("opt_md1_support", longvalue); run_boot_tail();
    assert(!strstr(g_cmdline, "androidboot.opt_"));
    puts("PASS oversized token rejected without truncation");
    reset(); put("opt_md1_support", "9");
    memset(g_cmdline, 'x', CMDLINE_LEN - 10); g_cmdline[CMDLINE_LEN - 10] = '\0';
    cmdline_tail = g_cmdline + strlen(g_cmdline);
    expect_panic = 1;
    if (setjmp(panic_target) == 0) { ccci_append_tel_fo_setting(g_cmdline); assert(0); }
    expect_panic = 0;
    assert(strlen(g_cmdline) == CMDLINE_LEN - 10);
    puts("PASS actual cmdline_append refuses output overflow before writing");
    puts("PASS actual-source modem export regression suite");
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='op486c-modem-export-') as tmp:
    source = Path(tmp)/'test.c'
    exe = Path(tmp)/'test'
    source.write_text(prefix + '\n'.join(parts) + main)
    print('actual_source_fixture_sha256=' + hashlib.sha256(source.read_bytes()).hexdigest(), flush=True)
    subprocess.run(['cc', '-O2', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined', '-fno-omit-frame-pointer', str(source), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=15)
