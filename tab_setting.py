import tkinter as tk
import serial.tools.list_ports
import json
import os
from config import *
from ui_components import ScrollableFrame, TouchKeyboard

ACTUATOR_CFG_FILE = "actuator_cfg.json"

class SettingTab:
    def __init__(self, parent_container, app_instance):
        self.container = parent_container
        self.app = app_instance
        self.fonts = app_instance.fonts
        self.active_kbd = None
        
        # Mapping Internal ID -> Alias Singkat (Tampilan) -> Nama Default
        self.actuator_keys = [
            ("PUMP_NUTRISI", "ACT1", "Pompa Nutrisi"),
            ("EXHAUST_FAN", "ACT2", "Exhaust Fan"),
            ("FAN_SIRKULER", "ACT3", "Fan Sirkuler"),
            ("FOGGER", "ACT4", "Fogger"),
            ("CUSTOM_1", "CUS1", "Custom 1"),
            ("CUSTOM_2", "CUS2", "Custom 2")
        ]
        
        self.frame = tk.Frame(self.container, bg=C_BG)
        self.frame.pack(fill="both", expand=True)

        self.render()

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

    def open_kbd(self, event, entry, title):
        if self.active_kbd and self.active_kbd.winfo_exists():
            self.active_kbd.destroy()
        self.active_kbd = TouchKeyboard(self.app.root, entry, title)

    def load_actuator_names(self):
        data = {}
        if os.path.exists(ACTUATOR_CFG_FILE):
            try:
                with open(ACTUATOR_CFG_FILE, "r") as f:
                    data = json.load(f)
            except: pass
        return data

    def save_actuator_names(self, entries_dict):
        data = {}
        for key, ent in entries_dict.items():
            data[key] = ent.get().strip()
            
        try:
            with open(ACTUATOR_CFG_FILE, "w") as f:
                json.dump(data, f, indent=4)
            self.show_centered_message("Berhasil", "Nama Aktuator berhasil disimpan!", "info")
        except Exception as e:
            self.show_centered_message("Error", f"Gagal menyimpan data: {str(e)}", "error")

    def open_actuator_label_dialog(self):
        popup = tk.Toplevel(self.app.root)
        popup.title("Pengaturan Label Aktuator")
        popup.configure(bg=C_BG)
        popup.transient(self.app.root)
        self.center_popup(popup, 680, 420)
        popup.resizable(False, False)

        content = tk.Frame(popup, bg="#ffffff", highlightbackground=C_BORDER, highlightthickness=1)
        content.pack(fill="both", expand=True, padx=8, pady=8)

        tk.Label(content, text="Ubah Nama Tampilan Aktuator", font=("Segoe UI", 13, "bold"), bg="#ffffff", fg=C_TEXT).pack(pady=(15, 5))

        grid_frame = tk.Frame(content, bg="#ffffff")
        grid_frame.pack(fill="both", expand=True, padx=20, pady=10)

        saved_names = self.load_actuator_names()
        entries = {}

        for idx, (real_id, display_id, default_name) in enumerate(self.actuator_keys):
            row = idx // 2
            col = idx % 2
            
            frm = tk.Frame(grid_frame, bg="#ffffff")
            frm.grid(row=row, column=col, padx=15, pady=8, sticky="ew")
            grid_frame.columnconfigure(col, weight=1)

            tk.Label(frm, text=f"{display_id}:", font=("Segoe UI", 10, "bold"), bg="#ffffff", fg=C_INACTIVE).pack(anchor="w")
            
            ent = tk.Entry(frm, font=("Segoe UI", 14), bg="#f0f7ff", relief="solid", bd=1, fg=C_TEXT)
            ent.pack(fill="x", ipady=6, pady=(2, 0))
            ent.insert(0, saved_names.get(real_id, default_name))
            
            ent.bind("<Button-1>", lambda e, entry=ent, title=f"Ubah Nama {display_id}": self.open_kbd(e, entry, title))
            
            entries[real_id] = ent

        btn_frm = tk.Frame(content, bg="#ffffff")
        btn_frm.pack(pady=(10, 15))

        def on_save():
            self.save_actuator_names(entries)
            if self.active_kbd and self.active_kbd.winfo_exists():
                self.active_kbd.destroy()
            popup.destroy()

        def on_cancel():
            if self.active_kbd and self.active_kbd.winfo_exists():
                self.active_kbd.destroy()
            safe_grab_release(popup)
            popup.destroy()

        popup.protocol("WM_DELETE_WINDOW", on_cancel)

        tk.Button(btn_frm, text="Simpan", font=("Segoe UI", 10, "bold"), bg=C_ACCENT, fg="#ffffff", relief="flat", width=15, pady=8, cursor="hand2", command=on_save).pack(side="left", padx=10)
        tk.Button(btn_frm, text="Batal", font=("Segoe UI", 10, "bold"), bg=C_INACTIVE, fg="#ffffff", relief="flat", width=15, pady=8, cursor="hand2", command=on_cancel).pack(side="left", padx=10)

    def render(self):
        for widget in self.frame.winfo_children():
            widget.destroy()

        self.scroll_container = ScrollableFrame(self.frame)
        self.scroll_container.pack(fill="both", expand=True)
        
        main_frm = tk.Frame(self.scroll_container.scrollable_frame, bg=C_BG)
        main_frm.pack(fill="both", expand=True, padx=20, pady=15)
        
        tk.Label(main_frm, text="PENGATURAN SISTEM", font=self.fonts["title"], bg=C_BG, fg=C_TEXT).pack(anchor="w", pady=(0, 15))
        
        # --- KARTU KONEKSI PORT OTOMATIS ---
        port_card = tk.Frame(main_frm, bg="#ffffff", highlightbackground=C_BORDER, highlightthickness=1)
        port_card.pack(fill="x", pady=(0, 15))
        tk.Label(port_card, text="Koneksi Serial Skypian Station", font=("Segoe UI", 11, "bold"), bg="#ffffff", fg=C_TEXT).pack(anchor="w", padx=15, pady=(15, 5))
        
        input_frm = tk.Frame(port_card, bg="#ffffff")
        input_frm.pack(fill="x", padx=15, pady=(5, 15))
        
        port_status = getattr(self.app, 'connected_port', None)
        status_text = f"Terhubung di {port_status}" if port_status else "Terputus"
        status_color = C_ONLINE if port_status else C_OFFLINE
        
        stat_text = f"Station ID: {self.app.station_id}" if port_status else "Station ID: [Menunggu Koneksi...]"
        lbl_color = C_ACCENT if port_status else C_INACTIVE

        # Sisi Kanan (Tombol Koneksi Atas-Bawah)
        btn_frm_koneksi = tk.Frame(input_frm, bg="#ffffff")
        btn_frm_koneksi.pack(side="right")
        
        btn_opts = {"font": ("Segoe UI", 9, "bold"), "relief": "flat", "width": 18, "pady": 6, "cursor": "hand2"}
        
        tk.Button(btn_frm_koneksi, text="Scan & Hubungkan", bg=C_ACCENT, fg="#ffffff", command=self.scan_and_connect, **btn_opts).pack(side="top", pady=(0, 5))
        tk.Button(btn_frm_koneksi, text="Putuskan", bg=C_OFFLINE, fg="#ffffff", command=self.disconnect_port, **btn_opts).pack(side="top")
        
        # Sisi Kiri (Status Port dan Station ID sejajar tombol)
        status_frm = tk.Frame(input_frm, bg="#ffffff")
        status_frm.pack(side="left", fill="both", expand=True)
        
        # Baris 1: Status Port (sejajar dengan tombol biru)
        row1_frm = tk.Frame(status_frm, bg="#ffffff")
        row1_frm.pack(fill="x", pady=(4, 12))
        
        tk.Label(row1_frm, text="Status Port:", font=("Segoe UI", 10), bg="#ffffff", width=10, anchor="w").pack(side="left")
        tk.Label(row1_frm, text=status_text, font=("Segoe UI", 10, "bold"), bg="#ffffff", fg=status_color, anchor="w").pack(side="left")
        
        # Baris 2: Station ID (sejajar dengan tombol merah)
        row2_frm = tk.Frame(status_frm, bg="#ffffff")
        row2_frm.pack(fill="x", pady=(2, 0))
        
        self.lbl_station_info = tk.Label(row2_frm, text=stat_text, font=("Segoe UI", 10, "bold"), bg="#ffffff", fg=lbl_color)
        self.lbl_station_info.pack(anchor="w")

        # --- KARTU PENGATURAN LABEL AKTUATOR ---
        actuator_card = tk.Frame(main_frm, bg="#ffffff", highlightbackground=C_BORDER, highlightthickness=1)
        actuator_card.pack(fill="x", pady=5)
        
        act_info_frm = tk.Frame(actuator_card, bg="#ffffff")
        act_info_frm.pack(fill="x", padx=15, pady=15)
        
        tk.Label(act_info_frm, text="Label Aktuator", font=("Segoe UI", 11, "bold"), bg="#ffffff", fg=C_TEXT).pack(side="left")
        
        # Tombol Edit dengan ukuran width=18 yang diselaraskan dengan tombol koneksi
        tk.Button(act_info_frm, text="Edit Label Aktuator", font=("Segoe UI", 9, "bold"), bg=C_ACCENT, fg="#ffffff", relief="flat", width=18, pady=6, cursor="hand2", command=self.open_actuator_label_dialog).pack(side="right")
        
    def scan_and_connect(self):
        ports = serial.tools.list_ports.comports()
        target_port = None
        
        for p in ports:
            desc = p.description.lower()
            if any(keyword in desc for keyword in ["usb", "ch340", "cp210", "uart"]):
                target_port = p.device
                break
                
        if not target_port and ports:
            for p in ports:
                if p.device not in ["COM1", "ttyS0"]: 
                    target_port = p.device
                    break
            if not target_port:
                target_port = ports[0].device 

        if target_port:
            self.app.connected_port = target_port
            save_settings(target_port, self.app.station_id)
            self.show_centered_message("Sukses", f"Station ditemukan dan terhubung di {target_port}", "info")
            self.render()
        else:
            self.show_centered_message("Gagal", "Tidak ada perangkat ESP/Hardware Serial yang terdeteksi di sistem.", "warning")
            
    def disconnect_port(self):
        if self.app.connected_port:
            self.app.connected_port = None
            save_settings("", self.app.station_id)
            self.show_centered_message("Terputus", "Koneksi port berhasil diputuskan.", "error")
            #self.frame = tk.Frame(self.container, bg=C_BG)
        self.frame.pack(fill="both", expand=True)

        self.render()