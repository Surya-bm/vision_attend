# ===========camera_service.py==================================
import threading
import multiprocessing as mp
import time
import pickle
import numpy as np
from django.conf import settings
from django.db import close_old_connections
from django.db import models
from .models import Person, VwPersonInfo
from .views import update_attendance
from colorama import Fore, Style, init

init(autoreset=True)

FILE = "CAMERA_SERVICE.py"

_manager = None
frame_dict = None          
embedding_dict = None      
_aux_stop_flag = {"stop": False}
_stop_events = {}
_processes = {}
fps_dict = None # Add global

def _camera_to_dict(cam):
    return {
        "id": str(cam.id),  # IMPORTANT: Convert to string
        "asset_no": cam.asset_no,
        "stream_url": cam.stream_url,
        # "stream_url": r"D:\BM\Projects\All worked projects folder\Github_Projects\vision_attend\camerain\long-distance.mp4",
        "roi_x": cam.roi_x,
        "roi_y": cam.roi_y,
        "roi_width": cam.roi_width,
        "roi_height": cam.roi_height,
        "type": cam.type,
    }

def _refresh_embeddings_loop(stop_flag, embedding_dict, interval=10):
    while not stop_flag["stop"]:
        try:
            embs, ids = [], []
            for person in Person.objects.filter(
                models.Q(face_embedding__isnull=False) | models.Q(face_embedding_mask__isnull=False)
            ):
                display_name = person.name.strip() if (person.name and person.name.strip()) else f"Stranger-[{person.unique_id}]"
                # Normal embedding
                if person.face_embedding:
                    try:
                        stored = pickle.loads(person.face_embedding)
                        if isinstance(stored, list):
                            for stored_emb in stored:
                                norm = np.linalg.norm(stored_emb)
                                if norm > 0:
                                    embs.append(stored_emb / norm)
                                    ids.append((person.unique_id, display_name, "normal"))
                        else:
                            norm = np.linalg.norm(stored)
                            if norm > 0:
                                embs.append(stored / norm)
                                ids.append((person.unique_id, display_name, "normal"))
                    except Exception as e:
                        print(f"[EMBED REFRESH] Normal embed error for person {person.unique_id}: {e}")

                # Mask embedding
                if person.face_embedding_mask:
                    try:
                        stored = pickle.loads(person.face_embedding_mask)
                        if isinstance(stored, list):
                            for stored_emb in stored:
                                norm = np.linalg.norm(stored_emb)
                                if norm > 0:
                                    embs.append(stored_emb / norm)
                                    ids.append((person.unique_id, display_name, "mask"))
                        else:
                            norm = np.linalg.norm(stored)
                            if norm > 0:
                                embs.append(stored / norm)
                                ids.append((person.unique_id, display_name, "mask"))
                    except Exception as e:
                        print(f"[EMBED REFRESH] Mask embed error for person {person.unique_id}: {e}")
            
            matrix = np.array(embs) if embs else None
            embedding_dict["data"] = (matrix, ids)
            normal_count = len([i for i in ids if i[2] == "normal"])
            mask_count = len([i for i in ids if i[2] == "mask"])
            print(Fore.GREEN + Style.BRIGHT + f"[{FILE}] [EMBED REFRESH] Loaded {len(ids)} embeddings ({normal_count} normal, {mask_count} mask). Matrix shape: {matrix.shape if matrix is not None else 'None'}")
        except Exception as e:
            print(f"[EMBED REFRESH ERROR] {e}")
        finally:
            close_old_connections()
        time.sleep(interval)


def get_frame_dict():
    global frame_dict
    return frame_dict


# ADD THIS NEW FUNCTION
def set_frame_dict(new_frame_dict):
    global frame_dict
    frame_dict = new_frame_dict


def get_fps_dict(): # NEW
    global fps_dict
    return fps_dict

def set_fps_dict(new_fps_dict): # NEW
    global fps_dict
    fps_dict = new_fps_dict

def stop_all():
    _aux_stop_flag["stop"] = True
    for ev in _stop_events.values():
        ev.set()
    for p in _processes.values():
        p.join(timeout=3)

        

# def _execute_attendance_and_learning_async(person_pk, camera_id, conf, raw_emb, full_frame_bytes):
#     try:
#         cooldown_seconds = getattr(settings, "ATTENDANCE_COOLDOWN_MINUTES", 0.5) * 60.0
#         now_ts = time.time()
#         cooldown_key = (camera_id, person_pk)

