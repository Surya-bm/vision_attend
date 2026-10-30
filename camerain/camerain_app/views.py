"""
views.py  -  Attendance Project
"""

import os
from django.conf import settings
import cv2
import numpy as np
import time
import base64
import requests
from requests.auth import HTTPBasicAuth
import pytz
from django.http import StreamingHttpResponse,JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.db import close_old_connections
from .models import Camera, Person, PersonFace
from datetime import timedelta

from colorama import Fore, Style, init
init(autoreset=True)

# import font

FILE = "VIEWS.py"


def index_Intime_Camera(request):
    host = request.get_host()
    print(Fore.CYAN + Style.BRIGHT + f"[{FILE}]   [DEBUG] Host = {host!r}")
    
    # OLD CODE: cameras =     cameras = Camera.objects.filter(status=True) 
    
    # New code
    cameras = Camera.objects.filter(instance_url=host, status=True) 
    
    print(Fore.CYAN + Style.BRIGHT + f"[{FILE}]   [DEBUG] Cameras found = {cameras.count()}")
    return render(request, "HTMLAPPS/CameraIn.html", {"cameras": cameras})



def video_feed(request, camera_id):
    return StreamingHttpResponse(
        _gen_frames_mp(camera_id),
        content_type="multipart/x-mixed-replace; boundary=frame",
    )

def get_camera_fps(request):
    from .camera_background_service import get_fps_dict
    fps = get_fps_dict()
    if fps is None:
        return JsonResponse({})
    return JsonResponse(dict(fps))


def _gen_frames_mp(camera_id):   
    from .camera_background_service import get_frame_dict
    print(Fore.LIGHTBLUE_EX + Style.BRIGHT + f"[{FILE}]   [INFO] Streaming from shared process memory for camera {camera_id}")
    try:
        while True:
            frame_dict = get_frame_dict()
            # fps_dict = get_fps_dict()

            # SAFETY CHECK: If service not started yet, wait
            if frame_dict is None:
                time.sleep(0.5)
                continue
            
            # DEBUG: compare camera_id and frame_dict keys
            keys = list(frame_dict.keys())
            if not keys:
                print(Fore.CYAN + Style.BRIGHT + f"[{FILE}]   [DEBUG] frame_dict is EMPTY! Waiting for GPU Worker...{keys}") 
                time.sleep(1)
                continue
            
            try:
                jpg_bytes = frame_dict.get(camera_id)
            except Exception:
                time.sleep(0.05)
                continue

            if jpg_bytes is None:
                time.sleep(0.01)
                continue

            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg_bytes + b"\r\n")
    finally:
        print(f"[INFO] Stream connection closed for camera {camera_id}")



IST = pytz.timezone("Asia/Kolkata")


# Global counter dictionary to track daily sequence numbers per person in RAM
detection_counters = {}

