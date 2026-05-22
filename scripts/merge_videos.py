#!/usr/bin/env python3
import os
import subprocess
import sys
import glob
import time

DOWNLOAD_DIR = "downloads"
VIDEO_EXTS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg'}

def is_video(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    return ext in VIDEO_EXTS

def get_video_duration(filepath):
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', filepath],
            capture_output=True, text=True, timeout=30
        )
        return float(result.stdout.strip())
    except:
        return 0

def merge_videos(video_files, output_path):
    concat_file = os.path.join(DOWNLOAD_DIR, "concat_list.txt")
    with open(concat_file, 'w') as f:
        for vf in video_files:
            f.write(f"file '{os.path.abspath(vf)}'\n")

    cmd = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
        '-i', concat_file,
        '-c', 'copy',
        output_path
    ]
    print(f"Merging {len(video_files)} videos into {output_path}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg error: {result.stderr}")
        return False

    if os.path.exists(output_path):
        for vf in video_files:
            os.remove(vf)
            print(f"Removed original: {vf}")
        os.remove(concat_file)
        print(f"Merged video saved: {output_path}")
        return True
    return False

def main():
    if not os.path.isdir(DOWNLOAD_DIR):
        print(f"Directory {DOWNLOAD_DIR} not found")
        return

    all_files = []
    for f in os.listdir(DOWNLOAD_DIR):
        fp = os.path.join(DOWNLOAD_DIR, f)
        if os.path.isfile(fp) and is_video(fp):
            all_files.append(fp)

    all_files.sort()

    if len(all_files) < 2:
        print(f"Only {len(all_files)} video file(s) found, skipping merge")
        return

    print(f"Found {len(all_files)} video files")

    timestamp = int(time.time())
    output = os.path.join(DOWNLOAD_DIR, f"merged_video_{timestamp}.mp4")

    if merge_videos(all_files, output):
        print(f"SUCCESS: Merged {len(all_files)} videos into {output}")
    else:
        print("FAILED: Video merge failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
