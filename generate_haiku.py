import os
import json
import openai
from datetime import datetime
import base64

# Load OpenAI key from environment
openai.api_key = os.getenv("OPENAI_API_KEY")

# Paths
IMAGE_FOLDER = "images"
OUTPUT_FILE = "haikus/haiku.json"
USED_IMAGES_FILE = "haikus/used_images.json"

def get_all_images():
    return sorted([f for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])

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
    all_images = get_all_images()
    used_images = load_used_images()

    unused_images = [img for img in all_images if img not in used_images]

    if not unused_images:
        # Reset if all used
        used_images = []
        unused_images = all_images
        print("All images used — restarting cycle.")

    next_image = unused_images[0]  # Pick the next one in order
    used_images.append(next_image)
    save_used_images(used_images)

    return next_image


def generate_haiku_from_image(image_path):
    print(f"Generating haiku from: {image_path}")
    with open(image_path, "rb") as img_file:
        image_data = base64.b64encode(img_file.read()).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{image_data}"

        response = openai.ChatCompletion.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Write a haiku inspired by this image. Do not explain it."},
                        {"type": "image_url", "image_url": {"url": data_url}}
                    ]
                }
            ],
            max_tokens=100
        )

    return response['choices'][0]['message']['content'].strip()


def save_haiku(image_name, haiku_text):
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    output = {
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "image": f"images/{image_name}",
        "haiku": haiku_text
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"Saved haiku to {OUTPUT_FILE}")

def main():
    image_name = pick_next_image()
    image_path = os.path.join(IMAGE_FOLDER, image_name)
    haiku = generate_haiku_from_image(image_path)
    save_haiku(image_name, haiku)

if __name__ == "__main__":
    main()
