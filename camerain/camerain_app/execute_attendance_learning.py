
import os
import numpy as np
from django.conf import settings
import time
from django.utils import timezone
import threading
from .models import Camera, VwPersonInfo, Person
from .views import update_attendance
import pickle
from colorama import Fore, Style, init
from django.db import close_old_connections
import uuid


init(autoreset=True)

event_queue = None  
_last_seen = {}  
_last_seen_lock = threading.Lock()
_stranger_insert_lock = threading.Lock()  # FIX: Prevents race condition on simultaneous stranger inserts

FILE = "EXECUTE_ATTENDANCE_LEARNING.py"

def _event_consumer_loop(stop_flag, event_queue):
    while not stop_flag["stop"]:
        try:
            person_pk, camera_id, conf, raw_emb, full_frame_bytes, embed_type = event_queue.get(timeout=1)
        except Exception:
            continue

        # NEW: If person_pk is None → it's a Stranger
        if person_pk is None:
            threading.Thread(
                target=_insert_stranger_async,
                args=(raw_emb,),
                daemon=True
            ).start()
        else:
            threading.Thread(
                target=_execute_attendance_and_learning_async,
                args=(person_pk, camera_id, conf, raw_emb, full_frame_bytes, embed_type),
                daemon=True
            ).start()

def _execute_attendance_and_learning_async(person_pk, camera_id, conf, raw_emb, full_frame_bytes, embed_type="normal"):
    try:
        cooldown_seconds = float(os.environ.get("ATTENDANCE_COOLDOWN_MINUTES", 0.5)) * 60.0
        print(Fore.CYAN + Style.BRIGHT + f"[{FILE}] [env] Processing attendance for person_pk={person_pk}, camera_id={camera_id}, conf={conf}, embed_type={embed_type}")
        now_ts = time.time()
        cooldown_key = (camera_id, person_pk)

        with _last_seen_lock:
            last_ts = _last_seen.get(cooldown_key, 0)
            if now_ts - last_ts < cooldown_seconds:
                return 
            _last_seen[cooldown_key] = now_ts

        camera_config = Camera.objects.filter(id=camera_id).first()
        person_obj = Person.objects.filter(unique_id=person_pk).first()
        
        if not camera_config or not person_obj:
            return
            
        try:
            emp_obj = VwPersonInfo.objects.filter(id=person_pk).first()
        except Exception:
            emp_obj = None

        if not emp_obj:
            emp_obj = person_obj  # FALLBACK to person_obj so non-employee strangers with names can still log attendance

        update_attendance(person_pk, camera_config, emp_obj, full_frame_bytes=full_frame_bytes)
        
        # AUTO-LEARNING: Save to appropriate embedding field based on embed_type
        if conf >= 0.58: 
            norm_emb = raw_emb / (np.linalg.norm(raw_emb) + 1e-6)
            
            if embed_type == "mask":
                # Save to face_embedding_mask
                current_list = []
                if person_obj.face_embedding_mask:
                    try:
                        unpickled = pickle.loads(person_obj.face_embedding_mask)
                        current_list = unpickled if isinstance(unpickled, list) else [unpickled]
                    except Exception:
                        current_list = []
                # Deduplicate: only add if not similar to existing
                if not any(np.dot(norm_emb, e) > 0.95 for e in current_list):
                    current_list.append(norm_emb)
                    if len(current_list) > 5:
                        current_list = current_list[-5:]
                    person_obj.face_embedding_mask = pickle.dumps(current_list)
                    person_obj.save(update_fields=["face_embedding_mask"])
                    print(Fore.GREEN + f"[{FILE}] [AUTO-LEARN] Added mask embedding for person {person_pk} (total: {len(current_list)})")
            else:
                # Save to face_embedding (normal)
                current_list = []
                if person_obj.face_embedding:
                    try:
                        unpickled = pickle.loads(person_obj.face_embedding)
                        current_list = unpickled if isinstance(unpickled, list) else [unpickled]
                    except Exception:
                        current_list = []
                if not any(np.dot(norm_emb, e) > 0.95 for e in current_list):
                    current_list.append(norm_emb)
                    if len(current_list) > 5:
                        current_list = current_list[-5:]
                    person_obj.face_embedding = pickle.dumps(current_list)
                    person_obj.save(update_fields=["face_embedding"])
                    print(Fore.GREEN + f"[{FILE}] [AUTO-LEARN] Added normal embedding for person {person_pk} (total: {len(current_list)})")
    except Exception as e:
        print(Fore.RED + Style.BRIGHT + f"[{FILE}] [EVENT ASYNC WORKER ERROR] {e}")
    finally:
        close_old_connections()


'''
def _event_consumer_loop(stop_flag, event_queue):
    while not stop_flag["stop"]:
        try:
            person_pk, camera_id, conf, raw_emb, full_frame_bytes, embed_type = event_queue.get(timeout=1)
        except Exception:
            continue
        
        threading.Thread(
            target=_execute_attendance_and_learning_async,
            args=(person_pk, camera_id, conf, raw_emb, full_frame_bytes, embed_type),
            daemon=True
        ).start()

'''



def _insert_stranger_async(raw_emb):
    """When no face match found, auto-enroll as Stranger in person table."""
    try:
        norm_emb = raw_emb / (np.linalg.norm(raw_emb) + 1e-6)
        emb_pickled = pickle.dumps([norm_emb])
        new_uuid = str(uuid.uuid4())

        # Resolve created_by_id dynamically from Camera, Person, or Users table (no hardcoded UUID)
        created_by = None
        cam = Camera.objects.filter(created_by_id__isnull=False).exclude(created_by_id="").first()
        if cam and cam.created_by_id:
            created_by = cam.created_by_id
        else:
            any_person = Person.objects.filter(created_by_id__isnull=False).exclude(created_by_id="").first()
            if any_person and any_person.created_by_id:
                created_by = any_person.created_by_id
            else:
                try:
                    from django.db import connection
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT id FROM users LIMIT 1")
                        row = cursor.fetchone()
                        if row:
                            created_by = str(row[0])
                except Exception:
                    pass

        # Resolve Stranger category_id
        stranger_cat_id = None
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT id FROM category WHERE LOWER(name) = 'stranger' LIMIT 1")
                row = cursor.fetchone()
                if row:
                    stranger_cat_id = row[0]
        except Exception:
            pass

        # FIX: Lock prevents two threads inserting at the same time
        with _stranger_insert_lock:
            Person.objects.create(
                id=new_uuid,
                status=True,
                created_by_id=created_by,
                created_on=timezone.now(),
                name="",  # DB NOT NULL constraint
                category_id=stranger_cat_id,
                face_embedding=emb_pickled,
                face_embedding_mask=None,  # Mask not worn on initial detection
                image=None,
                is_active=False,
            )
        print(Fore.CYAN + Style.BRIGHT + f"[{FILE}] [STRANGER] Inserted stranger uuid={new_uuid}, category_id={stranger_cat_id}")

    except Exception as e:
        print(Fore.RED + Style.BRIGHT + f"[{FILE}] [STRANGER ERROR] {e}")
    finally:
        close_old_connections()