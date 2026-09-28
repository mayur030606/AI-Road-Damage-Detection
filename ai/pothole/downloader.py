"""
Downloader and validator for Harisanth/Pothole-Finetuned-YOLOv8 model weights.
"""

import os
import sys
import logging
import requests
from ultralytics import YOLO

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("PotholeDownloader")

PRIMARY_MODEL_REPO = "Harisanth/Pothole-Finetuned-YOLOv8"

MODEL_SOURCES = [
    {
        "repo": "Harisanth/Pothole-Finetuned-YOLOv8",
        "url": "https://huggingface.co/Harisanth/Pothole-Finetuned-YOLOv8/resolve/main/best.pt",
        "name": "HuggingFace Primary (Harisanth/Pothole-Finetuned-YOLOv8)"
    },
    {
        "repo": "peterhdd/pothole-detection-yolov8",
        "url": "https://huggingface.co/peterhdd/pothole-detection-yolov8/resolve/main/best.pt",
        "name": "HuggingFace Mirror (peterhdd/pothole-detection-yolov8)"
    },
    {
        "repo": "samdutse/pothole-yolov8",
        "url": "https://huggingface.co/samdutse/pothole-yolov8/resolve/main/best.pt",
        "name": "HuggingFace Mirror (samdutse/pothole-yolov8)"
    }
]

DEFAULT_POTHOLE_MODEL_PATH = os.path.join("ai", "models", "pothole_model.pt")


def download_pothole_model(target_path: str = DEFAULT_POTHOLE_MODEL_PATH) -> str:
    """
    Download and validate Harisanth/Pothole-Finetuned-YOLOv8 weights file.
    Uses range-resume logic to handle connection interruptions.
    """
    target_abs = os.path.abspath(target_path)
    os.makedirs(os.path.dirname(target_abs), exist_ok=True)

    # 1. Validate if model already exists locally
    if os.path.exists(target_abs) and os.path.getsize(target_abs) > 1000000:
        try:
            logger.info(f"Existing model file found at '{target_abs}'. Validating checkpoint...")
            model = YOLO(target_abs)
            if hasattr(model, "names") and len(model.names) > 0:
                logger.info(f"Existing pothole model validated successfully! Classes (model.names): {model.names}")
                return target_abs
        except Exception as e:
            logger.warning(f"Validation of existing file failed ({e}). Will re-download...")

    # 2. Resumable download loop across sources
    temp_path = target_abs.replace(".pt", "_tmp.pt")

    for source in MODEL_SOURCES:
        url = source["url"]
        name = source["name"]
        logger.info(f"Attempting download from {name}: '{url}'...")

        attempt = 0
        max_attempts = 10

        while attempt < max_attempts:
            attempt += 1
            existing_size = os.path.getsize(temp_path) if os.path.exists(temp_path) else 0
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            
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
                                    logger.info(f"Download progress ({name}): {pct:.1f}% ({downloaded / (1024*1024):.1f} MB / {total_bytes / (1024*1024):.1f} MB)")

                    logger.info(f"Download loop completed ({os.path.getsize(temp_path) / (1024*1024):.1f} MB). Validating YOLO model...")
                    
                    try:
                        model = YOLO(temp_path)
                        if hasattr(model, "names") and len(model.names) > 0:
                            os.replace(temp_path, target_abs)
                            logger.info(f"✅ Successfully downloaded & verified pothole model at '{target_abs}'!")
                            logger.info(f"Verified Model Classes (model.names): {model.names}")
                            return target_abs
                    except Exception as ve:
                        logger.warning(f"Model validation failed ({ve}). Retrying chunk...")

            except Exception as e:
                logger.warning(f"Attempt {attempt}/{max_attempts} interrupted ({e}). Retrying from byte offset {os.path.getsize(temp_path) if os.path.exists(temp_path) else 0}...")

    raise RuntimeError(
        "Failed to download a valid pothole-trained YOLO model after multiple attempts. "
        "Please manually download best.pt from https://huggingface.co/Harisanth/Pothole-Finetuned-YOLOv8 "
        f"and save it to '{target_abs}'."
    )


if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_POTHOLE_MODEL_PATH
    download_pothole_model(out_path)
