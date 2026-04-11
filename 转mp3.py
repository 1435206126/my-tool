import subprocess
import os
import sys
from tkinter import Tk, filedialog, messagebox

def convert_to_mp3(input_path):
    base, _ = os.path.splitext(input_path)
    output_path = base + ".mp3"

    cmd = [
        "ffmpeg",
        "-y",                 # 覆盖同名文件
        "-i", input_path,     # 输入文件
        "-vn",                # 不要视频
        "-acodec", "libmp3lame",
        "-ab", "100k",        # 比特率
        output_path
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        messagebox.showinfo("完成", f"转换完成：\n{output_path}")
    except Exception as e:
        messagebox.showerror("错误", "转换失败，请确认 ffmpeg 已正确安装")

def main():
    root = Tk()
    root.withdraw()  # 不显示主窗口

    file_path = filedialog.askopenfilename(
        title="选择要转换的文件",
        filetypes=[("所有文件", "*.*")]
    )

    if not file_path:
        sys.exit()

    convert_to_mp3(file_path)

if __name__ == "__main__":
    main()
