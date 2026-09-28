"""
Download and verify a pre-trained Pothole YOLO model weights file with HTTP Range resume support.
"""

import os
import sys
import logging
import requests
from ultralytics import YOLO

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ModelDownloader")

MODEL_SOURCES = [
    {
        "url": "https://huggingface.co/peterhdd/pothole-detection-yolov8/resolve/main/best.pt",
        "name": "HuggingFace (peterhdd/pothole-detection-yolov8)"
    },
    {
        "url": "https://huggingface.co/samdutse/pothole-yolov8/resolve/main/best.pt",
        "name": "HuggingFace (samdutse/pothole-yolov8)"
    }
]

DEFAULT_TARGET_PATH = os.path.join("ai", "models", "pothole_model.pt")


def download_pothole_model(target_path: str = DEFAULT_TARGET_PATH) -> str:
    """Download and validate pothole YOLO model weights with automatic resume on drop."""
    target_abs = os.path.abspath(target_path)
    os.makedirs(os.path.dirname(target_abs), exist_ok=True)

    # 1. Check if target model file already exists and is valid
    if os.path.exists(target_abs) and os.path.getsize(target_abs) > 1000000:
        try:
            logger.info(f"Existing model file found at '{target_abs}'. Validating checkpoint...")
            model = YOLO(target_abs)
            has_pothole = any("pothole" in str(name).lower() or "crack" in str(name).lower() for name in model.names.values())
            if has_pothole:
                logger.info(f"Existing pothole model validated successfully! Classes (model.names): {model.names}")
                return target_abs
        except Exception as e:
            logger.warning(f"Existing file validation failed ({e}). Will re-download...")

    # 2. Resumable download loop
    for source in MODEL_SOURCES:
        url = source["url"]
        name = source["name"]
        temp_path = target_abs.replace(".pt", "_tmp.pt")
        logger.info(f"Attempting resumable download from {name}: '{url}'...")

        max_attempts = 15
        attempt = 0

        while attempt < max_attempts:
            attempt += 1
            existing_size = os.path.getsize(temp_path) if os.path.exists(temp_path) else 0
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            }
            if existing_size > 0:
                headers["Range"] = f"bytes={existing_size}-"

            try:
                response = requests.get(url, stream=True, allow_redirects=True, timeout=30, headers=headers)
                
                if response.status_code in (200, 206):
                    mode = "ab" if (response.status_code == 206 and existing_size > 0) else "wb"
                    if mode == "wb":
                        existing_size = 0

                    if response.status_code == 200 and "content-length" in response.headers:
                        total_bytes = int(response.headers["content-length"])
                    elif response.status_code == 206 and "content-range" in response.headers:
                        total_bytes = int(response.headers["content-range"].split("/")[-1])
                    else:
                        total_bytes = 0

                    downloaded = existing_size

                    with open(temp_path, mode) as f:
                        for chunk in response.iter_content(chunk_size=131072):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_bytes > 0 and (downloaded % (1024 * 1024) < 131072):
                                    pct = (downloaded / total_bytes) * 100
                                    logger.info(f"Download progress: {pct:.1f}% ({downloaded / (1024*1024):.1f} MB / {total_bytes / (1024*1024):.1f} MB)")

                    logger.info(f"Download loop completed ({os.path.getsize(temp_path) / (1024*1024):.1f} MB). Validating YOLO model...")
                    
                    # Validate PyTorch checkpoint
                    try:
                        model = YOLO(temp_path)
                        if hasattr(model, "names") and any("pothole" in str(v).lower() for v in model.names.values()):
                            os.replace(temp_path, target_abs)
                            logger.info(f"✅ Successfully downloaded and verified pothole model weights at '{target_abs}'!")
                            logger.info(f"Verified Model Classes (model.names): {model.names}")
                            return target_abs
                        else:
                            logger.warning(f"Downloaded checkpoint lacks 'pothole' class: {getattr(model, 'names', None)}")
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                            break
                    except Exception as ve:
                        logger.warning(f"Validation attempt failed ({ve}). Retrying download chunk...")

            except Exception as e:
                logger.warning(f"Attempt {attempt}/{max_attempts} interrupted ({e}). Retrying from byte offset {os.path.getsize(temp_path) if os.path.exists(temp_path) else 0}...")

    raise RuntimeError("Failed to download a valid pothole-trained YOLO model after multiple attempts.")


if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET_PATH
    download_pothole_model(out_path)
