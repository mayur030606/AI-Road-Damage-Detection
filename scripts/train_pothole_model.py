"""
Train & Evaluate YOLOv8s Pothole Detection Model
Dataset: datasets/pothole_combined/data.yaml
Classes: 0: Drain Hole, 1: Pothole, 2: Sewer Cover
Pretrained Weights: yolov8s.pt
Output directory: runs/pothole/
"""

import os
import sys
import time
import json
from pathlib import Path
from ultralytics import YOLO

sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_YAML = ROOT_DIR / "datasets" / "pothole_combined" / "data.yaml"
OUTPUT_DIR = ROOT_DIR / "runs" / "pothole"

CLASS_NAMES = {0: "Drain Hole", 1: "Pothole", 2: "Sewer Cover"}

def train_and_eval():
    print("============================================================")
    print("      TRAINING YOLOV8s POTHOLE DETECTION MODEL")
    print("============================================================\n")

    print(f"[+] Dataset YAML: {DATA_YAML}")
    print(f"[+] Output Directory: {OUTPUT_DIR}")
    print(f"[+] Base Model: yolov8s.pt\n")

    start_time = time.time()

    # Initialize model with pretrained YOLOv8s weights
    model = YOLO("yolov8s.pt")

    # Train model
    epochs = 20
    batch_size = 16
    imgsz = 640

    print(f"[+] Starting training for {epochs} epochs (batch={batch_size}, imgsz={imgsz})...")
    train_results = model.train(
        data=str(DATA_YAML),
        epochs=epochs,
        batch=batch_size,
        imgsz=imgsz,
        project=str(OUTPUT_DIR),
        name="train",
        exist_ok=True,
        save=True,
        val=True,
        plots=True,
        device="cpu"
    )

    elapsed_sec = time.time() - start_time
    hours, rem = divmod(elapsed_sec, 3600)
    minutes, seconds = divmod(rem, 60)
    time_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

    best_pt = OUTPUT_DIR / "train" / "weights" / "best.pt"
    last_pt = OUTPUT_DIR / "train" / "weights" / "last.pt"

    print("\n[+] Training completed successfully!")
    print(f"[+] Total Training Time: {time_str}")
    print(f"[+] Best Weights Saved: {best_pt}")
    print(f"[+] Last Weights Saved: {last_pt}\n")

    # Run evaluation on TEST split using best.pt
    print("============================================================")
    print("      EVALUATING FINAL MODEL ON TEST SPLIT")
    print("============================================================\n")

    test_model = YOLO(str(best_pt))
    test_results = test_model.val(
        data=str(DATA_YAML),
        split="test",
        project=str(OUTPUT_DIR),
        name="test_eval",
        exist_ok=True,
        device="cpu"
    )

    # Extract metrics
    # test_results.box metrics: map, map50, map75, mp, mr, maps (per class)
    box = test_results.box
    precision = float(box.mp)
    recall = float(box.mr)
    map50 = float(box.map50)
    map50_95 = float(box.map)

    print("\n============================================================")
    print("      FINAL PERFORMANCE & EVALUATION SUMMARY")
    print("============================================================")

    print(f"Training Epochs:               {epochs}")
    print(f"Total Training Time:           {time_str}")
    print(f"Location of best.pt:           {best_pt}")
    print(f"Location of last.pt:           {last_pt}\n")

    print(f"--- TEST SPLIT METRICS ---")
    print(f"Precision (P):                 {precision:.4f} ({precision*100:.2f}%)")
    print(f"Recall (R):                    {recall:.4f} ({recall*100:.2f}%)")
    print(f"mAP@0.50:                      {map50:.4f} ({map50*100:.2f}%)")
    print(f"mAP@0.50:0.95:                 {map50_95:.4f} ({map50_95*100:.2f}%)\n")

    print("--- PER-CLASS TEST METRICS ---")
    per_class_map50 = box.maps50 if hasattr(box, "maps50") else box.maps
    per_class_map = box.maps if hasattr(box, "maps") else box.maps

    for cid, cname in CLASS_NAMES.items():
        c_map50 = float(per_class_map50[cid]) if cid < len(per_class_map50) else 0.0
        c_map = float(per_class_map[cid]) if cid < len(per_class_map) else 0.0
        print(f"Class {cid} ({cname:11s}): mAP@0.50 = {c_map50:.4f} ({c_map50*100:.2f}%), mAP@0.50:0.95 = {c_map:.4f} ({c_map*100:.2f}%)")

    print("\n============================================================")

if __name__ == "__main__":
    train_and_eval()
