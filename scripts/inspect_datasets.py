"""
Dataset Inspection & Safeness Analysis Script for SIH Project
Inspects all 3 Roboflow datasets according to the exact 15-point specification.
Compares Dataset 1 & 2 for merging safeness.
Evaluates Dataset 3 (zebra crossing) format (object detection vs classification).
Does NOT modify files, combine datasets, or train any models.
"""

import os
import sys
import glob
import yaml
import hashlib
from pathlib import Path
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = Path(__file__).resolve().parent.parent
DATASETS_DIR = ROOT_DIR / "datasets"

TARGET_DATASETS = [
    {
        "id": "DATASET 1 — POTHOLE",
        "name": "pothole_dataset_1",
        "roboflow_info": "intel-unnati-training-program/pothole-detection-bqu6s:v7",
        "path": DATASETS_DIR / "pothole_dataset_1"
    },
    {
        "id": "DATASET 2 — POTHOLE",
        "name": "pothole_dataset_2",
        "roboflow_info": "intel-unnati-training-program/pothole-detection-bqu6s:v9",
        "path": DATASETS_DIR / "pothole_dataset_2"
    },
    {
        "id": "DATASET 3 — MISSING ZEBRA CROSSING",
        "name": "zebra_crossing_dataset",
        "roboflow_info": "co-099-mayur-rasal/road-marking-detection-qj8ey-bqgi6:v1",
        "path": DATASETS_DIR / "zebra_crossing_dataset"
    }
]

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

def inspect_dataset(ds_meta: dict) -> dict:
    name = ds_meta["name"]
    path = ds_meta["path"]

    info = {
        "id": ds_meta["id"],
        "name": name,
        "roboflow_info": ds_meta["roboflow_info"],
        "path": str(path),
        "exists": path.exists(),
        "yaml_found": False,
        "yaml_content": None,
        "num_classes": 0,
        "class_names": [],
        "class_ids": {},
        "splits": {"train": 0, "valid": 0, "test": 0, "unassigned": 0},
        "total_images": 0,
        "total_labels": 0,
        "orphan_labels": 0,
        "images_without_labels": 0,
        "format": "Unknown",
        "task_type": "Unknown", # Object Detection vs Classification
        "yolo_bbox_valid": True,
        "image_dimensions": set(),
        "image_hashes": dict(), # hash -> filepath
        "corrupt_images": 0,
        "problems": []
    }

    if not path.exists():
        info["problems"].append("Dataset folder does not exist.")
        return info

    # Find data.yaml
    yaml_files = list(path.glob("*.yaml")) + list(path.glob("**/*.yaml"))
    if yaml_files:
        info["yaml_found"] = True
        try:
            with open(yaml_files[0], "r", encoding="utf-8") as f:
                data_cfg = yaml.safe_load(f)
                info["yaml_content"] = data_cfg
                if isinstance(data_cfg, dict):
                    names = data_cfg.get("names", {})
                    if isinstance(names, list):
                        info["class_names"] = names
                        info["num_classes"] = len(names)
                        info["class_ids"] = {i: n for i, n in enumerate(names)}
                    elif isinstance(names, dict):
                        info["class_names"] = list(names.values())
                        info["num_classes"] = len(names)
                        info["class_ids"] = {int(k): v for k, v in names.items()}
        except Exception as e:
            info["problems"].append(f"Failed to parse data.yaml: {e}")

    # Gather images and labels
    all_images = []
    for ext in IMAGE_EXTS:
        all_images.extend(path.glob(f"**/*{ext}"))

    info["total_images"] = len(all_images)
    if info["total_images"] == 0:
        info["problems"].append("No image files found in dataset path.")

    image_stem_set = set()

    for img_path in all_images:
        image_stem_set.add(img_path.stem)
        parts = [p.lower() for p in img_path.parts]
        
        # Split tracking
        if "train" in parts:
            info["splits"]["train"] += 1
        elif "valid" in parts or "val" in parts:
            info["splits"]["valid"] += 1
        elif "test" in parts:
            info["splits"]["test"] += 1
        else:
            info["splits"]["unassigned"] += 1

        # Check image validity & size
        try:
            with Image.open(img_path) as img:
                img.verify()
            with Image.open(img_path) as img:
                info["image_dimensions"].add(img.size)
        except Exception:
            info["corrupt_images"] += 1

        # Calculate MD5 hash
        try:
            with open(img_path, "rb") as f:
                h = hashlib.md5(f.read()).hexdigest()
                info["image_hashes"][h] = img_path
        except Exception:
            pass

        # Check label file
        txt_path = img_path.with_suffix(".txt")
        if not txt_path.exists() and "images" in parts:
            lbl_parts = list(img_path.parts)
            idx = [i for i, p in enumerate(lbl_parts) if p.lower() == "images"]
            if idx:
                lbl_parts[idx[-1]] = "labels"
                lbl_path = Path(*lbl_parts).with_suffix(".txt")
                if lbl_path.exists():
                    txt_path = lbl_path

        if txt_path.exists():
            info["total_labels"] += 1
            info["format"] = "YOLOv8 txt annotations"
            info["task_type"] = "Object Detection"
            try:
                with open(txt_path, "r", encoding="utf-8") as lf:
                    lines = lf.readlines()
                    for line in lines:
                        tokens = line.strip().split()
                        if len(tokens) >= 5: # class_id, x_center, y_center, width, height
                            coords = [float(x) for x in tokens[1:5]]
                            if any(c < 0.0 or c > 1.0 for c in coords):
                                info["yolo_bbox_valid"] = False
                        elif len(tokens) == 1: # Single class label -> Image Classification
                            info["task_type"] = "Image Classification"
                        elif len(tokens) > 0 and len(tokens) < 5:
                            info["yolo_bbox_valid"] = False
            except Exception:
                info["yolo_bbox_valid"] = False
        else:
            info["images_without_labels"] += 1

    # Check for orphan label files (.txt without image)
    all_txts = list(path.glob("**/*.txt"))
    for txt in all_txts:
        if txt.name == "data.yaml" or txt.name == "README.roboflow.txt":
            continue
        if txt.stem not in image_stem_set:
            info["orphan_labels"] += 1

    if info["corrupt_images"] > 0:
        info["problems"].append(f"Found {info['corrupt_images']} corrupt/unreadable images.")
    if info["images_without_labels"] > 0:
        info["problems"].append(f"{info['images_without_labels']} images have no corresponding label file.")
    if info["orphan_labels"] > 0:
        info["problems"].append(f"{info['orphan_labels']} orphan label files found without matching image.")
    if not info["yolo_bbox_valid"]:
        info["problems"].append("Some bounding boxes contain out-of-bounds (<0 or >1) coordinates.")

    return info


