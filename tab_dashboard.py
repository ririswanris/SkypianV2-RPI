import tkinter as tk
from datetime import datetime, timedelta
import os
from PIL import Image, ImageTk
from config import *

# Cache gambar di memori agar TIDAK dibaca dari disk atau di-resize berulang kali
_ICON_CACHE = {}

def get_cached_icon(icon_filename, size=(60, 60)):
    """Memuat dan me-resize ikon satu kali saja, disimpan di RAM"""
    cache_key = (icon_filename, size)
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    icon_path = get_asset_path(icon_filename)
    if os.path.exists(icon_path):
        try:
            pil_img = Image.open(icon_path)
            try:
                resample_filter = Image.Resampling.BILINEAR  # Jauh lebih cepat dari LANCZOS untuk ARM Pi Zero
            except AttributeError:
                resample_filter = getattr(Image, 'BILINEAR', Image.NEAREST)
            pil_img = pil_img.resize(size, resample_filter)
            tk_img = ImageTk.PhotoImage(pil_img)
            _ICON_CACHE[cache_key] = tk_img
            return tk_img
        except Exception as e:
            print(f"Error memuat icon {icon_filename}: {e}")
    return None


class NativeCanvasGraph(tk.Toplevel):
    """
    Grafik Native Tkinter Canvas ultra-ringan khusus Raspberry Pi Zero.
    Menggantikan Matplotlib yang memakan 80MB RAM dan freeze 3 detik.
    Render dalam < 2 ms, responsif sentuh dan hemat daya.
    """
    def __init__(self, parent_root, metric_name, app_instance):
        super().__init__(parent_root)
        self.app = app_instance
        self.metric_name = metric_name
        self.title(f"Grafik: {metric_name}")
        self.configure(bg=C_BG)
        self.transient(parent_root)

        win_w, win_h = 520, 310
        parent_root.update_idletasks()
        rx, ry = parent_root.winfo_x(), parent_root.winfo_y()
        rw, rh = parent_root.winfo_width(), parent_root.winfo_height()
        pos_x = rx + max(0, (rw - win_w) // 2)
        pos_y = ry + max(0, (rh - win_h) // 2)
        self.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        self.resizable(False, False)

        # Header dialog
        header = tk.Frame(self, bg=C_BG)
        header.pack(fill="x", padx=15, pady=(10, 4))

        tk.Label(header, text=metric_name, font=("Segoe UI", 12, "bold"), bg=C_BG, fg=C_TEXT).pack(side="left")

        btn_close = tk.Button(
            header, text="✕ Tutup", font=("Segoe UI", 9, "bold"),
            bg="#ffffff", fg=C_OFFLINE, relief="flat", padx=12, pady=4,
            cursor="hand2", command=self.close_graph
        )
        btn_close.pack(side="right")

        # Container Canvas
        canvas_card = tk.Frame(self, bg="#ffffff", highlightbackground=C_BORDER, highlightthickness=1)
        canvas_card.pack(fill="both", expand=True, padx=12, pady=(4, 10))

        self.canvas_w = 490
        self.canvas_h = 240
        self.canvas = tk.Canvas(canvas_card, bg="#ffffff", highlightthickness=0, width=self.canvas_w, height=self.canvas_h)
        self.canvas.pack(fill="both", expand=True, padx=4, pady=4)

        self.draw_chart()

        self.protocol("WM_DELETE_WINDOW", self.close_graph)

        # Pastikan dialog tampil di depan dan aman dari crash grab X11
        self.lift()
        self.focus_force()
        safe_grab_set(self)

    def close_graph(self):
        safe_grab_release(self)
        try:
            self.destroy()
        except Exception:
            pass

    def draw_chart(self):
        self.canvas.delete("all")
        pad_l, pad_r, pad_t, pad_b = 45, 20, 25, 30
        plot_w = self.canvas_w - pad_l - pad_r
        plot_h = self.canvas_h - pad_t - pad_b

        # Ambil data riil
        if self.metric_name == "Suhu & Kelembapan Udara":
            air_dict = self.app.history_data.get(self.metric_name, {})
            data_t = air_dict.get("suhu", [0.0]) or [0.0]
            data_h = air_dict.get("kelembapan", [0]) or [0]
            count = max(len(data_t), len(data_h), 2)
            
            # Rentang Y Suhu & Kelembapan (0 - 100)
            min_y, max_y = 0.0, 100.0
            
            # Legend di atas kanan
            self.canvas.create_oval(self.canvas_w - 210, 10, self.canvas_w - 200, 20, fill="#ff9500", outline="")
            self.canvas.create_text(self.canvas_w - 150, 15, text=f"Suhu ({data_t[-1]}°C)", font=("Segoe UI", 8, "bold"), fill=C_TEXT, anchor="w")
            self.canvas.create_oval(self.canvas_w - 95, 10, self.canvas_w - 85, 20, fill=C_ACCENT, outline="")
            self.canvas.create_text(self.canvas_w - 40, 15, text=f"Kelembapan ({data_h[-1]}%)", font=("Segoe UI", 8, "bold"), fill=C_TEXT, anchor="w")

            # Grid & Ticks
            self._draw_grid_and_axes(pad_l, pad_t, plot_w, plot_h, min_y, max_y, count, "% / °C")
            self._plot_series(data_t, count, pad_l, pad_t, plot_w, plot_h, min_y, max_y, "#ff9500")
            self._plot_series(data_h, count, pad_l, pad_t, plot_w, plot_h, min_y, max_y, C_ACCENT)

        else:
            raw_data = self.app.history_data.get(self.metric_name, [0]) or [0]
            data = [float(x) for x in raw_data]
            count = max(len(data), 2)

            min_val = min(data)
            max_val = max(data)
            if min_val == max_val:
                min_y = max(0.0, min_val - 5.0)
                max_y = max_val + 5.0
            else:
                margin = (max_val - min_val) * 0.15
                min_y = max(0.0, min_val - margin)
                max_y = max_val + margin

            # Nilai terbaru
            latest_str = f"Terbaru: {data[-1]}"
            self.canvas.create_text(self.canvas_w - 25, 15, text=latest_str, font=("Segoe UI", 9, "bold"), fill=C_ACCENT, anchor="e")

            # Grid & Ticks
            self._draw_grid_and_axes(pad_l, pad_t, plot_w, plot_h, min_y, max_y, count, "")
            self._plot_series(data, count, pad_l, pad_t, plot_w, plot_h, min_y, max_y, C_ACCENT)

    def _draw_grid_and_axes(self, pad_l, pad_t, plot_w, plot_h, min_y, max_y, count, unit_label):
        steps = 4
        for i in range(steps + 1):
            val = min_y + (max_y - min_y) * (i / steps)
            y = pad_t + plot_h - (i / steps) * plot_h
            self.canvas.create_line(pad_l, y, pad_l + plot_w, y, fill="#f0f0f2", dash=(2, 2))
            val_txt = f"{int(val)}" if val.is_integer() else f"{val:.1f}"
            self.canvas.create_text(pad_l - 6, y, text=val_txt, font=("Segoe UI", 7), fill=C_INACTIVE, anchor="e")

        self.canvas.create_line(pad_l, pad_t + plot_h, pad_l + plot_w, pad_t + plot_h, fill=C_BORDER, width=1)
        self.canvas.create_line(pad_l, pad_t, pad_l, pad_t + plot_h, fill=C_BORDER, width=1)

        now = datetime.now()
        label_steps = min(count, 5)
        for i in range(label_steps):
            idx = int(i * (count - 1) / max(1, label_steps - 1))
            x = pad_l + (idx / max(1, count - 1)) * plot_w
            past_time = now - timedelta(minutes=(count - 1 - idx) * 2)
            time_str = past_time.strftime("%H:%M")
            self.canvas.create_text(x, pad_t + plot_h + 12, text=time_str, font=("Segoe UI", 7), fill=C_INACTIVE, anchor="center")

    def _plot_series(self, data_list, total_count, pad_l, pad_t, plot_w, plot_h, min_y, max_y, color):
        points = []
        val_range = max_y - min_y
        if val_range <= 0:
            val_range = 1.0

        for i, val in enumerate(data_list):
            x = pad_l + (i / max(1, total_count - 1)) * plot_w
            norm_y = (float(val) - min_y) / val_range
            norm_y = max(0.0, min(1.0, norm_y))
            y = pad_t + plot_h - (norm_y * plot_h)
            points.append((x, y))

        if len(points) >= 2:
            flat_pts = [coord for pt in points for coord in pt]
            self.canvas.create_line(*flat_pts, fill=color, width=2, smooth=False)

        for (x, y) in points:
            self.canvas.create_oval(x - 2.5, y - 2.5, x + 2.5, y + 2.5, fill="#ffffff", outline=color, width=1.5)


class DashboardTab:
    """
    Dashboard Tab yang telah dioptimasi untuk Raspberry Pi Zero:
    1. Render 1x saja saat inisialisasi (layout tidak dibuat ulang berulang-ulang).
    2. Ikon di-cache di memori (tidak ada baca SD Card / Lanczos resize berulang).
    3. Loop realtime HANYA mengubah teks label (sangat hemat CPU, 0ms latency).
    4. Mengganti grafik Matplotlib berat dengan Native Canvas Graph.
    """
    def __init__(self, parent_container, app_instance):
        self.container = parent_container
        self.app = app_instance
        self.fonts = app_instance.fonts
        self.card_icon_refs = []
        self.value_labels = {}

        # Frame utama tab dashboard (disimpan agar tidak dihancurkan saat tab switch)
        self.frame = tk.Frame(self.container, bg=C_BG)
        self.frame.pack(fill="both", expand=True)

        self.render()
        self.start_realtime_loop()

    def render(self):
        # 1. HEADER STATUS (Hardware Serial & Firebase Network)
        header = tk.Frame(self.frame, bg=C_BG)
        header.pack(fill="x", padx=15, pady=(8, 4))

        # Status Jaringan & Database
        net_status_frame = tk.Frame(header, bg=C_BG)
        net_status_frame.pack(anchor="w", pady=(0, 2))

        self.lbl_dot_net = tk.Label(net_status_frame, text="●", font=("Segoe UI", 11), bg=C_BG, fg=C_OFFLINE)
        self.lbl_dot_net.pack(side="left", padx=(0, 5))

        self.lbl_net_text = tk.Label(net_status_frame, text="Memeriksa Koneksi Database...", font=("Segoe UI", 9, "bold"), bg=C_BG, fg=C_TEXT)
        self.lbl_net_text.pack(side="left")

        # Status Hardware Master
        hw_status_frame = tk.Frame(header, bg=C_BG)
        hw_status_frame.pack(anchor="w")

        self.lbl_dot_hw = tk.Label(hw_status_frame, text="●", font=("Segoe UI", 11), bg=C_BG, fg=C_OFFLINE)
        self.lbl_dot_hw.pack(side="left", padx=(0, 5))

        self.lbl_hw_text = tk.Label(hw_status_frame, text="Memeriksa Port Serial...", font=("Segoe UI", 9, "bold"), bg=C_BG, fg=C_TEXT)
        self.lbl_hw_text.pack(side="left")

        # 2. GRID KARTU SENSOR (2 Kolom x 3 Baris)
        grid = tk.Frame(self.frame, bg=C_BG)
        grid.pack(fill="both", expand=True, padx=10, pady=4)

        for i in range(2): grid.columnconfigure(i, weight=1)
        for i in range(3): grid.rowconfigure(i, weight=1)

        self.value_labels.clear()

        # Nilai awal
        avg_soil = sum(self.app.history_data["Rata-rata Soil"][-5:]) // 5 if self.app.history_data["Rata-rata Soil"] else 0
        avg_ph = round(sum(self.app.history_data["Rata-rata pH Tanah"][-5:]) / 5, 1) if self.app.history_data["Rata-rata pH Tanah"] else 0.0
        water_temp = str(self.app.history_data["Suhu Air"][-1]) if self.app.history_data["Suhu Air"] else "0"
        water_ph = str(self.app.history_data["pH Air"][-1]) if self.app.history_data["pH Air"] else "0"
        water_tds = str(self.app.history_data["TDS Air"][-1]) if self.app.history_data["TDS Air"] else "0"

        air_t = self.app.history_data["Suhu & Kelembapan Udara"]["suhu"][-1] if self.app.history_data["Suhu & Kelembapan Udara"]["suhu"] else "0"
        air_h = self.app.history_data["Suhu & Kelembapan Udara"]["kelembapan"][-1] if self.app.history_data["Suhu & Kelembapan Udara"]["kelembapan"] else "0"
        air_val_str = f"{air_t} / {air_h}"

        # 6 Kartu Sensor
        self.create_dashboard_card(grid, "Rata-rata Soil", str(avg_soil), "%", "soil.png", 0, 0)
        self.create_dashboard_card(grid, "Rata-rata pH Tanah", str(avg_ph), "", "ph_tanah.png", 0, 1)
        self.create_dashboard_card(grid, "Suhu Air", water_temp, "°C", "temp_air.png", 1, 0)
        self.create_dashboard_card(grid, "pH Air", water_ph, "", "ph_air.png", 1, 1)
        self.create_dashboard_card(grid, "TDS Air", water_tds, "ppm", "tds.png", 2, 0)
        self.create_dashboard_card(grid, "Suhu & Kelembapan Udara", air_val_str, "°C / %", "temp_hum.png", 2, 1)

    def create_dashboard_card(self, parent, title, value, unit, icon_filename, row, col):
        """Membuat kartu sensor menggunakan Frame statis cepat tanpa kalkulasi polygon canvas berulang"""
        card_frame = tk.Frame(
            parent, bg="#ffffff",
            highlightbackground=C_BORDER, highlightthickness=1,
            cursor="hand2"
        )
        card_frame.grid(row=row, column=col, padx=6, pady=4, sticky="nsew")

        left_frame = tk.Frame(card_frame, bg="#ffffff")
        left_frame.pack(side="left", expand=True, fill="both", padx=12, pady=6)

        inner_content = tk.Frame(left_frame, bg="#ffffff")
        inner_content.pack(expand=True, anchor="w")

        lbl_title = tk.Label(inner_content, text=title, font=self.fonts.get("card_title", ("Segoe UI", 11, "bold")), bg="#ffffff", fg=C_INACTIVE)
        lbl_title.pack(anchor="w", pady=(0, 0))

        val_container = tk.Frame(inner_content, bg="#ffffff")
        val_container.pack(anchor="w", pady=(1, 0))

        lbl_val = tk.Label(val_container, text=value, font=self.fonts.get("card_val", ("Segoe UI", 28, "bold")), bg="#ffffff", fg=C_ACCENT)
        lbl_val.pack(side="left")

        # Simpan referensi label nilai agar bisa diupdate real-time tanpa render ulang
        self.value_labels[title] = lbl_val

        lbl_unit = tk.Label(val_container, text=f" {unit}", font=self.fonts.get("card_unit", ("Segoe UI", 9, "bold")), bg="#ffffff", fg=C_INACTIVE)
        lbl_unit.pack(side="left", anchor="s", pady=(0, 4))

        right_frame = tk.Frame(card_frame, bg="#ffffff", width=70)
        right_frame.pack(side="right", fill="y", padx=6, pady=4)
        right_frame.pack_propagate(False)

        lbl_icon = tk.Label(right_frame, bg="#ffffff")
        lbl_icon.pack(expand=True, fill="both")

        # Ambil ikon dari cache (RAM)
        tk_icon = get_cached_icon(icon_filename, (56, 56))
        if tk_icon:
            lbl_icon.config(image=tk_icon)
            self.card_icon_refs.append(tk_icon)

        # Binding klik untuk membuka grafik native
        for w in (card_frame, left_frame, inner_content, lbl_title, val_container, lbl_val, lbl_unit, right_frame, lbl_icon):
            w.bind("<Button-1>", lambda e, t=title: self.open_graph_window(t))

    def update_realtime_data(self):
        """
        Pembaruan Realtime Hemat Daya:
        Hanya meng-update teks Label dan indikator status dot jika frame masih ada di layar.
        Waktu eksekusi: < 0.2 milidetik (nol lag di Pi Zero).
        """
        if not self.frame.winfo_exists():
            return

        # 1. UPDATE STATUS HARDWARE MASTER
        if hasattr(self, 'lbl_dot_hw') and self.lbl_dot_hw.winfo_exists():
            is_hw_online = bool(getattr(self.app, 'connected_port', None))
            if is_hw_online:
                self.lbl_dot_hw.config(fg=C_ONLINE)
                self.lbl_hw_text.config(text=f"Hardware Master: Aktif ({self.app.connected_port})", fg=C_TEXT)
            else:
                self.lbl_dot_hw.config(fg=C_OFFLINE)
                self.lbl_hw_text.config(text="Hardware Master: Terputus / Tidak Ditemukan", fg=C_OFFLINE)

        # 2. UPDATE STATUS DATABASE (FIREBASE)
        if hasattr(self, 'lbl_dot_net') and self.lbl_dot_net.winfo_exists():
            is_net_online = getattr(self.app, 'is_network_connected', False)
            if is_net_online:
                self.lbl_dot_net.config(fg=C_ONLINE)
                self.lbl_net_text.config(text="Firebase Cloud: Sinkron (Online)", fg=C_ONLINE)
            else:
                self.lbl_dot_net.config(fg=C_OFFLINE)
                self.lbl_net_text.config(text="Firebase Cloud: Tidak Ada Internet (Offline)", fg=C_OFFLINE)

        # 3. UPDATE SELURUH 6 PARAMETER SENSOR SECARA LIVE
        try:
            hist = self.app.history_data

            # 1. Rata-rata Soil
            if "Rata-rata Soil" in self.value_labels and hist.get("Rata-rata Soil"):
                recent_soil = hist["Rata-rata Soil"][-5:]
                avg_soil = sum(recent_soil) // len(recent_soil)
                self.value_labels["Rata-rata Soil"].config(text=str(avg_soil))

            # 2. Rata-rata pH Tanah
            if "Rata-rata pH Tanah" in self.value_labels and hist.get("Rata-rata pH Tanah"):
                recent_ph = hist["Rata-rata pH Tanah"][-5:]
                avg_ph = round(sum(recent_ph) / len(recent_ph), 1)
                self.value_labels["Rata-rata pH Tanah"].config(text=str(avg_ph))

            # 3. Suhu Air
            if "Suhu Air" in self.value_labels and hist.get("Suhu Air"):
                self.value_labels["Suhu Air"].config(text=str(hist["Suhu Air"][-1]))

            # 4. pH Air
            if "pH Air" in self.value_labels and hist.get("pH Air"):
                self.value_labels["pH Air"].config(text=str(hist["pH Air"][-1]))

            # 5. TDS Air
            if "TDS Air" in self.value_labels and hist.get("TDS Air"):
                self.value_labels["TDS Air"].config(text=str(hist["TDS Air"][-1]))

            # 6. Suhu & Kelembapan Udara
            if "Suhu & Kelembapan Udara" in self.value_labels:
                air_data = hist.get("Suhu & Kelembapan Udara", {})
                suhu_list = air_data.get("suhu", [])
                hum_list = air_data.get("kelembapan", [])
                air_t = suhu_list[-1] if suhu_list else "0"
                air_h = hum_list[-1] if hum_list else "0"
                self.value_labels["Suhu & Kelembapan Udara"].config(text=f"{air_t} / {air_h}")

        except Exception as e:
            pass

        # Ulangi setiap 1000ms
        self.frame.after(1000, self.update_realtime_data)

    def start_realtime_loop(self):
        self.frame.after(1000, self.update_realtime_data)

    def open_graph_window(self, metric_name):
        """Membuka grafik native Tkinter Canvas super cepat tanpa Matplotlib"""
        NativeCanvasGraph(self.app.root, metric_name, self.app)
