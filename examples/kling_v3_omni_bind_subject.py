import base64
import os
import time
from pathlib import Path

import httpx
import jwt


BASE_URL = os.getenv("KLING_BASE_URL", "https://api-beijing.klingai.com")
ACCESS_KEY = os.environ["KLING_ACCESS_KEY"]
SECRET_KEY = os.environ["KLING_SECRET_KEY"]
START_IMAGE = os.environ["KLING_START_IMAGE"]  # local path or http(s) URL
ELEMENT_ID = os.environ["KLING_ELEMENT_ID"]  # create this first with the Element API


def bearer_token() -> str:
    now = int(time.time())
    payload = {"iss": ACCESS_KEY, "exp": now + 1800, "nbf": now - 5}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256", headers={"typ": "JWT"})


def image_input(value: str) -> str:
    if value.startswith(("http://", "https://")):
        return value
    return base64.b64encode(Path(value).read_bytes()).decode("utf-8")


headers = {
    "Authorization": f"Bearer {bearer_token()}",
    "Content-Type": "application/json",
}

payload = {
    "model_name": "kling-v3",
    "image": image_input(START_IMAGE),
    "prompt": "The bound subject walks toward camera naturally. Keep the identity, face, hairstyle, and outfit consistent.",
    "mode": "pro",
    "duration": "15",
    "element_list": [{"element_id": ELEMENT_ID}],
}

with httpx.Client(base_url=BASE_URL, headers=headers, timeout=120) as client:
    task_id = client.post("/v1/videos/image2video", json=payload).json()["data"]["task_id"]
    print("task_id:", task_id)

    while True:
        data = client.get(f"/v1/videos/image2video/{task_id}").json()["data"]
        status = data["task_status"]
        print(status, data.get("task_status_msg") or "")
        if status in {"succeed", "failed"}:
            break
        time.sleep(5)

    if status == "succeed":
        for video in data.get("task_result", {}).get("videos", []):
            print(video.get("url") or video.get("watermark_url"))
