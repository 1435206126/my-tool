import tkinter as tk
from tkinter import scrolledtext
import pyperclip
import threading
import time

# 循环深色列表
colors = ['red', 'black', '#006400', '#00008B', '#654321']  # 红、黑、深绿、深蓝、深棕

class ClipboardApp:
    def __init__(self, root):
        self.root = root
        root.title("自动粘贴工具")

        # 编辑框
        self.editor = scrolledtext.ScrolledText(root, width=80, height=20, wrap=tk.WORD)
        self.editor.pack(padx=10, pady=10)

        # 清空按钮
        self.clear_btn = tk.Button(root, text="清空内容", command=self.clear_content)
        self.clear_btn.pack(pady=5)

        self.last_clipboard = ""
        self.color_index = 0

        # 启动后台线程检测剪贴板
        threading.Thread(target=self.monitor_clipboard, daemon=True).start()

    def clear_content(self):
        self.editor.delete('1.0', tk.END)

    def monitor_clipboard(self):
        while True:
            try:
                clipboard_text = pyperclip.paste()
                # 检查是否是新内容且非空
                if clipboard_text != self.last_clipboard and clipboard_text.strip() != "":
                    self.last_clipboard = clipboard_text
                    self.add_text_block(clipboard_text)
            except Exception as e:
                print("读取剪贴板失败:", e)
            time.sleep(0.5)

    def add_text_block(self, text):
        # 在主线程更新 UI
        self.editor.after(0, lambda: self._insert_text_block(text))

    def _insert_text_block(self, text):
        color = colors[self.color_index]
        tag_name = f"color{self.color_index}"  # 唯一标签

        # 插入文字和空两行
        self.editor.insert(tk.END, text + "\n", (tag_name,))
        self.editor.insert(tk.END, "\n\n", (tag_name,))
        self.editor.tag_config(tag_name, foreground=color)

        # 循环颜色索引
        self.color_index = (self.color_index + 1) % len(colors)

        # 滚动到底部并把光标移动到最下方下一行
        self.editor.see(tk.END)
        self.editor.mark_set("insert", tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = ClipboardApp(root)
    root.mainloop()
