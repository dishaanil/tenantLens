"""
debug_camera.py
Drop this in perception/ and run it to visually preview what the camera captures.
Press SPACE to capture and save the frame, Q to quit.
"""

import cv2
import base64
import os
from datetime import datetime

print("Opening camera preview...")
print("  SPACE — capture frame + save as JPEG")
print("  Q     — quit")

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("ERROR: Cannot open camera. Check camera permissions in System Preferences > Privacy.")
    exit(1)

saved_path = None

while True:
    ret, frame = cap.read()
    if not ret:
        print("ERROR: Failed to read frame")
        break

    # Show live preview with instructions overlaid
    preview = frame.copy()
    cv2.putText(preview, "SPACE=capture  Q=quit", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    cv2.imshow("TenantLens — Camera Preview", preview)

    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'):
        break

    elif key == ord(' '):
        # Save frame as JPEG
        timestamp = datetime.now().strftime("%H%M%S")
        saved_path = f"debug_frame_{timestamp}.jpg"
        cv2.imwrite(saved_path, frame)
        print(f"\nFrame saved: {saved_path}")

        # Also show what base64 length will be sent to Gemini
        _, buf = cv2.imencode(".jpg", frame)
        b64 = base64.b64encode(buf).decode("utf-8")
        print(f"Base64 length: {len(b64)} chars")

        # Now run it through Gemini vision immediately
        print("\nSending to Gemini...")
        try:
            from gemini_vision import analyze_frame
            from violation_parser import parse

            raw = analyze_frame(b64)
            result = parse(raw)

            print(f"\nGemini response:")
            print(f"  VIOLATION:   {result.violation_type}")
            print(f"  CONFIDENCE:  {result.confidence}")
            print(f"  DESCRIPTION: {result.description}")

            # Overlay result on the captured frame and show it
            annotated = frame.copy()
            color = (0, 0, 255) if result.violation_type != "none" else (0, 255, 0)
            cv2.putText(annotated, f"VIOLATION: {result.violation_type}", (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            cv2.putText(annotated, f"CONFIDENCE: {result.confidence}", (10, 75),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            # Word-wrap description
            words = result.description.split()
            line, y = "", 110
            for word in words:
                if len(line + word) > 45:
                    cv2.putText(annotated, line, (10, y),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
                    y += 25
                    line = word + " "
                else:
                    line += word + " "
            if line:
                cv2.putText(annotated, line, (10, y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

            cv2.imshow("TenantLens — Gemini Result", annotated)

        except Exception as e:
            print(f"Gemini error: {e}")

cap.release()
cv2.destroyAllWindows()

if saved_path:
    print(f"\nLast saved frame: {os.path.abspath(saved_path)}")
