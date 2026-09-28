"""
READ-ONLY Training Configuration Verification for YOLOv8 data.yaml
Checks path resolution, folder existence, image counts, and class mappings.
Does NOT modify any files or train any model.
"""

import os
import sys
import yaml
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = Path(__file__).resolve().parent.parent
YAML_PATH = ROOT_DIR / "datasets" / "pothole_combined" / "data.yaml"

def verify_yaml():
    print("============================================================")
    print("      READ-ONLY YOLO TRAINING CONFIGURATION VERIFICATION")
    print("============================================================\n")

    # 1. Print complete contents of data.yaml
    print("1. Complete Contents of datasets/pothole_combined/data.yaml:")
    print("------------------------------------------------------------")
    with open(YAML_PATH, "r", encoding="utf-8") as f:
        raw_yaml_text = f.read()
        print(raw_yaml_text.strip())
    print("------------------------------------------------------------\n")

    yaml_cfg = yaml.safe_load(raw_yaml_text)

    # 2. Ultralytics Path Resolution Logic
    print("2. Ultralytics Path Resolution Check:")
    base_path_str = yaml_cfg.get("path", "")
    train_rel = yaml_cfg.get("train", "")
    val_rel = yaml_cfg.get("val", "")
    test_rel = yaml_cfg.get("test", "")

    # Ultralytics resolves relative 'path' relative to current working directory (ROOT_DIR)
    resolved_base = (ROOT_DIR / base_path_str).resolve()
    resolved_train_img = (resolved_base / train_rel).resolve()
    resolved_val_img = (resolved_base / val_rel).resolve()
    resolved_test_img = (resolved_base / test_rel).resolve()

    # Corresponding labels folders
    resolved_train_lbl = resolved_train_img.parent.parent / "labels" / "train"
    resolved_val_lbl = resolved_val_img.parent.parent / "labels" / "val"
    resolved_test_lbl = resolved_test_img.parent.parent / "labels" / "test"

    print(f"   - Specified 'path':  '{base_path_str}'")
    print(f"   - Resolved Base Dir: '{resolved_base}'")
    print(f"   - Resolved Train Img: '{resolved_train_img}'")
    print(f"   - Resolved Val Img:   '{resolved_val_img}'")
    print(f"   - Resolved Test Img:  '{resolved_test_img}'")
    print(f"   - Resolved Train Lbl: '{resolved_train_lbl}'")
    print(f"   - Resolved Val Lbl:   '{resolved_val_lbl}'")
    print(f"   - Resolved Test Lbl:  '{resolved_test_lbl}'\n")

    # 3. Directory Existence Verification
    print("3. Directory Existence Verification:")
    dirs_check = [
        ("train images", resolved_train_img),
        ("val images", resolved_val_img),
        ("test images", resolved_test_img),
        ("train labels", resolved_train_lbl),
        ("val labels", resolved_val_lbl),
        ("test labels", resolved_test_lbl),
    ]

    all_dirs_exist = True
    for name, p in dirs_check:
        exists = p.exists() and p.is_dir()
        if not exists:
            all_dirs_exist = False
        print(f"   - {name:15s} [{str(p)}]: {'EXISTS ✅' if exists else 'MISSING ❌'}")
    print()

    # 4. Image Count Verification
    print("4. Image Count Verification:")
    expected_counts = {"train": 3392, "val": 491, "test": 246}
    actual_counts = {
        "train": len(list(resolved_train_img.glob("*.*"))) if resolved_train_img.exists() else 0,
        "val": len(list(resolved_val_img.glob("*.*"))) if resolved_val_img.exists() else 0,
        "test": len(list(resolved_test_img.glob("*.*"))) if resolved_test_img.exists() else 0,
    }

    counts_match = True
    for split in ["train", "val", "test"]:
        exp = expected_counts[split]
        act = actual_counts[split]
        match = (exp == act)
        if not match:
            counts_match = False
        print(f"   - {split:5s} split: Expected = {exp:4d} | Actual = {act:4d} | Match: {'PASS ✅' if match else 'FAIL ❌'}")
    print()

    # 5. Class Mapping Verification
    print("5. YAML Class Mapping Verification:")
    expected_names = {0: "Drain Hole", 1: "Pothole", 2: "Sewer Cover"}
    actual_names = yaml_cfg.get("names", {})

    mapping_match = (actual_names == expected_names)
    print(f"   - Expected Mapping: {expected_names}")
    print(f"   - Actual Mapping:   {actual_names}")
    print(f"   - Mapping Result:   {'PASS ✅' if mapping_match else 'FAIL ❌'}\n")

    # 6. Overall Evaluation & Path Correctness Report
    print("6. Path Correctness & Final Verdict:")
    if resolved_base.exists() and all_dirs_exist and counts_match and mapping_match:
        print("   ✅ VERDICT: data.yaml training configuration is 100% CORRECT and ready for Ultralytics YOLOv8!")
    else:
        print("   ⚠️ VERDICT: Configuration issue detected:")
        if not resolved_base.exists():
            print(f"      - Base path '{resolved_base}' does not exist.")
        if not all_dirs_exist:
            print("      - One or more image/label directories are missing.")
        if not counts_match:
            print(f"      - Image counts mismatch: Expected {expected_counts}, got {actual_counts}")
        if not mapping_match:
            print(f"      - Class mapping mismatch.")

    print("\n============================================================")

if __name__ == "__main__":
    verify_yaml()
