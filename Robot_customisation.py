import socket
import json
import time
import math
from pathlib import Path

# === НАЛАШТУВАННЯ МЕРЕЖІ ТА ФАЙЛІВ ===
ROBOT_IP = "192.168.1.6"
PORT = 29999
TARGET_FILE = Path("/home/maks/current_target.json")

# === НАЛАШТУВАННЯ КООРДИНАТ РОБОТА ===
SAFE_Z = 0.0  
HOME_X, HOME_Y, HOME_Z, HOME_R = 280.0, 0.0, 129.0, 0.0

# === НАЛАШТУВАННЯ ВИСОТИ (ВІСЬ Z) ===
Z_BLUE_TOP = -137.4  
TABLE_Z = Z_BLUE_TOP - 20.0  

COLOR_Z_MAP = {
    "blue": TABLE_Z + 19.0,  
    "red": TABLE_Z + 36.0,   
    "green": TABLE_Z + 30.0,
    "yellow": TABLE_Z + 25.0
}
DEFAULT_Z = TABLE_Z + 20.0  

def camera_to_mm(x_cam, y_cam):
    x_mm = (y_cam * 226.0) + 181.3
    y_mm = (x_cam * 330.1) - 197.8
    return round(x_mm, 1), round(y_mm, 1)

def send_command(sock, cmd):
    try:
        sock.sendall((cmd + '\n').encode('utf-8'))
        return sock.recv(1024).decode('utf-8').strip()
    except Exception as e:
        print(f"Помилка: {e}")
        return None

def is_already_touched(x, y, touched_list, threshold=0.08):
    for tx, ty in touched_list:
        if math.hypot(x - tx, y - ty) < threshold:
            return True
    return False

def main():
    robot_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    robot_socket.settimeout(5.0)
    
    try:
        robot_socket.connect((ROBOT_IP, PORT))
    except Exception as e:
        print(f"Не вдалося підключитися: {e}")
        return

    send_command(robot_socket, "ClearError()")
    time.sleep(0.5)
    send_command(robot_socket, "EnableRobot()")
    time.sleep(2.0)
    send_command(robot_socket, "SpeedFactor(30)")

    send_command(robot_socket, f"MovJ({HOME_X}, {HOME_Y}, {HOME_Z}, {HOME_R})")
    time.sleep(3)

    touched_points = []  
    objects_processed = 0

    print("Робот запущено. Починаю обробку об'єктів...")

    while objects_processed < 3:
        try:
            with open(TARGET_FILE, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            time.sleep(0.5)
            continue

        if not data or not isinstance(data, list):
            time.sleep(0.5)
            continue

        target = None
        for obj in data:
            tx = float(obj.get("x", 0))
            ty = float(obj.get("y", 0))
            if not is_already_touched(tx, ty, touched_points):
                target = obj
                break

        if target is None:
            time.sleep(0.5)
            continue

        # Отримуємо дані про ціль
        orig_x, orig_y = target["x"], target["y"]
        target_color = target["color"]
        target_shape = target["shape"]

        # === ПЕРЕВІРКА ФОРМИ ДЛЯ ВИВОДУ ТЕКСТУ ===
        is_hard_to_pick = target_shape in ["tri_prism", "cone_cylinder"]

        print(f"🎯 Ціль: {target_color} {target_shape}")
        if is_hard_to_pick:
            print(f"⚠️ УВАГА: {target_shape} складно підняти, але я спробую торкнутися!")

        # Розрахунок координат
        x_cam = 1.0 - orig_x
        y_cam = 1.0 - orig_y
        x_mm, y_mm = camera_to_mm(x_cam, y_cam)
        target_z = COLOR_Z_MAP.get(target_color, DEFAULT_Z)

        # РУХ РОБОТА
        print(f"🚀 Рух до X={x_mm}, Y={y_mm}")
        send_command(robot_socket, f"MovJ({x_mm}, {y_mm}, {SAFE_Z}, 0.0)")
        time.sleep(2) 
        
        send_command(robot_socket, f"MovL({x_mm}, {y_mm}, {target_z}, 0.0)")
        time.sleep(1.5)
        
        # Додатковий вивід при торканні
        if is_hard_to_pick:
            print(f"❌ Торкнувся {target_shape}, але підняти не вдалося (слизька форма).")
        else:
            print(f"✅ Торкнувся {target_shape} успішно.")

        send_command(robot_socket, f"MovL({x_mm}, {y_mm}, {SAFE_Z}, 0.0)")
        time.sleep(1.5)

        send_command(robot_socket, f"MovJ({HOME_X}, {HOME_Y}, {HOME_Z}, {HOME_R})")
        time.sleep(3)

        # Зберігаємо в пам'ять
        touched_points.append((orig_x, orig_y))
        objects_processed += 1

    print(f"Обробку {objects_processed} об'єктів завершено.")

if __name__ == "__main__":
    main()
