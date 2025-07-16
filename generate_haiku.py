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

def pick_next_image(remote_images):
    try:
        response = requests.get("https://dailykorina.com/haiku/haiku.json")
        response.raise_for_status()

        if not response.text.strip():
            raise ValueError("haiku.json is empty")

        print("📄 haiku.json content:", response.text)

        last_data = response.json()
        last_image = os.path.basename(last_data.get("image", "1.jpg"))
        last_index = remote_images.index(last_image)
        next_index = (last_index + 1) % len(remote_images)
        print(f"🔁 Last image was {last_image}, next is {remote_images[next_index]}")
        return remote_images[next_index]
    except Exception as e:
        print(f"⚠️ Could not read haiku.json: {e}")
        return remote_images[0]


def download_image(image_name):
    url = f"https://dailykorina.com/haiku/images/{urllib.parse.quote(image_name)}"
    print(f"⬇️ Downloading image from: {url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
    }

    response = requests.get(url, headers=headers)
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

    response = openai.ChatCompletion.create(
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
                print(f"⚠️ Could not change directory: {e}")
                return

        with open(local_path, "rb") as f:
            print(f"📤 Uploading {local_path} as {remote_name}")
            ftp.storbinary(f"STOR {remote_name}", f)

        print(f"✅ Uploaded {remote_name} to {ftp.pwd()}")
        print("🔍 FTP current directory:", ftp.pwd())

def main():
    all_images = fetch_remote_image_list()
    if not all_images:
        print("❌ No images found on FTP.")
        return

    image_name = pick_next_image(all_images)
    image_path, image_url = download_image(image_name)
    haiku = generate_haiku_from_image(image_path)

    save_haiku(image_name, haiku, image_url)
    upload_to_bluehost(OUTPUT_FILE, "haiku.json")

    print("✅ Daily haiku generated and uploaded.")


if __name__ == "__main__":
    main()
