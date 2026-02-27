import time
from pathlib import Path
import shutil
import json
import hashlib
import secrets
import ctypes
import platform
import pickle
import math

import cv2
import numpy as np
import face_recognition

# ===================== AYARLAR =====================
CAM_INDEX = 0
TARGET_SAMPLES = 5

# ---- Güvenlik / Kullanılabilirlik Dengesi (SERT ama seni çok reddetmesin) ----
VERIFY_TIMEOUT = 20            # sn

# Eşleşme: 2 kademeli eşik (STRONG / WEAK)  ✅ DENGELİ PRESET
STRONG_TOL = 0.38              # bunun altı = güçlü eşleşme (hit say)
WEAK_TOL = 0.45                # bunun altı = sınırda (hit sayma), üstü = reddet

STABLE_MATCH_HITS = 7          # art arda kaç güçlü doğrulama olursa başarılı
REQUIRED_STRONG_VOTES = 2      # 5 encoding içinden kaç tanesi STRONG olmalı (2/5)

# Göz kırpma
EAR_THRESHOLD = 0.21           # blink eşiği (0.20-0.23 arası)
MIN_FACE_SIZE = 140            # px (yüz küçükse hiç deneme)
BLUR_MIN_VAR = 50              # düşük kameralar için yumuşatıldı (60-120 arası kalibre)

# ENROLL görsel kayıt (kanıt için)
SAVE_ENROLL_IMAGES = True
ENROLL_IMAGE_JPEG_QUALITY = 92

# Güvenlik aksiyonu
LOCK_WINDOWS_ON_FAIL = True
LOCK_WINDOWS_ON_CANCEL = True

# Kurtarma
RESCUE_LEN = 11
RESCUE_LOCK_SECONDS = 15 * 60

# UI (Kamera boyutu)
UI_W, UI_H = 1000, 600

# Modern Renk Paleti (BGR)
COLOR_ACCENT = (0, 165, 255)   # Turuncu
COLOR_TEXT = (240, 240, 240)   # Beyazımsı Gri
COLOR_PANEL_BG = (20, 20, 20)  # Koyu Gri
COLOR_SUCCESS = (0, 255, 0)    # Yeşil
COLOR_ERROR = (0, 0, 255)      # Kırmızı
COLOR_SCANNING = (255, 100, 0) # Neon Mavisi

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data_secure"
FACES_DIR = DATA_DIR / "faces"
MODEL_PATH = DATA_DIR / "face_encoding.pkl"  # Liste encoding
NAME_PATH = DATA_DIR / "name.txt"
RESCUE_PATH = DATA_DIR / "rescue.json"
# ===================================================

def lock_windows():
    if platform.system().lower() != "windows":
        return
    try:
        ctypes.windll.user32.LockWorkStation()
    except:
        pass

def ensure_dirs():
    DATA_DIR.mkdir(exist_ok=True)
    FACES_DIR.mkdir(exist_ok=True)

def open_cam():
    cap = cv2.VideoCapture(CAM_INDEX)
    if not cap.isOpened():
        raise RuntimeError("Kamera açılamadı.")
    return cap

# ------------------ EAR & Blur ------------------
def calculate_ear(eye_points):
    def dist(p1, p2):
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

    v1 = dist(eye_points[1], eye_points[5])
    v2 = dist(eye_points[2], eye_points[4])
    h = dist(eye_points[0], eye_points[3])
    if h == 0:
        return 0
    return (v1 + v2) / (2.0 * h)

def detect_blink(face_landmarks):
    if "left_eye" not in face_landmarks or "right_eye" not in face_landmarks:
        return False
    left_ear = calculate_ear(face_landmarks["left_eye"])
    right_ear = calculate_ear(face_landmarks["right_eye"])
    return ((left_ear + right_ear) / 2.0) < EAR_THRESHOLD

def blur_score(gray_roi):
    if gray_roi is None or gray_roi.size == 0:
        return 0.0
    return float(cv2.Laplacian(gray_roi, cv2.CV_64F).var())

# ------------------ Kurtarma Sistemi ------------------
def _hash_with_salt(salt: str, text: str) -> str:
    return hashlib.sha256((salt + text).encode("utf-8")).hexdigest()

def generate_rescue_code(length: int = 11) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(length))

