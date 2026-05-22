#!/usr/bin/env python3
import os
import sys
import json
import time
import subprocess
import shutil
from urllib.request import Request, urlopen

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".github_config")
VIDEO_EXTS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg'}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def github_get(url, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "local-tg-downloader"
    }
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            return json.loads(body) if body else {}
    except Exception as e:
        print(f"  API error: {e}")
        if hasattr(e, 'read'):
            try:
                print(f"  {e.read().decode()[:200]}")
            except:
                pass
        return None

def github_post(url, token, data):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "local-tg-downloader",
        "Content-Type": "application/json"
    }
    req = Request(url, headers=headers, method="POST", data=json.dumps(data).encode())
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.status == 204 or resp.status == 201
    except Exception as e:
        print(f"  Error: {e}")
        if hasattr(e, 'read'):
            try:
                print(f"  {e.read().decode()[:200]}")
            except:
                pass
        return False

def wget_download(url, output_path):
    print(f"  wget: {os.path.basename(output_path)}")
    result = subprocess.run(["wget", "-q", "--timeout=30", "-O", output_path, url],
                          capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  wget failed: {result.stderr[:200]}")
        return False
    size = os.path.getsize(output_path)
    print(f"    OK ({size/1024:.1f} KB)")
    return True

def main():
    print("=== Telegram Downloader Pipeline ===")
    print()

    config = load_config()

    if config.get("token") or config.get("repo"):
        print("Saved settings:")
        print(f"  Repo: {config.get('repo', 'Not set')}")
        print(f"  Token: {'****' + config['token'][-4:] if config.get('token') else 'Not set'}")
        change = input("Change these? (y/N): ").strip().lower()
        if change == 'y':
            config = {}

    if not config.get("token"):
        print("\nCreate a token at: https://github.com/settings/tokens/new")
        print("  Required scopes: repo, workflow")
        config["token"] = input("GitHub token: ").strip()
        while not config["token"]:
            config["token"] = input("GitHub token (required): ").strip()

    if not config.get("repo"):
        config["repo"] = input("GitHub repo (e.g. Hamid8338/telegram-downloder): ").strip()
        while not config["repo"] or '/' not in config["repo"] or config["repo"].count('/') != 1:
            print("  Invalid format. Use: username/repo-name")
            config["repo"] = input("GitHub repo: ").strip()

    save_config(config)

    repo = config["repo"]
    token = config["token"]
    owner, repo_name = repo.split("/")
    api_base = f"https://api.github.com/repos/{repo}"

    print(f"\nVerifying access to {repo}...")
    result = github_get(api_base, token)
    if result is None:
        print("  Failed to access repo. Check your token and repo name.")
        sys.exit(1)
    print(f"  OK - {result.get('full_name', repo)}")

    link = input("\nTelegram post URL: ").strip()
    while not link.startswith("https://t.me/"):
        print("  Invalid. Must start with https://t.me/...")
        link = input("Telegram post URL: ").strip()

    print(f"\nTriggering workflow...")
    ok = github_post(f"{api_base}/actions/workflows/tg-dl.yml/dispatches", token, {
        "ref": "main",
        "inputs": {"telegram_link": link}
    })
    if not ok:
        print("Failed to trigger workflow. Check token has 'workflow' scope.")
        sys.exit(1)
    print("Workflow triggered successfully")
    trigger_time = time.time()

    print("Waiting for workflow to start...")
    time.sleep(8)

    run_id = None
    for attempt in range(30):
        runs = github_get(
            f"{api_base}/actions/runs?event=workflow_dispatch&per_page=10", token)
        if runs and runs.get("workflow_runs"):
            for r in runs["workflow_runs"]:
                created = r.get("run_started_at") or r.get("created_at", "")
                if created:
                    created_ts = time.mktime(time.strptime(created.split(".")[0].split("Z")[0],
                        "%Y-%m-%dT%H:%M:%S"))
                    if created_ts > trigger_time:
                        run_id = r["id"]
                        break
        if run_id:
            break
        print(f"  Waiting... ({attempt+1})")
        time.sleep(5)

    if not run_id:
        print("Could not find the workflow run")
        sys.exit(1)

    print(f"\nRun ID: {run_id}")
    print("Waiting for completion...")

    head_sha = None
    while True:
        run = github_get(f"{api_base}/actions/runs/{run_id}", token)
        if not run:
            time.sleep(10)
            continue
        status = run.get("status", "unknown")
        conclusion = run.get("conclusion") or "-"
        print(f"  Status: {status}  Conclusion: {conclusion}")
        if status == "completed":
            head_sha = run.get("head_sha")
            break
        time.sleep(10)

    if conclusion != "success":
        print(f"\nWorkflow result: {conclusion}")
        sys.exit(1)

    if not head_sha:
        print("Could not get commit SHA")
        sys.exit(1)

    print(f"\nCommit SHA: {head_sha[:7]}")
    print("Listing files from repo...")

    contents = github_get(f"{api_base}/contents/downloads?ref={head_sha}", token)
    if not contents or not isinstance(contents, list):
        print("No files found in downloads/")
        sys.exit(1)

    files_to_download = []
    for item in contents:
        if item["type"] == "file" and item["name"] != ".gitkeep":
            files_to_download.append(item)

    if not files_to_download:
        print("No files to download")
        sys.exit(1)

    dl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloaded_files")
    if os.path.exists(dl_dir):
        shutil.rmtree(dl_dir)
    os.makedirs(dl_dir)

    print(f"Downloading {len(files_to_download)} files with wget...")
    for item in files_to_download:
        raw_url = f"https://raw.githubusercontent.com/{repo}/{head_sha}/{item['path']}"
        out_path = os.path.join(dl_dir, item["name"])
        if not wget_download(raw_url, out_path):
            print(f"  Failed to download {item['name']}")

    print(f"\nFiles saved to: {dl_dir}")
    files = [f for f in os.listdir(dl_dir) if os.path.isfile(os.path.join(dl_dir, f))]
    for f in files:
        size = os.path.getsize(os.path.join(dl_dir, f))
        print(f"  {f} ({size/1024:.1f} KB)")

    video_files = []
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext in VIDEO_EXTS:
            video_files.append(os.path.join(dl_dir, f))
    video_files.sort()

    if len(video_files) > 1:
        print(f"\nFound {len(video_files)} video files, merging...")
        if shutil.which("ffmpeg"):
            concat_list = os.path.join(dl_dir, "concat.txt")
            with open(concat_list, "w") as f:
                for vf in video_files:
                    f.write(f"file '{os.path.abspath(vf)}'\n")

            merged = os.path.join(dl_dir, "merged_video.mp4")
            cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                   "-i", concat_list, "-c", "copy", merged]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                for vf in video_files:
                    os.remove(vf)
                os.remove(concat_list)
                print(f"Merged video: {merged}")
            else:
                print(f"ffmpeg error: {result.stderr}")
        else:
            print("ffmpeg not found. Install: sudo apt install ffmpeg")
    else:
        print(f"\n{len(video_files)} video file(s), no merge needed")

    print("\nCleaning up GitHub repo...")
    github_post(f"{api_base}/actions/workflows/cleaner.yml/dispatches", token, {
        "ref": "main"
    })
    print("Cleaner workflow triggered")

    print("\n=== Done! ===")
    print(f"Files are in: {dl_dir}")

if __name__ == "__main__":
    main()
