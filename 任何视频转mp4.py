import subprocess
import tkinter as tk
from tkinter import filedialog
import os
import sys

def main():
    # 隐藏 tkinter 主窗口
    root = tk.Tk()
    root.withdraw()

    # 选择任意视频文件
    input_file = filedialog.askopenfilename(
        title="选择要转换的视频文件",
        filetypes=[
            ("Video files", "*.webm *.mkv *.avi *.mov *.flv *.wmv *.mpg *.mpeg *.m4v *.ts *.rmvb *.3gp"),
            ("All files", "*.*")
        ]
    )

    if not input_file:
        sys.exit(0)

    # 输出 mp4 文件（同目录同名）
    base, _ = os.path.splitext(input_file)
    output_file = base + ".mp4"

    # ffmpeg 转码命令（通用稳妥版）
    command = [
        "ffmpeg",
        "-y",
        "-i", input_file,
        "-map", "0:v:0?",
        "-map", "0:a:0?",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-profile:v", "high",
        "-level", "4.1",
        "-movflags", "+faststart",
        "-c:a", "aac",
        "-b:a", "192k",
        output_file
    ]

    # 执行（不弹黑窗）
    subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW
    )

if __name__ == "__main__":
    main()