def setup_rescue_code_first_run():
    code = generate_rescue_code(RESCUE_LEN)
    salt = secrets.token_hex(16)
    data = {
        "salt": salt,
        "hash": _hash_with_salt(salt, code),
        "len": RESCUE_LEN,
        "fails": 0,
        "lock_until": 0
    }
    RESCUE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + "=" * 64)
    print("🛟 KURTARMA KODUN (11 hane) — LÜTFEN GÜVENLİ YERE KAYDET")
    print(f"RESCUE CODE: {code}")
    print("=" * 64 + "\n")

def _load_rescue():
    return json.loads(RESCUE_PATH.read_text(encoding="utf-8"))

def _save_rescue(data: dict):
    RESCUE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def rescue_is_locked():
    if not RESCUE_PATH.exists():
        return False, 0
    data = _load_rescue()
    lock_until = int(data.get("lock_until", 0))
    now = int(time.time())
    if lock_until > now:
        return True, lock_until - now
    return False, 0

def rescue_register_fail():
    data = _load_rescue()
    data["fails"] = int(data.get("fails", 0)) + 1
    if data["fails"] >= 3:
        data["lock_until"] = int(time.time()) + RESCUE_LOCK_SECONDS
    _save_rescue(data)

def rescue_register_success():
    data = _load_rescue()
    data["fails"], data["lock_until"] = 0, 0
    _save_rescue(data)

def rescue_code_matches(entered: str) -> bool:
    if not RESCUE_PATH.exists():
        return False
    entered = entered.strip()
    if len(entered) != RESCUE_LEN or not entered.isdigit():
        return False
    data = _load_rescue()
    return _hash_with_salt(data["salt"], entered) == data["hash"]

def reset_all_data():
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)

# ------------------ UI Fonksiyonları ------------------
def draw_panel(img, x, y, w, h, bg_color=COLOR_PANEL_BG, border_color=COLOR_ACCENT, alpha=0.7, border_thick=1):
    overlay = img.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), bg_color, -1)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    if border_thick > 0:
        cv2.rectangle(img, (x, y), (x + w, y + h), border_color, border_thick)

def put_text(img, text, x, y, scale=0.6, color=COLOR_TEXT, thick=1):
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)

