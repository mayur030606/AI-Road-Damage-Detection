"""
Road Footage Capture Tool for Raspberry Pi 4 / 5 CSI Camera Module.

Supports:
1. Native Raspberry Pi Hardware Recorder (rpicam-vid / libcamera-vid)
   - Zero-overhead, hardware H.264 encoding via Raspberry Pi GPU/ISP.
2. Python Picamera2 / OpenCV CameraStream (frame-by-frame)
   - Works inside virtual environments (source env/bin/activate).

Usage:
  # Record 60-second road footage with the CSI camera:
  python ai/record_road_footage.py --output /home/pi/my_road_footage.mp4 --duration 60 --fps 30

  # Record continuously until Ctrl+C:
  python ai/record_road_footage.py --output /home/pi/my_road_footage.mp4

  # Record and immediately process through AI detection pipeline:
  python ai/record_road_footage.py --output /home/pi/test_clip.mp4 --duration 15 --auto-detect
"""

import argparse
import datetime
import logging
import os
import shutil
import subprocess
import sys
import time
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import cv2
import numpy as np

from ai.detector import CameraStream

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [RECORDER] %(message)s"
)
logger = logging.getLogger("RoadRecorder")


def record_with_rpicam_vid(
    output_path: str,
    duration_seconds: Optional[float] = None,
    width: int = 1280,
    height: int = 720,
    fps: int = 30
) -> bool:
    """
    Record road footage using official Raspberry Pi hardware-accelerated utility.
    Prefers rpicam-vid (Bookworm) or libcamera-vid (Bullseye).
    """
    cmd_name = shutil.which("rpicam-vid") or shutil.which("libcamera-vid")
    if not cmd_name:
        return False

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    duration_ms = int(duration_seconds * 1000) if duration_seconds and duration_seconds > 0 else 0

    print("\n" + "="*70)
    print(f"🎥 RECORDING VIA NATIVE RASPBERRY PI HARDWARE ENCODER ({os.path.basename(cmd_name)})")
    print(f"Output File:         {output_path}")
    print(f"Resolution:          {width}x{height} @ {fps} FPS")
    print(f"Duration:            {'Continuous (Press Ctrl+C to stop)' if duration_ms == 0 else f'{duration_seconds}s'}")
    print(f"Hardware Controls:   Native Hardware AEC / AWB Active")
    print("="*70 + "\n")

    # Command parameters for native MP4 container
    # -t 0 means record until Ctrl+C, --inline adds SPS/PPS headers
    cmd = [
        cmd_name,
        "-t", str(duration_ms),
        "--width", str(width),
        "--height", str(height),
        "--framerate", str(fps),
        "-o", output_path,
        "--codec", "libav",
        "--libav-format", "mp4"
    ]

    try:
        proc = subprocess.run(cmd, check=False)
        if proc.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
            file_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"\n✅ Hardware capture successful: {output_path} ({file_mb:.2f} MB)\n")
            return True
        else:
            # Fallback to standard H.264 stream and wrap into MP4
            logger.warning("libav mp4 direct write not supported, falling back to raw H.264 + ffmpeg wrap...")
            raw_h264 = output_path + ".h264"
            cmd_fallback = [
                cmd_name,
                "-t", str(duration_ms),
                "--width", str(width),
                "--height", str(height),
                "--framerate", str(fps),
                "-o", raw_h264,
                "--inline"
            ]
            proc2 = subprocess.run(cmd_fallback, check=False)
            if proc2.returncode == 0 and os.path.exists(raw_h264) and os.path.getsize(raw_h264) > 1024:
                # Wrap to MP4 using ffmpeg if available
                ffmpeg_bin = shutil.which("ffmpeg")
                if ffmpeg_bin:
                    subprocess.run([ffmpeg_bin, "-y", "-i", raw_h264, "-c", "copy", output_path], check=False)
                    if os.path.exists(raw_h264):
                        os.remove(raw_h264)
                    return True
                else:
                    # Rename to .h264
                    print(f"\n✅ Raw H.264 captured: {raw_h264}\n")
                    return True
    except KeyboardInterrupt:
        print("\nRecording stopped by user.")
        return os.path.exists(output_path)
    except Exception as e:
        logger.warning(f"rpicam-vid execution failed: {e}")

    return False


