import cv2
import time
import json
import os
from datetime import timezone, timedelta, datetime
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# Constants
CHECK_INTERVAL = 60  # seconds
DOWNTIME_THRESHOLD = timedelta(minutes=30)
CONFIG_PATH = "config.json"

# Load camera configuration
with open(CONFIG_PATH, "r") as f:
    camera_data = json.load(f)

# Group cameras by engine
engine_map = {}
for cam in camera_data:
    engine = cam["engine"]
    if engine not in engine_map:
        engine_map[engine] = []
    engine_map[engine].append(cam["rtsp"])

# Track engine statuses
engine_status = {
    engine: {
        "was_up": True,
        "went_down_at": None,
        "alert_sent": False
    } for engine in engine_map
}

def is_camera_online(rtsp_url):
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        return False
    ret, _ = cap.read()
    cap.release()
    return ret

def notify_slack(message):
    if SLACK_WEBHOOK_URL:
        requests.post(SLACK_WEBHOOK_URL, json={"text": message})

def main():
    while True:
        print("Checking camera statuses...")
        current_time = datetime.now(timezone.utc)

        for engine, urls in engine_map.items():
            all_down = all(not is_camera_online(url) for url in urls)
            status = engine_status[engine]

            if all_down:
                if status["was_up"]:
                    # Just went down now
                    status["was_up"] = False
                    status["went_down_at"] = current_time
                    print(f"{engine} just went down at {current_time}.")

                elif status["went_down_at"] and not status["alert_sent"]:
                    # Been down for a while
                    down_duration = current_time - status["went_down_at"]
                    if down_duration >= DOWNTIME_THRESHOLD:
                        notify_slack(f"⚠️ Attention required: engine `{engine}` has been offline for 30 minutes.")
                        status["alert_sent"] = True

            else:
                # Engine is up again
                if not status["was_up"]:
                    print(f"{engine} is back online at {current_time}.")
                status.update({"was_up": True, "went_down_at": None, "alert_sent": False})

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()