def print_report():
    print("=" * 60)
    print("       SIH 3-DATASET AUDIT & SAFENESS INSPECTION REPORT")
    print("=" * 60 + "\n")

    results = []
    for ds_meta in TARGET_DATASETS:
        res = inspect_dataset(ds_meta)
        results.append(res)

    for res in results:
        print(f"[{res['id']}]")
        print(f"Dataset name:              {res['name']}")
        print(f"Roboflow Project/Version:  {res['roboflow_info']}")
        print(f"Folder Path:               {res['path']}")
        
        if not res["exists"] or res["total_images"] == 0:
            print("Status:                    [!] DATASET NOT DOWNLOADED YET")
            print(f"Problems:                  {res['problems']}\n")
            continue

        print(f"Total Images:              {res['total_images']}")
        print(f"Train / Valid / Test:      Train={res['splits']['train']}, Valid={res['splits']['valid']}, Test={res['splits']['test']}")
        print(f"Annotation Format:         {res['format']}")
        print(f"Task Type:                 {res['task_type']}")
        print(f"Standard YOLO BBoxes:      {'YES' if res['yolo_bbox_valid'] else 'NO'}")
        print(f"Number of Classes:         {res['num_classes']}")
        print(f"Class Names:               {res['class_names']}")
        print(f"Class IDs Mapping:         {res['class_ids']}")
        print(f"Label Correspondence:      {res['total_labels']} labeled / {res['images_without_labels']} unlabelled")
        print(f"Orphan Labels:             {res['orphan_labels']}")
        dims_str = ", ".join([f"{w}x{h}" for w, h in list(res['image_dimensions'])[:5]])
        print(f"Image Dimensions:          {dims_str if dims_str else 'N/A'}")
        print(f"Corrupt Images:            {res['corrupt_images']}")
        print(f"Problems:                  {res['problems'] if res['problems'] else 'None'}")
        print()

    # Compare Dataset 1 & Dataset 2 for pothole merging safety
    d1, d2 = results[0], results[1]
    print("=" * 60)
    print("   POTHOLE DATASETS COMPARISON (DATASET 1 vs DATASET 2)")
    print("=" * 60)

    if d1["total_images"] > 0 and d2["total_images"] > 0:
        hash_overlap = set(d1["image_hashes"].keys()).intersection(set(d2["image_hashes"].keys()))
        classes_identical = (d1["class_names"] == d2["class_names"]) and (d1["class_ids"] == d2["class_ids"])
        bboxes_compatible = d1["yolo_bbox_valid"] and d2["yolo_bbox_valid"]
        
        print(f"Classes Identical & Spelled Same:   {'YES' if classes_identical else 'NO'}")
        print(f"Class IDs Compatible:               {'YES' if classes_identical else 'NO'}")
        print(f"Standard YOLO BBoxes:               {'YES' if bboxes_compatible else 'NO'}")
        print(f"Duplicate Images Between Datasets:  {len(hash_overlap)}")
        
        can_merge = classes_identical and bboxes_compatible and (len(hash_overlap) == 0)
        print(f"\nSAFE TO MERGE DATASET 1 AND DATASET 2?  ==> {'YES ✅' if can_merge else 'NO ⚠️'}")
        if not can_merge:
            reasons = []
            if not classes_identical:
                reasons.append(f"Class mismatch: Dataset 1 {d1['class_ids']} vs Dataset 2 {d2['class_ids']}")
            if len(hash_overlap) > 0:
                reasons.append(f"Found {len(hash_overlap)} duplicate images between Dataset 1 & 2")
            if not bboxes_compatible:
                reasons.append("Incompatible bounding box format")
            print("Reasons for precaution:", reasons)
    else:
        print("Comparison pending: One or both pothole datasets are not downloaded yet.")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    print_report()
