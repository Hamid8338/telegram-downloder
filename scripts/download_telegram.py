#!/usr/bin/env python3
import sys
import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote
import time

def download_file(url, output_path):
    try:
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"DOWNLOADED:{output_path}")
        return True
    except Exception as e:
        print(f"FAILED:{url}:{e}")
        return False

def extract_media_from_telegram(post_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    resp = requests.get(post_url, headers=headers, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    media_urls = []
    meta_video = soup.find('meta', property='og:video')
    if meta_video and meta_video.get('content'):
        media_urls.append(meta_video['content'])
    meta_image = soup.find('meta', property='og:image')
    if meta_image and meta_image.get('content'):
        media_urls.append(meta_image['content'])
    video_tags = soup.find_all('video')
    for vt in video_tags:
        src = vt.get('src')
        if src:
            media_urls.append(urljoin(post_url, src))
    doc_links = soup.find_all('a', class_=re.compile(r'tgme_widget_message_document'))
    for dl in doc_links:
        href = dl.get('href')
        if href:
            media_urls.append(href)
    video_elems = soup.find_all(class_=re.compile(r'tgme_widget_message_video_player'))
    for ve in video_elems:
        vs = ve.get('data-video-src')
        if vs:
            media_urls.append(vs)

    unique_urls = list(dict.fromkeys(media_urls))

    text_div = soup.find('div', class_='tgme_widget_message_text')
    text_content = text_div.get_text(strip=True) if text_div else ""

    links_in_text = re.findall(r'https?://[^\s<>"\'()]+', text_content) if text_content else []

    return unique_urls, text_content, links_in_text

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def main():
    if len(sys.argv) < 2:
        print("Usage: python download_telegram.py <telegram_post_url>")
        sys.exit(1)

    post_url = sys.argv[1].strip()
    print(f"Processing: {post_url}")

    os.makedirs("downloads", exist_ok=True)

    try:
        media_urls, text, links_in_text = extract_media_from_telegram(post_url)

        if text:
            text_path = os.path.join("downloads", "post_text.txt")
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(text)
            print(f"TEXT_SAVED:{text_path}")

        if links_in_text:
            links_path = os.path.join("downloads", "extracted_links.txt")
            with open(links_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(links_in_text))
            print(f"LINKS_SAVED:{links_path} ({len(links_in_text)} links)")

        if media_urls:
            downloaded = 0
            for i, url in enumerate(media_urls):
                clean_url = url.split('?')[0] if '?' in url else url
                ext = os.path.splitext(clean_url)[1] or '.mp4'
                base = f"telegram_media_{int(time.time())}_{i}{ext}"
                out = os.path.join("downloads", sanitize_filename(base))
                if download_file(url, out):
                    downloaded += 1
            print(f"Downloaded {downloaded}/{len(media_urls)} files")
        else:
            print("No media files found")

        if not media_urls and not text:
            print("Nothing extracted")
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
