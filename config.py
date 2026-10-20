import os
import json

# Warna Tema Utama & Styling
C_BG = "#f4f6f9"
C_TEXT = "#1c1c1e"
C_INACTIVE = "#8e8e93"
C_ACCENT = "#007aff"
C_ONLINE = "#34c759"
C_OFFLINE = "#ff3b30"
C_BORDER = "#e5e5ea"

SETTINGS_FILE = "settings.json"
NODES_FILE = "nodes.json"

# Batas waktu (detik) sebelum sensor node dinyatakan offline
# 45 detik ideal untuk sensor nirkabel (ESP-NOW / LoRa) agar tidak kelap-kelip offline
NODE_OFFLINE_TIMEOUT = 45.0

def safe_grab_set(window):
    """
    Mengaktifkan modal grab secara aman khusus untuk Raspberry Pi OS / Linux / X11.
    Mencegah crash '_tkinter.TclError: grab failed: window not viewable'
    yang terjadi saat X11 belum selesai me-map window ke layar.
    """
    def _try_grab():
        try:
            if window and window.winfo_exists():
                window.grab_set()
        except Exception:
            pass

    try:
        window.update_idletasks()
        window.grab_set()
    except Exception:
        # Jika window belum viewable di X11, coba lagi setelah 50ms secara asinkron
        try:
            window.after(50, _try_grab)
        except Exception:
            pass

def safe_grab_release(window):
    """Melepaskan modal grab secara aman"""
    try:
        if window and window.winfo_exists():
            window.grab_release()
    except Exception:
        pass

def setup_fonts():
    return {
        "title": ("Segoe UI", 16, "bold"),
        "normal": ("Segoe UI", 10),
        "bold": ("Segoe UI", 10, "bold"),
        "status": ("Segoe UI", 10, "bold"),
        "card_title": ("Segoe UI", 16, "bold"),
        "card_val": ("Segoe UI", 32, "bold"),
        "card_unit": ("Segoe UI", 8, "bold")
    }

def get_asset_path(filename):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # Cek langsung di root folder
    p_root = os.path.join(base_dir, filename)
    if os.path.exists(p_root):
        return p_root
    
    # Cek variasi lowercase di root folder
    name_no_ext, ext = os.path.splitext(filename)
    p_root_lower = os.path.join(base_dir, f"{name_no_ext.lower()}{ext.lower()}")
    if os.path.exists(p_root_lower):
        return p_root_lower

    # Cek di subfolder assets
    p_assets = os.path.join(base_dir, "assets", filename)
    if os.path.exists(p_assets):
        return p_assets
        
    p_assets_lower = os.path.join(base_dir, "assets", f"{name_no_ext.lower()}{ext.lower()}")
    if os.path.exists(p_assets_lower):
        return p_assets_lower
        
    return p_root

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_port": None, "station_id": None}

def save_settings(port, station_id):
    data = {"last_port": port, "station_id": station_id}
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print("Gagal menyimpan settings:", e)

def load_registered_nodes():
    if os.path.exists(NODES_FILE):
        try:
            with open(NODES_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_registered_nodes(nodes_list):
    try:
        with open(NODES_FILE, "w") as f:
            json.dump(nodes_list, f, indent=4)
    except Exception as e:
        print("Gagal menyimpan nodes:", e)
