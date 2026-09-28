"""
Deep Read-Only Cross-Dataset Verification for Pothole Dataset 1 vs Dataset 2
Calculates:
1. Annotation byte-for-byte identity check on duplicate images
2. Split mapping of duplicates (Dataset 1 split vs Dataset 2 split)
3. Count of cross-split boundary leaks (train <-> valid, train <-> test, valid <-> test)
4. Count of same-split duplicates (train <-> train, valid <-> valid, test <-> test)
5. Unique image counts: Dataset 1 only, Dataset 2 only, Shared, Total Union
6. Inspection of the two orphan .txt files
7. Bounding box class distribution for unique images
"""

import os
import sys
import glob
import hashlib
from pathlib import Path
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = Path(__file__).resolve().parent.parent
DATASETS_DIR = ROOT_DIR / "datasets"

D1_PATH = DATASETS_DIR / "pothole_dataset_1"
D2_PATH = DATASETS_DIR / "pothole_dataset_2"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
CLASS_NAMES = {0: "Drain Hole", 1: "Pothole", 2: "Sewer Cover"}

def get_image_info(dataset_path: Path):
    images = {} # md5_hash -> dict(path, split, stem, txt_path, txt_content, txt_hash)
    image_files = []
    for ext in IMAGE_EXTS:
        image_files.extend(dataset_path.glob(f"**/*{ext}"))

    for img_path in image_files:
        parts = [p.lower() for p in img_path.parts]
        split = "unassigned"
        if "train" in parts:
            split = "train"
        elif "valid" in parts or "val" in parts:
            split = "valid"
        elif "test" in parts:
            split = "test"

        # Image MD5
        with open(img_path, "rb") as f:
            img_hash = hashlib.md5(f.read()).hexdigest()

        # Label file
        txt_path = img_path.with_suffix(".txt")
        if not txt_path.exists() and "images" in parts:
            lbl_parts = list(img_path.parts)
            idx = [i for i, p in enumerate(lbl_parts) if p.lower() == "images"]
            if idx:
                lbl_parts[idx[-1]] = "labels"
                lbl_path = Path(*lbl_parts).with_suffix(".txt")
                if lbl_path.exists():
                    txt_path = lbl_path

        txt_content = ""
        txt_hash = None
        if txt_path.exists():
            with open(txt_path, "rb") as f:
                raw_bytes = f.read()
                txt_hash = hashlib.md5(raw_bytes).hexdigest()
                txt_content = raw_bytes.decode("utf-8", errors="ignore")

        images[img_hash] = {
            "path": img_path,
            "split": split,
            "stem": img_path.stem,
            "txt_path": txt_path if txt_path.exists() else None,
            "txt_hash": txt_hash,
            "txt_content": txt_content
        }

    return images

def find_orphan_labels(dataset_path: Path, known_stems: set):
    orphans = []
    all_txts = list(dataset_path.glob("**/*.txt"))
    for txt in all_txts:
        if txt.name in ("data.yaml", "README.roboflow.txt"):
            continue
        if txt.stem not in known_stems:
            content = ""
            valid_format = False
            try:
                with open(txt, "r", encoding="utf-8") as f:
                    content = f.read()
                    lines = content.strip().splitlines()
                    if lines:
                        tokens = lines[0].split()
                        if len(tokens) >= 5:
                            valid_format = True
            except Exception:
                pass
            orphans.append({
                "path": txt,
                "content": content,
                "valid": valid_format
            })
    return orphans

