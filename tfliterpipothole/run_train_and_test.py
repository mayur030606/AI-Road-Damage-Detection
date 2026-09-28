#!/usr/bin/env python3
"""
Scan tfliterpipothole dataset, prepare pothole model, evaluate on images, test on video.

The 72 JPG images are unlabeled test samples. Training from scratch requires VOC/YOLO
annotations (use labelImg in this folder). This script uses the verified pre-trained
Harisanth/Pothole-Finetuned-YOLOv8 weights and validates them on your local data.

Usage (from project root):
  python tfliterpipothole/run_train_and_test.py
  python tfliterpipothole/run_train_and_test.py --conf 0.50
  python tfliterpipothole/run_train_and_test.py --skip-video
"""

from __future__ import annotations

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DATASET_DIR = os.path.join(PROJECT_ROOT, "tfliterpipothole", "potholeimages", "potholeimages")
VIDEO_PATH = os.path.join(PROJECT_ROOT, "tfliterpipothole", "pothole1", "pothole1.mp4")
MODEL_PATH = os.path.join(PROJECT_ROOT, "ai", "models", "pothole_model.pt")
ONNX_PATH = os.path.join(PROJECT_ROOT, "ai", "models", "pothole_model.onnx")
IMAGE_OUTPUT = os.path.join(PROJECT_ROOT, "ai_output", "dataset_evaluation")
VIDEO_OUTPUT = os.path.join(PROJECT_ROOT, "ai_output", "video_test", "pothole1_detected.mp4")


def scan_dataset() -> dict:
    """Report contents of tfliterpipothole folder."""
    images = []
    if os.path.isdir(DATASET_DIR):
        images = sorted(
            f for f in os.listdir(DATASET_DIR)
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        )
    xml_labels = [
        f for f in os.listdir(DATASET_DIR)
        if f.lower().endswith(".xml")
    ] if os.path.isdir(DATASET_DIR) else []

    report = {
        "dataset_dir": DATASET_DIR,
        "image_count": len(images),
        "label_count": len(xml_labels),
        "video_path": VIDEO_PATH,
        "video_exists": os.path.isfile(VIDEO_PATH),
        "train_ready": len(xml_labels) > 0,
    }
    print("\n=== tfliterpipothole scan ===")
    print(f"  Images:     {report['image_count']} in potholeimages/potholeimages/")
    print(f"  Labels:     {report['label_count']} XML files (needed for custom training)")
    print(f"  Video:      {VIDEO_PATH} ({'found' if report['video_exists'] else 'MISSING'})")
    print(f"  Trainable:  {'yes' if report['train_ready'] else 'no — using pre-trained YOLO weights'}")
    return report


def ensure_model() -> str:
    """Use existing .onnx/.pt on disk. Do not import ultralytics on Raspberry Pi."""
    if os.path.isfile(ONNX_PATH) and os.path.getsize(ONNX_PATH) > 1000:
        print(f"\n=== model ready ===\n  {ONNX_PATH}")
        return ONNX_PATH
    if os.path.isfile(MODEL_PATH) and os.path.getsize(MODEL_PATH) > 1000:
        print(f"\n=== model ready ===\n  {MODEL_PATH}")
        return MODEL_PATH
    try:
        from ai.pothole.downloader import download_pothole_model
        path = download_pothole_model(MODEL_PATH)
        print(f"\n=== model ready ===\n  {path}")
        return path
    except ImportError:
        raise FileNotFoundError(
            f"No pothole model at {ONNX_PATH} or {MODEL_PATH}. "
            "Copy pothole_model.onnx from your PC to ai/models/ on the Pi."
        )


def test_images(conf: float, send_backend: bool, model_path: str = MODEL_PATH) -> dict:
    """Run batch image evaluation."""
    if not os.path.isdir(DATASET_DIR):
        print("\n=== image results ===\n  No image folder on this machine. Skipping.")
        return {"total_images": 0, "images_with_potholes": 0, "total_potholes_found": 0}

    from types import SimpleNamespace
    from ai.cli import cmd_evaluate_dataset

    args = SimpleNamespace(
        dir=DATASET_DIR,
        output_dir=IMAGE_OUTPUT,
        model=model_path,
        conf=conf,
        send_to_backend=send_backend,
        backend_url=os.environ.get("BACKEND_URL", "http://127.0.0.1:8000/api/v1/incidents"),
        token=os.environ.get("AUTH_TOKEN", "sih_admin"),
    )
    cmd_evaluate_dataset(args)
    summary_path = os.path.join(IMAGE_OUTPUT, "dataset_summary.json")
    if not os.path.isfile(summary_path):
        return {"total_images": 0, "images_with_potholes": 0, "total_potholes_found": 0}
    with open(summary_path, encoding="utf-8") as f:
        return json.load(f)


def test_video(conf: float) -> dict:
    """Run video inference and save annotated output."""
    from ai.detector import PotholeDetector

    if not os.path.isfile(VIDEO_PATH):
        raise FileNotFoundError(f"Video not found: {VIDEO_PATH}")

    os.makedirs(os.path.dirname(VIDEO_OUTPUT), exist_ok=True)
    detector = PotholeDetector(model_path=MODEL_PATH, pothole_conf=conf)
    result = detector.predict_video(VIDEO_PATH, output_path=VIDEO_OUTPUT, conf_threshold=conf)

    print("\n=== video test ===")
    print(f"  Input:      {VIDEO_PATH}")
    print(f"  Output:     {VIDEO_OUTPUT}")
    print(f"  Frames:     {result['processed_frames']}")
    print(f"  Detections: {result['total_detections']}")
    print(f"  Avg FPS:    {result['average_fps']}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Pothole model prep, image eval, video test")
    parser.add_argument("--conf", type=float, default=0.40, help="Detection confidence (default 0.40)")
    parser.add_argument("--skip-video", action="store_true", help="Skip video inference")
    parser.add_argument("--send-to-backend", action="store_true", help="POST image detections to backend")
    args = parser.parse_args()

    scan = scan_dataset()
    model_path = ensure_model()

    summary = test_images(conf=args.conf, send_backend=args.send_to_backend, model_path=model_path)
    print(f"\n=== image results ===")
    print(f"  Detected potholes in {summary['images_with_potholes']}/{summary['total_images']} images")
    print(f"  Total boxes: {summary['total_potholes_found']}")

    if not args.skip_video and scan["video_exists"]:
        test_video(conf=args.conf)

    print("\nDone. Annotated images:", IMAGE_OUTPUT)
    if not args.skip_video:
        print("Annotated video:", VIDEO_OUTPUT)


if __name__ == "__main__":
    main()
