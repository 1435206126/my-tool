import os
import sys
import re
import json
import shutil
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk, messagebox
import pyperclip
import yt_dlp
import humanize
from googletrans import Translator

CONFIG_FILE = "config.json"

# ---------------- 配置管理 ----------------
def load_config():
    default_path = os.path.join(os.getcwd(), "")
    if not os.path.exists(default_path):
        os.makedirs(default_path)
    config = {"download_path": default_path}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if os.path.exists(data.get("download_path", "")):
                    config["download_path"] = data["download_path"]
        except:
            pass
    return config

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f)

# ---------------- FFmpeg ----------------
def get_ffmpeg_path():
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(base_path, "ffmpeg.exe")
    return target if os.path.exists(target) else "ffmpeg"

def check_ffmpeg():
    return shutil.which("ffmpeg") is not None or os.path.exists(get_ffmpeg_path())

def sanitize_filename(name):
    name = re.sub(r'[\\/:*?"<>|]', '', name)
    return name.strip()

def transcode_video(input_path, output_path):
    ffmpeg_path = get_ffmpeg_path()
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    cmd = [
        ffmpeg_path, '-i', input_path,
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-y', output_path
    ]
    subprocess.run(cmd, startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# ---------------- 主程序 ----------------
class TwitterDownloaderApp:
    def __init__(self, root):
        self.root = root
        root.title("🐦 Twitter 视频下载+转码")
        root.geometry("400x750")

        self.config = load_config()
        self.downloading = False
        self.translator = Translator()
        self.default_font = ("Microsoft YaHei", 10)
        self.top_state = True  # 默认置顶
        root.attributes("-topmost", self.top_state)

        # 保存路径
        frame_path = tk.LabelFrame(root, text="📂 保存位置", padx=10, pady=5, font=self.default_font)
        frame_path.pack(fill="x", padx=10, pady=5)
        self.path_var = tk.StringVar(value=self.config["download_path"])
        tk.Entry(frame_path, textvariable=self.path_var, state="readonly", bg="#f0f0f0", font=self.default_font).pack(side="left", fill="x", expand=True)
        tk.Button(frame_path, text="更改文件夹", command=self.select_folder, font=self.default_font).pack(side="left", padx=5)

        # 链接输入
        frame_url = tk.LabelFrame(root, text="🔗 视频链接", padx=10, pady=5, font=self.default_font)
        frame_url.pack(fill="x", padx=10, pady=5)
        self.url_var = tk.StringVar()
        tk.Entry(frame_url, textvariable=self.url_var, font=self.default_font).pack(side="left", fill="x", expand=True)

        # 功能按钮
        frame_btn = tk.Frame(root)
        frame_btn.pack(pady=5)
        tk.Button(frame_btn, text="📋 粘贴并解析", command=self.parse_clipboard_url, bg="#e1f5fe", font=(self.default_font[0], 10, "bold"), width=15).pack(side="left", padx=10)
        self.top_btn = tk.Button(frame_btn, text="📍 取消置顶", command=self.toggle_top, font=self.default_font)
        self.top_btn.pack(side="left", padx=10)

        # 状态与进度
        self.status_var = tk.StringVar(value="准备就绪")
        tk.Label(root, textvariable=self.status_var, fg="#0078d7", font=self.default_font).pack(pady=(5,0))
        self.progress = ttk.Progressbar(root, orient="horizontal", length=350, mode="determinate")
        self.progress.pack(padx=10, pady=5)

        # 结果显示
        tk.Label(root, text="解析结果：", anchor="w", font=self.default_font).pack(fill="x", padx=10, pady=(10,0))
        self.result_box = scrolledtext.ScrolledText(root, width=80, height=20, font=self.default_font)
        self.result_box.pack(padx=10, pady=5, fill="both", expand=True)

        # FFmpeg 提示
        if not check_ffmpeg():
            tk.Label(root, text="⚠️ 未检测到 FFmpeg，可能无法转码！", fg="red", font=self.default_font).pack(pady=2)

    def toggle_top(self):
        self.top_state = not self.top_state
        self.root.attributes("-topmost", self.top_state)
        self.top_btn.config(text="📌 置顶窗口" if not self.top_state else "📍 取消置顶")

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.path_var.set(folder)
            self.config["download_path"] = folder
            save_config(self.config)

    def parse_clipboard_url(self):
        try:
            url = pyperclip.paste().strip()
        except:
            url = ""
        if not url or "http" not in url:
            self.status_var.set("❌ 剪贴板没有有效链接")
            return
        self.url_var.set(url)
        self.status_var.set("⏳ 正在解析视频...")
        self.result_box.delete("1.0", tk.END)
        threading.Thread(target=self.analyze, args=(url,), daemon=True).start()

    def translate_text(self, text):
        try:
            translated = self.translator.translate(text, dest='zh-cn')
            return translated.text
        except:
            return text

    def analyze(self, url):
        try:
            ydl_opts = {"quiet": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "twitter_video")
                video_id = info.get("id", "")
                description = info.get("description", "")
                description = re.sub(r'^@\S+\s*', '', description)
                translated_desc = self.translate_text(description)
                self.result_box.insert(tk.END, f"标题: {title}\n正文翻译: {translated_desc}\n{'-'*50}\n")

                # 收集所有 MP4 视频版本
                formats = info.get("formats", [])
                valid_formats = []
                for f in formats:
                    if f.get("vcodec") != 'none' and f.get("ext") == "mp4":
                        filesize = f.get("filesize") or f.get("filesize_approx") or 0
                        valid_formats.append({
                            "id": f["format_id"],
                            "res": f.get("resolution") or f"{f.get('width')}x{f.get('height')}",
                            "size_bytes": filesize,
                            "size_str": humanize.naturalsize(filesize) if filesize>0 else "未知大小",
                            "tbr": f.get("tbr") or 0
                        })

                if not valid_formats:
                    self.status_var.set("❌ 未找到可用视频")
                    return

                # 按分辨率排序，显示每个版本下载按钮
                valid_formats = sorted(valid_formats, key=lambda x: x["tbr"], reverse=True)
                self.status_var.set("✅ 解析成功")

                for f in valid_formats:
                    btn_text = f"下载 {f['res']} ({f['size_str']})"
                    info_text = f"📺 分辨率: {f['res']} | 大小: {f['size_str']}  "
                    self.result_box.insert(tk.END, info_text)
                    btn = tk.Button(self.result_box, text=btn_text, cursor="hand2", bg="#f0f0f0",
                                    font=self.default_font,
                                    command=lambda fid=f['id'], u=url, t=title, desc=translated_desc, vid=video_id:
                                    self.start_download(fid, u, t, desc, vid))
                    self.result_box.window_create(tk.END, window=btn)
                    self.result_box.insert(tk.END, "\n\n")

        except Exception as e:
            self.status_var.set("❌ 解析出错")
            self.result_box.insert(tk.END, str(e))

    def start_download(self, fmt_id, url, title, translated_desc, video_id):
        if self.downloading:
            self.status_var.set("❌ 已有任务在下载")
            return
        threading.Thread(target=self.download_and_transcode, args=(url, fmt_id, title, translated_desc, video_id), daemon=True).start()

    def download_and_transcode(self, url, fmt_id, title, translated_desc, video_id):
        self.downloading = True
        save_path = self.path_var.get()
        safe_text = sanitize_filename(translated_desc).replace("\n"," ")[:80] or f"twitter_{video_id}"
        tmp_file = os.path.join(save_path, f"{safe_text}_tmp.mp4")
        final_file = os.path.join(save_path, f"{safe_text}.mp4")

        self.progress['value'] = 0
        self.status_var.set(f"⬇️ 下载中: {safe_text}.mp4")

        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    p = d.get('_percent_str','0%').replace('%','')
                    self.progress['value'] = float(p)
                    self.status_var.set(f"⬇️ 下载中 {d.get('_percent_str')} | 速度: {d.get('_speed_str')}")
                except: pass
            elif d['status'] == 'finished':
                self.progress['value'] = 100
                self.status_var.set("⬇️ 下载完成，开始转码...")

        fmt_str = f"{fmt_id}+bestaudio/best" if check_ffmpeg() else f"{fmt_id}/best"
        ydl_opts = {
            "format": fmt_str,
            "outtmpl": tmp_file,
            "progress_hooks": [progress_hook],
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            self.status_var.set(f"❌ 下载失败: {str(e)}")
            self.downloading = False
            return

        # 转码
        try:
            transcode_video(tmp_file, final_file)
            os.remove(tmp_file)
            self.status_var.set(f"✅ 下载并转码完成: {final_file}")
        except Exception as e:
            self.status_var.set(f"❌ 转码失败: {str(e)}")

        self.downloading = False

if __name__ == "__main__":
    root = tk.Tk()
    app = TwitterDownloaderApp(root)
    root.mainloop()
