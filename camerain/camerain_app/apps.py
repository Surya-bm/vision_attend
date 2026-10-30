# apps.py

from django.apps import AppConfig
import threading
import os
import multiprocessing as mp
from django.db import connections
from django.db.utils import OperationalError


class CamerainAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "camerain_app"

    def ready(self):
        if os.environ.get("RUN_MAIN") != "true":
            return

        try:
            mp.set_start_method("spawn", force=True)
        except RuntimeError:
            pass  # start method already set — fine, ignore

        from .start_camera import start_background_camera
        thread = threading.Thread(target=start_background_camera, daemon=True)
        thread.start()

        try:
            connection = connections["default"]
            connection.ensure_connection()
            print("\n" + "=" * 60)
            print("DATABASE CONNECTED SUCCESSFULLY")
            print("=" * 60 + "\n")
        except OperationalError as e:
            print("\n" + "=" * 60)
            print(f"DATABASE CONNECTION FAILED: {e}")
            print("=" * 60 + "\n")
            raise e
