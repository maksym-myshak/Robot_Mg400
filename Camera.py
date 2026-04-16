import cv2
import numpy as np
import json
from pathlib import Path

# ==========================================
# 1) НАЛАШТУВАННЯ
# ==========================================
TARGET_FILE = Path("/home/maks/current_target.json")
CAM_INDEX = 0

cap = cv2.VideoCapture(CAM_INDEX)
cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
cap.set(cv2.CAP_PROP_EXPOSURE, -5)
cap.set(cv2.CAP_PROP_AUTO_WB, 0)

if not cap.isOpened():
    print(f"Не вдалося відкрити USB-камеру index={CAM_INDEX}")
    raise SystemExit(1)

kernel = np.ones((5, 5), np.uint8)

src_pts = np.float32([
    [7, 10], [633, 13], [633, 473], [6, 471]
])
dst_pts = np.float32([
    [0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0],
])
M = cv2.getPerspectiveTransform(src_pts, dst_pts)

color_ranges = {
    "red": [(np.array([0, 120, 70]), np.array([10, 255, 255])), (np.array([170, 120, 70]), np.array([180, 255, 255]))],
    "green": [(np.array([35, 70, 70]), np.array([85, 255, 255]))],
    "blue": [(np.array([90, 80, 70]), np.array([130, 255, 255]))],
    "yellow": [(np.array([18, 100, 100]), np.array([35, 255, 255]))],
}

draw_colors = {"red": (0, 0, 255), "green": (0, 255, 0), "blue": (255, 0, 0), "yellow": (0, 255, 255)}

def get_zone(x, y):
    x_zone = "left" if x < 0.33 else "center" if x < 0.66 else "right"
    y_zone = "far" if y < 0.33 else "mid" if y < 0.66 else "near"
    return f"{x_zone}-{y_zone}"

def get_shape_name(contour):
    peri = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, 0.01 * peri, True)
    corners = len(approx)
    area = cv2.contourArea(contour)
    circularity = 4 * np.pi * (area / (peri * peri)) if peri > 0 else 0

    if corners == 3: return "tri_prism"
    elif corners == 4:
        x, y, w, h = cv2.boundingRect(approx)
        ratio = float(w) / h
        return "cube" if 0.85 <= ratio <= 1.15 else "parallelepiped"
    elif corners == 6: return "hex_prism"
    elif circularity > 0.75 or corners > 7: return "cone_cylinder"
    return "unknown"

def detect_all_of_color(frame_hsv, color_name):
    full_mask = None
    for low, high in color_ranges[color_name]:
        mask = cv2.inRange(frame_hsv, low, high)
        full_mask = mask if full_mask is None else cv2.bitwise_or(full_mask, mask)

    full_mask = cv2.morphologyEx(full_mask, cv2.MORPH_OPEN, kernel)
    full_mask = cv2.morphologyEx(full_mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(full_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    detections = []
    for c in contours:
        if cv2.contourArea(c) < 500: continue
        shape = get_shape_name(c)
        x, y, w, h = cv2.boundingRect(c)
        cx, cy = x + w // 2, y + h // 2
        pt = np.array([[[cx, cy]]], dtype=np.float32)
        tx, ty = cv2.perspectiveTransform(pt, M)[0][0]
        tx, ty = max(0.0, min(1.0, float(tx))), max(0.0, min(1.0, float(ty)))
        detections.append({
            "color": color_name, "shape": shape, "center_px": (cx, cy),
            "bbox": (x, y, w, h), "x": round(tx, 3), "y": round(ty, 3), "zone": get_zone(tx, ty)
        })
    return detections, full_mask

last_text = ""
while True:
    ret, frame = cap.read()
    if not ret: break

    display = frame.copy()
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    combined_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    all_objects = []

    for color in ["red", "green", "blue", "yellow"]:
        det, mask = detect_all_of_color(hsv, color)
        all_objects.extend(det)
        combined_mask = cv2.bitwise_or(combined_mask, mask)

    all_objects.sort(key=lambda obj: (-obj["y"], obj["x"]))

    y_info = 40
    for idx, obj in enumerate(all_objects, start=1):
        x, y, w, h = obj["bbox"]
        cx, cy = obj["center_px"]
        clr = draw_colors[obj["color"]]

        cv2.rectangle(display, (x, y), (x + w, y + h), clr, 2)
        # --- МАЛЮВАННЯ ЦЕНТРУ ---
        cv2.circle(display, (cx, cy), 5, (255, 255, 255), -1)
        cv2.circle(display, (cx, cy), 2, clr, -1)

        label = f'#{idx} {obj["color"]} {obj["shape"]}'
        cv2.putText(display, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, clr, 2)
        cv2.putText(display, f'{label} x={obj["x"]} y={obj["y"]}', (25, y_info), cv2.FONT_HERSHEY_SIMPLEX, 0.65, clr, 2)
        y_info += 28

    if all_objects:
        data = [{"color": o["color"], "shape": o["shape"], "x": o["x"], "y": o["y"], "zone": o["zone"]} for o in all_objects]
        TARGET_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        if json.dumps(data) != last_text:
            print("Detected:", data)
            last_text = json.dumps(data)
    else:
        if TARGET_FILE.exists(): TARGET_FILE.write_text("[]")
        cv2.putText(display, 'TARGET -> none', (25, display.shape[0]-25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)

    # --- ВИВІД ВІКОН ---
    cv2.imshow("task2 objects queue usb", display)
    cv2.imshow("task2 mask usb", combined_mask)

    if cv2.waitKey(1) & 0xFF == 27: break

cap.release()
cv2.destroyAllWindows()
