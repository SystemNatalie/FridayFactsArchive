import feedparser
import requests
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin

RSS_URL = "https://www.factorio.com/blog/rss"
SIZE_LIMIT_MB = 50
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def archive_latest_fff():
    print("Checking RSS feed...")
    feed = feedparser.parse(RSS_URL)
    fff_posts = [e for e in feed.entries if "Friday Facts" in e.title]

    if not fff_posts:
        print("No FFF posts found.")
        return

    latest_post = fff_posts[0]
    safe_title = latest_post.title.replace(" ", "_").replace("#", "").strip()
    post_dir = f"archive/{safe_title}"
    media_dir = f"{post_dir}/media"

    if os.path.exists(f"{post_dir}/index.html"):
        print(f"Skipping: {safe_title} is already archived.")
        return

    print(f"Archiving: {safe_title}...")
    os.makedirs(media_dir, exist_ok=True)

    try:
        response = requests.get(latest_post.link, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"Failed to fetch post HTML: {e}")
        return

    # --- 1. INLINE CSS (Fixes CORS) ---
    print("Inlining CSS...")
    for link in soup.find_all("link", rel="stylesheet"):
        css_url = urljoin(latest_post.link, link.get("href"))
        try:
            css_data = requests.get(css_url, headers=HEADERS, timeout=10).text
            new_style = soup.new_tag("style")
            new_style.string = css_data
            link.replace_with(new_style)
        except:
            print(f"  Warning: Could not inline CSS from {css_url}")

    # --- 2. DOWNLOAD MEDIA ---
    tags = {'img': 'src', 'video': 'src', 'source': 'src', 'audio': 'src'}
    for tag_name, attr in tags.items():
        for element in soup.find_all(tag_name):
            media_url = element.get(attr)
            if not media_url: continue

            full_url = urljoin(latest_post.link, media_url)
            print(f"  Processing {tag_name}: {full_url}")

            try:
                # 1. Check size
                head = requests.head(full_url, headers=HEADERS, allow_redirects=True, timeout=5)
                size = int(head.headers.get('content-length', 0))

                if size > SIZE_LIMIT_MB * 1024 * 1024:
                    print(f"    Skipping (Too large: {size / 1024 / 1024:.1f}MB)")
                    continue

                # 2. Setup Filename
                filename = os.path.basename(full_url.split('?')[0])
                if not filename: filename = f"asset_{hash(full_url)}.{tag_name}"
                local_path = f"{media_dir}/{filename}"

                # 3. Download
                r = requests.get(full_url, headers=HEADERS, timeout=20)
                with open(local_path, "wb") as f:
                    f.write(r.content)

                # 4. Update HTML with strictly relative path
                element[attr] = f"media/{filename}"
                print(f"    Saved to {local_path}")

            except Exception as e:
                print(f"    Error downloading {full_url}: {e}")

    # --- 3. SAVE HTML ---
    with open(f"{post_dir}/index.html", "w", encoding="utf-8") as f:
        f.write(soup.prettify())
    print("Done!")


if __name__ == "__main__":
    archive_latest_fff()
