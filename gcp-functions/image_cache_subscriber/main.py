import base64
import json
import os
from io import BytesIO

import requests
from google.cloud import storage


def cache_image(event, context):
    """
    Pub/Sub triggered function to cache external images to GCS.
    Expects payload: {"url": "<external_url>", "hash": "<sha256hex>"}
    Writes to: gs://{GCS_MEDIA_BUCKET}/image-cache/{hash}.{ext}
    """
    try:
        data = json.loads(base64.b64decode(event["data"]).decode())
        image_url = data["url"]
        url_hash = data["hash"]
    except Exception as e:
        print(f"Invalid Pub/Sub payload: {e}")
        return

    bucket_name = os.environ.get("GCS_MEDIA_BUCKET")
    if not bucket_name:
        print("GCS_MEDIA_BUCKET is not set; skipping")
        return

    try:
        # Download the image (streamed)
        resp = requests.get(image_url, timeout=15, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "image/jpeg")
        # Derive extension
        ext_map = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        ext = ext_map.get(content_type, ".jpg")

        # Read content
        content = resp.content

        # Upload to GCS
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        object_name = f"image-cache/{url_hash}{ext}"
        blob = bucket.blob(object_name)

        # If already exists, skip
        if blob.exists():
            print(f"Blob already exists: {object_name}")
            return

        blob.cache_control = "public, max-age=86400"
        blob.upload_from_string(content, content_type=content_type)
        print(f"Cached {image_url[:60]}... as gs://{bucket_name}/{object_name}")
    except Exception as e:
        print(f"Failed to cache image {image_url}: {e}")

