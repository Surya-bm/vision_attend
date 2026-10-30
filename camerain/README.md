# checking gpu availability
import torch
print(torch.cuda.is_available())

# terminal for opencode

opencode auth login

# python manage.py runserver 0.0.0.0:7071

# 1.camera_worker.py

'''
app = FaceAnalysis(name='buffalo_l'): InsightFace (SCRFD detector + ArcFace recognition) -Loading model
cap = cv2.VideoCapture(stream_url) - Live CCTV RTSP stream-a open
ret, frame = cap.read() - Took feed from video frame by frame
'''

# 2. camera_service.py

'''
start_background_camera(): Database-la Active-ah irukura cameras-a 
eduthu ovvondrukkum camera_process_worker-a separate Multiprocessing (mp.Process) process-ah start pannudhu.
'''

'''
_refresh_embeddings_loop(): Ovvoru 30 seconds-kum database-la irundhu pickle format-la irukura 512D face embeddings-a unpickle panni 
Shared Memory matrix-la update pannudhu.

'''

'''
_event_consumer_loop(): Worker process queue-la thalluna matched person details-a vaangudhu.
_execute_attendance_and_learning_async(): Attendance API-a call pannudhu. Confidence score high-ah 
(e.g., conf >= 0.58) irundha, adha new multi-angle vector-ah database-la save pannudhu (Auto-learning).
'''

# utils.py
'''

Vela (Role): User Face Registration panra appo photo-la irundhu Embedding eduppadharkum, 
background tasks-kum use aagura Utility Helper File.

'''


# views.py
'''
Vela (Role): Django Web Pages render panradhu, Live Streaming Display, 
matrum External HR/Attendance Server API-kku Image and Data POST payload anuppuradhu.

'''


# Real-Time CCTV Multi-Person Face Recognition Attendance System

An enterprise-grade, multiprocessing CCTV monitoring and automated attendance logging service powered by **Django**, **InsightFace (SCRFD + ArcFace)**, and **NVIDIA GPU CUDA Acceleration**.
## 🚀 Key Features

* **Multi-Face Frame Processing**: Detects and draws bounding boxes for all people (e.g. multi-employee walk-throughs) in a single frame before pushing events.

* **In-Memory OSD Overlay & Base64 Payload**: Renders dynamic timestamps/location OSD bars completely in RAM (Zero disk writes).
* **Per-Person Cooldown Lock**: Independent `(camera_id, person_id)` tracking to ensure concurrent multi-person attendance logging without dropping events.
* **Auto-Learning Engine (V2)**: Dynamically harvests high-confidence facial angle embeddings ($\ge 0.68$) to improve recognition over time.
* **MySQL Pool Connection Protection**: Graceful connection recycling preventing database pool crashes under heavy stream concurrency.

## ⚙️ Tech Stack

* **Framework**: Django (Python 3.10+)
* **AI/ML Engine**: InsightFace (`buffalo_l`), SCRFD, PyTorch, ONNX Runtime GPU
* **Computer Vision**: OpenCV, NumPy
* **Hardware Acceleration**: NVIDIA CUDA (Tested on Quadro T1000 & Jetson Orin)

## 🛠️ Installation & Setup

1. **Clone the Repository**:
   ```bash
   git clone [https://github.com/your-username/cctv-face-attendance.git](https://github.com/your-username/cctv-face-attendance.git)
   cd cctv-face-attendance


## iou_threshold = 0.7

**1. Why are we keeping 0.3 default?Video frames fast-a move aagum bodhu (20-30 FPS) contiguous frames-la face box $30\%$ minimum overlap aagum. So $0.3$ is the sweet spot for smooth tracking.**

## max_disappeared = 5 

**Indha parameter camera-la frame drops or face detection misses ah handle panna use aagudhu.**
'''
1. Why are we keeping 5 default?
InsightFace model intermittent-a 1 or 2 frames face blur/motion glare nala miss panna kooda, tracker udane ID ah delete pannama 5 frames wait pannum'''


