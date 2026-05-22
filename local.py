#!/usr/bin/env python3
import os
import sys
import json
import time
import subprocess
import shutil
import re

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".github_config")
VIDEO_EXTS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg'}

def log(msg):
    print(msg, flush=True)

def gh(args, capture=True):
    cmd = [os.path.expanduser("~/.local/bin/gh")] + args
    env = os.environ.copy()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
    if result.returncode != 0 and capture:
        log(f"  gh error: {result.stderr.strip()[:200]}")
    if capture:
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    return "", "", result.returncode

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def main():
    log("=== Telegram Downloader Pipeline ===")
    log("")

    config = load_config()
    if config.get("token"):
        os.environ["GH_TOKEN"] = config["token"]

    if not config.get("token"):
        config["token"] = input("GitHub token: ").strip()
        config["repo"] = input("GitHub repo (e.g. Hamid8338/telegram-downloder): ").strip()
        os.environ["GH_TOKEN"] = config["token"]
        save_config(config)
    elif not config.get("repo"):
        config["repo"] = input("GitHub repo: ").strip()
        save_config(config)

    repo = config["repo"]
    os.environ["GH_TOKEN"] = config["token"]

    log(f"Checking {repo}...")
    out, err, code = gh(["repo", "view", repo, "--json", "name"])
    if code != 0:
        log(f"  Failed to access repo")
        sys.exit(1)
    log(f"  OK")

    if len(sys.argv) > 1:
        link = sys.argv[1].strip()
    else:
        link = input("\nTelegram post URL: ").strip()
    while not link.startswith("https://t.me/"):
        log("  Invalid link")
        if len(sys.argv) > 1:
            sys.exit(1)
        link = input("Telegram post URL: ").strip()

    log("Triggering workflow...")
    out, err, code = gh(["workflow", "run", "tg-dl.yml", "-f", f"telegram_link={link}"])
    if code != 0:
        log("  Failed to trigger")
        sys.exit(1)
    log("  Done")

    log("Waiting for run to start...")
    time.sleep(8)

    run_id = None
    for attempt in range(30):
        out, err, code = gh(["run", "list", "--workflow=tg-dl.yml", "--limit=5",
                             "--json=databaseId,status,conclusion,displayTitle"])
        if code == 0 and out:
            runs = json.loads(out)
            for r in runs:
                if r["status"] in ("in_progress", "queued", "pending", "waiting"):
                    run_id = r["databaseId"]
                    break
        if run_id:
            break
        log(f"  Waiting... ({attempt+1})")
        time.sleep(5)

    if not run_id:
        log("Could not find run")
        sys.exit(1)

    log(f"Run: {run_id}")
    log("Waiting for completion...")

    while True:
        out, err, code = gh(["run", "view", str(run_id),
                             "--json=status,conclusion,headSha"])
        if code == 0 and out:
            data = json.loads(out)
            status = data["status"]
            conclusion = data.get("conclusion") or "-"
            log(f"  Status: {status}  Conclusion: {conclusion}")
            if status == "completed":
                head_sha = data.get("headSha")
                break
        time.sleep(10)

    if conclusion != "success":
        log(f"Workflow failed: {conclusion}")
        sys.exit(1)
    if not head_sha:
        log("No commit SHA")
        sys.exit(1)

    log(f"Getting latest commit on main...")
    out, err, code = gh(["api", f"repos/{repo}/branches/main"])
    if code == 0 and out:
        data = json.loads(out)
        head_sha = data["commit"]["sha"]
    log(f"SHA: {head_sha[:7]}")

    out, err, code = gh(["api", f"repos/{repo}/contents/downloads?ref={head_sha}"])
    if code != 0 or not out:
        log("No files in downloads/")
        sys.exit(1)

    try:
        contents = json.loads(out)
    except:
        log("No files found")
        sys.exit(1)

    if not isinstance(contents, list):
        log("No files found")
        sys.exit(1)

    dl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloaded_files")
    if os.path.exists(dl_dir):
        shutil.rmtree(dl_dir)
    os.makedirs(dl_dir)

    files_to_get = [i for i in contents if i["type"] == "file" and i["name"] != ".gitkeep"]
    log(f"Downloading {len(files_to_get)} files with wget...")

    for item in files_to_get:
        raw_url = f"https://raw.githubusercontent.com/{repo}/{head_sha}/{item['path']}"
        out_path = os.path.join(dl_dir, item["name"])
        log(f"  wget: {item['name']}")
        log(f"    URL: {raw_url[:80]}...")
        r = subprocess.run(["wget", "-q", "--timeout=30", "-O", out_path, raw_url],
                          capture_output=True, text=True)
        if r.returncode == 0:
            size = os.path.getsize(out_path)
            log(f"    OK ({size/1024:.1f} KB)")
        else:
            log(f"    Failed (code={r.returncode})")
            if r.stderr:
                log(f"    stderr: {r.stderr[:200]}")
            if r.stdout:
                log(f"    stdout: {r.stdout[:200]}")

    log(f"\nFiles: {dl_dir}")
    files = [f for f in os.listdir(dl_dir) if os.path.isfile(os.path.join(dl_dir, f))]
    for f in files:
        sz = os.path.getsize(os.path.join(dl_dir, f))
        log(f"  {f} ({sz/1024:.1f} KB)")

    videos = []
    for f in files:
        if os.path.splitext(f)[1].lower() in VIDEO_EXTS:
            videos.append(os.path.join(dl_dir, f))
    videos.sort()

    if len(videos) > 1:
        log(f"Merging {len(videos)} videos...")
        if shutil.which("ffmpeg"):
            cl = os.path.join(dl_dir, "concat.txt")
            with open(cl, "w") as f:
                for v in videos:
                    f.write(f"file '{os.path.abspath(v)}'\n")
            merged = os.path.join(dl_dir, "merged_video.mp4")
            r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                               "-i", cl, "-c", "copy", merged],
                              capture_output=True, text=True)
            if r.returncode == 0:
                for v in videos:
                    os.remove(v)
                os.remove(cl)
                log(f"Merged: {merged}")
            else:
                log(f"ffmpeg error: {r.stderr[:200]}")
        else:
            log("Install ffmpeg: sudo apt install ffmpeg")
    else:
        log(f"{len(videos)} video(s), no merge")

    log("\nTriggering cleaner...")
    gh(["workflow", "run", "cleaner.yml"])
    log("Cleaner triggered")

    log("\n=== Done! ===")
    log(f"Files: {dl_dir}")

if __name__ == "__main__":
    main()
