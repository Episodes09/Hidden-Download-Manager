import os
import json
import requests
import time
import tkinter as tk
from tkinter import messagebox
from threading import Thread
import keyboard

HISTORY_FILE = "download_session.json"
QUEUE_FILE = "download_queue.json"

THEMES = {
    "Dark": {"bg": "#1e1e2e", "fg": "white", "accent": "#a6e3a1", "paused": "#fab387", "entry_bg": "#313244", "speed_fg": "#b4befe"},
    "Light": {"bg": "#f0f0f0", "fg": "#333333", "accent": "#27ae60", "paused": "#e67e22", "entry_bg": "#ffffff", "speed_fg": "#2980b9"}
}

class DownloadManager:
    def __init__(self, url=None, dest_dir="."):
        self.url = url
        self.dest_dir = dest_dir
        self.filename = ""
        self.dest_path = ""
        self.part_path = ""
        self.meta_path = ""
        self.is_paused = True
        self.is_cancelled = False  # Track cancellation status
        self.download_thread = None
        if url: self.setup_paths(url)

    def setup_paths(self, url):
        self.url = url
        self.filename = url.split("/")[-1].split("?")[0] or "downloaded_file"
        self.dest_path = os.path.join(self.dest_dir, self.filename)
        self.part_path = self.dest_path + ".part"
        self.meta_path = self.dest_path + ".json"

    def _load_meta(self):
        if os.path.exists(self.meta_path) and os.path.exists(self.part_path):
            try:
                with open(self.meta_path, 'r') as f:
                    return json.load(f).get("downloaded_bytes", 0)
            except: return 0
        return 0

    def _save_meta(self, downloaded_bytes):
        with open(self.meta_path, 'w') as f:
            json.dump({"downloaded_bytes": downloaded_bytes}, f)

    def start(self, progress_callback):
        self.is_paused = False
        self.is_cancelled = False
        self.download_thread = Thread(target=self._download_logic, args=(progress_callback,))
        self.download_thread.start()

    def pause(self):
        self.is_paused = True

    def cancel(self):
        """Halts operations and performs a hard wipe of temporary workspace remnants."""
        self.is_cancelled = True
        self.is_paused = True
        
        # Give the data loop an instant to release the file handle, then wipe files
        time.sleep(0.2)
        if os.path.exists(self.part_path):
            try: os.remove(self.part_path)
            except: pass
        if os.path.exists(self.meta_path):
            try: os.remove(self.meta_path)
            except: pass

    def _download_logic(self, progress_callback):
        start_byte = self._load_meta()
        headers = {'Range': f'bytes={start_byte}-'} if start_byte > 0 else {}
        try:
            response = requests.get(self.url, headers=headers, stream=True, timeout=15)
            if start_byte > 0 and response.status_code != 206:
                start_byte = 0
                response = requests.get(self.url, stream=True, timeout=15)

            total_bytes = int(response.headers.get('content-length', 0)) + start_byte
            downloaded = start_byte
            start_time = time.time()
            bytes_since_start = 0

            with open(self.part_path, 'ab' if start_byte > 0 else 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.is_paused or self.is_cancelled: break
                    if chunk:
                        file.write(chunk)
                        downloaded += len(chunk)
                        bytes_since_start += len(chunk)
                        self._save_meta(downloaded)
                        
                        elapsed = time.time() - start_time
                        if elapsed >= 0.8:
                            speed_mb = (bytes_since_start / elapsed) / (1024 * 1024)
                            start_time = time.time()
                            bytes_since_start = 0
                        else:
                            try: speed_mb
                            except NameError: speed_mb = 0.0

                        bytes_left = total_bytes - downloaded
                        mb_left = max(0, bytes_left / (1024 * 1024))
                        percent = int((downloaded / total_bytes) * 100) if total_bytes else 0
                        progress_callback("update", {"mb": mb_left, "pct": percent, "spd": speed_mb})

            if self.is_cancelled:
                return # Quit silently, cleanup routine handled inside .cancel()

            if downloaded == total_bytes:
                if os.path.exists(self.dest_path): os.remove(self.dest_path)
                os.rename(self.part_path, self.dest_path)
                if os.path.exists(self.meta_path): os.remove(self.meta_path)
                progress_callback("done", self.filename)
        except Exception as e:
            if not self.is_cancelled:
                progress_callback("error", str(e))

class FloatingWidget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Downloader")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.geometry("380x42+100+100")
        
        self.current_theme = "Dark"
        self.queue = self.load_queue()
        self.dm = DownloadManager()
        self.is_processing_queue = False

        # Build Context Menu (Now featuring the 🚫 Cancel command!)
        self.context_menu = tk.Menu(self.root, tearoff=0, bg="#313244", fg="white", activebackground="#a6e3a1", activeforeground="#11111b")
        self.context_menu.add_command(label="🚫 Cancel Active Download", command=self.cancel_current_download)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="📋 Queue Manager", command=self.open_queue_manager)
        self.context_menu.add_command(label="⚙️ Settings & Info", command=self.open_settings)

        # UI Components
        self.lbl_drag = tk.Label(self.root, text=" ☰ ", font=("Arial", 12), cursor="fleur")
        self.lbl_drag.pack(side="left", padx=4)
        self.lbl_drag.bind("<Button-1>", self.start_drag)
        self.lbl_drag.bind("<B1-Motion>", self.stop_drag)

        self.entry_url = tk.Entry(self.root, bd=0, width=13)
        self.entry_url.pack(side="left", padx=2)
        
        self.btn_action = tk.Button(self.root, text="►", command=self.toggle_download, bd=0, width=2, font=("Arial", 10, "bold"))
        self.btn_action.pack(side="left", padx=3)

        self.stats_frame = tk.Frame(self.root)
        self.stats_frame.pack(side="left", padx=6)

        self.lbl_speed = tk.Label(self.stats_frame, text="0.0 MB/s", font=("Arial", 7, "bold"), anchor="w", width=19)
        self.lbl_speed.pack(anchor="w")

        self.lbl_main_status = tk.Label(self.stats_frame, text="Ready", font=("Arial", 9, "bold"), anchor="w", width=19)
        self.lbl_main_status.pack(anchor="w")

        self.btn_minimize = tk.Button(self.root, text="—", command=self.hide_window, bd=0, width=2)
        self.btn_minimize.pack(side="left", padx=2)

        self.btn_close = tk.Button(self.root, text="✕", command=self.exit_application, bg="#f38ba8", fg="#11111b", bd=0, width=2)
        self.btn_close.pack(side="right", padx=5)

        # Right-click listeners mapped universally
        self.root.bind("<Button-3>", self.show_context_menu)
        self.lbl_drag.bind("<Button-3>", self.show_context_menu)
        self.stats_frame.bind("<Button-3>", self.show_context_menu)
        self.lbl_main_status.bind("<Button-3>", self.show_context_menu)

        self.apply_theme()
        self.check_saved_session()
        keyboard.add_hotkey('windows+shift+h', self.show_window)

    def apply_theme(self):
        t = THEMES[self.current_theme]
        self.root.configure(bg=t["bg"])
        self.lbl_drag.config(bg=t["bg"], fg=t["speed_fg"])
        self.entry_url.config(bg=t["entry_bg"], fg=t["fg"])
        self.stats_frame.config(bg=t["bg"])
        self.lbl_speed.config(bg=t["bg"], fg=t["speed_fg"])
        self.lbl_main_status.config(bg=t["bg"], fg=t["accent"] if self.lbl_main_status.cget("text")=="Ready" else t["fg"])
        self.btn_minimize.config(bg=t["paused"], fg="#11111b")
        if self.dm.is_paused:
            self.btn_action.config(bg=t["accent"], fg="#11111b")
        else:
            self.btn_action.config(bg=t["paused"], fg="#11111b")

    def show_context_menu(self, event):
        self.context_menu.post(event.x_root, event.y_root)

    def load_queue(self):
        if os.path.exists(QUEUE_FILE):
            try:
                with open(QUEUE_FILE, 'r') as f: return json.load(f)
            except: return []
        return []

    def save_queue(self):
        with open(QUEUE_FILE, 'w') as f: json.dump(self.queue, f)

    def start_drag(self, event):
        self.x = event.x
        self.y = event.y

    def stop_drag(self, event):
        x = self.root.winfo_x() + (event.x - self.x)
        y = self.root.winfo_y() + (event.y - self.y)
        self.root.geometry(f"+{x}+{y}")

    def hide_window(self): self.root.withdraw()
    def show_window(self):
        self.root.deiconify()
        self.root.attributes("-topmost", True)

    def exit_application(self):
        self.dm.pause()
        self.root.destroy()
        os._exit(0)

    def check_saved_session(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    saved_url = json.load(f).get("url")
                    if saved_url:
                        self.dm.setup_paths(saved_url)
                        self.entry_url.delete(0, tk.END)
                        self.entry_url.insert(0, saved_url)
                        self.lbl_main_status.config(text="Paused Queue", fg=THEMES[self.current_theme]["paused"])
                        return
            except: pass
        self.reset_ui_for_next()

    def reset_ui_for_next(self):
        self.entry_url.delete(0, tk.END)
        self.entry_url.insert(0, "Paste URL Here")
        self.lbl_main_status.config(text="Ready", fg=THEMES[self.current_theme]["accent"])
        self.lbl_speed.config(text="0.0 MB/s")
        self.btn_action.config(text="►")
        self.apply_theme()
        self.entry_url.bind("<FocusIn>", lambda e: self.entry_url.delete(0, tk.END) if self.entry_url.get()=="Paste URL Here" else None)

    def handle_callback(self, status_type, data):
        t = THEMES[self.current_theme]
        if status_type == "update":
            self.lbl_speed.config(text=f"{data['spd']:.1f} MB/s")
            self.lbl_main_status.config(text=f"{data['mb']:.1f}MB left ({data['pct']}%)", fg=t["fg"])
        elif status_type == "done":
            if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
            self.show_window()
            messagebox.showinfo("Success", f"Finished: {data}")
            self.process_next_in_queue()
        elif status_type == "error":
            self.show_window()
            messagebox.showerror("Error", "Download failed or link expired.")
            self.btn_action.config(text="►", bg=t["accent"])
            self.is_processing_queue = False

    def toggle_download(self):
        url = self.entry_url.get()
        if not url or url == "Paste URL Here": return
        if self.dm.url != url: self.dm.setup_paths(url)

        t = THEMES[self.current_theme]
        if self.dm.is_paused:
            with open(HISTORY_FILE, 'w') as f: json.dump({"url": url}, f)
            self.dm.start(self.handle_callback)
            self.btn_action.config(text="║", bg=t["paused"])
        else:
            self.dm.pause()
            self.lbl_main_status.config(text="Paused", fg=t["paused"])
            self.btn_action.config(text="►", bg=t["accent"])

    def cancel_current_download(self):
        """Halts the current thread, dumps file segments, and rolls the queue pipeline forward."""
        if self.dm.url and not self.dm.is_paused:
            # Drop active indicators
            if os.path.exists(HISTORY_FILE): 
                try: os.remove(HISTORY_FILE)
                except: pass
                
            self.dm.cancel()
            messagebox.showinfo("Cancelled", "Download aborted. Partial cache files cleared successfully.")
            self.process_next_in_queue()
        else:
            # If item was paused but session file exists, clean it up manually
            if os.path.exists(HISTORY_FILE):
                try: os.remove(HISTORY_FILE)
                except: pass
            self.dm.cancel()
            self.process_next_in_queue()

    def process_next_in_queue(self):
        if self.queue:
            next_url = self.queue.pop(0)
            self.save_queue()
            self.dm = DownloadManager(next_url)
            self.entry_url.delete(0, tk.END)
            self.entry_url.insert(0, next_url)
            with open(HISTORY_FILE, 'w') as f: json.dump({"url": next_url}, f)
            self.dm.start(self.handle_callback)
            self.btn_action.config(text="║", bg=THEMES[self.current_theme]["paused"])
            self.is_processing_queue = True
        else:
            self.is_processing_queue = False
            self.dm = DownloadManager()
            self.reset_ui_for_next()

    def open_queue_manager(self):
        qm = tk.Toplevel(self.root)
        qm.title("Queue Operations")
        qm.geometry("400x300")
        qm.configure(bg=THEMES[self.current_theme]["bg"])
        qm.attributes("-topmost", True)

        lbl = tk.Label(qm, text="On-Going & Pending Queue Links", fg=THEMES[self.current_theme]["fg"], bg=THEMES[self.current_theme]["bg"], font=("Arial", 10, "bold"))
        lbl.pack(pady=5)

        listbox = tk.Listbox(qm, bg=THEMES[self.current_theme]["entry_bg"], fg=THEMES[self.current_theme]["fg"], bd=0, highlightthickness=0)
        listbox.pack(fill="both", expand=True, padx=10, pady=5)

        for item in self.queue: listbox.insert(tk.END, item)

        entry_q = tk.Entry(qm, bg=THEMES[self.current_theme]["entry_bg"], fg=THEMES[self.current_theme]["fg"], bd=0)
        entry_q.pack(fill="x", padx=10, pady=5)

        def add_to_q():
            u = entry_q.get()
            if u:
                self.queue.append(u)
                self.save_queue()
                listbox.insert(tk.END, u)
                entry_q.delete(0, tk.END)
                if self.lbl_main_status.cget("text") == "Ready" and not self.is_processing_queue:
                    self.process_next_in_queue()

        def clear_q():
            self.queue.clear()
            self.save_queue()
            listbox.delete(0, tk.END)

        btn_frame = tk.Frame(qm, bg=THEMES[self.current_theme]["bg"])
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Add Link to Queue", command=add_to_q, bg=THEMES[self.current_theme]["accent"], bd=0, padx=5).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Clear Queue", command=clear_q, bg="#f38ba8", bd=0, padx=5).pack(side="left", padx=5)

    def open_settings(self):
        sm = tk.Toplevel(self.root)
        sm.title("Settings & Developer Info")
        sm.geometry("320x240")
        sm.configure(bg=THEMES[self.current_theme]["bg"])
        sm.attributes("-topmost", True)

        dev_frame = tk.LabelFrame(sm, text=" Developer Identity ", fg=THEMES[self.current_theme]["accent"], bg=THEMES[self.current_theme]["bg"], padx=10, pady=10)
        dev_frame.pack(fill="x", padx=10, pady=10)

        tk.Label(dev_frame, text="Discord: episodes1000", fg=THEMES[self.current_theme]["fg"], bg=THEMES[self.current_theme]["bg"], font=("Arial", 10)).pack(anchor="w")
        tk.Label(dev_frame, text="GitHub: Episodes09", fg=THEMES[self.current_theme]["fg"], bg=THEMES[self.current_theme]["bg"], font=("Arial", 10)).pack(anchor="w")

        theme_frame = tk.LabelFrame(sm, text=" Customize Theme ", fg=THEMES[self.current_theme]["accent"], bg=THEMES[self.current_theme]["bg"], padx=10, pady=10)
        theme_frame.pack(fill="x", padx=10, pady=5)

        def switch_theme(chosen):
            self.current_theme = chosen
            self.apply_theme()
            sm.configure(bg=THEMES[chosen]["bg"])
            dev_frame.config(fg=THEMES[chosen]["accent"], bg=THEMES[chosen]["bg"])
            theme_frame.config(fg=THEMES[chosen]["accent"], bg=THEMES[chosen]["bg"])
            for widget in dev_frame.winfo_children(): widget.config(fg=THEMES[chosen]["fg"], bg=THEMES[chosen]["bg"])
            for widget in theme_frame.winfo_children(): widget.config(fg=THEMES[chosen]["fg"], bg=THEMES[chosen]["bg"])

        theme_var = tk.StringVar(value=self.current_theme)
        tk.Radiobutton(theme_frame, text="Dark Cyberpunk Mode", variable=theme_var, value="Dark", command=lambda: switch_theme("Dark"), bg=THEMES[self.current_theme]["bg"], fg=THEMES[self.current_theme]["fg"], selectcolor=THEMES[self.current_theme]["entry_bg"]).pack(anchor="w")
        tk.Radiobutton(theme_frame, text="Classic Light Mode", variable=theme_var, value="Light", command=lambda: switch_theme("Light"), bg=THEMES[self.current_theme]["bg"], fg=THEMES[self.current_theme]["fg"], selectcolor=THEMES[self.current_theme]["entry_bg"]).pack(anchor="w")

if __name__ == "__main__":
    app = FloatingWidget()
    app.root.mainloop()
