#!/usr/bin/env python3
"""Compile actual LK diagnostic function on the remote build host only."""
from pathlib import Path
import sys, tempfile, subprocess
source = (Path(sys.argv[1]) / 'app/mt_boot/fastboot.c').read_text()
a = source.index('static void oppo_fastboot_publish_preloader_bootarg_vars(void)')
b = source.index('static void oppo_fastboot_publish_hw_vars(void)', a)
fn = source[a:b]
prefix = r'''#include <assert.h>
#include <stdio.h>
#include <string.h>
#define CRITICAL 0
#define dprintf(...) ((void)0)
static unsigned int address_value = 0x47eada80, size_value = 0x1695;
static int published;
static unsigned int platform_get_bootarg_addr(void) { return address_value; }
static unsigned int platform_get_bootarg_size(void) { return size_value; }
static void fastboot_publish(const char *name, const char *value) {
  published++;
  if (!strcmp(name,"preloader-bootarg-addr")) assert(!strcmp(value,address_value ? "0x47eada80" : "0x00000000"));
  else if (!strcmp(name,"preloader-bootarg-size")) assert(!strcmp(value,size_value ? "0x1695" : "0x0"));
  else if (!strcmp(name,"preloader-bootarg-units")) assert(!strcmp(value,"unknown"));
  else assert(!strcmp(value,"not-scanned"));
}
'''
main = r'''int main(void) {
  oppo_fastboot_publish_preloader_bootarg_vars(); assert(published == 5);
  address_value = size_value = 0; published = 0;
  oppo_fastboot_publish_preloader_bootarg_vars(); assert(published == 5);
  puts("PASS: unmapped preloader address and zero metadata handled without dereference");
}
'''
with tempfile.TemporaryDirectory() as tmp:
  c = Path(tmp)/'test.c'; exe=Path(tmp)/'test'
  c.write_text(prefix + fn + main)
  subprocess.run(['cc','-O2','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],check=True)
  subprocess.run([str(exe)],check=True)
