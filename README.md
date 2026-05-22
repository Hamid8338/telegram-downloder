# Telegram Downloader

Downloads media and text from public Telegram posts via GitHub Actions.

## How to use

1. Go to **Actions** tab → **TG Downloader** workflow
2. Click **Run workflow**
3. Paste a Telegram post URL and click **Run**

## What it does

1. Downloads all media files (video/image/document) from the post
2. Extracts text content and any links found in the post
3. Downloads linked files via `wget`
4. If multiple video files are downloaded, merges them into one
5. Cleans up the downloads folder after commit
