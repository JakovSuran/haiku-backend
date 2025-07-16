import os
import json
import openai
import base64
import urllib.parse
import requests
from datetime import datetime, timezone
from ftplib import FTP

# Load OpenAI key
openai.api_key = os.getenv("OPENAI_API_KEY")



OUTPUT_FILE = "haikus/haiku.json"
USED_IMAGES_FILE = "haikus/used_images.json"
BLUEHOST_IMAGE_URL = "https://dailykorina.com/haiku/images"

def fetch_remote_image_list():
    ftp_host = os.getenv("FTP_HOST")
    ftp_user = os.getenv("FTP_USER")
    ftp_pass = os.getenv("FTP_PASS")
    ftp_path = os.getenv("FTP_IMAGES_PATH", "")  # can be blank

    with FTP(ftp_host) as ftp:
        ftp.login(ftp_user, ftp_pass)
        print("📂 Logged into FTP.")
        print("📍 Starting in directory:", ftp.pwd())

        if ftp_path:
            try:
                ftp.cwd(ftp_path)
                print("✅ Changed to:", ftp.pwd())
            except Exception as e:
                print(f"❌ Failed to change to '{ftp_path}': {e}")
                return []

        files = ftp.nlst()
        print("📄 Files in current dir:", files)

        image_files = [f for f in files if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        image_files.sort()
        return image_files




def load_used_images():
    try:
        with open(USED_IMAGES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_used_images(used_images):
    with open(USED_IMAGES_FILE, "w", encoding="utf-8") as f:
        json.dump(used_images, f, indent=2)

def pick_next_image():
    all_images = fetch_remote_image_list()
    used_images = load_used_images()
    unused_images = [img for img in all_images if img not in used_images]

    if not unused_images:
        print("All remote images used — restarting cycle.")
        used_images = []
        unused_images = all_images

    next_image = unused_images[0]
    used_images.append(next_image)
    save_used_images(used_images)
    return next_image


def download_image(image_name):
    url = f"{BLUEHOST_IMAGE_URL}/{urllib.parse.quote(image_name)}"
    print(f"⬇️ Downloading image from: {url}")
    response = requests.get(url)
    response.raise_for_status()

    local_path = f"/tmp/{image_name}"
    with open(local_path, "wb") as f:
        f.write(response.content)
    return local_path, url

def generate_haiku_from_image(image_path):
    print(f"🧠 Generating haiku from: {image_path}")
    with open(image_path, "rb") as img_file:
        encoded = base64.b64encode(img_file.read()).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{encoded}"

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    { "type": "text", "text": "Write a haiku inspired by this image. Do not explain it." },
                    { "type": "image_url", "image_url": { "url": data_url } }
                ]
            }
        ],
        max_tokens=100
    )

    return response.choices[0].message.content.strip()

def save_haiku(image_name, haiku_text, full_url):
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    data = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "image": full_url,
        "haiku": haiku_text
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"💾 Saved haiku.json")

def upload_to_bluehost(local_path, remote_name):
    ftp_host = os.getenv("FTP_HOST")
    ftp_user = os.getenv("FTP_USER")
    ftp_pass = os.getenv("FTP_PASS")
    ftp_path = os.getenv("FTP_PATH", "")

    with FTP(ftp_host) as ftp:
        ftp.login(ftp_user, ftp_pass)
        print("🧭 Logged into FTP:", ftp.pwd())

        if ftp_path:
            try:
                ftp.cwd(ftp_path)
            except Exception as e:
                print(f"❌ Failed to change to {ftp_path}: {e}")
                return

        with open(local_path, "rb") as f:
            print(f"📤 Uploading {local_path} as {remote_name}")
            ftp.storbinary(f"STOR {remote_name}", f)

        print(f"✅ Uploaded {remote_name} to {ftp.pwd()}")
        print("🔍 FTP current directory:", ftp.pwd())


def main():
    image_name = pick_next_image()
    image_path, image_url = download_image(image_name)
    haiku = generate_haiku_from_image(image_path)
    save_haiku(image_name, haiku, image_url)
    upload_to_bluehost(OUTPUT_FILE, "haiku.json")

if __name__ == "__main__":
    main()
