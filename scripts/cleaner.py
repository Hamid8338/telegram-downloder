#!/usr/bin/env python3
import os
import sys

DOWNLOAD_DIR = "downloads"
KEEP_FILES = {'.gitkeep'}

def main():
    if not os.path.isdir(DOWNLOAD_DIR):
        print(f"Directory '{DOWNLOAD_DIR}' not found, nothing to clean")
        return

    deleted = 0
    skipped = 0
    for f in os.listdir(DOWNLOAD_DIR):
        fp = os.path.join(DOWNLOAD_DIR, f)
        if os.path.isfile(fp) and f not in KEEP_FILES:
            os.remove(fp)
            print(f"Deleted: {fp}")
            deleted += 1
        elif f in KEEP_FILES:
            skipped += 1

    print(f"Cleaned {deleted} files (skipped {skipped} protected files)")

if __name__ == "__main__":
    main()
