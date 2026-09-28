"""
Generate a short 2-second test video file for Pothole Video Inference testing.
"""
import os
import cv2
import numpy as np

def generate_sample_video(output_path="sample_video.mp4", duration_sec=2, fps=15):
    height, width = 480, 640
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    total_frames = duration_sec * fps
    for frame_idx in range(total_frames):
        # Road asphalt frame
        img = np.full((height, width, 3), 60, dtype=np.uint8)
        
        # Pothole moves down screen as bus travels
        y_pos = int(100 + frame_idx * 15)
        cv2.ellipse(img, (320, y_pos), (70, 40), 0, 0, 360, (20, 20, 20), -1)
        cv2.ellipse(img, (320, y_pos), (70, 40), 0, 0, 360, (90, 90, 90), 3)

        out.write(img)

    out.release()
    print(f"Generated sample video file: {output_path} ({total_frames} frames)")

if __name__ == "__main__":
    generate_sample_video()
