import os
import sys
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, ttk, messagebox

# ================= FFmpeg 处理 =================

def get_ffmpeg_path():
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    local = os.path.join(base, "ffmpeg.exe")
    return local if os.path.exists(local) else "ffmpeg"

def check_ffmpeg():
    try:
        subprocess.run([get_ffmpeg_path(), "-version"],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        return True
    except:
        return False

# ================= 主应用 =================

class Mp4TranscoderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🎬 MP4 通用转码器")
        self.root.geometry("460x220")
        self.root.resizable(False, False)

        self.input_path = tk.StringVar()
        self.status = tk.StringVar(value="请选择 MP4 文件")

        self.build_ui()

        if not check_ffmpeg():
            messagebox.showwarning(
                "FFmpeg 未检测到",
                "未检测到 ffmpeg，转码可能失败。\n"
                "请确认 ffmpeg.exe 在 PATH 或脚本同目录。"
            )

    # ---------- UI ----------
    def build_ui(self):
        frame = tk.Frame(self.root, padx=12, pady=12)
        frame.pack(fill="both", expand=True)

        tk.Entry(frame, textvariable=self.input_path, width=55).pack(pady=5)

        tk.Button(
            frame,
            text="选择 MP4 文件",
            command=self.select_file
        ).pack(pady=4)

        self.progress = ttk.Progressbar(
            frame, length=420, mode="indeterminate"
        )
        self.progress.pack(pady=6)

        tk.Button(
            frame,
            text="开始转码（通用 MP4）",
            height=2,
            command=self.start_transcode
        ).pack(pady=6)

        tk.Label(
            frame,
            textvariable=self.status,
            fg="#0078d7"
        ).pack(pady=4)

    # ---------- 功能 ----------
    def select_file(self):
        path = filedialog.askopenfilename(
            title="选择 MP4 文件",
            filetypes=[("MP4 files", "*.mp4")]
        )
        if path:
            self.input_path.set(path)
            self.status.set("已选择文件")

    def start_transcode(self):
        if not self.input_path.get():
            messagebox.showerror("错误", "请先选择 MP4 文件")
            return

        self.progress.start()
        self.status.set("正在转码...")
        threading.Thread(target=self.transcode, daemon=True).start()

    def transcode(self):
        src = self.input_path.get()
        dst = os.path.splitext(src)[0] + "_通用.mp4"

        cmd = [
            get_ffmpeg_path(),
            "-y",
            "-i", src,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            dst
        ]

        try:
            subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=self._startupinfo(),
                check=True
            )
            self.root.after(0, self.on_success, dst)
        except Exception as e:
            self.root.after(0, self.on_fail, str(e))

    def _startupinfo(self):
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return si

    # ---------- 回调 ----------
    def on_success(self, path):
        self.progress.stop()
        self.status.set("转码完成")
        messagebox.showinfo("完成", f"转码完成：\n{path}")

    def on_fail(self, err):
        self.progress.stop()
        self.status.set("转码失败")
        messagebox.showerror("失败", f"转码失败：\n{err}")

# ================= 启动入口 =================

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = Mp4TranscoderApp(root)
        root.mainloop()
    except Exception as e:
        messagebox.showerror("启动失败", str(e))
