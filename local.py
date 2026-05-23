#!/usr/bin/env python3
import os
import sys
import json
import time
import subprocess
import shutil

GH = os.path.expanduser("~/.local/bin/gh")
CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".github_config")
VIDEO_EXTS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg'}

def log(m):
    print(m, flush=True)

def load_config():
    if os.path.exists(CONFIG):
        with open(CONFIG) as f:
            return json.load(f)
    return {}

def save_config(c):
    with open(CONFIG, 'w') as f:
        json.dump(c, f, indent=2)

def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

def gh(args):
    return sh([GH] + args)

def main():
    log("=== Telegram Downloader ===")
    log("")

    cfg = load_config()
    if cfg.get("token"):
        os.environ["GH_TOKEN"] = cfg["token"]
    elif not os.environ.get("GH_TOKEN"):
        t = input("GitHub token: ").strip()
        r = input("Repo (Hamid8338/telegram-downloder): ").strip() or "Hamid8338/telegram-downloder"
        os.environ["GH_TOKEN"] = t
        save_config({"token": t, "repo": r})

    repo = cfg.get("repo") or "Hamid8338/telegram-downloder"

    log(f"Checking {repo}...")
    o, e, c = gh(["repo", "view", repo, "--json", "name"])
    if c != 0:
        log(f"Error: {e}")
        sys.exit(1)
    log("OK")

    link = sys.argv[1] if len(sys.argv) > 1 else input("Telegram link: ").strip()
    while not link.startswith("https://t.me/"):
        link = input("Telegram link: ").strip()

    log("Triggering workflow...")
    o, e, c = gh(["workflow", "run", "tg-dl.yml", "-f", f"telegram_link={link}"])
    if c != 0:
        log(f"Failed: {e}")
        sys.exit(1)
    log("Done")

    log("Waiting for run...")
    time.sleep(10)
    run_id = None
    for i in range(30):
        o, e, c = gh(["run", "list", "--workflow=tg-dl.yml", "--limit=5",
                       "--json=databaseId,status,conclusion"])
        if c == 0 and o:
            for r in json.loads(o):
                if r["status"] in ("in_progress", "queued", "pending", "waiting"):
                    run_id = r["databaseId"]
                    break
        if run_id:
            break
        log(f"  Waiting... ({i+1})")
        time.sleep(5)

    if not run_id:
        log("Run not found")
        sys.exit(1)

    log(f"Run: {run_id}")
    while True:
        o, e, c = gh(["run", "view", str(run_id), "--json=status,conclusion"])
        if c == 0 and o:
            d = json.loads(o)
            s, cn = d["status"], d.get("conclusion", "-")
            log(f"  {s} / {cn}")
            if s == "completed":
                if cn != "success":
                    log(f"Failed: {cn}")
                    sys.exit(1)
                break
        time.sleep(10)

    log("Getting latest commit...")
    o, e, c = gh(["api", f"repos/{repo}/branches/main"])
    if c != 0:
        log("Failed to get commit")
        sys.exit(1)
    sha = json.loads(o)["commit"]["sha"]
    log(f"SHA: {sha[:7]}")

    log("Listing files...")
    o, e, c = gh(["api", f"repos/{repo}/contents/downloads?ref={sha}"])
    if c != 0 or not o:
        log("No files")
        sys.exit(1)
    try:
        items = json.loads(o)
    except:
        log("No files")
        sys.exit(1)
    if not isinstance(items, list):
        log("No files")
        sys.exit(1)

    dl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloaded_files")
    if os.path.exists(dl_dir):
        shutil.rmtree(dl_dir)
    os.makedirs(dl_dir)

    files = [i for i in items if i["type"] == "file" and i["name"] != ".gitkeep"]
    log(f"Downloading {len(files)} file(s) with wget...")

    for f in files:
        url = f"https://raw.githubusercontent.com/{repo}/{sha}/{f['path']}"
        out = os.path.join(dl_dir, f["name"])
        log(f"  {f['name']}")
        r = subprocess.run(["wget", "-q", "--timeout=30", "-O", out, url],
                          capture_output=True, text=True)
        if r.returncode == 0:
            sz = os.path.getsize(out)
            log(f"    OK ({sz/1024:.1f} KB)")
        else:
            log(f"    FAILED")

    log(f"\nFiles in {dl_dir}:")
    for f in os.listdir(dl_dir):
        fp = os.path.join(dl_dir, f)
        if os.path.isfile(fp):
            log(f"  {f} ({os.path.getsize(fp)/1024:.1f} KB)")

    videos = sorted([os.path.join(dl_dir, f) for f in os.listdir(dl_dir)
                     if os.path.isfile(os.path.join(dl_dir, f))
                     and os.path.splitext(f)[1].lower() in VIDEO_EXTS])

    if len(videos) > 1:
        log(f"\nMerging {len(videos)} videos...")
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
                log(f"  Merged: merged_video.mp4")
            else:
                log(f"  ffmpeg error")
        else:
            log("  Install ffmpeg: sudo apt install ffmpeg")

    log("\nDone!")

if __name__ == "__main__":
    main()
