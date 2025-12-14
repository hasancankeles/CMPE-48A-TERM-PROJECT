import base64
import json
import os

import requests
from google.cloud import storage


def cache_image(event, context):
    """
    Pub/Sub triggered function to cache external images to GCS.
    Expects payload: {"url": "<external_url>", "hash": "<sha256hex>"}
    Writes to: gs://{GCS_IMAGE_CACHE_BUCKET}/image-cache/{hash}.{ext}
    
    After successful upload, calls back to the backend to update the database
    with the GCS URL for efficient future lookups.
    """
    try:
        data = json.loads(base64.b64decode(event["data"]).decode())
        image_url = data["url"]
        url_hash = data["hash"]
    except Exception as e:
        print(f"Invalid Pub/Sub payload: {e}")
        return

    bucket_name = os.environ.get("GCS_IMAGE_CACHE_BUCKET")
    if not bucket_name:
        print("GCS_IMAGE_CACHE_BUCKET is not set; skipping")
        return

    backend_url = os.environ.get("BACKEND_CALLBACK_URL", "")

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

        # If already exists, just notify backend and return
        if blob.exists():
            print(f"Blob already exists: {object_name}")
            gcs_url = f"https://storage.googleapis.com/{bucket_name}/{object_name}"
            _notify_backend(backend_url, url_hash, gcs_url)
            return

        blob.cache_control = "public, max-age=86400"
        blob.upload_from_string(content, content_type=content_type)
        
        gcs_url = f"https://storage.googleapis.com/{bucket_name}/{object_name}"
        print(f"Cached {image_url[:60]}... as {gcs_url}")
        
        # Notify backend to update database with GCS URL
        _notify_backend(backend_url, url_hash, gcs_url)
        
    except Exception as e:
        print(f"Failed to cache image {image_url}: {e}")


def _notify_backend(backend_url: str, url_hash: str, gcs_url: str) -> None:
    """
    Call the backend to update the ImageCache entry with the GCS URL.
    This enables efficient database lookups instead of GCS API calls.
    """
    if not backend_url:
        print("BACKEND_CALLBACK_URL not set; skipping callback")
        return
    
    try:
        callback_endpoint = f"{backend_url}/api/foods/image-cache-callback/"
        response = requests.post(
            callback_endpoint,
            json={"hash": url_hash, "gcs_url": gcs_url},
            timeout=10,
            headers={"Content-Type": "application/json"}
        )
        if response.ok:
            print(f"Backend notified successfully: {response.status_code}")
        else:
            print(f"Backend notification failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Failed to notify backend: {e}")

