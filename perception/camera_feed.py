"""
camera_feed.py
Perception Agent — Step 1
Opens the device camera, waits for it to warm up, then captures a frame.
Mac cameras need ~20 frames before delivering real image data.
"""
 
import cv2
import base64
 
 
def get_frame_base64(camera_index: int = 0, warmup_frames: int = 20) -> str:
    """
    Capture a single frame from the camera.
    Discards the first `warmup_frames` frames to allow the camera to initialise.
    Returns base64-encoded JPEG string.
    """
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera at index {camera_index}")
 
    # Set resolution explicitly so Mac camera initialises faster
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
 
    # Warm up — discard early black frames
    print(f"Warming up camera ({warmup_frames} frames)...")
    for _ in range(warmup_frames):
        cap.read()
 
    # Now capture the real frame
    ret, frame = cap.read()
    cap.release()
 
    if not ret or frame is None:
        raise RuntimeError("Failed to capture frame after warmup")
 
    # Quick brightness check — warn if still black
    brightness = frame.mean()
    if brightness < 5:
        print(f"WARNING: Frame looks very dark (brightness={brightness:.1f}). "
              "Check camera permissions or increase warmup_frames.")
 
    print(f"Frame captured — brightness: {brightness:.1f}, size: {frame.shape}")
 
    _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return base64.b64encode(buffer).decode("utf-8")
 
 
if __name__ == "__main__":
    import numpy as np
 
    print("Capturing frame with warmup...")
    b64 = get_frame_base64()
    print(f"OK — base64 length: {len(b64)}")
 
    # Decode and save so you can visually verify it
    img_bytes = base64.b64decode(b64)
    img_array = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    cv2.imwrite("camera_test_frame.jpg", img)
    print("Saved camera_test_frame.jpg — open in Finder to verify image")
 