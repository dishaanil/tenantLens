"""
verify_camera_feed.py
Place in perception/ and run to confirm camera_feed.py captures
the same frame as debug_camera.py.
Saves the captured frame as verify_frame.jpg so you can open and inspect it.
"""

import base64
import cv2
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from camera_feed import get_frame_base64

print("Capturing frame via camera_feed.get_frame_base64()...")
b64 = get_frame_base64()
print(f"Base64 length: {len(b64)} chars")

# Decode base64 back to image
img_bytes = base64.b64decode(b64)
img_array = np.frombuffer(img_bytes, dtype=np.uint8)
img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

# Save so you can open it in Finder / Preview
save_path = "verify_frame.jpg"
cv2.imwrite(save_path, img)
print(f"Saved: {os.path.abspath(save_path)}")
print("Open this file in Finder to confirm it matches what you see in debug_camera.py")

# Also show it in a window
cv2.imshow("camera_feed.py capture", img)
print("\nPress any key to close the window...")
cv2.waitKey(0)
cv2.destroyAllWindows()
