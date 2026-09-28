"""
Build Deduplicated Combined Pothole Dataset & Run Verification
Creates datasets/pothole_combined with zero duplicate images.
Target totals:
- Train: 3,392 images
- Val: 491 images
- Test: 246 images
- Total: 4,129 unique images
"""

import os
import sys
import glob
import shutil
import yaml
import hashlib
from pathlib import Path
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = Path(__file__).resolve().parent.parent
DATASETS_DIR = ROOT_DIR / "datasets"

D1_PATH = DATASETS_DIR / "pothole_dataset_1"
D2_PATH = DATASETS_DIR / "pothole_dataset_2"
COMBINED_PATH = DATASETS_DIR / "pothole_combined"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
CLASS_NAMES = {0: "Drain Hole", 1: "Pothole", 2: "Sewer Cover"}

def get_image_info(dataset_path: Path):
    images = {}
    image_files = []
    for ext in IMAGE_EXTS:
        image_files.extend(dataset_path.glob(f"**/*{ext}"))

    for img_path in image_files:
        parts = [p.lower() for p in img_path.parts]
        split = "unassigned"
        if "train" in parts:
            split = "train"
        elif "valid" in parts or "val" in parts:
            split = "val"
        elif "test" in parts:
            split = "test"

        with open(img_path, "rb") as f:
            img_hash = hashlib.md5(f.read()).hexdigest()

        txt_path = img_path.with_suffix(".txt")
        if not txt_path.exists() and "images" in parts:
            lbl_parts = list(img_path.parts)
            idx = [i for i, p in enumerate(lbl_parts) if p.lower() == "images"]
            if idx:
                lbl_parts[idx[-1]] = "labels"
                lbl_path = Path(*lbl_parts).with_suffix(".txt")
                if lbl_path.exists():
                    txt_path = lbl_path

        images[img_hash] = {
            "img_path": img_path,
            "split": split,
            "txt_path": txt_path if txt_path.exists() else None
        }

    return images

def build_combined():
    print("============================================================")
    print("      BUILDING DEDUPLICATED COMBINED POTHOLE DATASET")
    print("============================================================\n")

    if COMBINED_PATH.exists():
        print(f"[!] Removing pre-existing directory: {COMBINED_PATH}")
        shutil.rmtree(COMBINED_PATH)

    # Create directory structure
    for split in ["train", "val", "test"]:
        (COMBINED_PATH / "images" / split).mkdir(parents=True, exist_ok=True)
        (COMBINED_PATH / "labels" / split).mkdir(parents=True, exist_ok=True)

    d1_imgs = get_image_info(D1_PATH)
    d2_imgs = get_image_info(D2_PATH)

    h1_set = set(d1_imgs.keys())
    h2_set = set(d2_imgs.keys())

    shared_hashes = h1_set.intersection(h2_set)
    d1_only_hashes = h1_set - h2_set
    d2_only_hashes = h2_set - h1_set

    print(f"Dataset 1 Total: {len(h1_set)}")
    print(f"Dataset 2 Total: {len(h2_set)}")
    print(f"Shared Duplicates: {len(shared_hashes)}")
    print(f"Dataset 1 Unique Only: {len(d1_only_hashes)}")
    print(f"Dataset 2 Unique Only: {len(d2_only_hashes)}")
    print(f"Expected Unique Combined Total: {len(h1_set | h2_set)}\n")

    # Priority for copying:
    # 1. Copy shared images from Dataset 2 (v9)
    # 2. Copy Dataset 1 only images from Dataset 1
    # 3. Copy Dataset 2 only images from Dataset 2

    copied_count = 0

    def copy_file_entry(info: dict, prefix: str):
        nonlocal copied_count
        split = info["split"]
        img_src = info["img_path"]
        txt_src = info["txt_path"]

        dst_img_name = f"{prefix}_{img_src.name}"
        dst_img_path = COMBINED_PATH / "images" / split / dst_img_name
        shutil.copy2(img_src, dst_img_path)

        if txt_src and txt_src.name != "README.dataset.txt":
            dst_txt_name = f"{prefix}_{img_src.stem}.txt"
            dst_txt_path = COMBINED_PATH / "labels" / split / dst_txt_name
            shutil.copy2(txt_src, dst_txt_path)

        copied_count += 1

    print("[+] Copying shared unique images...")
    for h in shared_hashes:
        copy_file_entry(d2_imgs[h], "shared")

    print("[+] Copying Dataset 1 unique images...")
    for h in d1_only_hashes:
        copy_file_entry(d1_imgs[h], "d1")

    print("[+] Copying Dataset 2 unique images...")
    for h in d2_only_hashes:
        copy_file_entry(d2_imgs[h], "d2")

    print(f"\n[SUCCESS] Copied {copied_count} total unique images into {COMBINED_PATH}")

    # Write data.yaml
    data_yaml_path = COMBINED_PATH / "data.yaml"
    data_yaml_content = {
        "path": "./datasets/pothole_combined",
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": {
            0: "Drain Hole",
            1: "Pothole",
            2: "Sewer Cover"
        }
    }

    with open(data_yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data_yaml_content, f, sort_keys=False)

    print(f"[SUCCESS] Created data.yaml at {data_yaml_path}")

