import os
import json
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk
import threading
import pyperclip
import yt_dlp
import humanize
import shutil
import re

# --- 配置管理 ---
CONFIG_FILE = "config.json"

def load_config():
    default_path = os.path.join(os.getcwd(), "downloads")
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

def check_ffmpeg():
    return shutil.which("ffmpeg") is not None

def sanitize_filename(name):
    name = re.sub(r'[\\/:*?"<>|]', '', name)
    return name.strip()

# --- 主程序界面 ---
class TwitterDownloaderApp:
    def __init__(self, root):
        self.root = root
        root.title("🐦 推特视频下载助手 (增强版)")
        root.geometry("680x600")
        
        self.config = load_config()
        self.downloading = False

        self.default_font = ("Microsoft YaHei", 10)

        # 1. 顶部：保存路径
        frame_path = tk.LabelFrame(root, text="📂 保存位置", padx=10, pady=5, font=self.default_font)
        frame_path.pack(fill="x", padx=10, pady=5)
        
        self.path_var = tk.StringVar(value=self.config["download_path"])
        tk.Entry(frame_path, textvariable=self.path_var, state="readonly", bg="#f0f0f0", font=self.default_font).pack(side="left", fill="x", expand=True)
        tk.Button(frame_path, text="更改文件夹", command=self.select_folder, font=self.default_font).pack(side="left", padx=5)

        # 2. 中部：链接输入
        frame_url = tk.LabelFrame(root, text="🔗 视频链接", padx=10, pady=5, font=self.default_font)
        frame_url.pack(fill="x", padx=10, pady=5)
        
        self.url_var = tk.StringVar()
        self.url_entry = tk.Entry(frame_url, textvariable=self.url_var, font=self.default_font)
        self.url_entry.pack(side="left", fill="x", expand=True)
        
        # 3. 功能按钮
        frame_btn = tk.Frame(root)
        frame_btn.pack(pady=5)
        
        tk.Button(frame_btn, text="📋 粘贴并解析", command=self.parse_clipboard_url, bg="#e1f5fe", font=(self.default_font[0], 10, "bold"), width=15).pack(side="left", padx=10)
        self.top_btn = tk.Button(frame_btn, text="📌 置顶窗口", command=self.toggle_top, font=self.default_font)
        self.top_btn.pack(side="left", padx=10)

        # 4. 状态与进度
        self.status_var = tk.StringVar(value="准备就绪")
        tk.Label(root, textvariable=self.status_var, fg="#0078d7", font=self.default_font).pack(pady=(5, 0))
        
        self.progress = ttk.Progressbar(root, orient="horizontal", length=600, mode="determinate")
        self.progress.pack(padx=10, pady=5)

        # 5. 结果列表
        tk.Label(root, text="解析结果 (点击对应按钮下载)：", anchor="w", font=self.default_font).pack(fill="x", padx=10, pady=(10, 0))
        self.result_box = scrolledtext.ScrolledText(root, width=80, height=15, font=self.default_font)
        self.result_box.pack(padx=10, pady=5, fill="both", expand=True)
        
        self.top_state = False

        # FFmpeg 提示
        if not check_ffmpeg():
            tk.Label(root, text="⚠️ 未检测到 FFmpeg，将尝试下载兼容格式 (可能非最高画质)", fg="red", font=self.default_font).pack(pady=2)

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.path_var.set(folder)
            self.config["download_path"] = folder
            save_config(self.config)

    def toggle_top(self):
        self.top_state = not self.top_state
        self.root.attributes("-topmost", self.top_state)
        self.top_btn.config(text="📍 取消置顶" if self.top_state else "📌 置顶窗口")

    def parse_clipboard_url(self):
        try:
            url = pyperclip.paste().strip()
        except:
            url = ""
            
        if not url or "http" not in url:
            self.status_var.set("❌ 剪贴板没有有效链接")
            return

        self.url_var.set(url)
        self.status_var.set("⏳ 正在联网解析视频，请稍候...")
        self.result_box.delete("1.0", tk.END)
        threading.Thread(target=self.analyze, args=(url,), daemon=True).start()

    def analyze(self, url):
        try:
            ydl_opts = {"quiet": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "twitter_video")
                video_id = info.get("id", "")
                formats = info.get("formats", [])

                valid_formats = []
                for f in formats:
                    if f.get("vcodec") != 'none' and f.get("ext") == "mp4":
                        filesize = f.get("filesize") or f.get("filesize_approx") or 0
                        valid_formats.append({
                            "id": f["format_id"],
                            "res": f.get("resolution") or f"{f.get('width')}x{f.get('height')}",
                            "height": f.get("height") or 0,
                            "size_bytes": filesize,
                            "size_str": humanize.naturalsize(filesize) if filesize > 0 else "未知大小",
                            "tbr": f.get("tbr") or 0
                        })

                if not valid_formats:
                    self.status_var.set("❌ 解析失败：未找到可用视频")
                    return

                unique_formats = {}
                for f in valid_formats:
                    h = f["height"]
                    if h not in unique_formats or f["tbr"] > unique_formats[h]["tbr"]:
                        unique_formats[h] = f
                
                sorted_formats = sorted(unique_formats.values(), key=lambda x: x["height"], reverse=True)

                self.status_var.set(f"✅ 解析成功: {title[:30]}...")
                self.result_box.insert(tk.END, f"视频标题: {title}\n")
                self.result_box.insert(tk.END, "-" * 50 + "\n")

                for f in sorted_formats:
                    btn_text = f"下载 {f['res']} ({f['size_str']})"
                    info_text = f"📺 分辨率: {f['res']} | 大小: {f['size_str']}  "
                    self.result_box.insert(tk.END, info_text)
                    
                    btn = tk.Button(self.result_box, text=btn_text, cursor="hand2", bg="#f0f0f0",
                                    font=self.default_font,
                                    command=lambda fid=f['id'], u=url, t=title, vid=video_id: 
                                    self.start_download(fid, u, t, vid))
                    self.result_box.window_create(tk.END, window=btn)
                    self.result_box.insert(tk.END, "\n\n")

        except Exception as e:
            self.status_var.set("❌ 解析出错")
            self.result_box.insert(tk.END, f"错误信息: {str(e)}")

    def start_download(self, fmt_id, url, title, video_id):
        if self.downloading:
            self.status_var.set("❌ 当前已有任务在下载，请等待完成")
            return
        self.downloading = True
        threading.Thread(target=self.download_task, args=(fmt_id, url, title, video_id), daemon=True).start()

    def download_task(self, fmt_id, url, title, video_id):
        save_path = self.path_var.get()
        safe_title = sanitize_filename(title)
        if not safe_title or len(safe_title) > 100:
            safe_title = f"twitter_{video_id}"
        filename = f"{safe_title}.mp4"
        outtmpl = os.path.join(save_path, f"{safe_title}.%(ext)s")

        self.status_var.set(f"⬇️ 下载中: {filename}")
        self.progress['value'] = 0

        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    p = d.get('_percent_str', '0%').replace('%','')
                    self.progress['value'] = float(p)
                    self.status_var.set(f"⬇️ 下载中 {d.get('_percent_str')} | 速度: {d.get('_speed_str')}")
                except:
                    pass
            elif d['status'] == 'finished':
                self.progress['value'] = 100
                self.status_var.set("✅ 下载完成")

        fmt_str = f"{fmt_id}+bestaudio/best" if check_ffmpeg() else f"{fmt_id}/best"

        ydl_opts = {
            "format": fmt_str,
            "outtmpl": outtmpl,
            "progress_hooks": [progress_hook],
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            self.status_var.set(f"❌ 下载失败: {str(e)}")
        finally:
            self.downloading = False

if __name__ == "__main__":
    root = tk.Tk()
    app = TwitterDownloaderApp(root)
    root.mainloop()
