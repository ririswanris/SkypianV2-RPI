import firebase_admin
from firebase_admin import credentials, db
import time
from datetime import datetime
import threading
from config import NODE_OFFLINE_TIMEOUT

# Pastikan nama file ini sesuai dengan yang ada di folder proyek Anda
CRED_FILE = "skypianlog-firebase-adminsdk-fbsvc-316c98cf50.json" 

if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(CRED_FILE)
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://skypianlog-default-rtdb.asia-southeast1.firebasedatabase.app/'
        })
        print("✅ Firebase berhasil terhubung ke SkypianLog!")
    except Exception as e:
        print(f"❌ Gagal menginisialisasi Firebase: {e}")

# ==========================================
# 1. SINKRONISASI SENSOR & DASHBOARD (DELAY 5 DETIK)
# ==========================================
def _sync_dashboard(data):
    try:
        ref = db.reference('SkypianLog/DashboardLogs')
        data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ref.push(data)
    except Exception: pass

def _sync_nodes(registered_nodes, live_node_data):
    try:
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for node in registered_nodes:
            node_id = node.get("node_id")
            raw_mac = node.get("mac", "")
            mac_key = raw_mac.replace(":", "_")
            name = node.get("name", node_id)
            
            live_entry = live_node_data.get(node_id, {})
            packet = live_entry.get("packet", {})
            vals = packet.get("node") if isinstance(packet.get("node"), dict) else packet
            last_seen = live_entry.get("last_seen", 0)
            
            is_online = (time.time() - last_seen) <= NODE_OFFLINE_TIMEOUT if last_seen else False
            
            if is_online and vals:
                info_ref = db.reference(f'SkypianLog/SensorNodes/{mac_key}/Info')
                info_ref.update({"nama_node": name, "mac_address": raw_mac, "status": "Online", "last_update": timestamp_str})
                
                log_ref = db.reference(f'SkypianLog/SensorNodes/{mac_key}/Logs')
                log_payload = {
                    "soil_1": vals.get("soil_1", 0), "soil_2": vals.get("soil_2", 0),
                    "soil_3": vals.get("soil_3", 0), "soil_4": vals.get("soil_4", 0),
                    "ph_tanah": vals.get("ph_tanah", 0.0), "timestamp": timestamp_str
                }
                log_ref.push(log_payload)
            else:
                info_ref = db.reference(f'SkypianLog/SensorNodes/{mac_key}/Info')
                info_ref.update({"nama_node": name, "mac_address": raw_mac, "status": "Offline", "last_update": timestamp_str})
    except Exception: pass

def push_dashboard_log(data):
    threading.Thread(target=_sync_dashboard, args=(data,), daemon=True).start()

def push_nodes_log(registered_nodes, live_node_data):
    threading.Thread(target=_sync_nodes, args=(registered_nodes, live_node_data), daemon=True).start()

# ==========================================
# 2. SINKRONISASI AKTUATOR KONTROL (INSTAN / REAL-TIME)
# ==========================================
def _sync_actuators(actuator_data):
    """Menimpa data secara instan tanpa membuat log panjang"""
    try:
        ref = db.reference('SkypianLog/ActuatorStatus')
        actuator_data['last_update'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ref.set(actuator_data)
    except Exception as e: 
        print("Firebase push error:", e)

def push_actuator_state(actuator_data):
    threading.Thread(target=_sync_actuators, args=(actuator_data,), daemon=True).start()

_listener_actuator = None
_listener_schedule = None

def listen_web_commands(callback_function):
    global _listener_actuator
    def stream_handler(event):
        if event.data is not None:
            callback_function(event)
            
    try:
        ref = db.reference('SkypianLog/ActuatorStatus/states')
        _listener_actuator = ref.listen(stream_handler)
        print("✅ Listener Web Control Aktif!")
    except Exception as e:
        print(f"❌ Listener Control error: {e}")

# ==========================================
# 3. SINKRONISASI JADWAL OTOMATIS (SCHEDULES)
# ==========================================
def _sync_schedules(schedules_data):
    """Mengunggah (set) daftar jadwal ke Firebase agar tampil di Web"""
    try:
        ref = db.reference('SkypianLog/Schedules')
        ref.set(schedules_data)
    except Exception as e:
        print("Firebase schedule push error:", e)

def push_schedules(schedules_data):
    threading.Thread(target=_sync_schedules, args=(schedules_data,), daemon=True).start()

def listen_web_schedules(callback_function):
    global _listener_schedule  
    def stream_handler(event):
        if event.data is not None:
            callback_function(event.data)
            
    try:
        ref = db.reference('SkypianLog/Schedules')
        _listener_schedule = ref.listen(stream_handler)
        print("✅ Listener Web Schedules Aktif!")
    except Exception as e:
        print(f"❌ Listener Schedule error: {e}")
