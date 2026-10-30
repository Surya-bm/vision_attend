# "SINGLE_GPU_WORKER.py"

import os
import time
import threading
import queue
import cv2
import numpy as np
import torch
import insightface
from insightface.app import FaceAnalysis
from colorama import Fore, Style, init
from .camera_worker import InternalCaptureThread, LightweightFaceTracker

FILE = "SINGLE_GPU_WORKER.py"

def single_gpu_worker(active_cameras_config, frame_dict, embedding_dict, event_queue, fps_dict, stop_event):
    print(Fore.YELLOW + Style.BRIGHT + f"[{FILE}] Process started! PID={os.getpid()}", flush=True)

    if not torch.cuda.is_available():
        print(Fore.RED + Style.BRIGHT + f"[{FILE}] [CRITICAL] CUDA NOT AVAILABLE!", flush=True)
        return
    
    providers = ['CUDAExecutionProvider']

    # 1. LOAD MODEL ONLY ONCE
    try:
        app = FaceAnalysis(name='buffalo_l', providers=providers)
        # app.prepare(ctx_id=0, det_size=(640, 640))  
        app.prepare(ctx_id=0, det_size=(480, 480))  # Can reduce to (480, 480) for speed  
        print(Fore.GREEN + Style.BRIGHT + f"[{FILE}] [OK] InsightFace loaded successfully!", flush=True)
    except Exception as e:
        print(Fore.RED + Style.BRIGHT + f"[{FILE}] [CRITICAL] Failed to load InsightFace: {e}", flush=True)
        return

    # 2. Dynamic Camera Management Variables
    frame_queues = {}
    trackers = {}
    recognition_cache = {}
    roi_configs = {}
    running_threads = {}
    thread_stop_events = {}
    fps_frame_counts = {}
    fps_start_times = {}
    stranger_queued = {}  # FIX: Tracks which track_ids already pushed as stranger per camera
    
    # Stranger Confirmation Time Settings
    STRANGER_CONFIRM_SECONDS = 1.5   # 1.5 seconds continuously standing infront of camere maked as - Stranger
    STRANGER_MIN_FRAMES = 3          # check at least 3 frames before confirming as stranger
    stranger_candidates = {}         # save candidates for stranger confirmation per track_id per camera

    scale_x = 640 / 1000.0
    scale_y = 480 / 800.0
    
    # FIX: Added Margin Threshold to prevent false positives
    SIMILARITY_THRESHOLD = 0.46
    MIN_MATCH_MARGIN = 0.05 
    MAX_FACES = 10

    def is_clear_frontal_face(face):
        det_score = getattr(face, 'det_score', 0.0)
        if det_score < 0.70:
            return False

        bbox = face.bbox.astype(int)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if w < 60 or h < 60:
            return False

        if hasattr(face, 'pose') and face.pose is not None:
            try:
                pitch, yaw, roll = face.pose
                if abs(yaw) > 28 or abs(pitch) > 28:
                    return False
            except Exception:
                return False  # ← Pose parse error = reject (safe default)
        else:
            # Pose unavailable → fallback: check eye symmetry
            if not (hasattr(face, 'kps') and face.kps is not None and len(face.kps) >= 5):
                return False  # No pose + no landmarks = reject
            # Eye horizontal alignment check (eyes must be roughly level)
            left_eye, right_eye = face.kps[0], face.kps[1]
            dy = abs(float(left_eye[1]) - float(right_eye[1]))
            dx = abs(float(left_eye[0]) - float(right_eye[0])) + 1e-6
            tilt_ratio = dy / dx
            if tilt_ratio > 0.35:  # ~19° tilt max
                return False

        # Eye distance check: both eyes must be clearly visible (not too close/side)
        if hasattr(face, 'kps') and face.kps is not None and len(face.kps) >= 2:
            left_eye, right_eye = face.kps[0], face.kps[1]
            eye_dist = np.linalg.norm(right_eye - left_eye)
            if eye_dist < 22:
                return False

        return True


    # def _is_duplicate_stranger(emb):
    #     # FIX 2: Before inserting a new Stranger row, check if this face embedding
    #     # already exists in the RAM matrix as a Stranger entry (pk=None, name='Stranger').
    #     #
    #     # Concept:
    #     #   - Once a stranger is inserted (unique_id=50), their embedding is in the matrix.
    #     #   - Next frame: same person re-appears -> this check finds sim >= 0.45 -> skip insert.
    #     #   - This prevents duplicate rows (50, 51, 52...) for the same physical person.
    #     #
    #     # Why 0.45 (not 0.48)?
    #     #   - 0.48 = recognition threshold ("Is this a known person?")
    #     #   - 0.45 = slightly relaxed ("Is this face already a stored stranger?")
    #     #     Catches the same person at slightly different angles vs their stored embedding.
    #     #     Different people score < 0.30, so 0.45 stays safely above that boundary.
    #     #
    #     # Returns: True  = duplicate, skip insert
    #     #          False = new face, proceed to insert
    #     try:
    #         data = embedding_dict.get("data")
    #         if not data or data[0] is None or len(data[0]) == 0:
    #             return False
    #         matrix, ids = data
    #         for i, entry in enumerate(ids):
    #             pk, name = entry[0], entry[1]
    #             if pk is None and name == "Stranger":
    #                 sim = float(np.dot(matrix[i], emb))
    #                 if sim >= 0.45:
    #                     print(Fore.CYAN + f"[DUPLICATE STRANGER] sim={sim:.4f} >= 0.45 -> already enrolled, skip insert.")
    #                     return True
    #     except Exception as dup_err:
    #         print(f"[DUPLICATE CHECK ERROR] {dup_err}")
    #     return False
    def _is_duplicate_stranger(emb):
            try:
                data = embedding_dict.get("data")
                if not data or data[0] is None or len(data[0]) == 0:
                    return False
                matrix, ids = data
                
                
                sims = matrix @ emb
                max_sim = float(np.max(sims))
                
                if max_sim >= 0.45:
                    best_idx = int(np.argmax(sims))
                    matched_name = ids[best_idx][1] if best_idx < len(ids) else "Unknown"
                    print(Fore.CYAN + f"[DUPLICATE FACE CHECK] max_sim={max_sim:.4f} >= 0.45 with '{matched_name}' -> Already exists, skip insert.")
                    return True
            except Exception as dup_err:
                print(f"[DUPLICATE CHECK ERROR] {dup_err}")
            return False

    def recognize_face(current_emb):
        data = embedding_dict.get("data")
        if not data: return None, 0.0, False, None
        matrix, ids = data
        if matrix is None or len(matrix) == 0: return None, 0.0, False, None
        
        sims = matrix @ current_emb
        
        # DEBUG: Log similarity scores
        best_idx = int(np.argmax(sims))
        best_sim = float(sims[best_idx])
        person_name = ids[best_idx][1] if best_idx < len(ids) else "N/A"
        print(Fore.YELLOW + f"[RECOGNIZE] Best match: {person_name} | sim={best_sim:.4f} | threshold={SIMILARITY_THRESHOLD} | matrix_shape={matrix.shape}")
        
        # FIX: Margin check logic
        if len(sims) >= 2:
            top2_idx = np.argpartition(sims, -2)[-2:]
            top2_sorted = top2_idx[np.argsort(sims[top2_idx])[::-1]]
            best_idx, second_idx = top2_sorted[0], top2_sorted[1]
            margin = float(sims[best_idx] - sims[second_idx])
        else:
            best_idx = int(np.argmax(sims))
            margin = 1.0 

        best_sim = float(sims[best_idx])
        
        if best_sim >= SIMILARITY_THRESHOLD:
            confident = margin >= MIN_MATCH_MARGIN
            person_pk, person_name, embed_type = ids[best_idx]
            return (person_pk, person_name), best_sim, confident, embed_type
        return None, best_sim, False, None

    def _start_camera(cam_id, cam_data):
        stranger_candidates[cam_id] = {}
        if cam_id in running_threads: return
        
        q = queue.Queue(maxsize=2)
        frame_queues[cam_id] = q
        
        trackers[cam_id] = LightweightFaceTracker(max_disappeared=5, iou_threshold=0.3)
        recognition_cache[cam_id] = {}
        stranger_queued[cam_id] = set()  # FIX: Init stranger set for this camera
        
        roi = None
        if all(cam_data.get(k) is not None for k in ("roi_x", "roi_y", "roi_width", "roi_height")):
            roi = (
                int(cam_data["roi_x"] * scale_x),
                int(cam_data["roi_y"] * scale_y),
                int(cam_data["roi_width"] * scale_x),
                int(cam_data["roi_height"] * scale_y),
            )
        roi_configs[cam_id] = roi

        stop_ev = threading.Event()
        thread_stop_events[cam_id] = stop_ev
        t = InternalCaptureThread(cam_data, q, stop_ev)
        t.start()
        running_threads[cam_id] = t
        
        if cam_id not in fps_frame_counts:
            fps_frame_counts[cam_id] = 0
            fps_start_times[cam_id] = time.time()
            fps_dict[cam_id] = 0.0
            
        print(Fore.GREEN + Style.BRIGHT + f"[{FILE}] [SYNC] Started processing camera: {cam_data['asset_no']}")

    def _stop_camera(cam_id):
        if cam_id not in running_threads: return
        
        thread_stop_events[cam_id].set()
        
        del running_threads[cam_id]
        del thread_stop_events[cam_id]
        del frame_queues[cam_id]
        del trackers[cam_id]
        del recognition_cache[cam_id]
        del roi_configs[cam_id]
        
        if cam_id in frame_dict:
            del frame_dict[cam_id]
        if cam_id in fps_frame_counts: del fps_frame_counts[cam_id]
        if cam_id in fps_start_times: del fps_start_times[cam_id]
        if cam_id in fps_dict: del fps_dict[cam_id]
        if cam_id in stranger_queued: del stranger_queued[cam_id]  # FIX: Cleanup stranger set
        if cam_id in stranger_candidates: del stranger_candidates[cam_id]
            
        print(Fore.RED + Style.BRIGHT + f"[{FILE}] [SYNC] Stopped processing camera ID: {cam_id}")

    print(Fore.GREEN + Style.BRIGHT + f"[{FILE}] [OK] Starting processing loop. Waiting for cameras...")

    # 3. Main Processing Loop
    last_sync_time = 0
    current_config_snapshot = {}

    while not stop_event.is_set():
        
        # --- DYNAMIC SYNC CHECK ---
        now = time.time()
        if now - last_sync_time >= 1.0:
            last_sync_time = now
            new_config = active_cameras_config.get("data")
            if new_config is None: new_config = {}
            
            if new_config != current_config_snapshot:
                for cam_id, cam_data in new_config.items():
                    if cam_id not in current_config_snapshot:
                        _start_camera(cam_id, cam_data)
                    else:
                        if current_config_snapshot[cam_id] != cam_data:
                            _stop_camera(cam_id)
                            _start_camera(cam_id, cam_data)
                
                for cam_id in list(current_config_snapshot.keys()):
                    if cam_id not in new_config:
                        _stop_camera(cam_id)
                
                current_config_snapshot = new_config.copy()

        # --- PROCESS FRAMES ---
        for cam_id, cam_data in current_config_snapshot.items():
            q = frame_queues.get(cam_id)
            if q is None: continue

            frame = None
            try:
                frame = q.get_nowait()
            except queue.Empty:
                continue
            
            if frame is None:
                continue

            roi = roi_configs.get(cam_id)
            asset_no = cam_data["asset_no"]

            # --- INSIGHTFACE DETECTION ---
            start_time = time.time() # ADD THIS
            try:
                faces = app.get(frame)
            except Exception as e:
                faces = []

            det_time = (time.time() - start_time) * 1000 # ADD THIS
            if det_time > 100: # If detection takes more than 100ms, something is wrong
                print(Fore.YELLOW + f"[{FILE}] [WARN][{asset_no}] Detection took {det_time:.2f} ms. Check performance.", flush=True)

            # FPS Logic
            if cam_id not in fps_frame_counts:
                fps_frame_counts[cam_id] = 0
                fps_start_times[cam_id] = time.time()
                fps_dict[cam_id] = 0.0
            
            fps_frame_counts[cam_id] += 1
            elapsed_fps = time.time() - fps_start_times[cam_id]
            if elapsed_fps >= 1.0:
                current_fps = fps_frame_counts[cam_id] / elapsed_fps
                fps_dict[cam_id] = round(current_fps, 2)
                fps_frame_counts[cam_id] = 0
                fps_start_times[cam_id] = time.time()

            detected_boxes = []
            valid_faces = []

            for face in faces:
                if len(detected_boxes) >= MAX_FACES: break
                bbox = face.bbox.astype(int)
                x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]

                if (x2 - x1) < 25 or (y2 - y1) < 25: continue

                if roi:
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    rx1, ry1, rx2, ry2 = roi
                    if not (rx1 <= cx <= rx2 and ry1 <= cy <= ry2): continue

                detected_boxes.append([x1, y1, x2, y2])
                valid_faces.append(face)

            tracker = trackers.get(cam_id)
            if not tracker: continue
            
            # FIX: Tracker returns {index: track_id}
            tracked_results = tracker.update(detected_boxes)
            frame_matches = []

            if roi:
                rx1, ry1, rx2, ry2 = roi
                cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (0, 255, 255), 2)
                cv2.putText(frame, "ROI", (rx1, ry1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

            # FIX: Use enumerate to match index safely
            for idx, face in enumerate(valid_faces):
                bbox = face.bbox.astype(int)
                x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]

                # FIX: Direct index lookup instead of bbox matching
                track_id = tracked_results.get(idx, "ID-?")

                cache = recognition_cache.get(cam_id, {})
                if track_id in cache:
                    match, conf, confident, embed_type = cache[track_id]
                else:
                    emb = face.embedding
                    norm = np.linalg.norm(emb)
                    # FIX: Skip garbage zero-norm embeddings
                    if norm <= 0: continue
                    emb = emb / norm
                    print(Fore.MAGENTA + f"[RECOGNIZE] Face embedding norm: {norm:.4f}, dim: {emb.shape}")

                    # FIX: Returns match, confidence, confident (margin check) boolean, and embed_type
                    match, conf, confident, embed_type = recognize_face(emb)
                    cache[track_id] = (match, conf, confident, embed_type)
                    recognition_cache[cam_id] = cache

                # DRAWING & ATTENDANCE LOGIC
                if match:
                    person_pk, person_name = match[0], match[1]
                    
                    # FIX: Cancel stranger timer if person is recognized!
                    if cam_id in stranger_candidates and track_id in stranger_candidates[cam_id]:
                        del stranger_candidates[cam_id][track_id]
                    
                    if confident:
                        color = (0, 180, 0) # Green = Confident Match
                        # label = f"[{track_id}] {person_name} {conf * 100:.1f}%"
                        label = f"{person_name} {conf * 100:.1f}%"
                        # Only log attendance if confident!
                        if person_pk is not None:
                            frame_matches.append((person_pk, float(conf), emb, embed_type))
                    else:
                        color = (0, 165, 255) # Orange = Low-confidence Match
                        label = f"[{track_id}] Low-conf {person_name}"
                        
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                else:
                    # TIME-DELAY CONFIRMATION: Do not enroll immediately on the 1st unknown frame
                    now_ts = time.time()
                    candidates = stranger_candidates.setdefault(cam_id, {})

                    # ONLY enroll stranger when face is clear and frontal!
                    if is_clear_frontal_face(face):
                        if track_id not in candidates:
                            candidates[track_id] = {
                                "first_seen": now_ts,
                                "frames": 1,
                                "best_emb": emb,
                                "best_score": getattr(face, 'det_score', 0.0)
                            }
                        else:
                            candidates[track_id]["frames"] += 1
                            det_s = getattr(face, 'det_score', 0.0)
                            if det_s > candidates[track_id]["best_score"]:
                                candidates[track_id]["best_emb"] = emb
                                candidates[track_id]["best_score"] = det_s

                        elapsed = now_ts - candidates[track_id]["first_seen"]
                        frame_cnt = candidates[track_id]["frames"]

                        # Check if hold delay has passed
                        if elapsed >= STRANGER_CONFIRM_SECONDS and frame_cnt >= STRANGER_MIN_FRAMES:
                            color = (0, 0, 255) # Red = Confirmed Stranger
                            label = f"[{track_id}] Stranger"

                            if track_id not in stranger_queued.get(cam_id, set()):
                                best_emb = candidates[track_id]["best_emb"]
                                # FIX 2: Check if this embedding is already a stored stranger
                                if _is_duplicate_stranger(best_emb):
                                    recognition_cache[cam_id][track_id] = ((None, "Stranger"), 1.0, True, "normal")
                                    stranger_queued[cam_id].add(track_id)
                                    print(Fore.CYAN + f"[{FILE}] [STRANGER CACHED] Duplicate face, new track_id={track_id} -> reused existing Stranger entry.")
                                else:
                                    event_queue.put((None, cam_id, conf, best_emb, None, "Stranger"))
                                    stranger_queued[cam_id].add(track_id)
                                    print(Fore.GREEN + Style.BRIGHT + f"[{FILE}] [STRANGER ENROLLED] Confirmed after {elapsed:.1f}s! New frontal face! track_id={track_id}, queued for DB insert.")

                                    # INSTANT RAM UPDATE: Add newly detected face to matrix in RAM immediately!
                                    try:
                                        data = embedding_dict.get("data")
                                        if data and data[0] is not None and len(data[0]) > 0:
                                            cur_matrix, cur_ids = data
                                            norm_e = best_emb / (np.linalg.norm(best_emb) + 1e-6)
                                            updated_matrix = np.vstack([cur_matrix, norm_e.reshape(1, -1)])
                                            updated_ids = list(cur_ids) + [(None, "Stranger", "normal")]
                                            embedding_dict["data"] = (updated_matrix, updated_ids)
                                        recognition_cache[cam_id][track_id] = ((None, "Stranger"), 1.0, True, "normal")
                                        print(Fore.CYAN + f"[{FILE}] [INSTANT RAM UPDATE] Stranger embedding added to matrix. Next frame will match.")
                                    except Exception as em_err:
                                        print(f"[INSTANT MATRIX UPDATE ERROR] {em_err}")
                        else:
                            # Verifying / hold window -> Show orange box while confirming
                            color = (0, 165, 255) # Orange = Verifying
                            label = f"[{track_id}] Verifying... ({elapsed:.1f}s)"
                    else:
                        color = (255, 0, 0) # Red = Unknown
                        label = f"[{track_id}] Unknown"
                        print(Fore.YELLOW + f"[{FILE}] [STRANGER SKIPPED] Face turned away or low quality for track_id={track_id}")

                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            # Send matches to Attendance Queue
            if frame_matches:
                ok_crop, crop_buf = cv2.imencode(".jpg", frame)
                crop_bytes = crop_buf.tobytes() if ok_crop else None

                for person_pk, conf_val, emb_vec, embed_type in frame_matches:
                    event_queue.put((person_pk, cam_id, conf_val, emb_vec, crop_bytes, embed_type))

            ok, buf = cv2.imencode(".jpg", frame)
            if ok:
                frame_dict[cam_id] = buf.tobytes()