def analyze():
    print("============================================================")
    print("    POTHOLE DATASETS CROSS-OVERLAP DEEP AUDIT REPORT")
    print("============================================================\n")

    print("[+] Scanning Dataset 1...")
    d1_imgs = get_image_info(D1_PATH)
    d1_stems = {info["stem"] for info in d1_imgs.values()}
    d1_orphans = find_orphan_labels(D1_PATH, d1_stems)

    print("[+] Scanning Dataset 2...")
    d2_imgs = get_image_info(D2_PATH)
    d2_stems = {info["stem"] for info in d2_imgs.values()}
    d2_orphans = find_orphan_labels(D2_PATH, d2_stems)

    h1_set = set(d1_imgs.keys())
    h2_set = set(d2_imgs.keys())

    shared_hashes = h1_set.intersection(h2_set)
    d1_only_hashes = h1_set - h2_set
    d2_only_hashes = h2_set - h1_set
    union_hashes = h1_set.union(h2_set)

    print("------------------------------------------------------------")
    print(" 1. ANNOTATION BYTE-FOR-BYTE IDENTITY CHECK (DUPLICATE IMAGES)")
    print("------------------------------------------------------------")
    txt_identical = 0
    txt_different = 0

    split_matrix = Counter() # (split1, split2) -> count

    d1_shared_splits = Counter()
    d2_shared_splits = Counter()

    for h in shared_hashes:
        i1 = d1_imgs[h]
        i2 = d2_imgs[h]

        if i1["txt_hash"] == i2["txt_hash"]:
            txt_identical += 1
        else:
            txt_different += 1

        s1 = i1["split"]
        s2 = i2["split"]
        split_matrix[(s1, s2)] += 1
        d1_shared_splits[s1] += 1
        d2_shared_splits[s2] += 1

    print(f"Total Shared Duplicate Images:         {len(shared_hashes)}")
    print(f"Byte-for-Byte Identical Annotations:   {txt_identical}")
    print(f"Differing Annotations:                {txt_different}")
    print()

    print("------------------------------------------------------------")
    print(" 2 & 3. SPLIT BREAKDOWN OF SHARED DUPLICATES")
    print("------------------------------------------------------------")
    print("Dataset 1 Shared Duplicates Split Breakdown:")
    for s, c in d1_shared_splits.items():
        print(f"  - {s}: {c}")

    print("\nDataset 2 Shared Duplicates Split Breakdown:")
    for s, c in d2_shared_splits.items():
        print(f"  - {s}: {c}")
    print()

    print("------------------------------------------------------------")
    print(" 4 & 5. SPLIT BOUNDARY CROSSING & SAME-SPLIT COUNTS")
    print("------------------------------------------------------------")
    same_train = split_matrix[("train", "train")]
    same_valid = split_matrix[("valid", "valid")]
    same_test = split_matrix[("test", "test")]
    same_split_total = same_train + same_valid + same_test

    cross_train_valid = split_matrix[("train", "valid")] + split_matrix[("valid", "train")]
    cross_train_test = split_matrix[("train", "test")] + split_matrix[("test", "train")]
    cross_valid_test = split_matrix[("valid", "test")] + split_matrix[("test", "valid")]
    cross_split_total = cross_train_valid + cross_train_test + cross_valid_test

    print(f"Duplicates Remaining in Same Split:    {same_split_total}")
    print(f"  - train <-> train:                   {same_train}")
    print(f"  - valid <-> valid:                   {same_valid}")
    print(f"  - test  <-> test:                    {same_test}")
    print(f"\nDuplicates Crossing Split Boundaries:  {cross_split_total}")
    print(f"  - train <-> valid:                   {cross_train_valid}")
    print(f"  - train <-> test:                    {cross_train_test}")
    print(f"  - valid <-> test:                    {cross_valid_test}")
    print()

    print("------------------------------------------------------------")
    print(" 6. UNIQUE IMAGES DISTRIBUTION SUMMARY")
    print("------------------------------------------------------------")
    print(f"Dataset 1 Only Unique Images:          {len(d1_only_hashes)}")
    print(f"Dataset 2 Only Unique Images:          {len(d2_only_hashes)}")
    print(f"Shared Duplicate Images:              {len(shared_hashes)}")
    print(f"Total Unique Union Images:             {len(union_hashes)}")
    print()

    print("------------------------------------------------------------")
    print(" 7. ORPHAN LABEL FILES INSPECTION")
    print("------------------------------------------------------------")
    print(f"Dataset 1 Orphan Labels ({len(d1_orphans)}):")
    for o in d1_orphans:
        print(f"  - Path: {o['path']}")
        print(f"    Image Missing: YES")
        print(f"    Valid Annotation Format: {'YES' if o['valid'] else 'NO'}")
        print(f"    Content sample: {repr(o['content'].strip()[:100])}")

    print(f"\nDataset 2 Orphan Labels ({len(d2_orphans)}):")
    for o in d2_orphans:
        print(f"  - Path: {o['path']}")
        print(f"    Image Missing: YES")
        print(f"    Valid Annotation Format: {'YES' if o['valid'] else 'NO'}")
        print(f"    Content sample: {repr(o['content'].strip()[:100])}")
    print()

    print("------------------------------------------------------------")
    print(" 8. CLASS / OBJECT DISTRIBUTIONS FOR UNIQUE IMAGES")
    print("------------------------------------------------------------")

    def count_boxes(hash_set, img_dict):
        class_counts = Counter()
        total_boxes = 0
        for h in hash_set:
            info = img_dict[h]
            if info["txt_content"]:
                for line in info["txt_content"].strip().splitlines():
                    tokens = line.strip().split()
                    if len(tokens) >= 5:
                        try:
                            cls_id = int(tokens[0])
                            class_counts[cls_id] += 1
                            total_boxes += 1
                        except ValueError:
                            pass
        return class_counts, total_boxes

    d1_only_cls, d1_only_total = count_boxes(d1_only_hashes, d1_imgs)
    d2_only_cls, d2_only_total = count_boxes(d2_only_hashes, d2_imgs)
    shared_cls, shared_total = count_boxes(shared_hashes, d1_imgs)
    union_cls, union_total = count_boxes(union_hashes, {**d1_imgs, **d2_imgs})

    print(f"Dataset 1 Only Images ({len(d1_only_hashes)} imgs, {d1_only_total} bboxes):")
    for cid in sorted(CLASS_NAMES.keys()):
        print(f"  - {CLASS_NAMES[cid]} (ID {cid}): {d1_only_cls[cid]}")

    print(f"\nDataset 2 Only Images ({len(d2_only_hashes)} imgs, {d2_only_total} bboxes):")
    for cid in sorted(CLASS_NAMES.keys()):
        print(f"  - {CLASS_NAMES[cid]} (ID {cid}): {d2_only_cls[cid]}")

    print(f"\nShared Images ({len(shared_hashes)} imgs, {shared_total} bboxes):")
    for cid in sorted(CLASS_NAMES.keys()):
        print(f"  - {CLASS_NAMES[cid]} (ID {cid}): {shared_cls[cid]}")

    print(f"\nTotal Union Unique Images ({len(union_hashes)} imgs, {union_total} bboxes):")
    for cid in sorted(CLASS_NAMES.keys()):
        print(f"  - {CLASS_NAMES[cid]} (ID {cid}): {union_cls[cid]}")

    print("\n============================================================")

if __name__ == "__main__":
    analyze()
