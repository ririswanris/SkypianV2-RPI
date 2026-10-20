import tkinter as tk
import os
import serial
import threading
import queue
import json
import time
from datetime import datetime
from PIL import Image, ImageTk
from config import *
from tab_dashboard import DashboardTab
from tab_sensor_node import SensorNodeTab
from tab_kendali import KendaliTab
from tab_setting import SettingTab
import socket

class SkypianInterface:
    def __init__(self, root):
        self.root = root
        self.root.title("Skypian Smart Farming Gateway")
        self.root.geometry("800x480") 
        self.root.configure(bg=C_BG)

        # Status koneksi internet (diperbarui di background thread tanpa memblokir GUI)
        self.is_network_connected = False
        self.start_background_network_monitor()

        # Logging berkala ke Firebase setiap 5 detik
        self.root.after(5000, self.firebase_logging_loop)

        # Listener Firebase Realtime di background thread
        def start_firebase_listener():
            try:
                import firebase_sync
                firebase_sync.listen_web_commands(self.on_web_command_received)
                firebase_sync.listen_web_schedules(self.on_web_schedules_received)
            except Exception as e:
                print("[Firebase Error] Gagal memulai listener Firebase:", e)
                
        threading.Thread(target=start_firebase_listener, daemon=True).start()

        # Ikon Title Bar
        try:
            icon_path = get_asset_path("skypian2.pn.png")
            if os.path.exists(icon_path):
                ico_img = Image.open(icon_path)
                self.title_icon = ImageTk.PhotoImage(ico_img)
                self.root.iconphoto(True, self.title_icon)
        except Exception as e:
            print("[UI Warning] Gagal memuat ikon title bar:", e)

        self.fonts = setup_fonts()
        saved_cfg = load_settings()
        self.connected_port = saved_cfg.get("last_port")
        self.station_id = saved_cfg.get("station_id") or "sky001"

        self.history_data = {
            "Rata-rata Soil": [0], "Rata-rata pH Tanah": [0.0],
            "Suhu Air": [0.0], "pH Air": [0.0], "TDS Air": [0],
            "Suhu & Kelembapan Udara": {"suhu": [0.0], "kelembapan": [0]}
        }

        self.live_node_data = {}
        self.serial_tx_queue = queue.Queue()

        self.actuator_states = {
            "PUMP_NUTRISI": False, "EXHAUST_FAN": False,
            "FAN_SIRKULER": False, "FOGGER": False,
            "CUSTOM_1": False, "CUSTOM_2": False
        }
        self.auto_mode_active = False 
        
        self.tds_active_until = 0
        self.tds_cooldown_until = 0
        self.last_checked_minute = ""

        # Manajemen Tab (Single-Render / Cached Tabs)
        self.tab_instances = {}
        self.active_tab = None

        self.setup_ui()

        # Thread pembaca serial hardware
        self.serial_running = True
        self.serial_thread = threading.Thread(target=self.background_serial_reader, daemon=True)
        self.serial_thread.start()

        self.start_automation_loop()

    # ---------------------------------------------------------
    # MONITORING JARINGAN NON-BLOCKING (BACKGROUND THREAD)
    # ---------------------------------------------------------
    def start_background_network_monitor(self):
        """Mengecek koneksi internet di thread terpisah agar TIDAK MEMBEKUKAN GUI Pi Zero"""
        def _net_worker():
            while True:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(2.5)
                    s.connect(("8.8.8.8", 53))
                    s.close()
                    self.is_network_connected = True
                except Exception:
                    self.is_network_connected = False
                time.sleep(5.0)

        t = threading.Thread(target=_net_worker, daemon=True)
        t.start()

    # ---------------------------------------------------------
    # FUNGSI RESPONS DARI WEBSITE (WEB -> GATEWAY)
    # ---------------------------------------------------------
    def on_web_command_received(self, event):
        """Terpicu instan saat tombol di Website ditekan"""
        try:
            print(f"[Firebase] Command diterima: path='{event.path}', data={event.data}")
            
            if event.path == '/' and isinstance(event.data, dict):
                return 

            actuator_id = ""
            new_state = False

            if event.path != '/':
                actuator_id = event.path.replace('/', '')
                raw_state = event.data
                if isinstance(raw_state, str):
                    new_state = True if raw_state.upper() == "ON" else False
                else:
                    new_state = bool(raw_state)
            else:
                return

            if actuator_id not in self.actuator_states:
                return

            print(f"[Web Command] Eksekusi: {actuator_id} -> {new_state}")
            self.actuator_states[actuator_id] = new_state

            if getattr(self, 'connected_port', None):
                val = "ON" if new_state else "OFF"
                self.send_serial_command(f"CTRL,{actuator_id},{val}\n")
                
            if hasattr(self, 'active_tab') and self.active_tab:
                if hasattr(self.active_tab, 'update_all_manual_ui'):
                    self.root.after(0, self.active_tab.update_all_manual_ui)
                    
        except Exception as e:
            print(f"[Error] on_web_command_received: {e}")

    def on_web_schedules_received(self, web_schedules_data):
        """Terpicu instan saat Website merubah konfigurasi Jadwal"""
        print("[Schedule] Pembaruan Jadwal Diterima dari Website!")
        try:
            with open("schedules.json", "w") as f:
                json.dump(web_schedules_data, f, indent=4)
                
            if hasattr(self, 'active_tab'):
                if isinstance(self.active_tab, KendaliTab):
                    self.active_tab.schedules = web_schedules_data
                    self.root.after(0, self.active_tab.refresh_table)
        except Exception as e:
            print("[Schedule Error] Gagal sinkronisasi jadwal web ke lokal:", e)

    def firebase_logging_loop(self):
        import firebase_sync
        from config import load_registered_nodes

        if getattr(self, 'connected_port', None):
            # 1. LOG DASHBOARD
            try:
                avg_soil = sum(self.history_data["Rata-rata Soil"][-5:]) // 5 if self.history_data["Rata-rata Soil"] else 0
                avg_ph = round(sum(self.history_data["Rata-rata pH Tanah"][-5:]) / 5, 1) if self.history_data["Rata-rata pH Tanah"] else 0.0
                dashboard_payload = {
                    "rata_rata_soil": avg_soil, "rata_rata_ph_tanah": avg_ph,
                    "suhu_air": self.history_data["Suhu Air"][-1] if self.history_data["Suhu Air"] else 0,
                    "ph_air": self.history_data["pH Air"][-1] if self.history_data["pH Air"] else 0,
                    "tds_air": self.history_data["TDS Air"][-1] if self.history_data["TDS Air"] else 0,
                    "suhu_udara": self.history_data["Suhu & Kelembapan Udara"]["suhu"][-1] if self.history_data["Suhu & Kelembapan Udara"]["suhu"] else 0,
                    "kelembapan_udara": self.history_data["Suhu & Kelembapan Udara"]["kelembapan"][-1] if self.history_data["Suhu & Kelembapan Udara"]["kelembapan"] else 0
                }
                firebase_sync.push_dashboard_log(dashboard_payload)
            except Exception: pass

            # 2. LOG SENSOR NODES
            try:
                firebase_sync.push_nodes_log(load_registered_nodes(), self.live_node_data)
            except Exception: pass

        self.root.after(5000, self.firebase_logging_loop)

    def update_relay_status_lokal(self, actuator_id, state):
        if self.actuator_states.get(actuator_id) != state:
            self.actuator_states[actuator_id] = state
            
            if getattr(self, 'connected_port', None):
                self.send_serial_command(f"RELAY,{actuator_id},{state}\n")
            
            import firebase_sync
            firebase_sync.push_actuator_state({
                "mode": getattr(self, 'auto_mode_active', False) and "Otomatis" or "Manual",
                "states": self.actuator_states
            })
            print(f"[Actuator] Update Lokal Instan: {actuator_id} -> {state} terkirim ke Firebase!")

    # ---------------------------------------------------------
    # SETUP UI & SINGLE-RENDER TAB MANAGEMENT (Ringan untuk Pi Zero)
    # ---------------------------------------------------------
    def setup_ui(self):
        self.sidebar = tk.Frame(self.root, bg="#ffffff", width=140, highlightbackground=C_BORDER, highlightthickness=1)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        logo_container = tk.Frame(self.sidebar, bg="#ffffff")
        logo_container.pack(fill="x", padx=10, pady=(15, 10))

        # Render Logo Skypian (cache logo di memori)
        try:
            logo_path = get_asset_path("skypian2.pn.png")
            if os.path.exists(logo_path):
                raw_img = Image.open(logo_path)
                raw_img.thumbnail((110, 60), Image.Resampling.BILINEAR)
                self.logo_img = ImageTk.PhotoImage(raw_img)
                tk.Label(logo_container, image=self.logo_img, bg="#ffffff").pack(anchor="center")
            else:
                tk.Label(logo_container, text="SKYPIAN", font=("Segoe UI", 14, "bold"), bg="#ffffff", fg=C_ACCENT).pack(anchor="center")
        except Exception:
            tk.Label(logo_container, text="SKYPIAN", font=("Segoe UI", 14, "bold"), bg="#ffffff", fg=C_ACCENT).pack(anchor="center")

        tk.Frame(self.sidebar, bg=C_BORDER, height=1).pack(fill="x", padx=10, pady=(0, 10))

        btn_opts = {"font": ("Segoe UI", 10, "bold"), "anchor": "center", "relief": "flat", "pady": 14, "cursor": "hand2"}
        
        self.btn_dashboard = tk.Button(self.sidebar, text="Dashboard", **btn_opts, command=lambda: self.switch_tab("dashboard"))
        self.btn_dashboard.pack(fill="x", padx=8, pady=4)

        self.btn_sensor_node = tk.Button(self.sidebar, text="Sensor Node", **btn_opts, command=lambda: self.switch_tab("sensor_node"))
        self.btn_sensor_node.pack(fill="x", padx=8, pady=4)

        self.btn_kendali = tk.Button(self.sidebar, text="Kendali", **btn_opts, command=lambda: self.switch_tab("kendali"))
        self.btn_kendali.pack(fill="x", padx=8, pady=4)

        self.btn_setting = tk.Button(self.sidebar, text="Pengaturan", **btn_opts, command=lambda: self.switch_tab("setting"))
        self.btn_setting.pack(fill="x", padx=8, pady=4)

        self.content_container = tk.Frame(self.root, bg=C_BG)
        self.content_container.pack(side="right", fill="both", expand=True)

        # Inisialisasi awal pada tab Dashboard
        self.switch_tab("dashboard")

    def switch_tab(self, tab_name):
        """
        STRUKTUR SINGLE-RENDER / TAB CACHING:
        Tab tidak dihancurkan (destroy) saat berpindah halaman.
        Cukup sembunyikan dengan pack_forget() dan tampilkan dengan pack().
        Widget Dashboard di-render TEPAT 1 KALI saja. Nol lag saat berpindah tab!
        """
        btn_map = {
            "dashboard": self.btn_dashboard,
            "sensor_node": self.btn_sensor_node,
            "kendali": self.btn_kendali,
            "setting": self.btn_setting
        }

        # Update warna tombol sidebar
        for name, btn in btn_map.items():
            if name == tab_name:
                btn.config(bg=C_ACCENT, fg="#ffffff")
            else:
                btn.config(bg="#ffffff", fg=C_INACTIVE)

        # Sembunyikan tab lain yang sedang aktif
        for name, tab_obj in self.tab_instances.items():
            if name != tab_name and hasattr(tab_obj, 'frame') and tab_obj.frame.winfo_exists():
                tab_obj.frame.pack_forget()

        # Inisialisasi tab jika baru pertama kali dibuka (Lazy Loading)
        if tab_name not in self.tab_instances:
            if tab_name == "dashboard":
                self.tab_instances["dashboard"] = DashboardTab(self.content_container, self)
            elif tab_name == "sensor_node":
                self.tab_instances["sensor_node"] = SensorNodeTab(self.content_container, self)
            elif tab_name == "kendali":
                self.tab_instances["kendali"] = KendaliTab(self.content_container, self)
            elif tab_name == "setting":
                self.tab_instances["setting"] = SettingTab(self.content_container, self)

        # Tampilkan tab yang dipilih
        target_tab = self.tab_instances[tab_name]
        self.active_tab = target_tab
        if hasattr(target_tab, 'frame') and target_tab.frame.winfo_exists():
            target_tab.frame.pack(fill="both", expand=True)

        # Trigger event aktivasi tab jika ada
        if hasattr(target_tab, 'on_tab_activated'):
            target_tab.on_tab_activated()

    def send_serial_command(self, cmd):
        self.serial_tx_queue.put(cmd)

    # --- FUNGSI MESIN OTOMATISASI (JADWAL & TDS) ---
    def push_actuator_to_firebase_now(self):
        import firebase_sync
        firebase_sync.push_actuator_state({
            "mode": "Otomatis" if self.auto_mode_active else "Manual",
            "states": self.actuator_states
        })
        print("[Actuator] Update Lokal Instan Terkirim ke Web")

    def start_automation_loop(self):
        self.process_automation()
        self.root.after(1000, self.start_automation_loop)

    def process_automation(self):
        if not self.auto_mode_active:
            return

        current_time = time.time()
        now = datetime.now()
        current_hm = now.strftime("%H:%M")
        
        days_map = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
        current_day = days_map[now.weekday()]

        # 1. PENJADWALAN OTOMATIS (Timer)
        if self.last_checked_minute != current_hm:
            self.last_checked_minute = current_hm
            
            try:
                with open("schedules.json", "r") as f:
                    schedules = json.load(f)
            except: schedules = []
            
            for sched in schedules:
                if sched.get("everyday") or current_day in sched.get("days", []):
                    act_id = sched["actuator"]
                    
                    if current_hm == sched.get("on"):
                        if not self.actuator_states.get(act_id, False):
                            self.actuator_states[act_id] = True
                            self.send_serial_command(f"CTRL,{act_id},ON\n")
                            self.update_tab_kendali_ui()
                            self.push_actuator_to_firebase_now()
                            
                    elif current_hm == sched.get("off"):
                        if self.actuator_states.get(act_id, False):
                            self.actuator_states[act_id] = False
                            self.send_serial_command(f"CTRL,{act_id},OFF\n")
                            self.update_tab_kendali_ui()
                            self.push_actuator_to_firebase_now()

        # 2. LOGIKA TDS OTOMATIS (Pompa Nutrisi)
        try:
            with open("tds_cfg.json", "r") as f:
                tds_cfg = json.load(f)
        except: tds_cfg = {"batas_bawah": 800, "durasi_on": 30, "durasi_jeda": 5}

        # Jika pompa sedang menyala, cek apakah waktunya mati (Habis Durasi ON)
        if self.actuator_states.get("PUMP_NUTRISI", False) and self.tds_active_until > 0:
            if current_time >= self.tds_active_until:
                self.actuator_states["PUMP_NUTRISI"] = False
                self.send_serial_command("CTRL,PUMP_NUTRISI,OFF\n")
                self.tds_active_until = 0
                self.tds_cooldown_until = current_time + (tds_cfg.get("durasi_jeda", 5) * 60)
                self.update_tab_kendali_ui()
                self.push_actuator_to_firebase_now()

        # Jika pompa mati, cek apakah jeda sudah habis dan TDS masih di bawah batas
        if not self.actuator_states.get("PUMP_NUTRISI", False) and self.tds_active_until == 0:
            if current_time >= self.tds_cooldown_until:
                current_tds = 0
                if self.history_data["TDS Air"]:
                    current_tds = self.history_data["TDS Air"][-1]
                
                if current_tds > 0 and current_tds < tds_cfg.get("batas_bawah", 800):
                    self.actuator_states["PUMP_NUTRISI"] = True
                    self.send_serial_command("CTRL,PUMP_NUTRISI,ON\n")
                    self.tds_active_until = current_time + tds_cfg.get("durasi_on", 30)
                    self.update_tab_kendali_ui()
                    self.push_actuator_to_firebase_now()

    def update_tab_kendali_ui(self):
        if isinstance(self.active_tab, KendaliTab):
            self.root.after(0, self.active_tab.update_all_manual_ui)

    # ---------------------------------------------------------
    # FUNGSI SERIAL READER & PARSING TANGGUH (Mengatasi Lag & Bug Offline)
    # ---------------------------------------------------------
    def background_serial_reader(self):
        while self.serial_running:
            port = getattr(self, 'connected_port', None)
            if not port:
                time.sleep(1.0)
                continue
            
            try:
                with serial.Serial(port, 115200, timeout=0.1) as ser:
                    self.serial_obj = ser
                    time.sleep(1.5) 
                    
                    # Daftarkan semua node terdaftar ke ESP32 Master
                    nodes = load_registered_nodes()
                    for node in nodes:
                        cmd = f"ADD_NODE,{node['mac']},{node['node_id']}\n"
                        ser.write(cmd.encode('utf-8'))
                        time.sleep(0.05)
                    ser.reset_input_buffer()

                    while self.serial_running and self.connected_port == port:
                        # Kirim antrean perintah serial
                        while not self.serial_tx_queue.empty():
                            cmd_to_send = self.serial_tx_queue.get()
                            ser.write(cmd_to_send.encode('utf-8'))
                            ser.flush()

                        # Kuras dan baca seluruh antrean buffer serial agar tidak terjadi lag data
                        has_data = False
                        while ser.in_waiting:
                            has_data = True
                            raw_line = ser.readline()
                            if not raw_line:
                                break
                            line = raw_line.decode('utf-8', errors='ignore').strip()
                            if not line:
                                continue

                            # Ekstraksi substring JSON yang tangguh
                            # (Menangani jika ada teks debug atau karakter tambahan di baris serial)
                            start_idx = line.find('{')
                            end_idx = line.rfind('}')
                            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                                json_str = line[start_idx:end_idx + 1]
                                try:
                                    data = json.loads(json_str)
                                    self.process_incoming_packet(data)
                                except json.JSONDecodeError:
                                    pass

                        if not has_data:
                            time.sleep(0.05)
            except Exception as e:
                print("[Serial Error] Terputus / Gangguan:", e)
                time.sleep(2.0)

    def process_incoming_packet(self, data):
        """
        Memproses paket data serial dengan fitur Self-Healing MAC Pairing:
        Jika ESP32 mengirimkan 'UNKNOWN_NODE', Python otomatis memetakan kembali MAC
        ke node_id yang terdaftar dan mengirim ulang ADD_NODE ke ESP32.
        """
        if not isinstance(data, dict):
            return

        node_id = data.get("node_id")
        raw_mac = data.get("mac") or data.get("mac_address")
        norm_mac = raw_mac.strip().upper() if raw_mac else ""

        # FITUR PERBAIKAN BUG OFFLINE:
        # Jika node_id bernilai UNKNOWN_NODE atau kosong, cari berdasarkan MAC Address
        if not node_id or node_id == "UNKNOWN_NODE" or node_id == "null":
            if norm_mac:
                for reg_node in load_registered_nodes():
                    if reg_node.get("mac", "").strip().upper() == norm_mac:
                        node_id = reg_node.get("node_id")
                        # Kirim perintah sinkronisasi ulang ke ESP32 Master
                        self.send_serial_command(f"ADD_NODE,{norm_mac},{node_id}\n")
                        print(f"[Self-Healing] MAC {norm_mac} dipetakan kembali ke {node_id}")
                        break

        # Jika paket berasal dari Sensor Node yang terdaftar
        if node_id and node_id != "UNKNOWN_NODE":
            # Normalisasi jika data node tidak bersarang (flat JSON)
            if "node" not in data or not isinstance(data.get("node"), dict):
                data["node"] = {
                    "soil_1": data.get("soil_1", 0),
                    "soil_2": data.get("soil_2", 0),
                    "soil_3": data.get("soil_3", 0),
                    "soil_4": data.get("soil_4", 0),
                    "ph_tanah": data.get("ph_tanah", 0.0)
                }

            self.live_node_data[node_id] = {
                "packet": data,
                "last_seen": time.time()
            }
            
            # Hitung agregasi data tanah untuk dashboard
            current_time = time.time()
            total_soil = 0
            total_ph = 0
            active_node_count = 0

            for n_id, entry in self.live_node_data.items():
                # Gunakan timeout 45 detik agar status tidak kelap-kelip offline
                if (current_time - entry.get("last_seen", 0)) <= NODE_OFFLINE_TIMEOUT:
                    node_vals = entry.get("packet", {}).get("node", {})
                    s1 = node_vals.get("soil_1", 0)
                    s2 = node_vals.get("soil_2", 0)
                    s3 = node_vals.get("soil_3", 0)
                    s4 = node_vals.get("soil_4", 0)
                    node_avg_soil = (s1 + s2 + s3 + s4) / 4.0
                    
                    total_soil += node_avg_soil
                    total_ph += node_vals.get("ph_tanah", 0.0)
                    active_node_count += 1

            if active_node_count > 0:
                avg_all_soil = int(total_soil / active_node_count)
                avg_all_ph = round(total_ph / active_node_count, 1)

                self.history_data["Rata-rata Soil"].append(avg_all_soil)
                self.history_data["Rata-rata pH Tanah"].append(avg_all_ph)
                
                if len(self.history_data["Rata-rata Soil"]) > 20: self.history_data["Rata-rata Soil"].pop(0)
                if len(self.history_data["Rata-rata pH Tanah"]) > 20: self.history_data["Rata-rata pH Tanah"].pop(0)

        # Periksa data sensor lokal dari Master (Suhu Air, pH Air, TDS, Udara)
        local_vals = data.get("local", {})
        if not local_vals and any(k in data for k in ["air_temp", "air_ph", "air_tds", "udara_temp", "udara_hum"]):
            local_vals = data

        if local_vals:
            if "air_temp" in local_vals:
                self.history_data["Suhu Air"].append(local_vals.get("air_temp", 25.8))
            if "air_ph" in local_vals:
                self.history_data["pH Air"].append(local_vals.get("air_ph", 7.1))
            if "air_tds" in local_vals:
                self.history_data["TDS Air"].append(int(local_vals.get("air_tds", 650)))
            if "udara_temp" in local_vals:
                self.history_data["Suhu & Kelembapan Udara"]["suhu"].append(local_vals.get("udara_temp", 28.5))
            if "udara_hum" in local_vals:
                self.history_data["Suhu & Kelembapan Udara"]["kelembapan"].append(local_vals.get("udara_hum", 65))

            for key in ["Suhu Air", "pH Air", "TDS Air"]:
                if len(self.history_data[key]) > 20: self.history_data[key].pop(0)
            if len(self.history_data["Suhu & Kelembapan Udara"]["suhu"]) > 20:
                self.history_data["Suhu & Kelembapan Udara"]["suhu"].pop(0)
                self.history_data["Suhu & Kelembapan Udara"]["kelembapan"].pop(0)

        # Perbarui tampilan jika Tab Sensor Node sedang aktif
        if isinstance(self.active_tab, SensorNodeTab):
            self.root.after(0, self.active_tab.update_live_data)

    def on_port_connected(self):
        self.connected_port = load_settings().get("last_port")
        if isinstance(self.active_tab, SensorNodeTab):
            self.active_tab.render()

if __name__ == "__main__":
    root = tk.Tk()
    app = SkypianInterface(root)
    root.mainloop()
