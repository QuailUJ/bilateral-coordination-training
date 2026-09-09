"""Timestamped training state shared by the live HUD and historical replay."""
import copy
import math


def _clean(value):
    if isinstance(value, float):
        return round(value, 5) if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_clean(item) for item in value]
    return value


def start_diagnostics(scene, now):
    from games.game1_bilateral_vertical import config as shared
    from games.game2_finger_vertical import config as finger
    scene.tracking_interruptions = {"left": 0, "right": 0}
    scene.tracking_lost = {"left": False, "right": False}
    scene.diagnostics = {
        "version": 1, "time_origin": now, "time_unit": "seconds",
        "coordinate_system": "mirrored_normalized_image",
        "tip_landmark": scene.hand_identity.tip_id,
        "target_pairs": 10, "action": dict(scene.selected_action),
        "parameters": {"shared": {key: value for key, value in vars(shared).items()
                                    if key.isupper() and isinstance(value, (float, int))},
                       "finger": {key: value for key, value in vars(finger).items()
                                    if key.isupper() and isinstance(value, (float, int))},
                       "identity": {"confidence": scene.hand_identity.confidence,
                                    "stable_frames": scene.hand_identity.stable_frames,
                                    "wrist_jump": 0.18, "tip_jump": 0.20,
                                    "overlap": 0.10, "camera_gap_s": 0.35}},
        "frames": [],
    }
    scene.debug_snapshot = None
    if getattr(scene.hand_identity, "tracking_point_kind", "") == "palm_center":
        from common.fist_tracking import PALM_IDS, REACQUIRE_S, LOSS_GRACE_S
        from games.game1_bilateral_vertical.fist_motion import CALIBRATION_S, CIRCLE_RADIUS
        scene.diagnostics.update(version=5, tip_landmark=None, tracking_point_kind="palm_center",
                                 tracking_landmarks=list(PALM_IDS), reference_kind="observed_top_reversal",
                                 algorithm="upper_reversal_circle_v1")
        scene.diagnostics["circle_direction_convention"] = "display_clockwise_top_right_bottom_left"
        scene.diagnostics["parameters"]["fist"] = dict(reacquire_s=REACQUIRE_S, loss_grace_s=LOSS_GRACE_S,
                                                       calibration_s=0, axis_reversal_on=0.012, axis_calibration_s=0)
        scene.diagnostics["parameters"]["circle_trial"] = dict(reversal=.012, minimum_span=.06,
            minimum_winding_degrees=270, minimum_direction_consistency=.65)


