# camerain/camerain_app/start_camera.py
import os
import time
import multiprocessing as mp
import threading
from django.db import close_old_connections
from colorama import Fore, Style
from .camera_background_service import _refresh_embeddings_loop, _camera_to_dict
from .models import Camera
from .execute_attendance_learning import _event_consumer_loop, _execute_attendance_and_learning_async
# from dotenv import load_dotenv
from dotenv import dotenv_values,find_dotenv # Import this instead of load_dotenv
import sys # NEW IMPORT
from django.conf import settings

FILE = "start_camera.py"

_aux_stop_flag = {"stop": False}
_stop_events = {}
_processes = {}


# NEW LOGIC: Extract ONLY the port number from command line
def get_current_instance_port():
    try:
        if 'runserver' in sys.argv:
            idx = sys.argv.index('runserver')
            addr = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else '8000'
            
            # Extract just the port number
            if ':' in addr:
                port = addr.split(':')[-1] # Splits '0.0.0.0:8002' and takes '8002'
            else:
                port = addr # It's already just the port (e.g., '8002')
            
            return port
    except Exception:
        pass
    return None # Return None if we can't detect (fallback to all cameras)


def _camera_config_sync_loop(stop_flag, active_cameras_config, interval=5): # Added active_cameras_config
    current_port = get_current_instance_port()
    print(Fore.CYAN + Style.BRIGHT + f"[{FILE}] [SYNC] Camera DB sync loop started (Every {interval} secs)")

    if current_port:
        print(Fore.CYAN + Style.BRIGHT + f"[{FILE}] [SYNC] Filtering cameras for port='{current_port}'")

    while not stop_flag["stop"]:
        try:
            # Fetch current active cameras from DB
            cameras = Camera.objects.filter(status=True)

            # NEW LOGIC: Filter by port ending with :7071 (Handles 127.0.0.1, 0.0.0.0, 192.168.x.x)
            if current_port:
                cameras = cameras.filter(instance_url__endswith=f':{current_port}')

            # NEW DEBUG: Check how many cameras DB actually returned
            db_count = cameras.count()
            print(Fore.MAGENTA + f"[SYNC DEBUG] DB returned {db_count} cameras for port {current_port}", flush=True)

            # host detected filter by it
            # if current_host:
            #     cameras = cameras.filter(instance_url=current_host)
                
            new_config = {}
            for cam in cameras:
                # if not cam.stream_url:
                #     print(Fore.RED + f"[SYNC DEBUG] Skipping cam {cam.id} because stream_url is empty!", flush=True)
                #     continue
                new_config[str(cam.id)] = _camera_to_dict(cam)
            print(Fore.MAGENTA + f"[SYNC DEBUG] Found {len(new_config)} cameras. Keys: {list(new_config.keys())}", flush=True)
            # Update the shared dictionary
            active_cameras_config["data"] = new_config
            
        except Exception as e:
            print(Fore.RED + Style.BRIGHT + f"[{FILE}] [SYNC ERROR] {e}")
        finally:
            close_old_connections()
        
        time.sleep(interval)     


# env sync loop to reload .env variables dynamicall

_tracked_env_keys = set()

def _env_sync_loop(stop_flag, interval=5):
    global _tracked_env_keys
    print(Fore.CYAN + Style.BRIGHT + f"[{FILE}] [ENV SYNC] Started .env auto-reload loop (Every {interval} secs)")
    
    while not stop_flag["stop"]:
        try:
            # 1. Automatically find the exact path of .env file
            env_path = find_dotenv()
            if not env_path:
                # .env file not found, wait and try again
                time.sleep(interval)
                continue

            # 2. Read current active values from .env file
            new_values = dotenv_values(env_path)
            current_keys = set(new_values.keys())
            
            # 3. Find keys that were REMOVED or COMMENTED OUT in .env
            keys_to_remove = _tracked_env_keys - current_keys
            
            # Delete those keys from os.environ so Django sees them as missing
            for key in keys_to_remove:
                if key in os.environ:
                    del os.environ[key]
            
            # 4. Add/Update keys that are currently in .env
            for key, value in new_values.items():
                # If value is None (empty variable), set it as empty string
                os.environ[key] = value if value is not None else ""
            
            # 5. Update our tracked keys for the next loop
            _tracked_env_keys = current_keys
            
        except Exception as e:
            print(Fore.RED + Style.BRIGHT + f"[{FILE}] [ENV SYNC ERROR] {e}")
        
        time.sleep(interval)



# def _env_sync_loop(stop_flag, interval=10):
#     print(Fore.CYAN + Style.BRIGHT + f"[{FILE}] [ENV SYNC] Started .env auto-reload loop (Every {interval} secs)")
#     while not stop_flag["stop"]:
#         try:
#             # override=True is the magic! It forces os.environ to update with new .env values
#             load_dotenv(override=True)
#         except Exception as e:
#             print(Fore.RED + Style.BRIGHT + f"[{FILE}] [ENV SYNC ERROR] {e}")
#         time.sleep(interval)