def record_with_python_stream(
    output_path: str,
    duration_seconds: Optional[float] = None,
    source: str = "0",
    width: int = 1280,
    height: int = 720,
    fps: int = 30
) -> str:
    """Record road footage via Python Picamera2 or OpenCV CameraStream."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    print("\n" + "="*70)
    print("🎥 RECORDING VIA PYTHON CAMERA STREAM (Picamera2 / OpenCV)")
    print(f"Output File:         {output_path}")
    print(f"Target Resolution:   {width}x{height} @ {fps} FPS")
    print(f"Duration:            {'Continuous (Press Ctrl+C to stop)' if duration_seconds is None else f'{duration_seconds}s'}")
    print("="*70 + "\n")

    try:
        cam = CameraStream(
            source=source,
            width=width,
            height=height,
            fps=fps,
            enable_aec=True,
            enable_awb=True
        )
    except Exception as e:
        logger.error(f"Failed to initialize camera: {e}")
        print("\n" + "!"*70)
        print("❌ CAMERA INITIALIZATION FAILED")
        print("Troubleshooting steps:")
        print("1. If 'infra_monitor' service is running, stop it to free the camera:")
        print("     sudo systemctl stop infra_monitor")
        print("2. Ensure system packages are visible in your virtual environment:")
        print("     echo 'include-system-site-packages = true' >> env/pyvenv.cfg")
        print("3. Verify the camera hardware is detected by the OS:")
        print("     rpicam-hello --list-cameras")
        print("4. Test hardware preview:")
        print("     rpicam-hello -t 5000")
        print("!"*70 + "\n")
        raise

    time.sleep(1.0)  # Allow AEC/AWB hardware settling time

    # Open VideoWriter with fallback codecs
    writer = None
    for fourcc_str in ("mp4v", "avc1", "MJPG", "XVID"):
        try:
            fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
            w = cv2.VideoWriter(output_path, fourcc, float(fps), (width, height))
            if w.isOpened():
                writer = w
                logger.info(f"Opened VideoWriter with codec '{fourcc_str}'.")
                break
        except Exception:
            continue

    if writer is None or not writer.isOpened():
        cam.release()
        raise RuntimeError(f"Could not open VideoWriter for '{output_path}'. Ensure openh264 or ffmpeg is installed.")

    frame_count = 0
    consecutive_failures = 0
    start_time = time.time()
    max_frames = int(duration_seconds * fps) if duration_seconds else None

    logger.info("Recording active... Press Ctrl+C to finish.")

    try:
        while True:
            ret, frame = cam.read_frame()
            if not ret or frame is None:
                consecutive_failures += 1
                if consecutive_failures > 60:
                    logger.error("Camera stopped producing frames for >2 seconds.")
                    break
                time.sleep(0.01)
                continue

            consecutive_failures = 0
            writer.write(frame)
            frame_count += 1

            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                current_fps = frame_count / elapsed if elapsed > 0 else 0.0
                sys.stdout.write(f"\rCaptured: {frame_count:5d} frames | Elapsed: {elapsed:5.1f}s | Real-time FPS: {current_fps:4.1f}")
                sys.stdout.flush()

            if max_frames and frame_count >= max_frames:
                break

    except KeyboardInterrupt:
        print("\nRecording stopped by user.")
    finally:
        writer.release()
        cam.release()

    total_time = time.time() - start_time
    avg_fps = frame_count / total_time if total_time > 0 else 0.0
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024) if os.path.exists(output_path) else 0.0

    print(f"\n\n✅ Video recording saved to: {os.path.abspath(output_path)}")
    print(f"Total Frames: {frame_count} | Duration: {total_time:.1f}s | Avg FPS: {avg_fps:.1f} | Size: {file_size_mb:.2f} MB\n")
    return output_path


def record_footage(
    output_path: str,
    duration_seconds: Optional[float] = None,
    source: str = "0",
    width: int = 1280,
    height: int = 720,
    fps: int = 30,
    backend: str = "auto"
) -> str:
    """
    Unified road footage recorder.
    Attempts native hardware recorder (rpicam-vid) first on Raspberry Pi,
    falling back to Python Picamera2 / OpenCV.
    """
    if backend in ("auto", "rpicam") and sys.platform.startswith("linux") and source in ("0", 0, "csi"):
        success = record_with_rpicam_vid(
            output_path=output_path,
            duration_seconds=duration_seconds,
            width=width,
            height=height,
            fps=fps
        )
        if success:
            return output_path
        logger.info("Hardware recorder unavailable or returned error, switching to Python stream capture...")

    return record_with_python_stream(
        output_path=output_path,
        duration_seconds=duration_seconds,
        source=source,
        width=width,
        height=height,
        fps=fps
    )


def main():
    parser = argparse.ArgumentParser(description="Record Road Footage using Raspberry Pi Camera Module")
    parser.add_argument("--output", type=str, default=None, help="Destination .mp4 file path")
    parser.add_argument("--duration", type=float, default=None, help="Recording duration in seconds (e.g. 60)")
    parser.add_argument("--source", type=str, default="0", help="Camera source: '0', 'csi', or device index")
    parser.add_argument("--width", type=int, default=1280, help="Video width (default: 1280)")
    parser.add_argument("--height", type=int, default=720, help="Video height (default: 720)")
    parser.add_argument("--fps", type=int, default=30, help="Target FPS (default: 30)")
    parser.add_argument("--backend", choices=["auto", "rpicam", "python"], default="auto", help="Capture backend")
    parser.add_argument("--auto-detect", action="store_true", help="Automatically run detector on saved video")
    args = parser.parse_args()

    if args.output is None:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = os.path.join("ai", "samples", f"road_capture_{ts}.mp4")

    out_file = record_footage(
        output_path=args.output,
        duration_seconds=args.duration,
        source=args.source,
        width=args.width,
        height=args.height,
        fps=args.fps,
        backend=args.backend
    )

    if args.auto_detect:
        logger.info(f"Auto-detect requested. Launching Edge Perception Pipeline on '{out_file}'...")
        from ai.detector import EdgePerceptionPipeline
        pipeline = EdgePerceptionPipeline(
            camera_source=out_file,
            resolution=(args.width, args.height),
            fps=args.fps,
            pothole_conf=0.75
        )
        pipeline.run()


if __name__ == "__main__":
    main()
