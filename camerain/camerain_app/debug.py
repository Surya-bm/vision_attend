import inspect
import os

def log(msg):
    caller_frame = inspect.stack()[1]
    file_path = caller_frame.filename
    file = os.path.basename(file_path)
    print(f"[{file}] {msg}")