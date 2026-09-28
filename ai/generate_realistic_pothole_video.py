"""
Synthetic Realistic Road, Pothole & Traffic Video Generator.

Produces high-definition 1280x720 @ 30 FPS video sequences simulating a
vehicle driving along an urban municipal road with:
- Asphalt road texture, road markings, and perspective vanishing point.
- Dynamic vehicle traffic (cars, buses, motorcycles) for traffic density estimation.
- Realistic road surface pothole anomalies with perspective scaling and asphalt degradation textures.
- Engineered to trigger the 0.75 pothole threshold and circular buffer incident capture.

Usage:
  python ai/generate_realistic_pothole_video.py --output ai/samples/real_pothole_720p.mp4 --duration 12
"""

import argparse
import math
import os
import random
import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
import cv2
import numpy as np

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "samples", "real_pothole_720p.mp4")


def generate_realistic_pothole_video(
    output_path: str = OUTPUT_PATH,
    duration_sec: float = 12.0,
    fps: int = 30,
    width: int = 1280,
    height: int = 720
):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    total_frames = int(duration_sec * fps)

    print("\n" + "="*70)
    print("🎬 GENERATING REALISTIC 720p POTHOLE & TRAFFIC ROAD VIDEO")
    print(f"Output Path:         {output_path}")
    print(f"Resolution:          {width}x{height} @ {fps} FPS")
    print(f"Total Frames:        {total_frames} ({duration_sec} seconds)")
    print("="*70 + "\n")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, float(fps), (width, height))

    if not writer.isOpened():
        raise RuntimeError(f"Could not open VideoWriter for '{output_path}'")

    # Seed for deterministic visual quality
    random.seed(42)
    np.random.seed(42)

    # Base road asphalt background
    horizon_y = int(height * 0.42)
    road_left_bottom = int(width * 0.08)
    road_right_bottom = int(width * 0.92)
    vanishing_pt = (width // 2, horizon_y)

    # Road texture noise template
    noise_template = np.random.randint(-12, 12, (height, width, 3), dtype=np.int16)

    # Pothole appearance schedule: appears at frame 100, approaches until frame 200
    pothole_1_start = int(3.5 * fps)  # frame ~105
    pothole_1_end = int(7.0 * fps)    # frame ~210

    # Traffic vehicle schedule
    vehicles = [
        {"type": "car", "color": (180, 50, 40), "lane": "left", "start_frame": 10, "speed": 1.2, "y": float(horizon_y + 10)},
        {"type": "bus", "color": (40, 140, 210), "lane": "left", "start_frame": 90, "speed": 0.9, "y": float(horizon_y + 10)},
        {"type": "car", "color": (50, 160, 50), "lane": "right", "start_frame": 150, "speed": 1.4, "y": float(horizon_y + 10)},
        {"type": "motorcycle", "color": (30, 30, 30), "lane": "right", "start_frame": 40, "speed": 1.6, "y": float(horizon_y + 10)}
    ]

    for frame_idx in range(total_frames):
        # 1. Sky & Environment
        frame = np.full((height, width, 3), (190, 160, 130), dtype=np.uint8)  # Distant urban sky
        # Horizon city silhouette
        cv2.rectangle(frame, (0, horizon_y - 40), (width, horizon_y), (140, 120, 110), -1)

        # 2. Road Asphalt Surface (Perspective Trapezoid)
        road_pts = np.array([
            vanishing_pt,
            vanishing_pt,
            [road_right_bottom, height],
            [road_left_bottom, height]
        ], dtype=np.int32)

        road_mask = np.zeros((height, width), dtype=np.uint8)
        cv2.fillPoly(road_mask, [road_pts], 255)

        # Asphalt base color
        asphalt = np.full((height, width, 3), (68, 68, 70), dtype=np.uint8)
        # Apply texture
        asphalt_noisy = np.clip(asphalt.astype(np.int16) + noise_template, 0, 255).astype(np.uint8)
        frame = np.where(road_mask[:, :, None] == 255, asphalt_noisy, frame)

        # Road edges
        cv2.line(frame, vanishing_pt, (road_left_bottom, height), (220, 220, 220), 4)
        cv2.line(frame, vanishing_pt, (road_right_bottom, height), (220, 220, 220), 4)

        # Center Dashed Line (animated with vehicle forward motion)
        dash_offset = (frame_idx * 16) % 120
        for dy in range(horizon_y + 10, height, 50):
            proj_y = dy + dash_offset
            if proj_y >= height or proj_y <= horizon_y:
                continue
            progress = (proj_y - horizon_y) / (height - horizon_y)
            dash_len = int(10 + progress * 40)
            dash_thick = max(1, int(progress * 6))
            cx = width // 2
            cv2.line(frame, (cx, proj_y), (cx, min(height, proj_y + dash_len)), (255, 255, 255), dash_thick)

        # 3. Render Simulated Traffic Vehicles
        for v in vehicles:
            if frame_idx >= v["start_frame"]:
                v_y = v["y"] + (frame_idx - v["start_frame"]) * (v["speed"] * 2.5)
                if horizon_y < v_y < height + 50:
                    v_prog = (v_y - horizon_y) / (height - horizon_y)
                    v_scale = 0.2 + v_prog * 1.8

                    if v["lane"] == "left":
                        vx = int((width // 2) - 60 * v_scale - 120 * v_prog)
                    else:
                        vx = int((width // 2) + 60 * v_scale + 120 * v_prog)

                    if v["type"] == "bus":
                        bw, bh = int(90 * v_scale), int(75 * v_scale)
                        cv2.rectangle(frame, (vx - bw//2, int(v_y - bh)), (vx + bw//2, int(v_y)), v["color"], -1)
                        cv2.rectangle(frame, (vx - bw//2, int(v_y - bh)), (vx + bw//2, int(v_y)), (20, 20, 20), 2)
                        # Bus windshield
                        cv2.rectangle(frame, (vx - bw//2 + 4, int(v_y - bh + 6)), (vx + bw//2 - 4, int(v_y - bh//2)), (200, 220, 230), -1)
                    elif v["type"] == "car":
                        cw, ch = int(70 * v_scale), int(45 * v_scale)
                        cv2.rectangle(frame, (vx - cw//2, int(v_y - ch)), (vx + cw//2, int(v_y)), v["color"], -1)
                        cv2.rectangle(frame, (vx - cw//2, int(v_y - ch)), (vx + cw//2, int(v_y)), (30, 30, 30), 2)
                        # Rear window
                        cv2.rectangle(frame, (vx - cw//2 + 6, int(v_y - ch + 5)), (vx + cw//2 - 6, int(v_y - ch//2)), (50, 50, 50), -1)
                        # Tail lights
                        cv2.circle(frame, (vx - cw//2 + 8, int(v_y - 8)), max(1, int(3*v_scale)), (0, 0, 255), -1)
                        cv2.circle(frame, (vx + cw//2 - 8, int(v_y - 8)), max(1, int(3*v_scale)), (0, 0, 255), -1)
                    elif v["type"] == "motorcycle":
                        mw, mh = int(24 * v_scale), int(35 * v_scale)
                        cv2.rectangle(frame, (vx - mw//2, int(v_y - mh)), (vx + mw//2, int(v_y)), v["color"], -1)
                        cv2.circle(frame, (vx, int(v_y - mh - 6)), max(2, int(5*v_scale)), (100, 100, 220), -1)  # Rider helmet

        # 4. Render Realistic Approaching Pothole Defect
        if pothole_1_start <= frame_idx <= pothole_1_end:
            p_progress = (frame_idx - pothole_1_start) / (pothole_1_end - pothole_1_start)
            # Pothole moves down the driver's lane (center-right)
            py = int(horizon_y + 40 + p_progress * (height - horizon_y - 50))
            px = int((width // 2) + 70 + p_progress * 130)

            # Perspective scale
            p_scale = 0.25 + p_progress * 1.5
            rad_x = int(60 * p_scale)
            rad_y = int(32 * p_scale)

            # Outer cracked asphalt rim
            cv2.ellipse(frame, (px, py), (rad_x + 8, rad_y + 5), 0, 0, 360, (40, 40, 42), -1)
            cv2.ellipse(frame, (px, py), (rad_x + 8, rad_y + 5), 0, 0, 360, (85, 85, 88), 2)

            # Inner deep depression cavity (dark asphalt void)
            cv2.ellipse(frame, (px, py), (rad_x, rad_y), 0, 0, 360, (18, 18, 20), -1)

            # High-contrast asphalt jagged rim highlights
            for angle in range(0, 360, 30):
                rad = math.radians(angle)
                jx = int(px + (rad_x - 3) * math.cos(rad) + random.uniform(-2, 2))
                jy = int(py + (rad_y - 2) * math.sin(rad) + random.uniform(-2, 2))
                cv2.circle(frame, (jx, jy), max(1, int(2 * p_scale)), (120, 120, 125), -1)

            # Internal depth shadow & water reflection patch
            cv2.ellipse(frame, (px + 3, py + 2), (int(rad_x * 0.65), int(rad_y * 0.55)), 0, 0, 360, (10, 10, 12), -1)
            cv2.ellipse(frame, (px - int(rad_x*0.2), py - int(rad_y*0.1)), (int(rad_x * 0.3), int(rad_y * 0.2)), -15, 0, 360, (45, 55, 60), -1)

        writer.write(frame)

        if (frame_idx + 1) % 60 == 0:
            sys.stdout.write(f"\rRendered {frame_idx + 1}/{total_frames} frames ({((frame_idx+1)/total_frames)*100:.1f}%)")
            sys.stdout.flush()

    writer.release()
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n✅ Generated realistic road video: {os.path.abspath(output_path)} ({file_size_mb:.2f} MB)")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Realistic 720p Road & Pothole Video")
    parser.add_argument("--output", type=str, default=OUTPUT_PATH, help="Output .mp4 file path")
    parser.add_argument("--duration", type=float, default=12.0, help="Duration in seconds (default: 12)")
    parser.add_argument("--fps", type=int, default=30, help="FPS (default: 30)")
    args = parser.parse_args()

    generate_realistic_pothole_video(
        output_path=args.output,
        duration_sec=args.duration,
        fps=args.fps
    )
