import tkinter as tk
from config import *

class PlaceholderTab:
    def __init__(self, parent_container, tab_name, app_instance):
        self.container = parent_container
        self.tab_name = tab_name
        self.app = app_instance
        
        self.render()

    def render(self):
        frame = tk.Frame(self.container, bg=C_BG)
        frame.pack(expand=True, fill="both")
        
        tk.Label(
            frame, 
            text=f"Tampilan {self.tab_name} akan dirancang di sini", 
            font=self.app.fonts["head"], 
            bg=C_BG, 
            fg=C_INACTIVE
        ).pack(expand=True)