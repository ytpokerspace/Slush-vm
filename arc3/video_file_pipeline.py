"""Ordinary video-file ingestion and midpoint forecasting baselines.

Optional dependency: opencv-python (install with: pip install opencv-python).
This module evaluates five-second windows from real video files. It does not train
a neural network; it builds reproducible frame-level evaluation records that can
later become a dataset for a learned temporal model.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def clip_windows(duration_seconds: float, clip_seconds: float = 5.0,
                 stride_seconds: float | None = None) -> list[tuple[float, float]]:
    """Create non-overlapping or strided windows; discard incomplete trailing clips."""
    if duration_seconds < 0 or clip_seconds <= 0:
        raise ValueError("duration must be non-negative and clip_seconds must be positive")
    stride = clip_seconds if stride_seconds is None else stride_seconds
    if stride <= 0:
        raise ValueError("stride_seconds must be positive")
    windows = []
    start = 0.0
    while start + clip_seconds <= duration_seconds + 1e-9:
        windows.append((round(start, 6), round(start + clip_seconds, 6)))
        start += stride
    return windows


def pixel_metrics(predicted: Any, actual: Any) -> dict[str, float | int]:
    """Compare same-sized RGB/gray frames using MAE and exact-pixel agreement."""
    import numpy as np

    p = np.asarray(predicted).astype(np.float32)
    a = np.asarray(actual).astype(np.float32)
    if p.shape != a.shape or p.size == 0:
        raise ValueError("predicted and actual frames must have equal non-empty shapes")
    delta = np.abs(p - a)
    return {
        "mean_absolute_error": float(delta.mean()),
        "normalized_mae": float(delta.mean() / 255.0),
        "exact_pixel_fraction": float((p == a).all(axis=-1).mean()) if p.ndim >= 3 else float((p == a).mean()),
        "pixel_count": int(p.shape[0] * p.shape[1]),
    }


def _require_cv2():
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(
            "Video support requires OpenCV. Install it with: pip install opencv-python"
        ) from exc
    return cv2


def _read_sampled_frames(video_path: str | Path, sample_fps: float,
                         width: int, height: int) -> tuple[list[Any], list[float], dict[str, Any]]:
    cv2 = _require_cv2()
    if sample_fps <= 0 or width <= 0 or height <= 0:
        raise ValueError("sample_fps, width, and height must be positive")
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        raise ValueError(f"could not open video file: {video_path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frame_count / fps if fps > 0 and frame_count > 0 else 0.0
    frames, timestamps = [], []
    if fps > 0:
        source_index = 0
        next_time = 0.0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            timestamp = source_index / fps
            if timestamp + 1e-9 >= next_time:
                resized = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
                frames.append(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))
                timestamps.append(timestamp)
                next_time += 1.0 / sample_fps
            source_index += 1
    capture.release()
    if len(frames) < 2:
        raise ValueError("video must yield at least two sampled frames; check file and FPS metadata")
    actual_duration = duration if duration > 0 else timestamps[-1]
    return frames, timestamps, {
        "path": str(video_path),
        "source_fps": fps,
        "source_frame_count": frame_count,
        "duration_seconds": actual_duration,
        "sampled_frames": len(frames),
        "sample_fps_requested": sample_fps,
        "frame_size": {"width": width, "height": height},
    }


def _forecast_persistence(history: list[Any]) -> Any:
    """Baseline: next frame equals the latest observed frame."""
    return history[-1].copy()


def _forecast_flow(history: list[Any]) -> Any:
    """Dense optical-flow extrapolation from the latest two frames (heuristic)."""
    import numpy as np
    cv2 = _require_cv2()
    if len(history) < 2:
        return _forecast_persistence(history)
    previous = cv2.cvtColor(history[-2], cv2.COLOR_RGB2GRAY)
    current = cv2.cvtColor(history[-1], cv2.COLOR_RGB2GRAY)
    flow = cv2.calcOpticalFlowFarneback(previous, current, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    h, w = current.shape
    x, y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    # Extrapolate one sampled time-step by advecting the current image along flow.
    map_x = x - flow[..., 0]
    map_y = y - flow[..., 1]
    predicted = cv2.remap(history[-1], map_x, map_y, interpolation=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REPLICATE)
    return predicted


def evaluate_video_file(
    video_path: str | Path,
    *,
    clip_seconds: float = 5.0,
    stride_seconds: float = 5.0,
    sample_fps: float = 4.0,
    width: int = 160,
    height: int = 90,
    method: str = "persistence",
) -> dict[str, Any]:
    """Evaluate midpoint forecasts from sampled ordinary video frames.

    The target is the sampled frame nearest each clip's temporal midpoint.
    Forecasts use only samples strictly earlier than the target. The actual
    target frame is held out of the forecast context and used only for scoring.
    """
    if method not in {"persistence", "optical_flow"}:
        raise ValueError("method must be 'persistence' or 'optical_flow'")
    if clip_seconds <= 0 or stride_seconds <= 0:
        raise ValueError("clip_seconds and stride_seconds must be positive")
    frames, timestamps, metadata = _read_sampled_frames(video_path, sample_fps, width, height)
    windows = clip_windows(metadata["duration_seconds"], clip_seconds, stride_seconds)
    records = []
    predictor = _forecast_persistence if method == "persistence" else _forecast_flow
    for clip_index, (start, end) in enumerate(windows):
        indices = [i for i, t in enumerate(timestamps) if start <= t <= end]
        if len(indices) < 2:
            continue
        midpoint = start + clip_seconds / 2.0
        target_index = min(indices, key=lambda i: (abs(timestamps[i] - midpoint), i))
        context_indices = [i for i in indices if timestamps[i] < timestamps[target_index]]
        if not context_indices:
            continue
        predicted = predictor([frames[i] for i in context_indices])
        actual = frames[target_index]
        metrics = pixel_metrics(predicted, actual)
        records.append({
            "clip_index": clip_index,
            "clip_start_seconds": start,
            "clip_end_seconds": end,
            "midpoint_target_seconds": timestamps[target_index],
            "context_frame_count": len(context_indices),
            "context_last_timestamp_seconds": timestamps[context_indices[-1]],
            "prediction_method": method,
            "metrics": metrics,
        })
    return {
        "schema": "ordinary_video_midpoint_eval_v1",
        "video": metadata,
        "settings": {
            "clip_seconds": clip_seconds, "stride_seconds": stride_seconds,
            "sample_fps": sample_fps, "method": method,
        },
        "clips_evaluated": len(records),
        "records": records,
        "aggregate": {
            "mean_absolute_error": (
                sum(r["metrics"]["mean_absolute_error"] for r in records) / len(records)
                if records else None
            ),
            "normalized_mae": (
                sum(r["metrics"]["normalized_mae"] for r in records) / len(records)
                if records else None
            ),
        },
        "limitations": [
            "These are image-level baselines, not a trained video prediction model.",
            "Optical flow is an apparent-motion estimate and can be confused by camera motion, occlusion, blur, and lighting.",
            "Pixel similarity does not measure whether an event or physical explanation is correct.",
            "A five-second clip produces one midpoint evaluation here; future work should also score multiple horizons and event labels.",
        ],
    }



def export_video_dataset(
    video_path: str | Path,
    output_dir: str | Path,
    *,
    clip_seconds: float = 5.0,
    stride_seconds: float = 5.0,
    sample_fps: float = 4.0,
    width: int = 160,
    height: int = 90,
) -> dict[str, Any]:
    """Export sampled frames and future-target manifests; this is not model training."""
    cv2 = _require_cv2()
    import numpy as np

    frames, timestamps, metadata = _read_sampled_frames(video_path, sample_fps, width, height)
    root = Path(output_dir)
    frame_dir = root / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_paths = []
    for index, (frame, timestamp) in enumerate(zip(frames, timestamps)):
        relative = Path("frames") / f"frame_{index:06d}_{timestamp:.3f}s.jpg"
        target_path = root / relative
        if not cv2.imwrite(str(target_path), cv2.cvtColor(np.asarray(frame), cv2.COLOR_RGB2BGR)):
            raise OSError(f"failed to write frame: {target_path}")
        frame_paths.append(relative.as_posix())

    clips = []
    for clip_index, (start, end) in enumerate(clip_windows(metadata["duration_seconds"], clip_seconds, stride_seconds)):
        indices = [i for i, t in enumerate(timestamps) if start <= t <= end]
        if len(indices) < 3:
            continue
        midpoint = start + clip_seconds / 2.0
        target_index = min(indices, key=lambda i: (abs(timestamps[i] - midpoint), i))
        context = [i for i in indices if timestamps[i] < timestamps[target_index]]
        future = [i for i in indices if timestamps[i] > timestamps[target_index]]
        if not context or not future:
            continue
        clips.append({
            "clip_id": f"clip_{clip_index:06d}", "start_seconds": start,
            "end_seconds": end, "midpoint_seconds": timestamps[target_index],
            "context_frames": [frame_paths[i] for i in context],
            "target_frame": frame_paths[target_index],
            "future_frames": [frame_paths[i] for i in future],
            "label_status": "unlabeled_frame_sequence",
        })
    manifest = {
        "schema": "ordinary_video_training_manifest_v1", "source": metadata,
        "sampling": {"clip_seconds": clip_seconds, "stride_seconds": stride_seconds,
                     "sample_fps": sample_fps, "width": width, "height": height},
        "clips": clips,
        "notes": [
            "Unlabeled frame sequences for future training; no semantic event labels are inferred.",
            "Split train/validation/test by source video, not adjacent clips, to reduce leakage.",
            "Review licensing, privacy, and source permissions before training.",
        ],
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"output_dir": str(root), "frames_exported": len(frame_paths),
            "clips_exported": len(clips), "manifest_path": str(root / "manifest.json"),
            "schema": manifest["schema"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", help="path to an ordinary video file (e.g. MP4, MOV, AVI)")
    parser.add_argument("--clip-seconds", type=float, default=5.0)
    parser.add_argument("--stride-seconds", type=float, default=5.0)
    parser.add_argument("--sample-fps", type=float, default=4.0)
    parser.add_argument("--width", type=int, default=160)
    parser.add_argument("--height", type=int, default=90)
    parser.add_argument("--method", choices=("persistence", "optical_flow"), default="persistence")
    parser.add_argument("--output", help="optional path for JSON results")\n    parser.add_argument("--export-dataset", help="export sampled frames and training manifest to this directory")
    args = parser.parse_args()
    if args.export_dataset:
        exported = export_video_dataset(
            args.video, args.export_dataset, clip_seconds=args.clip_seconds,
            stride_seconds=args.stride_seconds, sample_fps=args.sample_fps,
            width=args.width, height=args.height,
        )
        print(json.dumps({"dataset_export": exported}, indent=2, sort_keys=True))
    result = evaluate_video_file(
        args.video, clip_seconds=args.clip_seconds, stride_seconds=args.stride_seconds,
        sample_fps=args.sample_fps, width=args.width, height=args.height, method=args.method,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
