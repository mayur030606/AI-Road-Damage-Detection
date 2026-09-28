"""
CLI Entry Point for Phase 1 Pothole Detection & Vision Pipeline.
"""

import argparse
import json
import logging
import os
import sys

from ai.aggregator import EventAggregator
from ai.detector import PotholeDetector, DEFAULT_MODEL_PATH
from ai.tracker import DefectTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("Phase1CLI")


def main():
    parser = argparse.ArgumentParser(description="SIH26124 Phase 1 - Pothole AI Detection Prototype")
    parser.add_argument("--source", type=str, required=True, help="Path to input image, video file, or camera index (e.g. 0)")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL_PATH, help="Path to pothole-trained YOLO weights file")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold (0.0 - 1.0)")
    parser.add_argument("--device", type=str, default="cpu", help="Compute device ('cpu', 'cuda', etc.)")
    parser.add_argument("--output-dir", type=str, default="ai_output", help="Directory for output files")
    parser.add_argument("--device-id", type=str, default="BUS-EDGE-001", help="Simulated bus device ID")
    parser.add_argument("--max-frames", type=int, default=None, help="Max video frames to process")

    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    logger.info(f"Initializing Pothole Detector with authentic model '{args.model}' (Conf: {args.conf})...")

    # If model weights do not exist locally, download verified pothole weights
    if not os.path.exists(args.model):
        logger.info(f"Model file '{args.model}' not found locally. Running download_model script...")
        from ai.download_model import download_pothole_model
        download_pothole_model(args.model)

    detector = PotholeDetector(
        model_path=args.model,
        conf_threshold=args.conf,
        device=args.device,
        require_pothole_class=True
    )

    aggregator = EventAggregator(device_id=args.device_id)

    # Determine input type (Image vs Video / Camera)
    source_str = str(args.source)
    source_lower = source_str.lower()
    is_camera = source_str.isdigit()
    is_image = not is_camera and any(source_lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp"])
    is_video = is_camera or any(source_lower.endswith(ext) for ext in [".mp4", ".avi", ".mov", ".mkv"])

    if is_image:
        logger.info(f"Running pothole image inference on '{args.source}'...")
        annotated_save_path = os.path.join(args.output_dir, f"annotated_{os.path.basename(args.source)}")
        
        result = detector.predict_image(
            image_input=args.source,
            conf_threshold=args.conf,
            save_path=annotated_save_path
        )

        events = aggregator.create_events_from_frame(result)
        
        json_save_path = os.path.join(args.output_dir, f"result_{os.path.splitext(os.path.basename(args.source))[0]}.json")
        output_payload = {
            "summary": result.to_dict(),
            "model_path": detector.model_path,
            "model_classes": detector.class_names,
            "aggregated_events": [e.to_dict() for e in events]
        }
        
        with open(json_save_path, "w") as f:
            json.dump(output_payload, f, indent=2)

        print("\n" + "="*60)
        print(f"✅ POTHOLE IMAGE INFERENCE COMPLETE")
        print(f"Model Path: {detector.model_path}")
        print(f"Model Classes (model.names): {detector.class_names}")
        print(f"Source Image: {args.source}")
        print(f"Potholes Detected: {result.detection_count}")
        print(f"Inference Time: {result.inference_time_ms:.1f} ms")
        print(f"Annotated Image Saved: {annotated_save_path}")
        print(f"JSON Result Saved: {json_save_path}")
        print("="*60 + "\n")

    elif is_video:
        logger.info(f"Running video inference with temporal tracking on '{args.source}'...")
        out_filename = "camera_stream" if is_camera else os.path.splitext(os.path.basename(args.source))[0]
        annotated_video_path = os.path.join(args.output_dir, f"annotated_{out_filename}.mp4")
        
        tracker = DefectTracker(iou_match_threshold=0.25, max_lost_frames=5)
        emitted_events = []

        def frame_callback(frame_idx, frame_res):
            newly_closed = tracker.update(frame_res.detections, frame_idx)
            for track in newly_closed:
                evt = aggregator.create_event_from_track(track)
                emitted_events.append(evt)

        summary = detector.predict_video(
            video_path=int(args.source) if is_camera else args.source,
            output_path=annotated_video_path,
            conf_threshold=args.conf,
            max_frames=args.max_frames,
            frame_callback=frame_callback
        )

        final_closed = tracker.flush_remaining_tracks()
        for track in final_closed:
            evt = aggregator.create_event_from_track(track)
            emitted_events.append(evt)

        json_save_path = os.path.join(args.output_dir, f"result_{out_filename}.json")
        output_payload = {
            "video_summary": summary,
            "model_path": detector.model_path,
            "model_classes": detector.class_names,
            "unique_aggregated_events_count": len(emitted_events),
            "aggregated_events": [e.to_dict() for e in emitted_events]
        }

        with open(json_save_path, "w") as f:
            json.dump(output_payload, f, indent=2)

        print("\n" + "="*60)
        print(f"✅ VIDEO POTHOLE INFERENCE COMPLETE")
        print(f"Model Path: {detector.model_path}")
        print(f"Model Classes (model.names): {detector.class_names}")
        print(f"Source Video: {args.source}")
        print(f"Processed Frames: {summary['processed_frames']}")
        print(f"Average FPS: {summary['average_fps']}")
        print(f"Total Detections: {summary['total_detections']}")
        print(f"Unique Aggregated Pothole Events: {len(emitted_events)}")
        print(f"Annotated Video Saved: {annotated_video_path}")
        print(f"JSON Output Saved: {json_save_path}")
        print("="*60 + "\n")

    else:
        logger.error(f"Unsupported source format '{args.source}'. Expected image (.jpg, .png) or video (.mp4, .avi) or camera index (0).")
        sys.exit(1)


if __name__ == "__main__":
    main()