def confirm_reset_overlay(window_name: str, frame) -> bool:
    overlay = frame.copy()
    draw_panel(overlay, 60, UI_H // 2 - 90, UI_W - 120, 180, alpha=0.85)
    put_text(overlay, "EMIN MISIN? (Y: EVET / N: HAYIR)", 90, UI_H // 2 - 20, 0.9, thick=2)
    put_text(overlay, "Onaylarsan tum veriler silinir (foto+model+ayarlar).", 90, UI_H // 2 + 20, 0.7, thick=2)
    cv2.imshow(window_name, overlay)
    start = time.time()
    while time.time() - start < 6:
        k = cv2.waitKey(50) & 0xFF
        if k in (ord("y"), ord("Y")):
            return True
        if k in (ord("n"), ord("N"), 27):
            return False
    return False

# ------------------ ENROLL (Kayıt - 5 Foto) ------------------
def enroll_flow():
    name = input("Kayıt edilecek isim (örn: gorkem): ").strip()
    if not name:
        return False

    user_dir = FACES_DIR / name
    user_dir.mkdir(parents=True, exist_ok=True)

    encodings = []
    cap = open_cam()

    window_name = "Enroll (Kayit)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, UI_W, UI_H)

    print("\nKAYIT MODU: Toplam 5 örnek alınacak.")
    print("İPUCU: Düz / hafif sağ / hafif sol / hafif yukarı / hafif aşağı açı yap.")
    print("Kayıt almak için GOZ KIRPIN. (Çıkış: Q)\n")

    try:
        while len(encodings) < TARGET_SAMPLES:
            ok, frame = cap.read()
            if not ok:
                break

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locs = face_recognition.face_locations(rgb)

            show = cv2.resize(frame, (UI_W, UI_H))
            draw_panel(show, 10, 10, 540, 120, alpha=0.65)
            put_text(show, f"Kaydedilen: {len(encodings)}/{TARGET_SAMPLES}", 25, 45, 0.9, color=COLOR_ACCENT, thick=2)
            put_text(show, "Kayit icin: GOZ KIRP", 25, 85, 0.7, thick=2)
            put_text(show, "Farkli acilar: duz/sag/sol/yukari/asagi", 25, 115, 0.55, thick=1)

            status = "Yuz araniyor..."
            sub = "Kameraya bak / isigi arttir"
            box_color = COLOR_SCANNING

            if face_locs:
                top, right, bottom, left = max(face_locs, key=lambda r: (r[2]-r[0])*(r[1]-r[3]))
                fw = right - left
                fh = bottom - top

                # UI koordinatlarına çevir
                h_ratio = UI_H / frame.shape[0]
                w_ratio = UI_W / frame.shape[1]
                y1, x2, y2, x1 = int(top*h_ratio), int(right*w_ratio), int(bottom*h_ratio), int(left*w_ratio)

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                roi = gray[top:bottom, left:right]
                b = blur_score(roi)

                # Landmark + blink
                landmarks_list = face_recognition.face_landmarks(rgb, [(top, right, bottom, left)])
                blink = False
                if landmarks_list:
                    blink = detect_blink(landmarks_list[0])

                # Kalite koşulları
                if fw < MIN_FACE_SIZE or fh < MIN_FACE_SIZE:
                    status = "Yuz cok kucuk"
                    sub = "Biraz yaklas"
                    box_color = COLOR_ERROR
                elif b < BLUR_MIN_VAR:
                    status = "Bulanik / kalite dusuk"
                    sub = f"Blur skor: {int(b)} (>= {BLUR_MIN_VAR} olmali)"
                    box_color = COLOR_ERROR
                else:
                    status = "Hazir"
                    sub = f"Blur: {int(b)} | Kirp: {'EVET' if blink else 'HAYIR'}"
                    box_color = COLOR_SUCCESS if blink else COLOR_SCANNING

                    # Blink anında yakala
                    if blink:
                        face_encs = face_recognition.face_encodings(rgb, [(top, right, bottom, left)])
                        if face_encs:
                            encodings.append(face_encs[0])

                            # Görsel kaydet (kayıt yaptığını anlaman için)
                            if SAVE_ENROLL_IMAGES:
                                img_path = user_dir / f"sample_{len(encodings):02d}.jpg"
                                cv2.imwrite(
                                    str(img_path),
                                    frame,
                                    [int(cv2.IMWRITE_JPEG_QUALITY), ENROLL_IMAGE_JPEG_QUALITY]
                                )

                            draw_panel(show, 10, 140, 540, 70, alpha=0.75, border_thick=0)
                            put_text(show, "✅ ORNEK KAYDEDILDI!", 25, 185, 0.9, color=COLOR_SUCCESS, thick=2)
                            cv2.rectangle(show, (x1, y1), (x2, y2), COLOR_SUCCESS, 3)
                            cv2.imshow(window_name, show)
                            cv2.waitKey(500)  # kullanıcı fark etsin diye kısa bekleme

                # Çizimler
                cv2.rectangle(show, (x1, y1), (x2, y2), box_color, 2)
                draw_panel(show, x1, min(UI_H-80, y2 + 10), max(10, x2 - x1), 70, alpha=0.6, border_thick=0)
                put_text(show, status, x1 + 10, min(UI_H-45, y2 + 40), 0.65, thick=1)
                put_text(show, sub, x1 + 10, min(UI_H-20, y2 + 65), 0.5, thick=1)

            cv2.imshow(window_name, show)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q")):
                return False

    finally:
        cap.release()
        cv2.destroyAllWindows()

    if encodings:
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(encodings, f)   # liste encoding
        NAME_PATH.write_text(name, encoding="utf-8")
        setup_rescue_code_first_run()
        print("✅ Kayıt tamamlandı. (5 encoding + örnek görseller kaydedildi)")
        return True

    return False

# ------------------ VERIFY (Doğrulama ve Kilit) ------------------
def verify_flow():
    if not MODEL_PATH.exists() or not NAME_PATH.exists():
        return

    name = NAME_PATH.read_text(encoding="utf-8").strip()
    with open(MODEL_PATH, "rb") as f:
        known_encodings = pickle.load(f)

    # Eski format varsa (tek vektör) listeye çevir
    if isinstance(known_encodings, np.ndarray):
        known_encodings = [known_encodings]

    cap = open_cam()
    start = time.time()

    rescue_mode = False
    typed_digits = ""

    blinked = False
    match_hits = 0

    window_name = "LockFace (Secure)"
    btn = {"x": UI_W - 200, "y": 20, "w": 180, "h": 50}
    ibox = {"x": UI_W - 420, "y": 90, "w": 400, "h": 90}

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, UI_W, UI_H)

    def on_mouse(event, mx, my, flags, param):
        nonlocal rescue_mode, typed_digits
        if event == cv2.EVENT_LBUTTONDOWN:
            if btn["x"] <= mx <= btn["x"] + btn["w"] and btn["y"] <= my <= btn["y"] + btn["h"]:
                rescue_mode = True
                typed_digits = ""

    cv2.setMouseCallback(window_name, on_mouse)

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            ui = cv2.resize(frame, (UI_W, UI_H))
            h_ratio = UI_H / frame.shape[0]
            w_ratio = UI_W / frame.shape[1]

            # Üst Bar
            draw_panel(ui, 20, 20, UI_W - 250, 60, alpha=0.65)
            put_text(ui, "YUZ DOGRULAMA SISTEMI", 40, 58, 1.0, color=COLOR_ACCENT, thick=2)

            status, sub = "", ""
            current_scan_color = COLOR_SCANNING

            if not rescue_mode:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                face_locations = face_recognition.face_locations(rgb_frame)

                if face_locations:
                    top, right, bottom, left = max(face_locations, key=lambda r: (r[2]-r[0])*(r[1]-r[3]))
                    fw = right - left
                    fh = bottom - top

                    y1, x2, y2, x1 = int(top*h_ratio), int(right*w_ratio), int(bottom*h_ratio), int(left*w_ratio)

                    # Boyut filtresi
                    if fw < MIN_FACE_SIZE or fh < MIN_FACE_SIZE:
                        match_hits = 0
                        blinked = False
                        status = "Yuz cok kucuk"
                        sub = "Yaklas / kameraya yakin dur"
                        current_scan_color = COLOR_ERROR
                    else:
                        # Blur filtresi
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        roi = gray[top:bottom, left:right]
                        b = blur_score(roi)

                        if b < BLUR_MIN_VAR:
                            match_hits = 0
                            blinked = False
                            status = "Goruntu kalitesi dusuk"
                            sub = f"Bulanik/parlama (skor {int(b)})"
                            current_scan_color = COLOR_ERROR
                        else:
                            # Landmarks + blink
                            landmarks_list = face_recognition.face_landmarks(rgb_frame, [(top, right, bottom, left)])
                            if landmarks_list and detect_blink(landmarks_list[0]):
                                blinked = True

                            if not blinked:
                                match_hits = 0
                                status = "Canlilik Kontrolu"
                                sub = "Lutfen goz kirpin"
                                current_scan_color = COLOR_SCANNING
                            else:
                                status = "Yuz Taraniyor..."
                                sub = "Sistem analiz ediyor..."
                                current_scan_color = COLOR_SCANNING

                                face_encodings = face_recognition.face_encodings(rgb_frame, [(top, right, bottom, left)])
                                if face_encodings:
                                    dists = face_recognition.face_distance(known_encodings, face_encodings[0])
                                    best_dist = float(np.min(dists))
                                    strong_votes = int(np.sum(dists < STRONG_TOL))

                                    if strong_votes >= REQUIRED_STRONG_VOTES:
                                        match_hits += 1
                                        status = "Guclu Eslesme"
                                        sub = f"Onay {strong_votes}/5 | En iyi {best_dist:.3f} | ({match_hits}/{STABLE_MATCH_HITS})"
                                        current_scan_color = COLOR_SUCCESS

                                        if match_hits >= STABLE_MATCH_HITS:
                                            draw_panel(ui, 40, 220, UI_W - 80, 120,
                                                       bg_color=COLOR_SUCCESS, border_color=COLOR_SUCCESS, alpha=0.85)
                                            put_text(ui, f"BASARILI: {name}", 70, 295, 1.2, thick=3)
                                            cv2.rectangle(ui, (x1, y1), (x2, y2), COLOR_SUCCESS, 2)
                                            cv2.imshow(window_name, ui)
                                            cv2.waitKey(600)
                                            return

                                    elif best_dist < WEAK_TOL:
                                        # Sınırda: hit sayma
                                        match_hits = 0
                                        status = "Sinirda Eslesme"
                                        sub = f"En iyi {best_dist:.3f} | Daha net bak / isigi arttir"
                                        current_scan_color = COLOR_SCANNING

                                    else:
                                        # Net red: hit sıfırla ama blinked'ı SIFIRLAMA ✅ (seni çok reddetmesin)
                                        match_hits = 0
                                        status = "Taninmayan Yuz!"
                                        sub = "Eslesme reddedildi."
                                        current_scan_color = COLOR_ERROR

                    cv2.rectangle(ui, (x1, y1), (x2, y2), current_scan_color, 2)
                    draw_panel(ui, x1, min(UI_H-80, y2 + 10), max(10, x2 - x1), 60, alpha=0.6, border_thick=0)
                    put_text(ui, status, x1 + 10, min(UI_H-45, y2 + 35), 0.6, thick=1)
                    put_text(ui, sub, x1 + 10, min(UI_H-20, y2 + 60), 0.45, thick=1)

                else:
                    blinked = False
                    match_hits = 0
                    draw_panel(ui, UI_W // 2 - 200, UI_H // 2 - 50, 400, 100, alpha=0.7)
                    put_text(ui, "Yuz bulunamadi", UI_W // 2 - 140, UI_H // 2 - 10, 0.9, thick=2)
                    put_text(ui, "Kameraya bakiniz / Isigi arttirin", UI_W // 2 - 170, UI_H // 2 + 30, 0.6, thick=1)

            # Kurtarma Butonu
            draw_panel(ui, btn["x"], btn["y"], btn["w"], btn["h"], alpha=0.7, border_thick=2 if rescue_mode else 1)
            put_text(ui, "Kurtarma Modu", btn["x"] + 15, btn["y"] + 32, 0.6, color=COLOR_ACCENT, thick=2)

            # Kurtarma Paneli
            if rescue_mode:
                locked, remain = rescue_is_locked()
                draw_panel(ui, 50, 360, UI_W - 100, 130, alpha=0.85)
                put_text(ui, "KURTARMA MODU AKTIF", 80, 400, 1.0, color=COLOR_ACCENT, thick=2)

                if locked:
                    put_text(ui, f"KILITLI: {remain}sn kaldi", 80, 440, 0.8, color=COLOR_ERROR, thick=2)
                else:
                    put_text(ui, "11 haneli kodu girip ENTER ile onaylayin.", 80, 440, 0.6, thick=1)

                draw_panel(ui, ibox["x"], ibox["y"], ibox["w"], ibox["h"], alpha=0.8)
                put_text(ui, "Kurtarma Kodu:", ibox["x"] + 15, ibox["y"] + 30, 0.6, color=COLOR_ACCENT, thick=1)
                put_text(ui, "*" * len(typed_digits), ibox["x"] + 15, ibox["y"] + 65, 1.2, thick=2)
                put_text(ui, "[ESC: Iptal]  [Backspace: Temizle]", 480, 460, 0.5, thick=1)

            # Timeout
            if (not rescue_mode) and (time.time() - start > VERIFY_TIMEOUT):
                draw_panel(ui, 50, 220, UI_W - 100, 120, bg_color=COLOR_ERROR, border_color=COLOR_ERROR, alpha=0.9)
                put_text(ui, "ISLEM BASARISIZ (Zaman Asimi)", 80, 285, 1.1, thick=3)
                cv2.imshow(window_name, ui)
                cv2.waitKey(900)
                if LOCK_WINDOWS_ON_FAIL:
                    lock_windows()
                return

            cv2.imshow(window_name, ui)
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), ord("Q")):
                if LOCK_WINDOWS_ON_CANCEL:
                    lock_windows()
                return

            if rescue_mode:
                if key == 27:
                    rescue_mode = False
                    typed_digits = ""
                    start = time.time()
                    continue
                if key in (8, 127):
                    typed_digits = ""
                    continue
                if ord("0") <= key <= ord("9") and len(typed_digits) < RESCUE_LEN:
                    typed_digits += chr(key)
                    continue
                if key in (10, 13):
                    locked, _ = rescue_is_locked()
                    if locked:
                        typed_digits = ""
                        continue
                    if rescue_code_matches(typed_digits):
                        rescue_register_success()
                        if confirm_reset_overlay(window_name, ui):
                            reset_all_data()
                            return
                        else:
                            typed_digits, rescue_mode, start = "", False, time.time()
                            continue
                    else:
                        rescue_register_fail()
                        typed_digits = ""
                        continue

    except Exception as e:
        print(f"HATA OLUŞTU: {e}")
        if LOCK_WINDOWS_ON_FAIL:
            lock_windows()
        raise
    finally:
        cap.release()
        cv2.destroyAllWindows()

def main():
    ensure_dirs()
    if not MODEL_PATH.exists():
        if not enroll_flow():
            return
    verify_flow()

if __name__ == "__main__":
    main()