def verify_combined():
    print("\n============================================================")
    print("      READ-ONLY VERIFICATION OF COMBINED POTHOLE DATASET")
    print("============================================================\n")

    split_img_counts = {}
    split_lbl_counts = {}
    hash_to_split = {}
    duplicate_hashes = set()
    cross_split_hashes = set()

    all_class_ids = set()
    normalized_valid = True
    bbox_counts = Counter()
    total_bboxes = 0

    for split in ["train", "val", "test"]:
        img_dir = COMBINED_PATH / "images" / split
        lbl_dir = COMBINED_PATH / "labels" / split

        img_files = list(img_dir.glob("*.*"))
        lbl_files = list(lbl_dir.glob("*.txt"))

        split_img_counts[split] = len(img_files)
        split_lbl_counts[split] = len(lbl_files)

        for img_path in img_files:
            # MD5 hash
            with open(img_path, "rb") as f:
                h = hashlib.md5(f.read()).hexdigest()

            if h in hash_to_split:
                duplicate_hashes.add(h)
                if hash_to_split[h] != split:
                    cross_split_hashes.add(h)
            else:
                hash_to_split[h] = split

            # Verify label file exists
            txt_path = lbl_dir / f"{img_path.stem}.txt"
            if not txt_path.exists():
                print(f"[ERROR] Missing label for image: {img_path.name}")

            # Inspect label bounding boxes
            if txt_path.exists():
                with open(txt_path, "r", encoding="utf-8") as lf:
                    lines = lf.readlines()
                    for line in lines:
                        tokens = line.strip().split()
                        if len(tokens) >= 5:
                            try:
                                cls_id = int(tokens[0])
                                all_class_ids.add(cls_id)
                                bbox_counts[cls_id] += 1
                                total_bboxes += 1

                                coords = [float(x) for x in tokens[1:5]]
                                if any(c < 0.0 or c > 1.0 for c in coords):
                                    normalized_valid = False
                            except ValueError:
                                pass

    print("1. Split Image and Label Counts:")
    for split in ["train", "val", "test"]:
        imgs = split_img_counts[split]
        lbls = split_lbl_counts[split]
        match_str = "YES" if imgs == lbls else "NO"
        print(f"   - {split:5s}: Images = {imgs:4d} | Labels = {lbls:4d} | 1-to-1 Match: {match_str}")

    total_combined_imgs = sum(split_img_counts.values())
    total_combined_lbls = sum(split_lbl_counts.values())
    print(f"   - TOTAL: Images = {total_combined_imgs} | Labels = {total_combined_lbls}")

    print("\n2. Duplicate Image & Hash Verification:")
    print(f"   - Internal Duplicate Image Hashes: {len(duplicate_hashes)} ({'PASS ✅' if len(duplicate_hashes) == 0 else 'FAIL ❌'})")
    print(f"   - Cross-Split Hash Leaks:        {len(cross_split_hashes)} ({'PASS ✅' if len(cross_split_hashes) == 0 else 'FAIL ❌'})")

    print("\n3. Annotation & Class ID Verification:")
    print(f"   - Class IDs Present:             {sorted(list(all_class_ids))}")
    print(f"   - Only Class IDs 0, 1, 2 Used:    {'PASS ✅' if all_class_ids.issubset({0, 1, 2}) else 'FAIL ❌'}")
    print(f"   - Normalized Coordinates [0..1]: {'PASS ✅' if normalized_valid else 'FAIL ❌'}")

    print("\n4. data.yaml Verification:")
    yaml_path = COMBINED_PATH / "data.yaml"
    with open(yaml_path, "r", encoding="utf-8") as f:
        yaml_cfg = yaml.safe_load(f)
    print(f"   - Path:  {yaml_cfg.get('path')}")
    print(f"   - Train: {yaml_cfg.get('train')}")
    print(f"   - Val:   {yaml_cfg.get('val')}")
    print(f"   - Test:  {yaml_cfg.get('test')}")
    print(f"   - Names: {yaml_cfg.get('names')}")

    print("\n5. Bounding Box Class Distribution Report:")
    for cid in sorted(CLASS_NAMES.keys()):
        cname = CLASS_NAMES[cid]
        count = bbox_counts[cid]
        pct = (count / total_bboxes * 100) if total_bboxes > 0 else 0
        print(f"   - Class {cid} ({cname:11s}): {count:5d} bounding boxes ({pct:5.2f}%)")
    print(f"   - Total Bounding Boxes:     {total_bboxes}")

    print("\n============================================================")

if __name__ == "__main__":
    build_combined()
    verify_combined()