# ---------------------------------------------
# MULTI-GPU SPLIT LOGIC
# ---------------------------------------------
def split_cameras_for_multi_gpu(camera_list, num_gpus):
    """Splits a list into N roughly equal chunks."""
    k, m = divmod(len(camera_list), num_gpus)
    return [camera_list[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(num_gpus)]



def start_background_camera():
    global _manager, frame_dict, embedding_dict, event_queue, active_cameras_config,fps_dict
    print(Fore.CYAN + Style.BRIGHT + f"[{FILE}] [CCTV] Initializing multiprocessing camera service...")
    _manager = mp.Manager()
    frame_dict = _manager.dict()
    embedding_dict = _manager.dict()
    event_queue = _manager.Queue()
    active_cameras_config = _manager.dict()
    fps_dict = _manager.dict() # NEW: Create fps shared dict

    from .camera_background_service import set_frame_dict,set_fps_dict
    set_frame_dict(frame_dict)
    set_fps_dict(fps_dict) # NEW

    # Pass the shared dicts/queues to the threads
    threading.Thread(target=_camera_config_sync_loop, args=(_aux_stop_flag, active_cameras_config), daemon=True).start() 
    threading.Thread(target=_refresh_embeddings_loop, args=(_aux_stop_flag, embedding_dict), daemon=True).start()
    threading.Thread(target=_event_consumer_loop, args=(_aux_stop_flag, event_queue), daemon=True).start()
    threading.Thread(target=_env_sync_loop, args=(_aux_stop_flag,), daemon=True).start()

    cameras = Camera.objects.filter(status=True)
    initial_config = {}
    for cam in cameras:
        # if not cam.stream_url:
        #     continue
        cam_dict = _camera_to_dict(cam)
        initial_config[str(cam.id)] = cam_dict

    active_cameras_config["data"] = initial_config # Set initial data

    if not initial_config:
        print(Fore.YELLOW + Style.BRIGHT + f"[{FILE}] [CCTV] No active cameras found!")
        return

    
    # START ONLY ONE PROCESS
    from .single_gpu_worker import single_gpu_worker
    stop_event = mp.Event()
    _stop_events["single_worker"] = stop_event
    
    p = mp.Process(target=single_gpu_worker,
                   args=(active_cameras_config, frame_dict, embedding_dict, event_queue, fps_dict, stop_event),
                    daemon=True,
                   name="SingleGPUWorker")
    
    p.start()
    _processes["single_worker"] = p
    print(Fore.CYAN + Style.BRIGHT + f"[{FILE}] [CCTV] Started SINGLE GPU Worker, pid={p.pid}")

    # print(Fore.RED + "[DEBUG] Running worker in main thread to catch errors!")
    # single_gpu_worker(active_cameras_config, frame_dict, embedding_dict, event_queue, fps_dict, stop_event)`
    

    # # 11-08-2026
    # # ---------------------------------------------
    # # MULTI-GPU SPLIT LOGIC
    # # ---------------------------------------------
    # # NOTE: NUM_GPUS is read from settings.py (which itself reads NUM_GPUS
    # # from .env via decouple's config()). This avoids duplicating the parsing
    # # logic here, and avoids a race condition with the _env_sync_loop thread
    # # (that thread updates os.environ asynchronously, so os.environ.get()
    # # right here is not guaranteed to see the latest value yet).
    # # from django.conf import settings
    # NUM_GPUS = getattr(settings, "NUM_GPUS", 1)  # falls back to 1 if not set in settings.py
 
    # # initial_config is {cam_id: cam_dict} -> convert to a plain list before splitting
    # camera_dicts = list(initial_config.values())
 
    # # Split cameras into NUM_GPUS chunks
    # camera_chunks = split_cameras_for_multi_gpu(camera_dicts, NUM_GPUS)
 
    # from .single_gpu_worker import single_gpu_worker
 
    # for gpu_id, chunk in enumerate(camera_chunks):
    #     if not chunk:
    #         continue  # Skip if no cameras assigned to this GPU
 
    #     # NOTE: chunk is only used ONCE, here, to decide which camera IDs
    #     # belong to this GPU. We pass those IDs (assigned_cam_ids) to the
    #     # worker alongside the LIVE active_cameras_config dict, so the
    #     # worker's existing "DYNAMIC SYNC CHECK" logic keeps working exactly
    #     # as before (active_cameras_config.get("data")) -- it just filters
    #     # the live config down to this GPU's own camera IDs each time it syncs.
    #     assigned_cam_ids = [str(cam["id"]) for cam in chunk]
 
    #     stop_event = mp.Event()
    #     _stop_events[f"worker_gpu_{gpu_id}"] = stop_event
 
    #     # Start a separate worker for each GPU
    #     p = mp.Process(
    #         target=single_gpu_worker,
    #         args=(active_cameras_config, assigned_cam_ids, frame_dict, embedding_dict, event_queue, fps_dict, stop_event, gpu_id),
    #         daemon=True,
    #         name=f"GPU-Worker-{gpu_id}"
    #     )
    #     p.start()
    #     _processes[f"worker_gpu_{gpu_id}"] = p
    #     print(Fore.CYAN + Style.BRIGHT + f"[{FILE}] [CCTV] Started Worker on GPU:{gpu_id} with {len(chunk)} cameras, pid={p.pid}")