"""
Generate a test road surface image for Pothole Model inference verification.
"""
import os
import cv2
import numpy as np

def generate_sample_image(output_path="sample_pothole_road.jpg"):
    height, width = 640, 640
    # Asphalt road background texture
    img = np.full((height, width, 3), 60, dtype=np.uint8)
    noise = np.random.randint(-15, 15, (height, width, 3), dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    
    # White lane divider markings
    for y in range(0, height, 90):
        cv2.rectangle(img, (315, y), (325, y + 45), (240, 240, 240), -1)

    # Large dark pothole crater
    center = (260, 380)
    axes = (85, 55)
    cv2.ellipse(img, center, axes, -10, 0, 360, (25, 25, 25), -1)
    cv2.ellipse(img, center, axes, -10, 0, 360, (90, 90, 90), 4)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    cv2.imwrite(output_path, img)
    print(f"Generated test road image at: {output_path}")

if __name__ == "__main__":
    generate_sample_image()
