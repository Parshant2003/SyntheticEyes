"""
control_panel.py  (ui folder mein)  --  SIMPLE CONTROL PANEL (Tkinter)

Purpose: 5 buttons (LEFT, RIGHT, UP, DOWN, GENERATE MOTION), motion chuno, "Render" dabao,
         status/progress dekho, aur video bante hi folder khol lo.
Run (project root se):   python ui/control_panel.py
Tkinter Python ke saath hi aata hai, koi extra install nahi.
Status: UNTESTED (maine ise chalake nahi dekha; sirf syntax check hua hai).
"""
import os
import queue
import re
import sys
import threading
import tkinter as tk
from tkinter import ttk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import config  # noqa: E402
import eye_control  # noqa: E402

LABELS = [("left", "LEFT"), ("right", "RIGHT"), ("up", "UP"), ("down", "DOWN"), ("generate", "GENERATE MOTION")]
FRAME_RE = re.compile(r"frame (\d+)/(\d+)")


def parse_progress(message):
    """'[left] frame 12/73 (30s)' -> (12, 73). Frame line na ho to None."""
    m = FRAME_RE.search(message)
    return (int(m.group(1)), int(m.group(2))) if m else None


class ControlPanel(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Synthetic Eyes - Control Panel")
        self.resizable(False, False)
        self.msgs = queue.Queue()
        self.cancel = threading.Event()
        self.worker = None
        self.last_video = None

        self.motion = tk.StringVar(value="generate")
        self.quality = tk.StringVar(value="draft")
        self.use_gpu = tk.BooleanVar(value=True)
        self.preview = tk.BooleanVar(value=False)

        pad = {"padx": 10, "pady": 6}
        ttk.Label(self, text="1. Movement chuno", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=5, sticky="w", **pad)
        for i, (value, text) in enumerate(LABELS):
            tk.Radiobutton(self, text=text, value=value, variable=self.motion, indicatoron=False,
                           width=18, height=2, font=("Segoe UI", 10, "bold")).grid(row=1, column=i, padx=4, pady=4)

        ttk.Label(self, text="2. Options", font=("Segoe UI", 11, "bold")).grid(row=2, column=0, columnspan=5, sticky="w", **pad)
        ttk.Label(self, text="Quality:").grid(row=3, column=0, sticky="e")
        ttk.Combobox(self, textvariable=self.quality, values=list(config.QUALITY), width=8, state="readonly").grid(row=3, column=1, sticky="w")
        ttk.Checkbutton(self, text="GPU (Intel Arc)", variable=self.use_gpu).grid(row=3, column=2, sticky="w")
        ttk.Checkbutton(self, text="Sirf preview (8 stills)", variable=self.preview).grid(row=3, column=3, columnspan=2, sticky="w")

        ttk.Label(self, text="3. Render", font=("Segoe UI", 11, "bold")).grid(row=4, column=0, columnspan=5, sticky="w", **pad)
        self.btn_start = ttk.Button(self, text="Start Render", command=self.start)
        self.btn_start.grid(row=5, column=0, columnspan=2, sticky="we", padx=10)
        self.btn_cancel = ttk.Button(self, text="Cancel", command=self.cancel_render, state="disabled")
        self.btn_cancel.grid(row=5, column=2, sticky="we", padx=4)
        self.btn_open = ttk.Button(self, text="Open output folder", command=self.open_output)
        self.btn_open.grid(row=5, column=3, columnspan=2, sticky="we", padx=10)

        self.progress = ttk.Progressbar(self, length=780, mode="determinate")
        self.progress.grid(row=6, column=0, columnspan=5, padx=10, pady=8)
        self.status = tk.StringVar(value="Taiyaar. Movement chuno aur Start Render dabao.")
        ttk.Label(self, textvariable=self.status, wraplength=780).grid(row=7, column=0, columnspan=5, sticky="w", padx=10, pady=4)
        self.log = tk.Text(self, height=8, width=104, state="disabled", font=("Consolas", 9))
        self.log.grid(row=8, column=0, columnspan=5, padx=10, pady=8)

        self.after(150, self.poll)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # --- actions
    def start(self):
        if self.worker and self.worker.is_alive():
            return
        self.cancel.clear()
        self.progress["value"] = 0
        self.btn_start.config(state="disabled")
        self.btn_cancel.config(state="normal")
        motion, quality, gpu, preview = self.motion.get(), self.quality.get(), self.use_gpu.get(), self.preview.get()
        self.set_status(f"{motion.upper()} ({quality}) shuru ho raha hai...")
        self.worker = threading.Thread(target=self._work, args=(motion, quality, gpu, preview), daemon=True)
        self.worker.start()

    def _work(self, motion, quality, gpu, preview):
        try:
            res = eye_control.run_motion(motion, quality, gpu=gpu, preview=preview,
                                         status_cb=lambda m: self.msgs.put(("status", m)),
                                         cancel_event=self.cancel)
            self.msgs.put(("done", res))
        except Exception as e:                       # UI crash na ho: error status mein dikhao
            self.msgs.put(("error", str(e)))

    def cancel_render(self):
        self.cancel.set()
        self.set_status("Cancel ho raha hai...")

    def open_output(self):
        folder = self.last_video and os.path.dirname(self.last_video) or config.VIDEOS_DIR
        os.makedirs(folder, exist_ok=True)
        try:
            os.startfile(folder)                     # Windows
        except AttributeError:
            self.set_status("Folder: " + folder)

    def on_close(self):
        self.cancel.set()
        self.destroy()

    # --- UI updates (sirf main thread se)
    def set_status(self, text):
        self.status.set(text)

    def append_log(self, text):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def poll(self):
        try:
            while True:
                kind, payload = self.msgs.get_nowait()
                if kind == "status":
                    prog = parse_progress(payload)
                    if prog:
                        self.progress["maximum"] = prog[1]
                        self.progress["value"] = prog[0]
                        self.set_status(f"Rendering: frame {prog[0]} / {prog[1]}")
                        if prog[0] % 10:
                            continue
                    else:
                        self.set_status(payload)
                    self.append_log(payload)
                elif kind == "done":
                    self.finish()
                    if "path" in payload:
                        self.last_video = payload["path"]
                        self.set_status(f"Ho gaya! Video: {payload['path']}  ({payload['seconds']} s)")
                        self.append_log("DONE: " + payload["path"])
                    else:
                        self.set_status("Preview ready: " + payload["preview_dir"])
                        self.append_log("Preview: " + payload["preview_dir"])
                elif kind == "error":
                    self.finish()
                    self.set_status("ERROR: " + payload.splitlines()[0])
                    self.append_log(payload)
        except queue.Empty:
            pass
        self.after(150, self.poll)

    def finish(self):
        self.btn_start.config(state="normal")
        self.btn_cancel.config(state="disabled")


if __name__ == "__main__":
    ControlPanel().mainloop()