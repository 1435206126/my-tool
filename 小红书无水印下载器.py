import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk
import pyperclip
import yt_dlp
import humanize

# --------------------
# 工具函数
# --------------------
def sanitize_filename(name):
    name = re.sub(r'[\\/:*?"<>|]', '', name)
    return name.strip()

def select_folder():
    folder = filedialog.askdirectory()
    if folder:
        path_var.set(folder)

# --------------------
# 主逻辑
# --------------------
class XHSDownloaderApp:
    def __init__(self, root):
        self.root = root
        root.title("📌 小红书无水印下载器")
        root.geometry("300x900")
        root.attributes("-topmost", True)  # 默认置顶

        # 保存路径
        global path_var
        path_var = tk.StringVar(value=os.path.join(os.getcwd(), ""))
        frame_path = tk.LabelFrame(root, text="📂 保存路径", padx=10, pady=5)
        frame_path.pack(fill="x", padx=10, pady=5)
        tk.Entry(frame_path, textvariable=path_var, state="readonly").pack(side="left", fill="x", expand=True)
        tk.Button(frame_path, text="更改", command=select_folder).pack(side="left", padx=5)

        # 功能按钮：粘贴并解析
        tk.Button(root, text="📋 粘贴并解析", command=self.paste_and_parse, bg="#4caf50", fg="white").pack(pady=10)

        # 状态
        self.status_var = tk.StringVar(value="准备就绪")
        tk.Label(root, textvariable=self.status_var).pack()
        self.progress = ttk.Progressbar(root, orient="horizontal", length=350, mode="determinate")
        self.progress.pack(pady=5)

        # 结果列表
        tk.Label(root, text="解析结果 (点击下载)：").pack(anchor="w", padx=10)
        self.result_box = scrolledtext.ScrolledText(root, width=50, height=15)
        self.result_box.pack(padx=10, pady=5, fill="both", expand=True)

        self.downloading = False

    # 粘贴剪贴板并解析
    def paste_and_parse(self):
        try:
            url = pyperclip.paste().strip()
        except:
            url = ""
        if not url or "http" not in url:
            self.status_var.set("❌ 剪贴板没有有效链接")
            return

        self.result_box.delete("1.0", tk.END)
        self.status_var.set("⏳ 正在解析视频，请稍候...")
        threading.Thread(target=self.analyze, args=(url,), daemon=True).start()

    # 解析视频
    def analyze(self, url):
        try:
            ydl_opts = {"quiet": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "xhs_video")
                video_id = info.get("id", "")
                formats = info.get("formats", [])

                valid_formats = []
                for f in formats:
                    if f.get("vcodec") != 'none' and f.get("ext") == "mp4":
                        filesize = f.get("filesize") or f.get("filesize_approx") or 0
                        valid_formats.append({
                            "id": f["format_id"],
                            "res": f.get("resolution") or f"{f.get('width')}x{f.get('height')}",
                            "size_bytes": filesize,
                            "size_str": humanize.naturalsize(filesize) if filesize > 0 else "未知大小",
                            "tbr": f.get("tbr") or 0
                        })

                if not valid_formats:
                    self.status_var.set("❌ 解析失败：未找到可用视频")
                    return

                # 去重同分辨率，选最高码率
                unique_formats = {}
                for f in valid_formats:
                    h = f["res"]
                    if h not in unique_formats or f["tbr"] > unique_formats[h]["tbr"]:
                        unique_formats[h] = f
                sorted_formats = sorted(unique_formats.values(), key=lambda x: int(re.sub("[^0-9]", "", x["res"]) or 0), reverse=True)

                self.status_var.set(f"✅ 解析成功: {title[:30]}...")
                self.result_box.insert(tk.END, f"视频标题: {title}\n" + "-"*40 + "\n")

                for f in sorted_formats:
                    btn_text = f"下载 {f['res']} ({f['size_str']})"
                    btn = tk.Button(self.result_box, text=btn_text, cursor="hand2", bg="#f0f0f0",
                                    command=lambda fid=f['id'], u=url, t=title, vid=video_id: self.start_download(fid, u, t, vid))
                    self.result_box.window_create(tk.END, window=btn)
                    self.result_box.insert(tk.END, "\n\n")

        except Exception as e:
            self.status_var.set("❌ 解析出错")
            self.result_box.insert(tk.END, f"错误信息: {str(e)}\n")

    # 开始下载
    def start_download(self, fmt_id, url, title, video_id):
        if self.downloading:
            self.status_var.set("❌ 当前已有任务在下载")
            return
        self.downloading = True
        threading.Thread(target=self.download_task, args=(fmt_id, url, title, video_id), daemon=True).start()

    def download_task(self, fmt_id, url, title, video_id):
        save_path = path_var.get()
        safe_title = sanitize_filename(title)
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
                self.status_var.set(f"✅ 下载完成: {filename}")

        ydl_opts = {
            "format": f"{fmt_id}/best",
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

# --------------------
# 启动 GUI
# --------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = XHSDownloaderApp(root)
    root.mainloop()