def update_attendance(vw_person_id, camera_config, emp_obj, full_frame_bytes=None, cooldown_minutes=None):
    global detection_counters

    # 1. Camera Stream URL Check
    # if not camera_config.stream_url or camera_config.stream_url.strip() in ["", "0", None]:
    #     print(Fore.RED + Style.BRIGHT + f"[{FILE}]   [ATTENDANCE] Blocked: Camera {camera_config.id} has NO valid stream URL.")
    #     return

    if cooldown_minutes is None:
        cooldown_minutes = float(os.environ.get("ATTENDANCE_COOLDOWN_MINUTES", 0.5))

    now = timezone.now().astimezone(IST)
    today_date_str = str(now.date())
    camera_type = (camera_config.type or "").upper().strip()  # "IN" or "OUT"

    try:
        # 2. Resolve standard UUID for person validation
        person_obj = Person.objects.filter(unique_id=vw_person_id).first()
        if not person_obj:
            print(Fore.YELLOW + Style.BRIGHT + f"[{FILE}]   [WARNING] No Person row for unique_id={vw_person_id} ({getattr(emp_obj, 'name', 'Unknown')}) — skipping")
            return

        person_uuid = person_obj.id

        # 3. Dynamic Serial Counter Calculation (In-Memory per Person per Day)
        label_name = (getattr(emp_obj, "name", "unknown") or "unknown").lower().replace(" ", "_")
        date_time_ms_str = now.strftime("%Y%m%d-%H%M%S")

        # Key uniquely identifies person & date (e.g. "rajesh_2026-07-27")
        counter_key = f"{label_name}_{today_date_str}"
        detection_counters[counter_key] = detection_counters.get(counter_key, 0) + 1
        counter = detection_counters[counter_key]

        # Dynamic Filename Construction (e.g., rajesh-20260727-133600-1.jpeg)
        custom_filename = f"{label_name}-{date_time_ms_str}-{counter}.jpeg"

        # 4. Process Full Frame Image & Burn OSD Bar in RAM
        formatted_image_base64 = None

        if full_frame_bytes is not None:
            try:
                nparr = np.frombuffer(full_frame_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                if img is not None:
                    h, w, _ = img.shape

                    # date_str = now.strftime("%Y-%m-%d")
                    # day_str = now.strftime("%A")
                    # time_str = now.strftime("%H:%M:%S")
                    # location_str = getattr(camera_config, "model_name", None) or f"Camera_{str(camera_config.id)[:8]}"

                    # overlay_text = f"{date_str} ({day_str})  {time_str}  |  Camera: {location_str}"

                    # 06-08-2026
                    date_str = now.strftime("%a, %d %b %Y") # Output: "Thu, 06 Aug 2026"
                    time_str = now.strftime("%H:%M:%S")
                    location_str = getattr(camera_config, "model_name", None) or f"Camera_{str(camera_config.id)[:8]}"
                    overlay_text = f"{date_str}  {time_str}  |  Camera: {location_str}"

                    # --- 1. FONT SIZE CONTROL ---
                    # 0.7 = Small font
                    # 1.0 = Normal font (Default)
                    # 1.5 = Large font
                    FONT_SIZE_MULTIPLIER = 0.7  # <--- CHANGE THIS FOR SIZE

                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = max(0.5, h / 720.0) * FONT_SIZE_MULTIPLIER

                    # --- 2. FONT THICKNESS CONTROL ---
                    # Change the '3' below:
                    # 1 = Thin
                    # 2 = Normal
                    # 3 or 4 = Bold/Thick
                    font_thickness = max(1, int(font_scale * 1)) # <--- CHANGE '3' FOR THICKNESS

                    (text_w, text_h), baseline = cv2.getTextSize(overlay_text, font, font_scale, font_thickness)

                    bar_height = max(40, text_h + baseline + 20)
                    cv2.rectangle(img, (0, h - bar_height), (w, h), (0, 0, 0), -1)

                    text_x = 20
                    text_y = h - baseline - 10

                    # Draw OSD Text
                    cv2.putText(img, overlay_text, (text_x, text_y), font, font_scale, (0, 0, 0), font_thickness + 2, cv2.LINE_AA)
                    cv2.putText(img, overlay_text, (text_x, text_y), font, font_scale, (255, 255, 255), font_thickness, cv2.LINE_AA)
                    '''
                    FONT_SIZE_MULTIPLIER = 0.6
                    font_scale = max(0.5, h / 720.0) * FONT_SIZE_MULTIPLIER
                    font_thickness = max(1, int(font_scale * 2))
                    (text_w, text_h), baseline = cv2.getTextSize(overlay_text, font, font_scale, font_thickness)
                    # font = cv2.FONT_HERSHEY_SIMPLEX
                    # font_scale = max(0.5, h / 720.0)
                    # font_thickness = max(1, int(font_scale * 2))

                    # (text_w, text_h), baseline = cv2.getTextSize(overlay_text, font, font_scale, font_thickness)

                    bar_height = max(40, text_h + baseline + 20)
                    cv2.rectangle(img, (0, h - bar_height), (w, h), (0, 0, 0), -1)

                    text_x = 20
                    text_y = h - baseline - 10

                    # Draw OSD Text
                    cv2.putText(img, overlay_text, (text_x, text_y), font, font_scale, (0, 0, 0), font_thickness + 2, cv2.LINE_AA)
                    cv2.putText(img, overlay_text, (text_x, text_y), font, font_scale, (255, 255, 255), font_thickness, cv2.LINE_AA)
                    '''
                    success, encoded_img = cv2.imencode('.jpg', img)
                    if success:
                        osd_jpg_bytes = encoded_img.tobytes()
                        image_base64 = base64.b64encode(osd_jpg_bytes).decode("utf-8")
                    else:
                        image_base64 = base64.b64encode(full_frame_bytes).decode("utf-8")
                else:
                    image_base64 = base64.b64encode(full_frame_bytes).decode("utf-8")

            except Exception as e:
                print(Fore.RED + Style.BRIGHT + f"[{FILE}]   [ERROR] Failed to draw OSD overlay on full frame: {e}")
                image_base64 = base64.b64encode(full_frame_bytes).decode("utf-8")

            formatted_image_base64 = f"data:image/jpeg;base64,{image_base64}"

        # 5. Build Payload & Send Directly to External API
        # url = getattr(settings, "ATTENDANCE_API_URL", None)
        url = os.environ.get("ATTENDANCE_API_URL", None)
        payload = {
            "image": formatted_image_base64,
            "filename": custom_filename,
            "file_name": custom_filename,
            "person_id": str(person_uuid),
            "camera_id": camera_config.id,
            "camera_unique_id": getattr(camera_config, "unique_id", ""),
            "person_no": getattr(emp_obj, "employee_no", ""), 
            "date": today_date_str,
            "title": camera_type  
        }

        response = requests.post(
            url,
            auth=HTTPBasicAuth(os.environ.get("API_USERNAME", ""), os.environ.get("API_PASSWORD", "")),
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30
        )

        print(Fore.GREEN + Style.BRIGHT + f"[{FILE}] [API SENT] Status: {response.status_code} | Person: {getattr(emp_obj, 'name', '')} | File: {custom_filename}")
        print("API Response:", response.text)

    except requests.exceptions.RequestException as e:
        print("API requests failed:", e)
    except Exception as e:
        print("Error during attendance processing:", e)
    
    finally:
        # Prevents thread MySQL connection leaks
        close_old_connections()


