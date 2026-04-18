"""
Re-render images for an existing date's content.json without calling any AI APIs.
Usage:  python rerender.py [YYYY-MM-DD]
        python rerender.py           # uses today's date
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

parser = argparse.ArgumentParser(description="Re-render images for an existing content.json.")
parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="Date string YYYY-MM-DD")
parser.add_argument("--session", type=int, default=1, help="Session number")
args = parser.parse_args()

date_str = args.date
session = args.session

output_dir = Path(__file__).parent / "output" / date_str / f"session_{session}"
content_file = output_dir / "content.json"

if not content_file.exists():
    print(f"ERROR: {content_file} not found")
    sys.exit(1)

print(f"Re-rendering images for {date_str} (Session {session})")
print(f"Loading: {content_file}")
all_posts = json.loads(content_file.read_text(encoding="utf-8"))

from image_renderer import render_post_images

for post_key, post_content in all_posts.items():
    post_num = post_key.replace("post_", "")
    post_dir = output_dir / f"post_{post_num}"
    post_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n── Post {post_num}: {post_content.get('post_label', '')} ──")
    image_paths = render_post_images(post_content, str(post_dir))
    print(f"   Done: {len(image_paths)} slides")

print("\n✅ All posts re-rendered successfully!")
print(f"Output: {output_dir}")
