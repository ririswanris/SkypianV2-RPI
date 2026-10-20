import tkinter as tk
from tkinter import ttk
from config import *

class ScrollableFrame(tk.Frame):
    """Container Frame yang bisa di-scroll secara vertikal (Touch Friendly)"""
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, bg=C_BG, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=C_BG)

        self.scrollable_frame.bind("<Configure>", self._configure_scrollable_frame)

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind("<Configure>", self.on_canvas_configure)
        
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)

    def _configure_scrollable_frame(self, event=None):
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=(0, 0, bbox[2], bbox[3]))

    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")

class TouchKeyboard(tk.Toplevel):
    """Keyboard Virtual On-Screen dengan Kolom Pratinjau (Preview)"""
    def __init__(self, parent, target_entry, title="Keyboard Virtual"):
        super().__init__(parent)
        self.parent = parent
        self.target = target_entry
        self.title(title)
        self.configure(bg="#d1d5db") 
        self.transient(parent)
        
        # PERBAIKAN: Posisi dikalkulasi ke "Tengah Bawah" berdasarkan layar utama
        parent.update_idletasks()
        root = parent.winfo_toplevel()
        root_w = root.winfo_width() if root.winfo_width() > 100 else 800
        root_h = root.winfo_height() if root.winfo_height() > 100 else 480
        
        w = 780 # Lebar keyboard 780px (pas untuk layar 800px)
        h = 280 # Tinggi keyboard 280px
        x = root.winfo_x() + (root_w - w) // 2
        y = root.winfo_y() + (root_h - h) - 10 # 10 pixel dari dasar layar
        
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        self.resizable(False, False)

        top_frm = tk.Frame(self, bg="#d1d5db")
        top_frm.pack(fill="x", padx=10, pady=(10, 5))

        tk.Label(top_frm, text=title + ":", font=("Segoe UI", 10, "bold"), bg="#d1d5db", fg=C_TEXT).pack(side="left")

        self.preview_var = tk.StringVar()
        self.preview_var.set(self.target.get())

        self.lbl_preview = tk.Entry(top_frm, textvariable=self.preview_var, font=("Segoe UI", 14, "bold"), bg="#ffffff", fg=C_ACCENT, state="readonly", relief="solid", bd=1)
        self.lbl_preview.pack(side="left", fill="x", expand=True, padx=10)

        tk.Button(top_frm, text="BATAL", font=("Segoe UI", 10, "bold"), bg=C_OFFLINE, fg="#ffffff", relief="flat", cursor="hand2", command=self.close_keyboard).pack(side="right")

        main_frm = tk.Frame(self, bg="#d1d5db", padx=5, pady=5)
        main_frm.pack(fill="both", expand=True)

        keys = [
            ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0', 'BACK'],
            ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', '-'],
            ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', ':'],
            ['Z', 'X', 'C', 'V', 'B', 'N', 'M', '_', 'CLEAR'],
            ['SPACE', 'ENTER']
        ]

        for row in keys:
            row_frm = tk.Frame(main_frm, bg="#d1d5db")
            row_frm.pack(fill="both", pady=2, expand=True)
            for key in row:
                w_key = 10 if key in ['SPACE', 'ENTER', 'BACK', 'CLEAR'] else 4
                btn_bg = C_ACCENT if key == 'ENTER' else "#ffffff"
                btn_fg = "#ffffff" if key == 'ENTER' else C_TEXT
                
                btn = tk.Button(
                    row_frm, text=key, font=("Segoe UI", 12, "bold"), width=w_key,
                    bg=btn_bg, fg=btn_fg, relief="raised", bd=2, cursor="hand2",
                    command=lambda k=key: self.press(k)
                )
                btn.pack(side="left", padx=2, fill="both", expand=True)

        self.protocol("WM_DELETE_WINDOW", self.close_keyboard)

        # Setelah seluruh tombol selesai dirender, aktifkan fokus & grab aman
        self.lift()
        self.focus_force()
        safe_grab_set(self)

    def close_keyboard(self):
        safe_grab_release(self)
        try:
            if self.winfo_exists():
                self.destroy()
        except Exception:
            pass
        # Kembalikan modal grab ke dialog pemanggil jika ada
        try:
            if self.parent and self.parent.winfo_exists():
                safe_grab_set(self.parent)
        except Exception:
            pass

    def press(self, key):
        current = self.preview_var.get()
        if key == 'BACK': self.preview_var.set(current[:-1])
        elif key == 'CLEAR': self.preview_var.set("")
        elif key == 'SPACE': self.preview_var.set(current + ' ')
        elif key == 'ENTER':
            self.target.delete(0, tk.END)
            self.target.insert(0, current)
            self.close_keyboard()
        else: self.preview_var.set(current + key)
