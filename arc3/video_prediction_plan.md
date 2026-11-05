# Physics-Informed Video Prediction Roadmap

## Goal
Given earlier frames, predict plausible future frames and physical events, then evaluate predictions against held-out future observations. The system must separate observed evidence, estimated state, hypotheses, and verified outcomes.

## Current implemented pieces
- `video_file_pipeline.py`: samples ordinary video files, scores persistence and optical-flow midpoint baselines, and exports frame/clip manifests. It does not train a model.
- `object_perception.py` / `object_tracker.py`: basic grid-oriented component perception and tracking scaffolds; not a robust general-purpose skateboard detector.
- `physics_forecast.py`: takes externally supplied object-center tracks and generates constant-velocity and acceleration-based trajectory hypotheses, with optional simplified ground-contact hypothesis. It does not detect objects or render future images.
- `temporal_video.py`: evaluates discrete grid sequences, not natural RGB footage.

## Architecture stages

### 1. Video normalization
Decode frames with timestamps, preserve source-video identity, record frame rate/resolution, and optionally estimate camera motion. Never mix frames from one source video across train and test splits.

### 2. Visual state estimation
Detect and track the skater, skateboard, ramp/ground boundaries, and other relevant objects. Store bounding boxes or masks, keypoints, object confidence, occlusion state, and track IDs. Keep uncertainty explicit. A human-reviewed subset should validate detector and tracker quality before using tracks as training truth.

### 3. Coordinate and physical-state estimation
Estimate image-space position and velocity first. If camera calibration and ground-plane information are available, transform to approximate world coordinates. Infer contact/airborne phases and board-skater relationship only when supported by observations; do not assume image-space vertical motion is gravity without accounting for camera motion and perspective.

### 4. Multi-hypothesis physics rollout
Generate several short-horizon futures: constant velocity, observed acceleration, gravity-aware airborne motion, contact/rolling, and collision/landing hypotheses. Use event gates and contact constraints rather than one global equation. Keep hypotheses separate until evidence ranks them; rankings are not probabilities until calibrated on held-out data.

### 5. Visual future prediction
Render object trajectories into predicted masks/boxes as an interpretable baseline. Then train a learned predictor on context frames and future targets, optionally conditioned on state estimates and physics rollouts. The learned model should be compared against persistence and optical-flow baselines.

### 6. Evaluation
Use source-video-level train/validation/test splits to prevent near-duplicate frame leakage. Report per-horizon RGB MAE/PSNR or perceptual metrics, object-center/box displacement, event-label accuracy when reliable labels exist, calibration of uncertainty, and runtime. Report aggregate and per-scene metrics; do not claim improvement unless the held-out baseline comparison supports it.

## Initial dataset protocol
1. Use appropriately licensed videos and avoid collecting identifiable personal data unnecessarily.
2. Split by source video, not by adjacent clips.
3. Keep source URL/license, timestamps, frame sampling settings, and processing version in a manifest.
4. Add labels for visible objects and events only when manually checked or produced by a validated annotation pipeline.
5. Start with short horizons (e.g. 0.25, 0.5, 1.0 seconds), then test longer horizons separately.
6. Store actual future frames as targets; never include target or later frames in the model input.

## Acceptance gates
- CI tests pass on the feature branch.
- Unit tests cover invalid timestamps, frame shape mismatch, no-detection/occlusion cases, and deterministic rollouts.
- A small real-video smoke test produces a valid manifest and non-empty metrics.
- A held-out benchmark compares persistence, optical flow, kinematic rollout, and any learned model on identical clips.
- Results explicitly label measured, estimated, and unimplemented capabilities.

## Known limitations
The present code is a scaffold, not an end-to-end learned physics engine. It lacks robust natural-video object detection, camera-motion compensation, board/skater interaction modeling, contact-state estimation, future RGB frame generation, and trained weights. The next implementation should prioritize trustworthy track extraction and physically consistent trajectory hypotheses before adding model complexity.