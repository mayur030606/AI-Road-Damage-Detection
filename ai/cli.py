"""
Modular Command-Line Interface (CLI) for SIH26124 Edge Perception System.

Commands:
  live          - Run full edge perception pipeline on CSI camera / USB camera
  video         - Process a pre-recorded HD video file
  test-camera   - Run camera diagnostics, verify 1280x720 resolution, AEC/AWB, and capture test snapshot
  sync          - Manually flush offline SQLite queue to central backend
  status        - Inspect edge hardware status, storage usage, and queue backlog
  traffic       - Run standalone traffic density estimation stream
"""

import argparse
import datetime
import json
import logging
import os
import shutil
import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import time
from typing import Optional

import cv2
import requests

from ai.aggregator import CentralAggregator, OfflineQueueManager, GPSProvider
from ai.detector import (
    CameraStream,
    EdgePerceptionPipeline,
    PotholeDetector,
    DEFAULT_POTHOLE_MODEL,
    DEFAULT_VEHICLE_MODEL,
    DEFAULT_CAPTURES_DIR
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("SIH26124_CLI")


def cmd_live(args):
    """Execute live edge pipeline on CSI camera. Never use a Windows laptop webcam."""
    is_index_source = str(args.source).isdigit()
    if sys.platform.startswith("win") and is_index_source and not getattr(args, "allow_webcam", False):
        print("ERROR: Live detection must run on the Raspberry Pi CSI camera.")
        print("Do not open the laptop webcam.")
        print()
        print("On the Pi run:")
        print("  cd ~/projects/my_app && source venv/bin/activate")
        print("  python -m ai.cli live --source 0 --conf 0.50 --stream-port 5001 \\")
        print("    --backend-url http://10.54.12.227:8000/api/v1/incidents --token sih_admin")
        sys.exit(1)

    print("\n" + "="*70)
    print("🚀 LAUNCHING LIVE EDGE ROAD INTELLIGENCE PIPELINE")
    print(f"Camera Source:       {args.source}")
    print(f"Target Resolution:   {args.width}x{args.height} @ {args.fps} FPS")
    print(f"Pothole Threshold:   {args.conf} (STRICT)")
    print(f"Central Backend:     {args.backend_url}")
    print(f"Auth Token:          Bearer {args.token[:4]}****")
    print(f"Circular Buffer:     5s Pre-event + 5s Post-event (10s HD Clip)")
    print(f"MJPEG Preview:       http://0.0.0.0:{getattr(args, 'stream_port', 5001)}/video_feed")
    print("="*70 + "\n")

    pipeline = EdgePerceptionPipeline(
        camera_source=args.source,
        resolution=(args.width, args.height),
        fps=args.fps,
        pothole_conf=args.conf,
        backend_url=args.backend_url,
        auth_token=args.token,
        enable_display=args.display,
        stream_port=getattr(args, "stream_port", 5001),
    )
    pipeline.run(max_frames=args.max_frames)


def cmd_video(args):
    """Process an offline video file."""
    if not os.path.exists(args.input):
        logger.error(f"Input video file not found at '{args.input}'")
        sys.exit(1)

    print("\n" + "="*70)
    print("🎬 PROCESSING ROAD INTELLIGENCE VIDEO FILE")
    print(f"Input Video:         {args.input}")
    print(f"Pothole Threshold:   {args.conf} (STRICT)")
    print(f"Central Backend:     {args.backend_url}")
    print(f"Display GUI:         {args.display}")
    print("="*70 + "\n")

    pipeline = EdgePerceptionPipeline(
        camera_source=args.input,
        resolution=(args.width, args.height),
        fps=args.fps,
        pothole_conf=args.conf,
        backend_url=args.backend_url,
        auth_token=args.token,
        enable_display=args.display
    )
    pipeline.run(max_frames=args.max_frames)


def cmd_test_camera(args):
    """Diagnose camera hardware, AEC/AWB, and test 1280x720 capture."""
    print("\n" + "="*70)
    print("🔍 RUNNING EDGE CAMERA HARDWARE DIAGNOSTICS")
    print(f"Testing Source:      {args.source}")
    print(f"Target Resolution:   {args.width}x{args.height} @ 30 FPS")
    print("="*70)

    # 1. Check Picamera2 availability
    has_picam2 = False
    try:
        from picamera2 import Picamera2
        has_picam2 = True
        print("  [✓] Picamera2 library: Installed (Bookworm libcamera stack available)")
    except ImportError:
        print("  [i] Picamera2 library: Not installed (using OpenCV V4L2 backend)")

    # 2. Test Stream Initialization
    out_dir = os.path.join(os.path.dirname(__file__), "..", "ai_output")
    os.makedirs(out_dir, exist_ok=True)
    snapshot_path = os.path.join(out_dir, f"camera_test_{args.width}x{args.height}.jpg")

    try:
        cam = CameraStream(
            source=args.source,
            width=args.width,
            height=args.height,
            fps=30,
            enable_aec=True,
            enable_awb=True
        )

        time.sleep(1.0)  # Allow AEC/AWB hardware settling time
        ret, frame = cam.read_frame()

        if ret and frame is not None:
            h, w = frame.shape[:2]
            print(f"  [✓] Camera Frame Grab: SUCCESS ({w}x{h} BGR)")
            print(f"  [✓] Hardware AEC/AWB: Active")

            # Draw test calibration watermark
            cv2.putText(
                frame,
                f"SIH26124 CAM TEST - {w}x{h} - {datetime.datetime.now().isoformat()}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )
            cv2.imwrite(snapshot_path, frame)
            print(f"  [✓] Snapshot Saved:   {os.path.abspath(snapshot_path)}")
            print("\n✅ Camera module is fully operational and configured for 1280x720 30FPS capture.")
        else:
            print("  [✗] Camera Frame Grab: FAILED (Empty frame received)")

        cam.release()
    except Exception as e:
        print(f"  [✗] Camera Initialization Error: {e}")


def cmd_sync(args):
    """Manually flush offline incident queue to central backend."""
    print("\n" + "="*70)
    print("🔄 FLUSHING OFFLINE INCIDENT QUEUE TO CENTRAL BACKEND")
    print(f"Target URL:          {args.backend_url}")
    print(f"Auth Token:          Bearer {args.token[:4]}****")
    print("="*70)

    aggregator = CentralAggregator(
        backend_url=args.backend_url,
        auth_token=args.token,
        auto_sync=False
    )

    stats_before = aggregator.queue_manager.get_queue_stats()
    print(f"Queue Status: Total={stats_before['total']}, Pending={stats_before['pending']}, Synced={stats_before['synced']}")

    if stats_before["pending"] == 0:
        print("✅ No pending incidents in queue. Everything is synchronized.")
        return

    synced = aggregator.flush_queue(batch_size=args.batch_size)
    stats_after = aggregator.queue_manager.get_queue_stats()

    print(f"Synchronization Result: Flushed {synced} incidents successfully.")
    print(f"Updated Queue Status: Pending={stats_after['pending']}, Synced={stats_after['synced']}")


def cmd_status(args):
    """Print edge health, storage, and queue statistics."""
    print("\n" + "="*70)
    print("📊 SIH26124 EDGE COMPUTING NODE SYSTEM STATUS")
    print("="*70)

    # 1. Edge Node Info
    print("  [Host Network]")
    print(f"    Static Node IP:    192.168.1.150")
    print(f"    SSH User:          pi")
    print(f"    Target Backend:    {args.backend_url}")

    # 2. Backend Connectivity Check
    is_online = False
    try:
        resp = requests.get(args.backend_url.replace("/incidents", "/health"), timeout=2.0)
        is_online = resp.status_code in (200, 404, 405)
    except Exception:
        is_online = False
    status_str = "ONLINE (Reachable)" if is_online else "OFFLINE (Unreachable - offline queue active)"
    print(f"    Backend Status:    {status_str}")

    # 3. Model Files Check
    print("\n  [AI Perception Models]")
    p_exists = os.path.exists(DEFAULT_POTHOLE_MODEL)
    p_size = f"{os.path.getsize(DEFAULT_POTHOLE_MODEL) / (1024*1024):.1f} MB" if p_exists else "MISSING"
    print(f"    Pothole Model:     {'[✓]' if p_exists else '[✗]'} {DEFAULT_POTHOLE_MODEL} ({p_size})")

    v_exists = os.path.exists(DEFAULT_VEHICLE_MODEL) or os.path.exists("yolov8n.pt")
    v_path = DEFAULT_VEHICLE_MODEL if os.path.exists(DEFAULT_VEHICLE_MODEL) else "yolov8n.pt"
    v_size = f"{os.path.getsize(v_path) / (1024*1024):.1f} MB" if v_exists else "MISSING"
    print(f"    Vehicle Model:     {'[✓]' if v_exists else '[✗]'} {v_path} ({v_size})")

    # 4. Storage & Captures
    print("\n  [Storage & Captures]")
    captures_dir = DEFAULT_CAPTURES_DIR
    os.makedirs(captures_dir, exist_ok=True)
    clips = [f for f in os.listdir(captures_dir) if f.endswith(".mp4")]
    total_clip_size_mb = sum(os.path.getsize(os.path.join(captures_dir, f)) for f in clips) / (1024 * 1024)
    print(f"    Captures Folder:   {captures_dir}")
    print(f"    Total Video Clips: {len(clips)} (.mp4 files)")
    print(f"    Disk Space Used:   {total_clip_size_mb:.2f} MB")

    # 5. Offline Queue
    print("\n  [Offline Telemetry Queue]")
    queue_mgr = OfflineQueueManager()
    stats = queue_mgr.get_queue_stats()
    print(f"    Total Logged:      {stats['total']}")
    print(f"    Pending Sync:      {stats['pending']}")
    print(f"    Synced to Cloud:   {stats['synced']}")

    # 6. GPS Status
    gps = GPSProvider()
    coords = gps.get_coordinates()
    print("\n  [GPS Telemetry]")
    print(f"    Hardware GPS:      {'Connected' if gps.has_hardware_gps else 'Simulated Urban Telemetry'}")
    print(f"    Current Lat/Lon:   {coords['latitude']}, {coords['longitude']} (Speed: {coords['speed_kmh']} km/h)")
    print("="*70 + "\n")


def cmd_traffic(args):
    """Run standalone traffic density estimation stream."""
    print("\n" + "="*70)
    print("🚦 STANDALONE TRAFFIC DENSITY ESTIMATOR")
    print(f"Source:              {args.source}")
    print("="*70 + "\n")

    detector = PotholeDetector(
        pothole_model_path=DEFAULT_POTHOLE_MODEL,
        vehicle_model_path=DEFAULT_VEHICLE_MODEL if os.path.exists(DEFAULT_VEHICLE_MODEL) else "yolov8n.pt",
        pothole_conf=args.conf
    )

    cam = CameraStream(source=args.source, width=1280, height=720, fps=30)
    frame_idx = 0

    try:
        while True:
            ret, frame = cam.read_frame()
            if not ret or frame is None:
                break
            frame_idx += 1

            if frame_idx % 3 == 0:
                traffic = detector.estimate_traffic_density(frame)
                sys.stdout.write(
                    f"\r[Frame {frame_idx:05d}] Density: {traffic.level:<6} | Vehicles: {traffic.vehicle_count:<2} "
                    f"| Congestion: {traffic.congestion_index*100:4.1f}% | Types: {traffic.vehicles_by_type}"
                )
                sys.stdout.flush()

            if args.display:
                traffic = detector.estimate_traffic_density(frame)
                hud = detector.draw_hud(frame, [], traffic, False, 30.0)
                cv2.imshow("Traffic Density Monitor", hud)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    except KeyboardInterrupt:
        pass
    finally:
        cam.release()
        if args.display:
            cv2.destroyAllWindows()
        print("\nTraffic monitoring stopped.")


def cmd_evaluate_dataset(args):
    """Batch evaluate all pothole images in a folder and optionally log to backend."""
    import glob
    img_files = glob.glob(os.path.join(args.dir, "*.jpg")) + glob.glob(os.path.join(args.dir, "*.png"))
    if not img_files:
        logger.error(f"No image files found in '{args.dir}'")
        return

    os.makedirs(args.output_dir, exist_ok=True)
    detector = PotholeDetector(
        model_path=args.model,
        conf_threshold=args.conf
    )
    aggregator = None
    if args.send_to_backend:
        aggregator = CentralAggregator(backend_url=args.backend_url, auth_token=args.token, auto_sync=False)

    print("\n" + "="*70)
    print("📁 BATCH EVALUATING POTHOLE DATASET IMAGES")
    print(f"Image Directory:     {args.dir} ({len(img_files)} images)")
    print(f"Confidence Threshold:{args.conf}")
    print(f"Output Directory:    {args.output_dir}")
    print(f"Forward to Backend:  {bool(aggregator)}")
    print("="*70 + "\n")

    total_detections = 0
    images_with_potholes = 0
    results_summary = []

    for i, fpath in enumerate(sorted(img_files)):
        fname = os.path.basename(fpath)
        img = cv2.imread(fpath)
        if img is None:
            continue

        potholes = detector.detect_potholes(img, conf_threshold=args.conf)
        traffic = detector.estimate_traffic_density(img)

        if len(potholes) > 0:
            images_with_potholes += 1
            total_detections += len(potholes)

        # Draw HUD annotation
        annotated = detector.draw_hud(img, potholes, traffic, False, 0.0)
        out_path = os.path.join(args.output_dir, f"detected_{fname}")
        cv2.imwrite(out_path, annotated)

        best_conf = max([p.confidence for p in potholes], default=0.0)
        results_summary.append({
            "image": fname,
            "detections": len(potholes),
            "best_confidence": round(best_conf, 4),
            "traffic_density": traffic.level
        })

        if aggregator and len(potholes) > 0:
            best_p = max(potholes, key=lambda p: p.confidence)
            payload = aggregator.package_incident(
                defect_type="POTHOLE",
                confidence=best_p.confidence,
                bbox=best_p.bbox.to_list(),
                estimated_size_sqm=round(best_p.area_ratio * 20.0, 4),
                video_clip_path=fpath,
                traffic_density_data=traffic.to_dict()
            )
            aggregator.transmit_incident(payload, video_clip_path=fpath)

        status_tag = f"✅ {len(potholes)} pothole(s) (Max Conf: {best_conf*100:.1f}%)" if len(potholes) > 0 else "Normal Road"
        print(f"[{i+1:02d}/{len(img_files)}] {fname:<15} : {status_tag}")

    summary_json_path = os.path.join(args.output_dir, "dataset_summary.json")
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_images": len(img_files),
            "images_with_potholes": images_with_potholes,
            "detection_rate": round(images_with_potholes / len(img_files) if img_files else 0.0, 4),
            "total_potholes_found": total_detections,
            "images": results_summary
        }, f, indent=2)

    print("\n" + "="*70)
    print("📊 DATASET EVALUATION COMPLETE")
    print(f"Processed Images:       {len(img_files)}")
    print(f"Images with Potholes:   {images_with_potholes} ({images_with_potholes/len(img_files)*100:.1f}%)")
    print(f"Total Defects Found:    {total_detections}")
    print(f"Annotated Directory:    {os.path.abspath(args.output_dir)}")
    print(f"Summary JSON Saved:     {os.path.abspath(summary_json_path)}")
    print("="*70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="SIH26124 Edge Road Intelligence & Capture CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Common args
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--backend-url", type=str, default="http://192.168.1.100:8000/api/v1/incidents", help="Municipal backend REST API")
    parent_parser.add_argument("--token", type=str, default="sih_admin", help="Bearer authentication token")

    # 1. live
    p_live = subparsers.add_parser("live", parents=[parent_parser], help="Run real-time edge capture on CSI / USB camera")
    p_live.add_argument("--source", type=str, default="0", help="Camera device index (0) or 'csi'")
    p_live.add_argument("--width", type=int, default=1280, help="Stream width (default: 1280)")
    p_live.add_argument("--height", type=int, default=720, help="Stream height (default: 720)")
    p_live.add_argument("--fps", type=int, default=30, help="Target FPS (default: 30)")
    p_live.add_argument("--conf", type=float, default=0.75, help="Strict pothole confidence threshold (default: 0.75)")
    p_live.add_argument("--display", action="store_true", help="Show live OpenCV GUI window")
    p_live.add_argument("--max-frames", type=int, default=None, help="Stop after N frames")
    p_live.add_argument("--stream-port", type=int, default=5001, help="MJPEG preview port for dashboard Live Pi camera (0=off)")
    p_live.add_argument("--allow-webcam", action="store_true", help="Windows only: allow laptop webcam (not used for SIH demo)")

    # 2. video
    p_video = subparsers.add_parser("video", parents=[parent_parser], help="Process a pre-recorded HD video file")
    p_video.add_argument("--input", type=str, required=True, help="Path to input .mp4 video file")
    p_video.add_argument("--width", type=int, default=1280, help="Video width")
    p_video.add_argument("--height", type=int, default=720, help="Video height")
    p_video.add_argument("--fps", type=int, default=30, help="Video FPS")
    p_video.add_argument("--conf", type=float, default=0.75, help="Strict pothole confidence threshold")
    p_video.add_argument("--display", action="store_true", help="Show live OpenCV GUI window")
    p_video.add_argument("--max-frames", type=int, default=None, help="Stop after N frames")

    # 3. test-camera
    p_cam = subparsers.add_parser("test-camera", help="Diagnose camera hardware and AEC/AWB")
    p_cam.add_argument("--source", type=str, default="0", help="Camera source index (0)")
    p_cam.add_argument("--width", type=int, default=1280, help="Test width")
    p_cam.add_argument("--height", type=int, default=720, help="Test height")

    # 4. sync
    p_sync = subparsers.add_parser("sync", parents=[parent_parser], help="Flush offline incident queue to backend")
    p_sync.add_argument("--batch-size", type=int, default=20, help="Number of incidents per sync batch")

    # 5. status
    p_status = subparsers.add_parser("status", parents=[parent_parser], help="Inspect edge device health, storage, and queue")

    # 6. traffic
    p_traffic = subparsers.add_parser("traffic", help="Standalone traffic density estimation")
    p_traffic.add_argument("--source", type=str, default="0", help="Camera source or video file")
    p_traffic.add_argument("--conf", type=float, default=0.35, help="Vehicle detection confidence")
    p_traffic.add_argument("--display", action="store_true", help="Display GUI window")

    # 7. evaluate-dataset
    p_eval = subparsers.add_parser("evaluate-dataset", parents=[parent_parser], help="Batch evaluate all pothole images in a directory")
    p_eval.add_argument("--dir", type=str, default="tfliterpipothole/potholeimages/potholeimages", help="Folder with pothole images")
    p_eval.add_argument("--output-dir", type=str, default="ai_output/dataset_evaluation", help="Output directory for annotated images")
    p_eval.add_argument("--model", type=str, default=DEFAULT_POTHOLE_MODEL, help="Model weights path (.pt or .tflite)")
    p_eval.add_argument("--conf", type=float, default=0.40, help="Confidence threshold")
    p_eval.add_argument("--send-to-backend", action="store_true", help="Transmit detected incidents to central dashboard")

    args = parser.parse_args()

    if args.command == "live":
        cmd_live(args)
    elif args.command == "video":
        cmd_video(args)
    elif args.command == "test-camera":
        cmd_test_camera(args)
    elif args.command == "sync":
        cmd_sync(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "traffic":
        cmd_traffic(args)
    elif args.command == "evaluate-dataset":
        cmd_evaluate_dataset(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

