import os
import math
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox
from PIL import Image, ImageTk, ImageOps, ImageFile

# 允许加载部分损坏的图片
ImageFile.LOAD_TRUNCATED_IMAGES = True

class ImageRenamerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("极简文件点选改名工具 (固定网格防遮挡版)")
        
        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()
        self.root.geometry(f"{self.screen_w}x{self.screen_h}")
        self.root.state('zoomed')
        
        self.folder_path = os.path.dirname(os.path.abspath(__file__))
        self.available_nums = []  
        self.max_num = 0          
        self.selected_info = {}   
        self.current_paths = {}   
        
        self.file_list = []       
        self.original_images = {} 
        self.tk_cache = {}        
        self.is_truncated = {}    
        
        self.thumb_size = 150     
        self.spacing = 15         # 格子与格子之间的距离
        self.padding_inside = 10  # 格子内部的留白
        self.columns = 1
        
        self.zoom_job = None      
        
        self.hover_idx = -1
        self.tooltip_timer = None

        self.setup_ui()
        self.load_files_into_memory()
        self.calculate_fit_screen_size()
        self.render_grid()

    def setup_ui(self):
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.main_frame, bg="#f5f5f5", highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self.main_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas.bind("<Button-1>", self.on_click)
        self.root.bind("<MouseWheel>", self.on_mousewheel)             
        self.root.bind("<Control-MouseWheel>", self.on_zoom)           
        
        self.canvas.bind("<Motion>", self.on_mouse_motion)
        self.canvas.bind("<Leave>", lambda e: self.hide_tooltip())

    def load_files_into_memory(self):
        current_script = os.path.abspath(__file__)
        img_exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'}
        
        for f in os.listdir(self.folder_path):
            full_path = os.path.join(self.folder_path, f)
            if full_path == current_script or os.path.isdir(full_path): 
                continue    
            
            self.file_list.append(full_path)
            self.current_paths[full_path] = full_path

        if not self.file_list:
            messagebox.showinfo("提示", "当前文件夹内没有文件！")
            self.root.destroy()
            return

        for path in self.file_list:
            ext = os.path.splitext(path)[1].lower()
            is_image = ext in img_exts
            img_obj = None
            
            if is_image:
                try:
                    img = Image.open(path)
                    img = ImageOps.exif_transpose(img) 
                    img = img.convert("RGB") 
                    img.thumbnail((800, 800))
                    img_obj = img
                except Exception:
                    is_image = False 
                    
            if not is_image:
                img_obj = Image.new('RGB', (400, 400), color="#e0e0e0")
                
            self.original_images[path] = {
                'img': img_obj,
                'is_img': is_image,
                'ext': ext[1:].upper() if len(ext) > 1 else "FILE"
            }

    def get_truncated_text_by_pixels(self, text, font_obj, max_pixels):
        if font_obj.measure(text) <= max_pixels:
            return text
            
        ext = ""
        if "." in text:
            parts = text.rsplit(".", 1)
            text_body = parts[0]
            ext = "." + parts[1]
        else:
            text_body = text

        for i in range(len(text_body), 0, -1):
            left_len = i // 2
            right_len = i - left_len
            test_str = (text_body[:left_len] + "..." + text_body[-right_len:] + ext) if right_len > 0 else (text_body[:left_len] + "..." + ext)
            if font_obj.measure(test_str) <= max_pixels:
                return test_str
        return "..."

    def calculate_fit_screen_size(self):
        total_files = len(self.file_list)
        if total_files == 0: return

        ratio = self.screen_w / self.screen_h
        c = math.ceil(math.sqrt(total_files * ratio))
        r = math.ceil(total_files / c)

        max_w = (self.screen_w - self.spacing * (c + 1)) / c
        max_h = (self.screen_h - self.spacing * (r + 1)) / r
        
        # 预留文本高度
        self.thumb_size = int(min(max_w, max_h * 0.8)) - self.padding_inside * 2
        if self.thumb_size < 50: self.thumb_size = 50 

    def get_grid_metrics(self):
        """计算格子的统一标准尺寸（严格盒子模型）"""
        cell_w = self.thumb_size + self.padding_inside * 2
        text_area_h = max(30, int(self.thumb_size * 0.2)) # 为文本固定预留的高度
        cell_h = self.thumb_size + self.padding_inside * 2 + text_area_h
        return cell_w, cell_h

    def on_zoom(self, event):
        self.hide_tooltip()
        if event.delta > 0:
            self.thumb_size += 20
        else:
            self.thumb_size -= 20
            
        if self.thumb_size < 50: self.thumb_size = 50
        if self.thumb_size > 800: self.thumb_size = 800

        if self.zoom_job:
            self.root.after_cancel(self.zoom_job)
        self.zoom_job = self.root.after(100, self.render_grid)

    def on_mousewheel(self, event):
        self.hide_tooltip()
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def render_grid(self):
        self.canvas.delete("all")
        self.tk_cache.clear()
        
        cell_w, cell_h = self.get_grid_metrics()
        
        self.columns = max(1, (self.root.winfo_width() - self.spacing) // (cell_w + self.spacing))
        if self.columns <= 1: 
            self.columns = max(1, (self.screen_w - self.spacing) // (cell_w + self.spacing))

        for idx, path in enumerate(self.file_list):
            self.draw_single_item(idx, path)

        total_rows = math.ceil(len(self.file_list) / self.columns)
        total_height = self.spacing + total_rows * (cell_h + self.spacing)
        self.canvas.configure(scrollregion=(0, 0, self.screen_w, total_height))

    def draw_single_item(self, idx, path):
        cell_w, cell_h = self.get_grid_metrics()
        
        col = idx % self.columns
        row = idx // self.columns
        
        # 计算该格子的左上角坐标 (x0, y0) 和 右下角坐标 (x1, y1)
        x0 = self.spacing + col * (cell_w + self.spacing)
        y0 = self.spacing + row * (cell_h + self.spacing)
        x1 = x0 + cell_w
        y1 = y0 + cell_h

        # 绘制格子的外边框（浅灰色结界）
        self.canvas.create_rectangle(x0, y0, x1, y1, outline="#cccccc", fill="#ffffff", tags=(f"item_{idx}", "bg_box"))

        font_size = max(9, int(self.thumb_size * 0.08))
        num_font_size = max(20, int(self.thumb_size * 0.4))
        custom_font = tkfont.Font(family="Microsoft YaHei", size=font_size)

        data = self.original_images[path]
        is_selected = path in self.selected_info

        if is_selected:
            display_img = data['img'].convert('L').point(lambda p: p * 0.5)
        else:
            display_img = data['img'].copy()

        display_img.thumbnail((self.thumb_size, self.thumb_size))
        tk_img = ImageTk.PhotoImage(display_img)
        self.tk_cache[f"{path}_{is_selected}"] = tk_img 

        # 计算图片放置中心
        img_x = x0 + cell_w // 2
        img_y = y0 + self.padding_inside + self.thumb_size // 2

        self.canvas.create_image(img_x, img_y, image=tk_img, anchor="center", tags=(f"item_{idx}", "image"))
        
        if not data['is_img']:
            ext_font_size = max(12, int(self.thumb_size * 0.2))
            self.canvas.create_text(img_x, img_y, text=data['ext'], 
                                    font=("Microsoft YaHei", ext_font_size, "bold"), 
                                    fill="#aaaaaa", tags=(f"item_{idx}",))

        # 文件名处理：绝对限制在格子内部（两边各留5像素余量）
        current_name = os.path.basename(self.current_paths[path])
        max_text_width = cell_w - 10 
        
        trunc_name = self.get_truncated_text_by_pixels(current_name, custom_font, max_text_width)
        self.is_truncated[path] = (trunc_name != current_name)
        
        # 文本放在图片正下方
        text_y = y0 + self.padding_inside + self.thumb_size + 5
        self.canvas.create_text(img_x, text_y, text=trunc_name, font=custom_font, 
                                fill="#333333", anchor="n", tags=(f"item_{idx}",))

        # 选中红字
        if is_selected:
            num = self.selected_info[path]
            self.canvas.create_text(img_x, img_y, text=str(num), 
                                    font=("Microsoft YaHei", num_font_size, "bold"), 
                                    fill="#ff2222", tags=(f"item_{idx}",))

    # ================= 悬停提示框核心逻辑 (带防越界 & 多行) =================
    def on_mouse_motion(self, event):
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        cell_w, cell_h = self.get_grid_metrics()

        # 根据带间距的网格计算鼠标停留在哪个格子
        col = int((canvas_x - self.spacing) // (cell_w + self.spacing))
        row = int((canvas_y - self.spacing) // (cell_h + self.spacing))
        idx = row * self.columns + col

        # 校验坐标是否在格子的空白间隙里，或者超出边界
        if col < 0 or col >= self.columns or row < 0 or idx >= len(self.file_list):
            idx = -1
        else:
            # 精确校验：鼠标是否在格子的实际范围内（而不是间隙中）
            x0 = self.spacing + col * (cell_w + self.spacing)
            y0 = self.spacing + row * (cell_h + self.spacing)
            if not (x0 <= canvas_x <= x0 + cell_w and y0 <= canvas_y <= y0 + cell_h):
                idx = -1

        if idx != self.hover_idx:
            self.hover_idx = idx
            self.hide_tooltip()
            
            if self.tooltip_timer:
                self.root.after_cancel(self.tooltip_timer)
                
            if idx != -1:
                self.tooltip_timer = self.root.after(500, lambda: self.show_tooltip(idx, canvas_x, canvas_y))

    def show_tooltip(self, idx, x, y):
        self.hide_tooltip() 
        path = self.file_list[idx]
        
        if not self.is_truncated.get(path, False):
            return
            
        full_name = os.path.basename(self.current_paths[path])
        
        # width=300 实现自动换行多行显示
        text_id = self.canvas.create_text(x + 15, y + 15, text=full_name, font=("Microsoft YaHei", 10), 
                                          fill="#ffffff", anchor="nw", width=300, justify="left", state="disabled", tags="tooltip_element")
        
        bbox = self.canvas.bbox(text_id)
        pad = 6
        bg_id = self.canvas.create_rectangle(bbox[0]-pad, bbox[1]-pad, bbox[2]+pad, bbox[3]+pad, 
                                             fill="#222222", outline="#555555", state="disabled", tags="tooltip_element")
        self.canvas.tag_lower(bg_id, text_id)
        
        # === 边缘碰撞检测算法（防止气泡弹到屏幕外面） ===
        bg_bbox = self.canvas.bbox(bg_id)
        shift_x, shift_y = 0, 0
        
        # 获取当前可视区域的真实坐标范围
        visible_right = self.canvas.canvasx(self.root.winfo_width())
        visible_bottom = self.canvas.canvasy(self.root.winfo_height())
        
        # 如果气泡右边缘超出了可视右边缘，向左推
        if bg_bbox[2] > visible_right:
            shift_x = visible_right - bg_bbox[2] - 15 
        # 如果气泡下边缘超出了可视下边缘，向上推
        if bg_bbox[3] > visible_bottom:
            shift_y = visible_bottom - bg_bbox[3] - 15 
            
        if shift_x != 0 or shift_y != 0:
            self.canvas.move(text_id, shift_x, shift_y)
            self.canvas.move(bg_id, shift_x, shift_y)

    def hide_tooltip(self):
        self.canvas.delete("tooltip_element")

    # =====================================================

    def on_click(self, event):
        self.hide_tooltip() 
        
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        cell_w, cell_h = self.get_grid_metrics()

        col = int((canvas_x - self.spacing) // (cell_w + self.spacing))
        row = int((canvas_y - self.spacing) // (cell_h + self.spacing))
        idx = row * self.columns + col

        if col < 0 or col >= self.columns or row < 0 or idx >= len(self.file_list): return
        
        # 精确校验点击
        x0 = self.spacing + col * (cell_w + self.spacing)
        y0 = self.spacing + row * (cell_h + self.spacing)
        if not (x0 <= canvas_x <= x0 + cell_w and y0 <= canvas_y <= y0 + cell_h):
            return

        orig_path = self.file_list[idx]
        current_path = self.current_paths[orig_path]
        dir_name = os.path.dirname(orig_path)
        base_name = os.path.basename(orig_path)

        if orig_path in self.selected_info:
            num = self.selected_info.pop(orig_path)
            self.available_nums.append(num)
            self.available_nums.sort()
            new_path = os.path.join(dir_name, base_name)
        else:
            if self.available_nums:
                num = self.available_nums.pop(0)
            else:
                self.max_num += 1
                num = self.max_num
            self.selected_info[orig_path] = num
            new_name = f"{num}{base_name}"
            new_path = os.path.join(dir_name, new_name)

        try:
            os.rename(current_path, new_path)
            self.current_paths[orig_path] = new_path
        except Exception as e:
            messagebox.showerror("错误", f"重命名被系统拒绝，请检查文件是否被打开！\n{e}")
            return

        self.canvas.delete(f"item_{idx}")
        self.draw_single_item(idx, orig_path)


if __name__ == "__main__":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
        
    root = tk.Tk()
    app = ImageRenamerApp(root)
    root.mainloop()