import tkinter as tk
from tkinter import ttk
import json
import os
import time
from config import *
from ui_components import ScrollableFrame

SCHEDULES_FILE = "schedules.json"
TDS_CFG_FILE = "tds_cfg.json"
ACTUATOR_CFG_FILE = "actuator_cfg.json"

class KendaliTab:
    def __init__(self, parent_container, app_instance):
        self.container = parent_container
        self.app = app_instance
        self.fonts = app_instance.fonts
        
        self.current_mode = "MANUAL" 
        self.manual_widgets = {}
        
        self.actuators = self.load_actuator_config()
        self.tds_config = self.load_tds_setting()
        self.schedules = self.load_schedules()
        
        self.frame = tk.Frame(self.container, bg=C_BG)
        self.frame.pack(fill="both", expand=True)

        self.setup_styles()
        self.render()
        self.auto_sync_ui_loop()

    def load_actuator_config(self):
        # Default name & deskripsi (6 Aktuator)
        defaults = {
            "PUMP_NUTRISI": "Pompa Nutrisi",
            "EXHAUST_FAN": "Exhaust Fan",
            "FAN_SIRKULER": "Fan Sirkuler",
            "FOGGER": "Fogger",
            "CUSTOM_1": "Custom 1",
            "CUSTOM_2": "Custom 2"
        }
        descs = {
            "PUMP_NUTRISI": "Kontrol aliran nutrisi (TDS)",
            "EXHAUST_FAN": "Sirkulasi pembuangan udara panas",
            "FAN_SIRKULER": "Meratakan suhu ruangan",
            "FOGGER": "Meningkatkan kelembapan instan",
            "CUSTOM_1": "Aktuator Tambahan (Fleksibel)",
            "CUSTOM_2": "Aktuator Tambahan (Fleksibel)"
        }
        
        try:
            if os.path.exists(ACTUATOR_CFG_FILE):
                with open(ACTUATOR_CFG_FILE, "r") as f:
                    saved = json.load(f)
                    for k in defaults.keys():
                        if k in saved and saved[k].strip() != "":
                            defaults[k] = saved[k]
        except: pass

        return [
            ("PUMP_NUTRISI", defaults["PUMP_NUTRISI"], descs["PUMP_NUTRISI"]),
            ("EXHAUST_FAN", defaults["EXHAUST_FAN"], descs["EXHAUST_FAN"]),
            ("FAN_SIRKULER", defaults["FAN_SIRKULER"], descs["FAN_SIRKULER"]),
            ("FOGGER", defaults["FOGGER"], descs["FOGGER"]),
            ("CUSTOM_1", defaults["CUSTOM_1"], descs["CUSTOM_1"]),
            ("CUSTOM_2", defaults["CUSTOM_2"], descs["CUSTOM_2"])
        ]

    def setup_styles(self):
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
            
        style.configure("Treeview", background="#ffffff", foreground=C_TEXT, rowheight=36, font=("Segoe UI", 11), fieldbackground="#ffffff", borderwidth=0)
        style.configure("Treeview.Heading", font=("Segoe UI", 11, "bold"), background="#f4f6f9", foreground=C_TEXT)
        style.map("Treeview", background=[("selected", "#e5f0ff")], foreground=[("selected", C_ACCENT)])
        style.configure("TCombobox", arrowsize=25, padding=8)
        self.app.root.option_add('*TCombobox*Listbox.font', ('Segoe UI', 14))

    def load_tds_setting(self):
        default_cfg = {"batas_bawah": 800, "durasi_on": 30, "durasi_jeda": 5}
        try:
            if os.path.exists(TDS_CFG_FILE):
                with open(TDS_CFG_FILE, "r") as f:
                    data = json.load(f)
                    return {"batas_bawah": data.get("batas_bawah", 800), "durasi_on": data.get("durasi_on", 30), "durasi_jeda": data.get("durasi_jeda", 5)}
        except: pass
        return default_cfg

    def save_tds_setting(self, batas, dur_on, dur_jeda):
        self.tds_config = {"batas_bawah": batas, "durasi_on": dur_on, "durasi_jeda": dur_jeda}
        try:
            with open(TDS_CFG_FILE, "w") as f:
                json.dump(self.tds_config, f, indent=4)
        except: pass

    def load_schedules(self):
        try:
            if os.path.exists(SCHEDULES_FILE):
                with open(SCHEDULES_FILE, "r") as f:
                    return json.load(f)
        except: pass
        return []

    def save_schedules(self):
        # 1. Simpan ke lokal (schedules.json)
        try:
            with open(SCHEDULES_FILE, "w") as f:
                json.dump(self.schedules, f, indent=4)
        except Exception as e: 
            print("Gagal simpan jadwal lokal:", e)
            
        # 2. Push jadwal terbaru ke Firebase (agar sinkron dengan web)
        if getattr(self.app, 'is_network_connected', False):
            try:
                import firebase_sync
                firebase_sync.push_schedules(self.schedules)
                print("⚡ Jadwal baru berhasil di-push ke Web!")
            except Exception as e:
                print("Gagal push jadwal ke firebase:", e)

    def center_popup(self, popup, w, h):
        self.app.root.update_idletasks()
        popup.update_idletasks()
        root_w = self.app.root.winfo_width() if self.app.root.winfo_width() > 100 else 800
        root_h = self.app.root.winfo_height() if self.app.root.winfo_height() > 100 else 480
        x = self.app.root.winfo_x() + (root_w - w) // 2
        y = self.app.root.winfo_y() + (root_h - h) // 2
        popup.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    def show_centered_message(self, title, message, msg_type="info"):
        popup = tk.Toplevel(self.app.root)
        popup.title(title)
        popup.configure(bg=C_BG)
        popup.transient(self.app.root)
        self.center_popup(popup, 360, 160)
        popup.resizable(False, False)

        content = tk.Frame(popup, bg="#ffffff", highlightbackground=C_BORDER, highlightthickness=1)
        content.pack(fill="both", expand=True, padx=8, pady=8)
        color = C_ONLINE if msg_type == "info" else C_OFFLINE if msg_type == "error" else "#ff9500"
        tk.Label(content, text=message, font=("Segoe UI", 10), bg="#ffffff", fg=C_TEXT, justify="center", wraplength=320).pack(expand=True, padx=12, pady=12)
        
        def close_msg():
            safe_grab_release(popup)
            popup.destroy()

        tk.Button(content, text="OK", font=("Segoe UI", 9, "bold"), bg=color, fg="#ffffff", relief="flat", width=10, pady=4, cursor="hand2", command=close_msg).pack(pady=(0, 10))
        popup.protocol("WM_DELETE_WINDOW", close_msg)
        popup.lift()
        safe_grab_set(popup)
        self.app.root.wait_window(popup)

    def ask_yes_no(self, title, message):
        self.yes_no_result = False
        popup = tk.Toplevel(self.app.root)
        popup.title(title)
        popup.configure(bg=C_BG)
        popup.transient(self.app.root)
        self.center_popup(popup, 360, 160)
        popup.resizable(False, False)
        
        content = tk.Frame(popup, bg="#ffffff", highlightbackground=C_BORDER, highlightthickness=1)
        content.pack(fill="both", expand=True, padx=8, pady=8)
        tk.Label(content, text=message, font=("Segoe UI", 10, "bold"), bg="#ffffff", fg=C_TEXT, justify="center", wraplength=320).pack(expand=True, padx=12, pady=12)
        
        btn_frame = tk.Frame(content, bg="#ffffff")
        btn_frame.pack(pady=(0, 10))
        
        def on_yes(): self.yes_no_result = True; popup.destroy()
        def on_no(): self.yes_no_result = False; popup.destroy()
            
        tk.Button(btn_frame, text="Ya", font=("Segoe UI", 9, "bold"), bg=C_OFFLINE, fg="#ffffff", relief="flat", width=10, pady=4, command=on_yes).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Batal", font=("Segoe UI", 9), bg=C_INACTIVE, fg="#ffffff", relief="flat", width=10, pady=4, command=on_no).pack(side="left", padx=5)
        self.app.root.wait_window(popup)
        return self.yes_no_result

    def render(self):
        for widget in self.frame.winfo_children(): widget.destroy()

        self.main_frame = tk.Frame(self.frame, bg=C_BG)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=15)

        header_frame = tk.Frame(self.main_frame, bg=C_BG)
        header_frame.pack(fill="x", pady=(0, 10))

        tk.Label(header_frame, text="KENDALI SISTEM", font=self.fonts["title"], bg=C_BG, fg=C_TEXT).pack(side="left")

        switch_frame = tk.Frame(header_frame, bg="#e5e5ea", padx=3, pady=3)
        switch_frame.pack(side="right")

        self.btn_manual = tk.Button(switch_frame, text="MODE MANUAL", font=("Segoe UI", 9, "bold"), width=15, relief="flat", cursor="hand2", command=lambda: self.switch_mode("MANUAL"))
        self.btn_manual.pack(side="left", fill="y")

        self.btn_auto = tk.Button(switch_frame, text="MODE OTOMATIS", font=("Segoe UI", 9, "bold"), width=15, relief="flat", cursor="hand2", command=lambda: self.switch_mode("OTOMATIS"))
        self.btn_auto.pack(side="left", fill="y")

        self.scroll_container = ScrollableFrame(self.main_frame)
        self.scroll_container.pack(fill="both", expand=True)

        self.switch_mode(self.current_mode)

    def switch_mode(self, mode):
        self.current_mode = mode
        if mode == "MANUAL":
            self.btn_manual.config(bg="#ffffff", fg=C_ACCENT)
            self.btn_auto.config(bg="#e5e5ea", fg=C_INACTIVE)
        else:
            self.btn_manual.config(bg="#e5e5ea", fg=C_INACTIVE)
            self.btn_auto.config(bg="#ffffff", fg=C_ACCENT)

        for widget in self.scroll_container.scrollable_frame.winfo_children():
            widget.destroy()
        self.manual_widgets.clear()

        if mode == "MANUAL": self.render_manual_view()
        else: self.render_otomatis_view()

    def render_manual_view(self):
        if self.app.auto_mode_active:
            warn_frm = tk.Frame(self.scroll_container.scrollable_frame, bg="#fff3cd", highlightbackground="#ffeeba", highlightthickness=1)
            warn_frm.pack(fill="x", pady=(5, 5))
            tk.Label(warn_frm, text="⚠️ Sistem sedang dalam Mode Master Otomatis. Tombol kontrol manual dinonaktifkan.", font=("Segoe UI", 9, "bold"), bg="#fff3cd", fg="#856404").pack(pady=8)

        grid_frame = tk.Frame(self.scroll_container.scrollable_frame, bg=C_BG)
        grid_frame.pack(fill="both", expand=True, pady=5)
        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)

        for index, act_info in enumerate(self.actuators):
            self.create_manual_card(grid_frame, act_info, index // 2, index % 2)
            
        self.update_all_manual_ui()

    def create_manual_card(self, parent, act_info, row, col):
        act_id, name, desc = act_info
        card = tk.Frame(parent, bg="#ffffff", highlightbackground=C_BORDER, highlightthickness=2)
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

        header = tk.Frame(card, bg="#ffffff")
        header.pack(fill="x", padx=15, pady=(15, 5))
        tk.Label(header, text=name, font=("Segoe UI", 11, "bold"), bg="#ffffff", fg=C_TEXT).pack(anchor="w")
        tk.Label(header, text=desc, font=("Segoe UI", 9), bg="#ffffff", fg=C_INACTIVE).pack(anchor="w", pady=(0, 5))
        
        tk.Frame(card, bg=C_BORDER, height=1).pack(fill="x", padx=15, pady=5)

        content = tk.Frame(card, bg="#ffffff")
        content.pack(fill="both", expand=True, padx=15, pady=15)

        status_frame = tk.Frame(content, bg="#ffffff")
        status_frame.pack(side="left")
        lbl_dot = tk.Label(status_frame, text="●", font=("Segoe UI", 12), bg="#ffffff")
        lbl_dot.pack(side="left", padx=(0, 5))
        lbl_status = tk.Label(status_frame, text="MATI", font=("Segoe UI", 9, "bold"), bg="#ffffff")
        lbl_status.pack(side="left")

        btn_toggle = tk.Button(content, text="HIDUPKAN", font=("Segoe UI", 9, "bold"), relief="flat", padx=15, pady=6)
        btn_toggle.pack(side="right")

        self.manual_widgets[act_id] = {"dot": lbl_dot, "status": lbl_status, "btn": btn_toggle}

        def on_toggle():
            if self.app.auto_mode_active: return
            self.app.actuator_states[act_id] = not self.app.actuator_states[act_id]
            self.update_all_manual_ui()
            if getattr(self.app, 'connected_port', None):
                val = "ON" if self.app.actuator_states[act_id] else "OFF"
                self.app.send_serial_command(f"CTRL,{act_id},{val}\n")

            if hasattr(self.app, 'push_actuator_to_firebase_now'):
                self.app.push_actuator_to_firebase_now()

        btn_toggle.config(command=on_toggle)
    def auto_sync_ui_loop(self):
            """Memaksa tab kendali mengecek status terbaru setiap 500ms (0.5 detik)"""
            if not hasattr(self, "frame") or not self.frame.winfo_exists():
                return

            self.update_all_manual_ui()
            self.frame.after(1000, self.auto_sync_ui_loop)
            
    def update_all_manual_ui(self):
        """Fungsi ini dipanggil oleh main.py saat ada instruksi dari Web"""
        # Jangan lanjut jika bukan mode manual
        if self.current_mode != "MANUAL": 
            return
            
        # PENTING: Gunakan app.actuator_states SEBAGAI KEBENARAN TUNGGAL
        for act_id, widgets in self.manual_widgets.items():
            # Jika widget tiba-tiba sudah dihapus dari layar, lewati
            if not widgets["btn"].winfo_exists():
                continue

            # Ambil status paling update dari memori utama aplikasi
            is_on = self.app.actuator_states.get(act_id, False)
            
            # Eksekusi pewarnaan UI secara paksa
            if is_on:
                widgets["dot"].config(fg=C_ONLINE)
                widgets["status"].config(text="HIDUP", fg=C_ONLINE)
                widgets["btn"].config(text="MATIKAN", bg="#ffe5e5", fg=C_OFFLINE)
            else:
                widgets["dot"].config(fg=C_INACTIVE)
                widgets["status"].config(text="MATI", fg=C_INACTIVE)
                widgets["btn"].config(text="HIDUPKAN", bg="#e5f0ff", fg=C_ACCENT)

            # Jika ternyata tiba-tiba auto mode aktif
            if getattr(self.app, 'auto_mode_active', False):
                widgets["btn"].config(state="disabled", bg="#f4f6f9", fg="#b5b5b5", cursor="arrow")
            else:
                widgets["btn"].config(state="normal", cursor="hand2")
        try:
            self.app.root.update_idletasks() 
            self.scroll_container.canvas.update() # Tambahkan baris ini
        except:
            pass
                
        # Memaksa layar Tkinter menggambar ulang saat ini juga (Force Refresh)
        self.app.root.update_idletasks()


    def render_otomatis_view(self):
        master_frame = tk.Frame(self.scroll_container.scrollable_frame, bg="#ffffff", highlightbackground=C_BORDER, highlightthickness=2)
        master_frame.pack(fill="x", pady=(5, 10))

        lbl_master = tk.Label(master_frame, text="Master Mode Otomatis:", font=("Segoe UI", 10, "bold"), bg="#ffffff", fg=C_TEXT)
        lbl_master.pack(side="left", padx=(15, 10), pady=12)
        lbl_indikator = tk.Label(master_frame, text="", font=("Segoe UI", 10, "bold"), bg="#ffffff")
        lbl_indikator.pack(side="left")

        btn_master = tk.Button(master_frame, font=("Segoe UI", 9, "bold"), relief="flat", padx=15, pady=6, cursor="hand2")
        btn_master.pack(side="right", padx=15)

        def update_master_ui():
            if self.app.auto_mode_active:
                lbl_indikator.config(text="AKTIF", fg=C_ONLINE)
                btn_master.config(text="MATIKAN MODE OTOMATIS", bg="#ffe5e5", fg=C_OFFLINE)
            else:
                lbl_indikator.config(text="NON-AKTIF", fg=C_OFFLINE)
                btn_master.config(text="AKTIFKAN MODE OTOMATIS", bg="#e5f0ff", fg=C_ACCENT)

        def toggle_master():
            self.app.auto_mode_active = not self.app.auto_mode_active
            update_master_ui()
            val = "AUTO" if self.app.auto_mode_active else "MANUAL"
            if getattr(self.app, 'connected_port', None):
                self.app.send_serial_command(f"SYS_MODE,{val}\n")
            for act in self.app.actuator_states:
                self.app.actuator_states[act] = False
                if getattr(self.app, 'connected_port', None):
                    self.app.send_serial_command(f"CTRL,{act},OFF\n")
            if hasattr(self.app, 'push_actuator_to_firebase_now'):
                self.app.push_actuator_to_firebase_now()

        btn_master.config(command=toggle_master)
        update_master_ui()

        card_tds = tk.Frame(self.scroll_container.scrollable_frame, bg="#ffffff", highlightbackground=C_BORDER, highlightthickness=2)
        card_tds.pack(fill="x", pady=(5, 15), ipady=5)
        
        tk.Label(card_tds, text="Otomatisasi Injeksi Nutrisi (TDS)", font=("Segoe UI", 11, "bold"), bg="#ffffff", fg=C_TEXT).pack(anchor="w", padx=15, pady=(12, 0))
        
        self.lbl_tds_param = tk.Label(card_tds, text="", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg=C_ACCENT, justify="left")
        self.lbl_tds_param.pack(anchor="w", padx=15, pady=(2, 10))

        def update_tds_param_label():
            b = self.tds_config.get("batas_bawah", 800)
            o = self.tds_config.get("durasi_on", 30)
            j = self.tds_config.get("durasi_jeda", 5)
            self.lbl_tds_param.config(text=f"Parameter Aktif ➔ Batas Bawah: {b} ppm  |  Pompa Aktif: {o} detik  |  Jeda: {j} menit")
        
        update_tds_param_label()

        input_frame = tk.Frame(card_tds, bg="#ffffff")
        input_frame.pack(fill="x", padx=15, pady=(5, 15))

        tds_spin_opts = {"font": ("Segoe UI", 16, "bold"), "fg": C_ACCENT, "bg": "#f0f7ff", "readonlybackground": "#f0f7ff", "justify": "center", "state": "readonly", "width": 6}

        frm_1 = tk.Frame(input_frame, bg="#ffffff")
        frm_1.pack(side="left", padx=(0, 20))
        tk.Label(frm_1, text="Batas Bawah (ppm):", font=("Segoe UI", 10, "bold"), bg="#ffffff", fg=C_TEXT).pack(anchor="w", pady=(0,4))
        ent_tds = tk.Spinbox(frm_1, from_=0, to=2000, increment=50, **tds_spin_opts)
        ent_tds.pack()

        frm_2 = tk.Frame(input_frame, bg="#ffffff")
        frm_2.pack(side="left", padx=(0, 20))
        tk.Label(frm_2, text="Durasi Pompa (Detik):", font=("Segoe UI", 10, "bold"), bg="#ffffff", fg=C_TEXT).pack(anchor="w", pady=(0,4))
        ent_on = tk.Spinbox(frm_2, from_=5, to=300, increment=5, **tds_spin_opts)
        ent_on.pack()

        frm_3 = tk.Frame(input_frame, bg="#ffffff")
        frm_3.pack(side="left", padx=(0, 20))
        tk.Label(frm_3, text="Durasi Jeda (Menit):", font=("Segoe UI", 10, "bold"), bg="#ffffff", fg=C_TEXT).pack(anchor="w", pady=(0,4))
        ent_jeda = tk.Spinbox(frm_3, from_=1, to=60, increment=1, **tds_spin_opts)
        ent_jeda.pack()

        def set_spinbox_val(spin_widget, value):
            spin_widget.config(state="normal")
            spin_widget.delete(0, tk.END)
            spin_widget.insert(0, str(value))
            spin_widget.config(state="readonly")

        set_spinbox_val(ent_tds, self.tds_config["batas_bawah"])
        set_spinbox_val(ent_on, self.tds_config["durasi_on"])
        set_spinbox_val(ent_jeda, self.tds_config["durasi_jeda"])

        def save_tds():
            try:
                self.save_tds_setting(int(ent_tds.get()), int(ent_on.get()), int(ent_jeda.get()))
                update_tds_param_label() 
                if getattr(self.app, 'connected_port', None):
                    self.app.send_serial_command(f"SET_TDS_CFG,{ent_tds.get()},{ent_on.get()},{ent_jeda.get()}\n")
                self.show_centered_message("Berhasil", "Pengaturan TDS berhasil disimpan!", "info")
            except ValueError:
                self.show_centered_message("Error", "Isian harus berupa angka.", "warning")

        frm_btn = tk.Frame(input_frame, bg="#ffffff")
        frm_btn.pack(side="left", fill="y", padx=(10, 0))
        tk.Label(frm_btn, text="", font=("Segoe UI", 9), bg="#ffffff").pack(pady=(0, 4))
        tk.Button(frm_btn, text="Simpan TDS", font=("Segoe UI", 9, "bold"), bg=C_ACCENT, fg="#ffffff", relief="flat", padx=12, pady=6, cursor="hand2", command=save_tds).pack(side="top")

        card_sched = tk.Frame(self.scroll_container.scrollable_frame, bg="#ffffff", highlightbackground=C_BORDER, highlightthickness=2)
        card_sched.pack(fill="both", expand=True)

        header_sched = tk.Frame(card_sched, bg="#ffffff")
        header_sched.pack(fill="x", padx=15, pady=12)
        tk.Label(header_sched, text="Penjadwalan Otomatis (Timer)", font=("Segoe UI", 11, "bold"), bg="#ffffff", fg=C_TEXT).pack(side="left")
        
        btn_action_frame = tk.Frame(header_sched, bg="#ffffff")
        btn_action_frame.pack(side="right")
        tk.Button(btn_action_frame, text="Hapus", font=("Segoe UI", 9, "bold"), bg="#fff0f0", fg=C_OFFLINE, relief="flat", padx=12, pady=4, cursor="hand2", command=self.delete_selected_schedule).pack(side="right", padx=(5, 0))
        tk.Button(btn_action_frame, text="Edit", font=("Segoe UI", 9, "bold"), bg="#f0f7ff", fg=C_ACCENT, relief="flat", padx=12, pady=4, cursor="hand2", command=self.edit_selected_schedule).pack(side="right", padx=(5, 0))
        tk.Button(btn_action_frame, text="+ Atur Jadwal Baru", font=("Segoe UI", 9, "bold"), bg=C_ONLINE, fg="#ffffff", relief="flat", padx=12, pady=4, cursor="hand2", command=lambda: self.open_schedule_dialog()).pack(side="right")

        columns = ("cek", "id", "actuator", "on", "off", "hari")
        self.tree = ttk.Treeview(card_sched, columns=columns, show="headings", height=5)
        self.tree.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        self.tree.heading("cek", text="Pilih")
        self.tree.heading("id", text="ID")
        self.tree.heading("actuator", text="Perangkat")
        self.tree.heading("on", text="Waktu(ON)")
        self.tree.heading("off", text="Waktu(OFF)")
        self.tree.heading("hari", text="Hari")

        self.tree.column("cek", width=60, anchor="center")
        self.tree.column("id", width=0, stretch=False) 
        self.tree.column("actuator", width=180, anchor="w")
        self.tree.column("on", width=110, anchor="center")
        self.tree.column("off", width=110, anchor="center")
        self.tree.column("hari", width=240, anchor="w")
        
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        self.refresh_table()

    def on_tree_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            if self.tree.identify_column(event.x) == "#1":
                item = self.tree.identify_row(event.y)
                vals = list(self.tree.item(item, "values"))
                vals[0] = "☑" if vals[0] == "☐" else "☐"
                self.tree.item(item, values=vals)

    def get_checked_items(self):
        return [self.tree.item(row, "values")[1] for row in self.tree.get_children() if self.tree.item(row, "values")[0] == "☑"]

    def refresh_table(self):
        for row in self.tree.get_children(): self.tree.delete(row)
        for sched in self.schedules:
            act_name = next((a[1] for a in self.actuators if a[0] == sched["actuator"]), sched["actuator"])
            hari_str = "Setiap Hari" if sched["everyday"] else ", ".join(sched["days"])
            self.tree.insert("", "end", values=("☐", sched["id"], act_name, sched["on"], sched["off"], hari_str))

    def create_touch_time(self, parent, default_h, default_m):
        frame = tk.Frame(parent, bg="#ffffff")
        var_h = tk.StringVar(value=f"{int(default_h):02d}")
        var_m = tk.StringVar(value=f"{int(default_m):02d}")
        
        def change_val(var, delta, max_val):
            v = int(var.get()) + delta
            if v < 0: v = max_val
            elif v > max_val: v = 0
            var.set(f"{v:02d}")
            
        btn_opts = {"font": ("Segoe UI", 16, "bold"), "bg": "#f0f7ff", "fg": C_ACCENT, "relief": "flat", "width": 2, "cursor": "hand2"}
        lbl_opts = {"font": ("Segoe UI", 18, "bold"), "bg": "#ffffff", "width": 2}
        
        tk.Button(frame, text="-", command=lambda: change_val(var_h, -1, 23), **btn_opts).pack(side="left", padx=2)
        tk.Label(frame, textvariable=var_h, **lbl_opts).pack(side="left", padx=2)
        tk.Button(frame, text="+", command=lambda: change_val(var_h, 1, 23), **btn_opts).pack(side="left", padx=2)
        tk.Label(frame, text=":", font=("Segoe UI", 16, "bold"), bg="#ffffff").pack(side="left", padx=5)
        tk.Button(frame, text="-", command=lambda: change_val(var_m, -1, 59), **btn_opts).pack(side="left", padx=2)
        tk.Label(frame, textvariable=var_m, **lbl_opts).pack(side="left", padx=2)
        tk.Button(frame, text="+", command=lambda: change_val(var_m, 1, 59), **btn_opts).pack(side="left", padx=2)
        
        return frame, var_h, var_m

    def open_schedule_dialog(self, edit_id=None):
        popup = tk.Toplevel(self.app.root)
        popup.title("Atur Jadwal Baru" if not edit_id else "Edit Jadwal")
        popup.configure(bg=C_BG)
        popup.transient(self.app.root)
        self.center_popup(popup, 760, 460)
        popup.resizable(False, False)

        content = tk.Frame(popup, bg="#ffffff", highlightbackground=C_BORDER, highlightthickness=1)
        content.pack(fill="both", expand=True, padx=8, pady=8)
        
        tk.Label(content, text="Detail Penjadwalan", font=("Segoe UI", 14, "bold"), bg="#ffffff", fg=C_TEXT).pack(anchor="w", padx=20, pady=(5, 10))

        act_options = [act for act in self.actuators if act[0] != "PUMP_NUTRISI"]
        
        frm_act = tk.Frame(content, bg="#ffffff")
        frm_act.pack(fill="x", padx=20, pady=(0, 5))
        tk.Label(frm_act, text="Pilih Aktuator:", font=("Segoe UI", 11, "bold"), bg="#ffffff", width=16, anchor="w").pack(side="left")
        cmb_act = ttk.Combobox(frm_act, values=[a[1] for a in act_options], state="readonly", font=("Segoe UI", 14))
        cmb_act.pack(side="left", fill="x", expand=True)
        cmb_act.current(0)

        frm_time_on = tk.Frame(content, bg="#ffffff")
        frm_time_on.pack(fill="x", padx=20, pady=5)
        tk.Label(frm_time_on, text="Waktu Hidup (ON):", font=("Segoe UI", 11, "bold"), bg="#ffffff", width=16, anchor="w").pack(side="left")
        frm_on, var_on_h, var_on_m = self.create_touch_time(frm_time_on, 8, 0)
        frm_on.pack(side="left")
        
        frm_time_off = tk.Frame(content, bg="#ffffff")
        frm_time_off.pack(fill="x", padx=20, pady=5)
        tk.Label(frm_time_off, text="Waktu Mati (OFF):", font=("Segoe UI", 11, "bold"), bg="#ffffff", width=16, anchor="w").pack(side="left")
        frm_off, var_off_h, var_off_m = self.create_touch_time(frm_time_off, 8, 30)
        frm_off.pack(side="left")

        tk.Label(content, text="Pilih Hari Aktif:", font=("Segoe UI", 11, "bold"), bg="#ffffff").pack(anchor="w", padx=20, pady=(15, 5))
        
        frm_days_wrapper = tk.Frame(content, bg="#ffffff")
        frm_days_wrapper.pack(fill="x", padx=20)
        frm_days = tk.Frame(frm_days_wrapper, bg="#ffffff")
        frm_days.pack(anchor="center") 
        
        days_list = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
        day_vars = {day: tk.BooleanVar() for day in days_list}
        var_everyday = tk.BooleanVar()

        def toggle_everyday():
            for v in day_vars.values(): v.set(var_everyday.get())
        def check_individual():
            var_everyday.set(all(v.get() for v in day_vars.values()))

        cb_every = tk.Checkbutton(frm_days, text="Setiap Hari", variable=var_everyday, bg="#ffffff", font=("Segoe UI", 11, "bold"), command=toggle_everyday)
        cb_every.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))
        
        for i, day in enumerate(days_list):
            tk.Checkbutton(frm_days, text=day, variable=day_vars[day], bg="#ffffff", font=("Segoe UI", 11), command=check_individual).grid(row=1 + (i//4), column=i%4, sticky="w", padx=15, pady=5)

        if edit_id:
            sched = next((s for s in self.schedules if s["id"] == edit_id), None)
            if sched:
                cmb_act.set(next((a[1] for a in self.actuators if a[0] == sched["actuator"]), ""))
                on_split = sched["on"].split(":")
                var_on_h.set(on_split[0]); var_on_m.set(on_split[1])
                off_split = sched["off"].split(":")
                var_off_h.set(off_split[0]); var_off_m.set(off_split[1])
                if sched["everyday"]:
                    var_everyday.set(True); toggle_everyday()
                else:
                    for d in sched["days"]:
                        if d in day_vars: day_vars[d].set(True)

        frm_btn = tk.Frame(content, bg="#ffffff")
        frm_btn.pack(pady=(15, 5))

        def on_save():
            selected_days = [d for d, v in day_vars.items() if v.get()]
            if not selected_days:
                self.show_centered_message("Peringatan", "Pilih minimal satu hari!", "warning")
                return

            on_time = f"{int(var_on_h.get()):02d}:{int(var_on_m.get()):02d}"
            off_time = f"{int(var_off_h.get()):02d}:{int(var_off_m.get()):02d}"

            new_data = {
                "id": edit_id if edit_id else str(int(time.time())),
                "actuator": act_options[cmb_act.current()][0],
                "on": on_time, "off": off_time,
                "everyday": var_everyday.get(), "days": selected_days
            }

            if edit_id:
                for i, s in enumerate(self.schedules):
                    if s["id"] == edit_id: self.schedules[i] = new_data
            else: self.schedules.append(new_data)
                
            self.save_schedules(); self.refresh_table(); popup.destroy()

        tk.Button(frm_btn, text="Simpan Jadwal", font=("Segoe UI", 11, "bold"), bg=C_ACCENT, fg="#ffffff", relief="flat", width=20, pady=8, cursor="hand2", command=on_save).pack(side="left", padx=10)
        tk.Button(frm_btn, text="Batal", font=("Segoe UI", 11, "bold"), bg=C_INACTIVE, fg="#ffffff", relief="flat", width=20, pady=8, cursor="hand2", command=popup.destroy).pack(side="left", padx=10)

    def edit_selected_schedule(self):
        checked = self.get_checked_items()
        if not checked:
            self.show_centered_message("Peringatan", "Tandai (ceklis) kotak satu jadwal pada tabel untuk diedit.", "warning")
            return
        if len(checked) > 1:
            self.show_centered_message("Peringatan", "Pilih hanya SATU jadwal untuk diedit.", "warning")
            return
        self.open_schedule_dialog(edit_id=str(checked[0]))

    def delete_selected_schedule(self):
        checked = self.get_checked_items()
        if not checked:
            self.show_centered_message("Peringatan", "Tandai (ceklis) kotak jadwal pada tabel yang ingin dihapus.", "warning")
            return
        if self.ask_yes_no("Konfirmasi Hapus", f"Apakah Anda yakin ingin menghapus {len(checked)} jadwal terpilih?"):
            self.schedules = [s for s in self.schedules if s["id"] not in checked]
            self.save_schedules()
            self.refresh_table()