def snapshot(scene, now, source="camera"):
    tracker = scene.sync_tracker
    paired = getattr(tracker, "completed_pairs", getattr(tracker, "score", 0))
    data = {"t": max(0, now - scene.diagnostics["time_origin"]), "source": source,
            "camera_index": getattr(scene, "_camera_index", None),
            "paired": paired, "average_score": getattr(tracker, "average_score", None),
            "pair_detail": copy.deepcopy(getattr(tracker, "last_pair_detail", None)),
            "window_remaining": None, "distance_hint": scene.distance_hint}
    data["training_mode"] = "single" if getattr(scene, "single_side", None) else "bilateral"
    data["target_pairs"] = scene.diagnostics["target_pairs"]
    if hasattr(scene, "score_kind"):
        data["score_kind"] = scene.score_kind
    if getattr(tracker, "window_start_t", None) is not None:
        data["window_remaining"] = max(0, tracker.window_sec - (now - tracker.window_start_t))
    for side in ("left", "right"):
        recognizer = getattr(scene, side + "_recognizer")
        landmarks = getattr(scene, side + "_landmarks")
        status = dict(scene.hand_identity.status[side.title()])
        for key in ("raw_wrist", "raw_tip"):
            if key in status:
                status[key] = [1.0 - status[key][0], status[key][1]]
        item = {"tracking": status, "completed": recognizer.completed,
                "waiting": len(getattr(tracker, "_pending_" + side, [])),
                "interruptions": scene.tracking_interruptions[side],
                "action": scene.selected_action[side],
                "state": getattr(recognizer, "state", getattr(recognizer, "_phase", "")),
                "feedback": getattr(recognizer, "feedback", ""),
                "half_swings": getattr(recognizer, "half_swings", None),
                "turn_degrees": math.degrees(getattr(recognizer, "turn_acc", 0)),
                "last_duration": getattr(recognizer, "last_rep_duration", None),
                "last_start": (getattr(recognizer, "last_rep_start_t", None) - scene.diagnostics["time_origin"]
                               if getattr(recognizer, "last_rep_start_t", None) is not None else None),
                "last_peak": getattr(recognizer, "last_rep_peak", None),
                "last_quality": getattr(recognizer, "last_rep_quality", None),
                "metrics": copy.deepcopy(getattr(recognizer, "metrics", {})),
                "tip": None, "wrist": None}
        start = getattr(recognizer, "_rep_start_t", getattr(recognizer, "_lap_start_t", getattr(recognizer, "_start_t", None)))
        item["current_start"] = start - scene.diagnostics["time_origin"] if start is not None else None
        if landmarks is not None:
            tip = landmarks[scene.hand_identity.tip_id]
            wrist = landmarks[0]
            item["tip"], item["wrist"] = [1-tip.x, tip.y], [1-wrist.x, wrist.y]
            item["offset_x"] = wrist.x - tip.x
            item["offset_y"] = tip.y - wrist.y
            xs, ys = [p.x for p in landmarks], [p.y for p in landmarks]
            span = max(max(xs)-min(xs), max(ys)-min(ys))
            item["distance_hint"] = "too_close" if span > 0.55 else "too_far" if span < 0.12 else "ok"
        if hasattr(recognizer, "amp_on"):
            item["metrics"].update(axis=recognizer.axis, amp_on=recognizer.amp_on,
                                   amp_off=recognizer.amp_off, min_interval=recognizer.min_interval_s)
        if hasattr(recognizer, "turn_threshold"):
            item["metrics"].update(turn_threshold_deg=math.degrees(recognizer.turn_threshold))
        if scene.diagnostics.get("tracking_point_kind") == "palm_center":
            from common.fist_tracking import palm_center
            item["tracking_point_kind"] = "palm_center"
            item["distance_hint"] = None
            item["reference"] = recognizer.reference
            item["turning_point"] = getattr(recognizer, "turning_point", None)
            if item["action"] in ("CW", "CCW") and hasattr(scene, "trail_start_times"):
                item["trail_start_t"] = scene.trail_start_times[side] - scene.diagnostics["time_origin"]
            if "turning_time" in item["metrics"]:
                item["metrics"]["turning_time"] -= scene.diagnostics["time_origin"]
            item["missing_seconds"] = max(0, now - getattr(scene, "_missing_since", {}).get(side, now))
            if landmarks is not None:
                item["tip"] = palm_center(landmarks)
                # Keep the anatomical wrist separately; replay's hollow marker
                # now represents the actual reference used by the recognizer.
                item["anatomical_wrist"] = item["wrist"]
                item["wrist"] = recognizer.reference
                item["offset_x"] = item["tip"][0] - recognizer.reference[0] if recognizer.reference else None
                item["offset_y"] = item["tip"][1] - recognizer.reference[1] if recognizer.reference else None
        data[side] = item
    return _clean(data)


def record_diagnostics(scene, now, source="camera"):
    if not hasattr(scene, "diagnostics"):
        return
    data = snapshot(scene, now, source)
    scene.debug_snapshot = data
    frames = scene.diagnostics["frames"]
    if source == "camera_gap" and frames and data["t"] - frames[-1]["t"] < 0.1:
        return
    frames.append(data)


def export_diagnostics(scene, ctx):
    data = {key: value for key, value in scene.diagnostics.items() if key != "time_origin"}
    data["camera_index"] = ctx.camera_index
    data["frame_size"] = list(scene.display_frame.shape[1::-1]) if scene.display_frame is not None else None
    return data
