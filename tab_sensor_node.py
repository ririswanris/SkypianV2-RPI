import tkinter as tk
import time
import re
from config import *
from ui_components import ScrollableFrame, TouchKeyboard

class SensorNodeTab:
    def __init__(self, parent_container, app_instance):
        self.container = parent_container
        self.app = app_instance
        self.fonts = app_instance.fonts
        self.registered_nodes = load_registered_nodes()
        self.node_card_widgets = {}

        # Frame utama tab sensor node
        self.frame = tk.Frame(self.container, bg=C_BG)
        self.frame.pack(fill="both", expand=True)

        self.render()
        self.check_connection_status()

    def on_tab_activated(self):
        """Dipanggil saat tab ini dipilih agar daftar node selalu sinkron"""
        self.registered_nodes = load_registered_nodes()
        self.render_node_cards()
        self.update_live_data()

    def render(self):
        for widget in self.frame.winfo_children():
            widget.destroy()

        self.node_card_widgets.clear()

        self.header_frame = tk.Frame(self.frame, bg=C_BG)
        self.header_frame.pack(side="top", fill="x", padx=20, pady=(20, 10))

        tk.Label(self.header_frame, text="MANAJEMEN SENSOR NODE", font=("Segoe UI", 16, "bold"), bg=C_BG, fg=C_TEXT).pack(side="left")

        # Tombol Tambah Node
        self.btn_add = tk.Button(
            self.header_frame, text="+ Tambah Node", font=("Segoe UI", 10, "bold"),
            bg=C_ACCENT, fg="#ffffff", relief="flat", padx=15, pady=8,
            cursor="hand2", command=self.open_add_node_dialog
        )
        self.btn_add.pack(side="right")

        self.lbl_status_node = tk.Label(self.header_frame, font=("Segoe UI", 10, "bold"), bg=C_BG)
        self.lbl_status_node.pack(side="right", padx=(0, 15))
        
        self.update_header_status()

        self.scroll_container = ScrollableFrame(self.frame)
        self.scroll_container.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.render_node_cards()

    def update_header_status(self):
        if hasattr(self, 'lbl_status_node') and self.lbl_status_node.winfo_exists():
            is_online = bool(getattr(self.app, 'connected_port', None))
            self.lbl_status_node.config(
                text="[Online]" if is_online else "[Offline]", 
                fg=C_ONLINE if is_online else C_OFFLINE
            )
            
            if hasattr(self, 'btn_add') and self.btn_add.winfo_exists():
                if is_online:
                    self.btn_add.config(state=tk.NORMAL, bg=C_ACCENT, cursor="hand2")
                else:
                    self.btn_add.config(state=tk.DISABLED, bg=C_INACTIVE, cursor="arrow")

    def render_node_cards(self):
        self.scroll_container.canvas.yview_moveto(0)
        
        for w in self.scroll_container.scrollable_frame.winfo_children():
            w.destroy()
        self.node_card_widgets.clear()

        self.registered_nodes = load_registered_nodes()
        if not self.registered_nodes:
            tk.Label(self.scroll_container.scrollable_frame, text="Belum Ada Sensor Node Terdaftar", font=("Segoe UI", 12, "bold"), bg=C_BG, fg=C_INACTIVE).pack(pady=50)
            return

        grid_frame = tk.Frame(self.scroll_container.scrollable_frame, bg=C_BG)
        grid_frame.pack(fill="both", expand=True)
        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1) 

        for index, node in enumerate(self.registered_nodes):
            row = index // 2
            col = index % 2
            self.create_node_card(grid_frame, node, row, col)

    def create_node_card(self, parent, node_info, row, col):
        card = tk.Frame(parent, bg="#ffffff", highlightbackground=C_BORDER, highlightthickness=2)
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

        node_id = node_info["node_id"]

        header = tk.Frame(card, bg="#f8f9fa")
        header.pack(fill="x")
        
        lbl_id = tk.Label(header, text=node_id, font=("Segoe UI", 12, "bold"), bg="#f8f9fa", fg=C_ACCENT)
        lbl_id.pack(side="left", padx=15, pady=10)
        
        status_frm = tk.Frame(header, bg="#f8f9fa")
        status_frm.pack(side="right", padx=15)
        lbl_dot = tk.Label(status_frm, text="●", font=("Segoe UI", 12), bg="#f8f9fa", fg=C_OFFLINE)
        lbl_dot.pack(side="left")
        lbl_status = tk.Label(status_frm, text="Offline", font=("Segoe UI", 9, "bold"), bg="#f8f9fa", fg=C_OFFLINE)
        lbl_status.pack(side="left", padx=(2, 0))

        tk.Label(card, text=f"MAC: {node_info['mac']}", font=("Segoe UI", 9), bg="#ffffff", fg=C_INACTIVE).pack(anchor="w", padx=15, pady=(5, 0))

        live_entry = self.app.live_node_data.get(node_id, {})
        packet = live_entry.get("packet", {})
        vals = packet.get("node") if isinstance(packet.get("node"), dict) else packet
        
        s1, s2, s3, s4 = vals.get("soil_1", 0), vals.get("soil_2", 0), vals.get("soil_3", 0), vals.get("soil_4", 0)
        ph_val = vals.get("ph_tanah", 0.0)

        val_frame = tk.Frame(card, bg="#ffffff")
        val_frame.pack(fill="x", padx=15, pady=10)
        
        lbl_soil = tk.Label(val_frame, text=f"Soil: S1:{s1}% | S2:{s2}% | S3:{s3}% | S4:{s4}%", font=("Segoe UI", 10, "bold"), bg="#ffffff", fg=C_TEXT)
        lbl_soil.pack(anchor="w")

        lbl_ph = tk.Label(val_frame, text=f"pH Tanah: {ph_val}", font=("Segoe UI", 14, "bold"), bg="#ffffff", fg=C_ONLINE)
        lbl_ph.pack(anchor="w", pady=(4, 0))

        btn_del = tk.Button(card, text="Hapus Node", font=("Segoe UI", 9, "bold"), bg="#ffe5e5", fg=C_OFFLINE, relief="flat", padx=15, pady=6, cursor="hand2", command=lambda: self.confirm_remove(node_info))
        btn_del.pack(side="right", padx=15, pady=(0, 15))

        self.node_card_widgets[node_id] = {
            "dot": lbl_dot,
            "status": lbl_status,
            "soil": lbl_soil,
            "ph": lbl_ph,
            "last_seen": live_entry.get("last_seen", 0)
        }

    def update_live_data(self):
        """Memperbarui nilai dan status node secara realtime menggunakan NODE_OFFLINE_TIMEOUT yang aman"""
        self.update_header_status()
        current = time.time()
        for node_id, w in self.node_card_widgets.items():
            entry = self.app.live_node_data.get(node_id)
            if entry and (current - entry.get("last_seen", 0)) <= NODE_OFFLINE_TIMEOUT:
                packet = entry.get("packet", {})
                vals = packet.get("node") if isinstance(packet.get("node"), dict) else packet
                w["dot"].config(fg=C_ONLINE)
                w["status"].config(text="Aktif", fg=C_ONLINE)
                w["soil"].config(text=f"Soil: S1:{vals.get('soil_1',0)}% | S2:{vals.get('soil_2',0)}% | S3:{vals.get('soil_3',0)}% | S4:{vals.get('soil_4',0)}%")
                w["ph"].config(text=f"pH Tanah: {vals.get('ph_tanah', 0.0)}")
            else:
                w["dot"].config(fg=C_OFFLINE)
                w["status"].config(text="Offline", fg=C_OFFLINE)

    def check_connection_status(self):
        if self.frame.winfo_exists():
            self.update_live_data()
            self.frame.after(1000, self.check_connection_status)

    def center_popup(self, popup, w, h):
        self.app.root.update_idletasks()
        popup.update_idletasks()
        root_w = self.app.root.winfo_width()
        root_h = self.app.root.winfo_height()
        if root_w < 100: root_w = 800
        if root_h < 100: root_h = 480
        x = self.app.root.winfo_rootx() + (root_w - w) // 2
        y = self.app.root.winfo_rooty() + (root_h - h) // 2
        popup.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    def show_centered_message(self, title, message, msg_type="info"):
        popup = tk.Toplevel(self.app.root)
        popup.title(title)
        popup.configure(bg=C_BG)
        popup.transient(self.app.root)
        self.center_popup(popup, 380, 180)
        popup.resizable(False, False)

        content = tk.Frame(popup, bg="#ffffff", highlightbackground=C_BORDER, highlightthickness=1)
        content.pack(fill="both", expand=True, padx=8, pady=8)

        color = C_ONLINE if msg_type == "info" else C_OFFLINE if msg_type == "error" else "#ff9500"
        tk.Label(content, text=message, font=("Segoe UI", 10, "bold"), bg="#ffffff", fg=C_TEXT, justify="center", wraplength=340).pack(expand=True, padx=12, pady=12)
        
        def close_msg():
            safe_grab_release(popup)
            popup.destroy()

        tk.Button(content, text="OK", font=("Segoe UI", 9, "bold"), bg=color, fg="#ffffff", relief="flat", width=10, pady=4, cursor="hand2", command=close_msg).pack(pady=(0, 10))
        popup.protocol("WM_DELETE_WINDOW", close_msg)
        popup.lift()
        safe_grab_set(popup)
        self.app.root.wait_window(popup)

    def open_add_node_dialog(self):
        popup = tk.Toplevel(self.app.root)
        popup.title("Tambah Node")
        popup.configure(bg=C_BG)
        popup.transient(self.app.root)
        self.center_popup(popup, 460, 300) 

        content = tk.Frame(popup, bg="#ffffff")
        content.pack(fill="both", expand=True, padx=15, pady=15)

        tk.Label(content, text="ID Node:", font=("Segoe UI", 11, "bold"), bg="#ffffff").pack(anchor="w")
        entry_id = tk.Entry(content, font=("Segoe UI", 14), bg="#f8f9fa", relief="solid", bd=1)
        entry_id.pack(fill="x", pady=(4, 15), ipady=6)
        entry_id.insert(0, f"NODE_{len(self.registered_nodes)+1}")

        tk.Label(content, text="MAC Address (XX:XX:XX:XX:XX:XX):", font=("Segoe UI", 11, "bold"), bg="#ffffff").pack(anchor="w")
        entry_mac = tk.Entry(content, font=("Segoe UI", 14), bg="#f8f9fa", relief="solid", bd=1)
        entry_mac.pack(fill="x", pady=4, ipady=6)

        self.active_kbd = None 

        def open_kbd(event, entry, title):
            if self.active_kbd and self.active_kbd.winfo_exists():
                self.active_kbd.destroy()
            self.active_kbd = TouchKeyboard(popup, entry, title)

        entry_id.bind("<Button-1>", lambda e: open_kbd(e, entry_id, "Ketik ID Node"))
        entry_mac.bind("<Button-1>", lambda e: open_kbd(e, entry_mac, "Ketik MAC Address"))

        def close_dialog_clean():
            if self.active_kbd and self.active_kbd.winfo_exists():
                self.active_kbd.destroy()
            safe_grab_release(popup)
            popup.destroy()

        popup.protocol("WM_DELETE_WINDOW", close_dialog_clean)

        btn_frame = tk.Frame(content, bg="#ffffff")
        btn_frame.pack(pady=(20, 0))

        def on_submit():
            node_id, mac_addr = entry_id.get().strip(), entry_mac.get().strip().upper()
            if not node_id: return
            
            # 1. VALIDASI FORMAT MAC ADDRESS
            pattern = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
            if not pattern.match(mac_addr):
                entry_mac.delete(0, tk.END)
                self.show_centered_message("MAC Tidak Valid", "Format MAC Address salah.\nInput telah dibersihkan. (Contoh: A1:B2:C3:D4:E5:F6)", "error")
                return

            # 2. VALIDASI DUPLIKAT MAC ADDRESS
            if any(n["mac"] == mac_addr for n in self.registered_nodes):
                self.show_centered_message("Peringatan", "MAC Address tersebut sudah terdaftar di sistem!", "warning")
                return

            # 3. DAFTARKAN KE HARDWARE ESP32 MASTER
            if getattr(self.app, 'connected_port', None):
                self.app.send_serial_command(f"ADD_NODE,{mac_addr},{node_id}\n")
                
            self.registered_nodes.append({"node_id": node_id, "mac": mac_addr, "last_soil": [0,0,0,0], "last_ph": 0.0})
            save_registered_nodes(self.registered_nodes)
            close_dialog_clean()
            self.render_node_cards()
            self.show_centered_message("Berhasil", f"Node {node_id} ({mac_addr}) berhasil didaftarkan!\nMenunggu data sensor pertama masuk.", "info")

        tk.Button(btn_frame, text="Simpan Node", font=("Segoe UI", 11, "bold"), bg=C_ACCENT, fg="#ffffff", relief="flat", width=15, pady=8, cursor="hand2", command=on_submit).pack(side="left", padx=10)
        tk.Button(btn_frame, text="Batal", font=("Segoe UI", 11, "bold"), bg=C_INACTIVE, fg="#ffffff", relief="flat", width=15, pady=8, cursor="hand2", command=close_dialog_clean).pack(side="left", padx=10)

        # Aktifkan modal grab aman SETELAH semua layout selesai dibuat
        popup.lift()
        safe_grab_set(popup)

    def confirm_remove(self, node_info):
        popup = tk.Toplevel(self.app.root)
        popup.title("Hapus Node")
        popup.configure(bg=C_BG)
        popup.transient(self.app.root)
        self.center_popup(popup, 360, 160)
        popup.resizable(False, False)
        
        content = tk.Frame(popup, bg="#ffffff", highlightbackground=C_BORDER, highlightthickness=1)
        content.pack(fill="both", expand=True, padx=8, pady=8)
        tk.Label(content, text=f"Yakin ingin menghapus {node_info['node_id']}?", font=("Segoe UI", 11, "bold"), bg="#ffffff", fg=C_TEXT).pack(expand=True, padx=12, pady=12)
        
        btn_frame = tk.Frame(content, bg="#ffffff")
        btn_frame.pack(pady=(0, 10))
        
        def on_close():
            safe_grab_release(popup)
            popup.destroy()

        def on_yes():
            self.registered_nodes = [n for n in self.registered_nodes if n["node_id"] != node_info["node_id"]]
            save_registered_nodes(self.registered_nodes)
            
            # Beritahu Master Gateway untuk menghapus jalur ESP-NOW
            if getattr(self.app, 'connected_port', None):
                self.app.send_serial_command(f"DEL_NODE,{node_info['mac']}\n")
                
            on_close()
            self.render_node_cards()
            
        tk.Button(btn_frame, text="Ya, Hapus", font=("Segoe UI", 10, "bold"), bg=C_OFFLINE, fg="#ffffff", relief="flat", width=10, pady=4, cursor="hand2", command=on_yes).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Batal", font=("Segoe UI", 10, "bold"), bg=C_INACTIVE, fg="#ffffff", relief="flat", width=10, pady=4, cursor="hand2", command=on_close).pack(side="left", padx=5)
        popup.protocol("WM_DELETE_WINDOW", on_close)

        popup.lift()
        safe_grab_set(popup)
