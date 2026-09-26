import json
import os
import subprocess
import tempfile
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


TIKTOK_USERNAME = "yuhdoggo"
TIKTOK_URL = f"https://www.tiktok.com/@{TIKTOK_USERNAME}"

YOUTUBE_CLIENT_ID = os.environ["YOUTUBE_CLIENT_ID"]
YOUTUBE_CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]
YOUTUBE_REFRESH_TOKEN = os.environ["YOUTUBE_REFRESH_TOKEN"]

UPLOADED_FILE = Path("uploaded.json")

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload"
]


def load_uploaded():
    if not UPLOADED_FILE.exists():
        return set()

    with open(UPLOADED_FILE, "r", encoding="utf-8") as f:
        return set(json.load(f))


def save_uploaded(uploaded):
    with open(UPLOADED_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(uploaded), f, indent=2)


def get_youtube():
    credentials = Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        scopes=YOUTUBE_SCOPES,
    )

    return build("youtube", "v3", credentials=credentials)


def get_tiktok_videos(folder):
    print(f"Checking {TIKTOK_URL}...")

    command = [
        "yt-dlp",
        "--flat-playlist",
        "--playlist-end", "10",
        "--print", "%(id)s",
        TIKTOK_URL,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        print(result.stderr)
        return []

    video_ids = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]

    return video_ids


def download_tiktok(video_id, folder):
    url = f"https://www.tiktok.com/@{TIKTOK_USERNAME}/video/{video_id}"

    output = os.path.join(folder, f"{video_id}.%(ext)s")

    command = [
        "yt-dlp",
        "--no-playlist",
        "-o", output,
        url,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        print(result.stderr)
        return None

    files = list(Path(folder).glob(f"{video_id}.*"))

    if not files:
        return None

    return str(files[0])


def upload_to_youtube(youtube, video_file, video_id):
    title = f"TikTok #{video_id}"

    body = {
        "snippet": {
            "title": title[:100],
            "description": (
                f"Original video: "
                f"https://www.tiktok.com/@{TIKTOK_USERNAME}/video/{video_id}"
            ),
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        video_file,
        mimetype="video/*",
        resumable=True,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = request.execute()

    print(
        f"Uploaded to YouTube: "
        f"https://www.youtube.com/watch?v={response['id']}"
    )


def main():
    uploaded = load_uploaded()
    youtube = get_youtube()

    with tempfile.TemporaryDirectory() as folder:

        video_ids = get_tiktok_videos(folder)

        print(f"Found {len(video_ids)} TikTok videos.")

        # Process oldest first
        for video_id in reversed(video_ids):

            if video_id in uploaded:
                print(f"Already uploaded: {video_id}")
                continue

            print(f"New TikTok found: {video_id}")

            video_file = download_tiktok(video_id, folder)

            if not video_file:
                print(f"Could not download {video_id}")
                continue

            try:
                upload_to_youtube(
                    youtube,
                    video_file,
                    video_id,
                )

                uploaded.add(video_id)
                save_uploaded(uploaded)

            except Exception as e:
                print(f"YouTube upload failed: {e}")

            finally:
                try:
                    os.remove(video_file)
                except OSError:
                    pass


if __name__ == "__main__":
    main()