#         with _last_seen_lock:
#             last_ts = _last_seen.get(cooldown_key, 0)
#             if now_ts - last_ts < cooldown_seconds:
#                 return 
#             _last_seen[cooldown_key] = now_ts

#         camera_config = Camera.objects.filter(id=camera_id).first()
#         person_obj = Person.objects.filter(unique_id=person_pk).first()
        
#         if not camera_config or not person_obj:
#             return
            
#         emp_obj = VwPersonInfo.objects.filter(id=person_pk).first()
#         if not emp_obj:
#             return

#         update_attendance(person_pk, camera_config, emp_obj, full_frame_bytes=full_frame_bytes)
        
#         if conf >= 0.58: 
#             current_list = []
#             if person_obj.face_embedding:
#                 try:
#                     unpickled = pickle.loads(person_obj.face_embedding)
#                     current_list = unpickled if isinstance(unpickled, list) else [unpickled]
#                 except Exception:
#                     current_list = []
#     except Exception as e:
#         print(Fore.RED + Style.BRIGHT + f"[{FILE}] [EVENT ASYNC WORKER ERROR] {e}")
#     finally:
#         close_old_connections()

# def _event_consumer_loop(stop_flag):
#     while not stop_flag["stop"]:
#         try:
#             person_pk, camera_id, conf, raw_emb, full_frame_bytes = event_queue.get(timeout=1)
#         except Exception:
#             continue
        
#         threading.Thread(
#             target=_execute_attendance_and_learning_async,
#             args=(person_pk, camera_id, conf, raw_emb, full_frame_bytes),
#             daemon=True
#         ).start()



# # NEW: Dynamic Camera Sync Loop
# def _camera_config_sync_loop(stop_flag, interval=5):
#     print(Fore.CYAN + Style.BRIGHT + f"[{FILE}] [SYNC] Camera DB sync loop started (Every {interval} secs)")
#     while not stop_flag["stop"]:
#         try:
#             # Fetch current active cameras from DB
#             cameras = Camera.objects.filter(status=True)
#             new_config = {}
#             for cam in cameras:
#                 if not cam.stream_url:
#                     continue
#                 new_config[str(cam.id)] = _camera_to_dict(cam)
            
#             # Update the shared dictionary
#             active_cameras_config["data"] = new_config
            
#         except Exception as e:
#             print(Fore.RED + Style.BRIGHT + f"[{FILE}] [SYNC ERROR] {e}")
#         finally:
#             close_old_connections()
        
#         time.sleep(interval)



# def start_background_camera():
#     global _manager, frame_dict, embedding_dict, event_queue,active_cameras_config
#     print(Fore.CYAN + Style.BRIGHT + f"[{FILE}] [CCTV] Initializing multiprocessing camera service...")
#     _manager = mp.Manager()
#     frame_dict = _manager.dict()
#     embedding_dict = _manager.dict()
#     event_queue = _manager.Queue()

#     active_cameras_config = _manager.dict()
#     threading.Thread(target=_camera_config_sync_loop, args=(_aux_stop_flag,), daemon=True).start() 
#     threading.Thread(target=_refresh_embeddings_loop, args=(_aux_stop_flag,), daemon=True).start()
#     threading.Thread(target=_event_consumer_loop, args=(_aux_stop_flag,), daemon=True).start()

#     cameras = Camera.objects.filter(status=True)
#     # camera_dicts = []
#     initial_config = {}
#     for cam in cameras:
#         if not cam.stream_url:
#             continue

#         cam_dict = _camera_to_dict(cam)
#         initial_config[str(cam.id)] = cam_dict
#         # camera_dicts.append(_camera_to_dict(cam))

#     active_cameras_config["data"] = initial_config # Set initial data

#     if not initial_config:
#         print(Fore.YELLOW + Style.BRIGHT + f"[{FILE}] [CCTV] No active cameras found!")
#         return

#     # START ONLY ONE PROCESS
#     from .camera_worker import single_gpu_worker
#     stop_event = mp.Event()
#     _stop_events["single_worker"] = stop_event
    
#     p = mp.Process(target=single_gpu_worker,
#                    args=(active_cameras_config, frame_dict, embedding_dict, event_queue, stop_event),
#                     daemon=True,
#                    name="SingleGPUWorker")
#     p.start()
#     _processes["single_worker"] = p
#     print(Fore.CYAN + Style.BRIGHT + f"[{FILE}] [CCTV] Started SINGLE GPU Worker, pid={p.pid}")

