#!/usr/bin/env python3
"""
Widget build script — minifies widget.js using rjsmin.
Outputs:
  frontend/chatbot-widget/dist/abhinav-chatbot.min.js
  wordpress/abhinav-chatbot-plugin/dist/abhinav-chatbot.min.js
"""
import os
import sys
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.join(BASE, "..", "..")

SRC = os.path.join(WORKSPACE, "frontend", "chatbot-widget", "src", "widget.js")
DIST_FRONTEND = os.path.join(WORKSPACE, "frontend", "chatbot-widget", "dist", "abhinav-chatbot.min.js")
DIST_WP = os.path.join(WORKSPACE, "wordpress", "abhinav-chatbot-plugin", "dist", "abhinav-chatbot.min.js")

os.makedirs(os.path.dirname(DIST_FRONTEND), exist_ok=True)
os.makedirs(os.path.dirname(DIST_WP), exist_ok=True)

try:
    import rjsmin  # type: ignore
    print("  Using rjsmin for minification...")
    with open(SRC, "r", encoding="utf-8") as f:
        source = f.read()
    minified = rjsmin.jsmin(source)
    minify_method = "rjsmin"
except ImportError:
    print("  rjsmin not installed — using basic whitespace reduction fallback...")
    import re
    with open(SRC, "r", encoding="utf-8") as f:
        source = f.read()
    # Basic: strip single-line comments and compress whitespace (safe for this widget)
    minified = re.sub(r'//[^\n]*\n', '\n', source)
    minified = re.sub(r'\n\s*\n', '\n', minified)
    minified = re.sub(r'^\s+', '', minified, flags=re.MULTILINE)
    minify_method = "basic_fallback"

# Write outputs
for dest in [DIST_FRONTEND, DIST_WP]:
    with open(dest, "w", encoding="utf-8") as f:
        f.write(minified)
    print(f"  Written: {os.path.relpath(dest, WORKSPACE)}")

orig_size = len(source.encode("utf-8"))
mini_size = len(minified.encode("utf-8"))
reduction = (1 - mini_size / orig_size) * 100

print(f"\n  Method      : {minify_method}")
print(f"  Original    : {orig_size:,} bytes")
print(f"  Minified    : {mini_size:,} bytes")
print(f"  Reduction   : {reduction:.1f}%")
print("\n  Build complete.")
