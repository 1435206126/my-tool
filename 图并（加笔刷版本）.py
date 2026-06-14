import os
import json
import base64
import re
import time
import tempfile
import pyperclip
import webview
from PIL import Image, ImageDraw, ImageOps

CONFIG_FILE = 'config.json'

class Api:
    def __init__(self):
        self.save_dir_1 = os.path.expanduser("D:\\yifa\\1\u3010\u6bcf\u65e5\u6742\u56fe\u3011")
        self.save_dir_2 = os.path.expanduser("D:\yifa")
        self.load_config()
        self.temp_dir = os.path.join(tempfile.gettempdir(), "img_merge_temp")
        os.makedirs(self.temp_dir, exist_ok=True)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.save_dir_1 = data.get('save_dir_1', self.save_dir_1)
                    self.save_dir_2 = data.get('save_dir_2', self.save_dir_2)
            except:
                pass

    def save_config(self):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({'save_dir_1': self.save_dir_1, 'save_dir_2': self.save_dir_2}, f)

    def get_save_paths(self):
        return [self.save_dir_1, self.save_dir_2]

    def choose_directory(self, index):
        result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
        if result and len(result) > 0:
            if index == 1:
                self.save_dir_1 = result[0]
            else:
                self.save_dir_2 = result[0]
            self.save_config()
            return result[0]
        return None

    def get_clipboard(self):
        try:
            return pyperclip.paste()
        except:
            return ""

    def stash_temp_file(self, filename, b64_data):
        try:
            header, encoded = b64_data.split(",", 1)
            data = base64.b64decode(encoded)
            safe_name = f"{int(time.time()*1000)}_{filename}"
            filepath = os.path.join(self.temp_dir, safe_name)
            with open(filepath, "wb") as f:
                f.write(data)
            return filepath
        except:
            return ""

    def save_blueprint(self, blueprint_json, is_single, path_index, custom_text):
        try:
            blueprint = json.loads(blueprint_json)
            clip_text = custom_text.strip()
            if clip_text:
                clip_text = re.sub(r'\s+', '', clip_text)
                clip_text = re.sub(r'[\\/*?:"<>|]', '', clip_text)[:100]
            if not clip_text:
                clip_text = "合成图片_" + time.strftime("%H%M%S")

            target_dir = self.save_dir_1 if path_index == 1 else self.save_dir_2
            if not target_dir or not os.path.exists(target_dir):
                target_dir = os.path.expanduser("~/Desktop")

            images_data = blueprint.get('images', [])
            if not images_data:
                return {"success": False, "msg": "无图片可保存"}

            # ============== 模式一：保存单张图片 ==============
            if is_single:
                count = 0
                for i, d in enumerate(images_data):
                    img = Image.open(d['path']).convert("RGBA")
                    crop = d['crop']
                    cropped = img.crop((crop['left'], crop['top'], img.width - crop['right'], img.height - crop['bottom']))

                    if d.get('masks'):
                        for stroke in d['masks']:
                            mask = Image.new('L', cropped.size, 0)
                            draw = ImageDraw.Draw(mask)
                            pts = [(p['x'] - crop['left'], p['y'] - crop['top']) for p in stroke['points']]
                            if len(pts) > 1:
                                draw.line(pts, fill=255, width=stroke['size'], joint='curve')
                            elif len(pts) == 1:
                                rad = stroke['size'] / 2
                                draw.ellipse([pts[0][0]-rad, pts[0][1]-rad, pts[0][0]+rad, pts[0][1]+rad], fill=255)
                            
                            stype = stroke.get('type', 'mosaic')
                            if stype == 'color':
                                layer_img = Image.new('RGBA', cropped.size, stroke.get('color', '#000000'))
                            elif stype == 'invert':
                                layer_img = ImageOps.invert(cropped.convert('RGB')).convert('RGBA')
                            else: # mosaic
                                mosaic = img.resize((max(1, img.width//30), max(1, img.height//30)), Image.Resampling.NEAREST)
                                layer_img = mosaic.resize(img.size, Image.Resampling.NEAREST).crop((crop['left'], crop['top'], img.width - crop['right'], img.height - crop['bottom']))
                            
                            cropped.paste(layer_img, (0, 0), mask)

                    filename = f"{clip_text}_片段{i+1}.png"
                    cropped.save(os.path.join(target_dir, filename), "PNG")
                    count += 1
                return {"success": True, "msg": f"✅ 已极速保存 {count} 张单图到 路径{path_index}"}

            # ============== 模式二：拼接保存长图 ==============
            else:
                max_w = 0
                for d in images_data:
                    w = d['originalWidth'] - d['crop']['left'] - d['crop']['right']
                    if w > max_w: max_w = w

                total_h = 0
                layout = []
                for i, d in enumerate(images_data):
                    w = d['originalWidth'] - d['crop']['left'] - d['crop']['right']
                    h = d['originalHeight'] - d['crop']['top'] - d['crop']['bottom']
                    if w <= 0 or h <= 0: continue
                    scale = max_w / w
                    rw, rh = int(w * scale), int(h * scale)
                    layout.append({'data': d, 'rw': rw, 'rh': rh, 'scale': scale, 'y': total_h})
                    space = d.get('spacingBottom', 0) if i < len(images_data) - 1 else 0
                    total_h += rh + space

                bg_color = blueprint.get('bgColor', '#ffffff')
                bg = Image.new('RGB', (int(max_w), int(total_h)), bg_color)

                for item in layout:
                    d = item['data']
                    crop = d['crop']
                    img = Image.open(d['path']).convert("RGBA")
                    cropped = img.crop((crop['left'], crop['top'], img.width - crop['right'], img.height - crop['bottom']))
                    resized = cropped.resize((item['rw'], item['rh']), Image.Resampling.LANCZOS)

                    if d.get('masks'):
                        for stroke in d['masks']:
                            mask = Image.new('L', (item['rw'], item['rh']), 0)
                            draw = ImageDraw.Draw(mask)
                            pts = [(int((p['x'] - crop['left']) * item['scale']), int((p['y'] - crop['top']) * item['scale'])) for p in stroke['points']]
                            if len(pts) > 1:
                                draw.line(pts, fill=255, width=int(stroke['size'] * item['scale']), joint='curve')
                            elif len(pts) == 1:
                                rad = int(stroke['size'] * item['scale'] / 2)
                                draw.ellipse([pts[0][0]-rad, pts[0][1]-rad, pts[0][0]+rad, pts[0][1]+rad], fill=255)

                            stype = stroke.get('type', 'mosaic')
                            if stype == 'color':
                                layer_img = Image.new('RGBA', (item['rw'], item['rh']), stroke.get('color', '#000000'))
                            elif stype == 'invert':
                                layer_img = ImageOps.invert(resized.convert('RGB')).convert('RGBA')
                            else: # mosaic
                                mosaic = img.resize((max(1, img.width//30), max(1, img.height//30)), Image.Resampling.NEAREST)
                                mosaic = mosaic.resize(img.size, Image.Resampling.NEAREST).crop((crop['left'], crop['top'], img.width - crop['right'], img.height - crop['bottom']))
                                layer_img = mosaic.resize((item['rw'], item['rh']), Image.Resampling.NEAREST)

                            resized.paste(layer_img, (0, 0), mask)

                    if resized.mode == 'RGBA':
                        bg.paste(resized, (0, int(item['y'])), resized)
                    else:
                        bg.paste(resized, (0, int(item['y'])))

                filename = f"{clip_text}.jpg"
                bg.save(os.path.join(target_dir, filename), "JPEG", quality=95)
                return {"success": True, "msg": f"✅ 闪电保存成功: {filename}"}

        except Exception as e:
            return {"success": False, "msg": f"❌ 保存失败: {str(e)}"}

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>图片合成编辑器 - 混合架构极速版</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Roboto, system-ui, sans-serif; }
        body { background: #eef2f7; display: flex; height: 100vh; overflow: hidden; user-select: none; }
        .toast-container { position: fixed; top: 24px; left: 50%; transform: translateX(-50%); z-index: 9999; display: flex; flex-direction: column; gap: 12px; pointer-events: none; }
        .toast { background: rgba(31, 42, 68, 0.9); color: white; padding: 12px 24px; border-radius: 8px; font-size: 14px; font-weight: 500; box-shadow: 0 4px 12px rgba(0,0,0,0.15); opacity: 0; transform: translateY(-20px); transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1); }
        .toast.show { opacity: 1; transform: translateY(0); }
        
        /* --- 彻底解决滚动和等比自适应的核心布局 --- */
        .control-sidebar { width: clamp(200px, 20vw, 300px); background: white; border-right: 1px solid #ddd; flex-shrink: 0; height: 100vh; overflow: hidden; }
        .sidebar-inner { display: flex; flex-direction: column; height: 100vh; padding: 1.5vh 1vw; gap: 1vh; justify-content: space-between; }
        
        .path-row { display: flex; gap: 0.5vw; flex: 1.5; min-height: 0; }
        .filename-row { display: flex; flex: 1.2; min-height: 0; }
        .tools-row-1 { display: flex; gap: 0.5vw; flex: 1; min-height: 0; }
        .spacing-row { display: flex; flex: 0.8; min-height: 0; align-items: center; background: #f8fafc; border-radius: 1vh; padding: 0 1vh; border: 1px solid #e2e8f0; }
        .tools-row-2 { display: flex; gap: 0.5vw; flex: 1.2; min-height: 0; }
        .brush-size-row { display: flex; flex: 0.8; min-height: 0; align-items: center; background: #f4f7fa; border-radius: 1vh; padding: 0 1vh; border: 1px solid #e0e6ed; transition: 0.2s; }
        .save-row { display: flex; flex: 1.5; min-height: 0; }

        .square-btn { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; background: #f8fafd; border: 1px solid #dce5ef; border-radius: 1vh; cursor: pointer; transition: 0.2s; position: relative; color: #2c3e58; }
        .square-btn > span { line-height: 1.2; color: inherit; }
        .square-btn:hover { background: #eef3fc; border-color: #a0bbdf; }
        .square-btn.active-single { background: #e8f0fe; border-color: #4b6cb7; color: #4b6cb7; }
        .square-btn.active-locked { background: #4b6cb7; border-color: #4b6cb7; color: white; box-shadow: 0 4px 12px rgba(75,108,183,0.3); }

        textarea { width: 100%; height: 100%; border: 1px solid #cbd5e1; border-radius: 1vh; padding: 1vh; font-size: 1.3vh; resize: none; outline: none; color: #0f172a; }
        textarea::placeholder { color: #94a3b8; font-size: 1.2vh; }
        input[type="range"] { flex: 1; height: 1vh; border-radius: 1vh; accent-color: #4b6cb7; }
        
        .action-btn-primary { width: 100%; height: 100%; background: #4b6cb7; color: white; border: none; border-radius: 4vh; font-size: 1.5vh; font-weight: bold; cursor: pointer; display: flex; justify-content: center; align-items: center; gap: 1vh; transition: 0.2s; box-shadow: 0 0.5vh 1.5vh rgba(75,108,183,0.2); }
        .action-btn-primary:hover { background: #3a579a; transform: translateY(-1px); }

        .setting-gear { position: absolute; top: 0.5vh; right: 0.5vh; font-size: 1.5vh; cursor: pointer; background: rgba(0,0,0,0.05); border-radius: 50%; width: 2.5vh; height: 2.5vh; display: flex; align-items: center; justify-content: center; transition: 0.2s; }
        .setting-gear:hover { background: rgba(0,0,0,0.15); transform: scale(1.1); }
        /* ---------------------------------------------------- */

        .thumbnail-sidebar { width: 180px; background: #f9fbfd; border-right: 1px solid #e2e8f0; display: flex; flex-direction: column; flex-shrink: 0; height: 100vh; overflow: hidden; }
        .thumbnail-header { padding: 14px 12px; background: white; border-bottom: 1px solid #e6edf4; display: flex; justify-content: space-between; align-items: center; }
        .thumbnail-header h4 { font-size: 13px; font-weight: 600; }
        .select-all-btn { background: #eef2f5; border: 1px solid #dce5ef; color: #4a627a; padding: 5px 10px; border-radius: 30px; font-size: 11px; font-weight: bold; cursor: pointer; transition: 0.2s; }
        .select-all-btn.active { background: #4b6cb7; border-color: #4b6cb7; color: white; }
        .thumbnail-list { flex: 1; overflow-y: auto; padding: 12px 8px; }
        .thumbnail-item { background: white; border-radius: 14px; margin-bottom: 12px; padding: 8px; cursor: pointer; border: 2px solid transparent; transition: 0.1s; box-shadow: 0 1px 3px rgba(0,0,0,0.05); position: relative; }
        .thumbnail-item.selected { border-color: #ff9900; background: #fffdf8; box-shadow: 0 2px 8px rgba(255,153,0,0.15); }
        .thumbnail-img { width: 100%; height: 90px; background: #f1f5f9; border-radius: 10px; display: flex; align-items: center; justify-content: center; margin-bottom: 6px; overflow: hidden; pointer-events: none; }
        .thumbnail-info { display: flex; justify-content: space-between; align-items: center; font-size: 10px; }
        .thumbnail-del { color: #aaa; font-size: 14px; cursor: pointer; padding: 0 4px; }
        .drag-hint { height: 3px; background: #ff9900; margin: 2px 0; opacity: 0; transition: 0.1s; }
        .drag-hint.active { opacity: 1; }
        
        .preview-area { flex: 1; display: flex; flex-direction: column; background: #eef2f8; position: relative; overflow: hidden; }
        .preview-header { padding: 10px 16px; background: white; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; }
        .header-tips { font-size: 12px; color: #64748b; font-weight: 500; display: flex; gap: 8px; }
        .header-tips span { background: #f1f5f9; padding: 4px 10px; border-radius: 20px; border: 1px solid #e2e8f0; }
        .preview-content { flex: 1; position: relative; background: #dadfe8; overflow: hidden; }
        .canvas-wrapper { position: absolute; width: 100%; height: 100%; touch-action: none; cursor: grab; }
        canvas { position: absolute; transform-origin: 0 0; image-rendering: crisp-edges; }
        .empty-upload-overlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; background: #f8fafc; cursor: pointer; z-index: 20; }
        .big-plus { background: rgba(75, 108, 183, 0.08); width: 180px; height: 180px; border-radius: 48px; display: flex; flex-direction: column; align-items: center; justify-content: center; border: 2px dashed #9bb4da; transition: 0.2s; }
        .big-plus:hover { transform: scale(1.05); }
        .big-plus span:first-child { font-size: 70px; font-weight: 300; color: #4b6cb7; }
        .zoom-controls { display: flex; gap: 8px; align-items: center; }
        .zoom-btn { width: 28px; height: 28px; background: #f0f2f5; border: 1px solid #d0dae8; border-radius: 8px; cursor: pointer; font-weight: bold; color:#4a627a; }
        #cutLineGuide { position: absolute; left: 0; width: 100%; height: 2px; border-top: 2px dashed #ff3b30; pointer-events: none; display: none; z-index: 100; box-shadow: 0 2px 4px rgba(255,59,48,0.3); }
        #cutLineGuide::after { content: '✂️ 单击切割'; position: absolute; right: 20px; top: -24px; background: rgba(255,59,48,0.9); color: white; padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: bold; }
        #brushCursor { position: absolute; border: 1.5px solid rgba(0, 0, 0, 0.8); border-radius: 50%; pointer-events: none; display: none; z-index: 999; transform: translate(-50%, -50%); box-shadow: 0 0 0 1.5px rgba(255, 255, 255, 0.8); }
    </style>
</head>
<body>
<div id="toastContainer" class="toast-container"></div>

<div class="control-sidebar">
    <div class="sidebar-inner">
        
        <div class="path-row">
            <div class="square-btn" style="background:#f1f5f9; border-color:#cbd5e1;" onclick="saveLongImage(1, false)">
                <div class="setting-gear" onclick="changeDir(1); event.stopPropagation();" title="更改主路径">⚙️</div>
                <span style="font-size: 3vh; margin-bottom:0.5vh;">📂 1</span>
                <span style="font-size: 1.2vh; font-weight:bold;">存至主路径</span>
            </div>
            <div class="square-btn" style="background:#f1f5f9; border-color:#cbd5e1;" onclick="saveLongImage(2, false)">
                <div class="setting-gear" onclick="changeDir(2); event.stopPropagation();" title="更改备用路径">⚙️</div>
                <span style="font-size: 3vh; margin-bottom:0.5vh;">📂 2</span>
                <span style="font-size: 1.2vh; font-weight:bold;">存至备用路径</span>
            </div>
        </div>

        <div class="filename-row">
            <textarea id="filenameInput" placeholder="命名 (自动读取剪贴板)&#10;非法字符和空格将被自动抹除"></textarea>
        </div>

        <div class="tools-row-1">
            <div class="square-btn" id="compactUploadBtn">
                <span style="font-size: 2vh; margin-bottom:0.5vh;">➕</span><span style="font-size:1.1vh; font-weight:bold;">添加图片</span>
            </div>
            <div class="square-btn" id="saveSingleBtn">
                <span style="font-size: 2vh; margin-bottom:0.5vh;">📸</span><span style="font-size:1.1vh; font-weight:bold;">存单张</span>
            </div>
            <div class="square-btn" id="clearAllBtn" style="color:#e11d48;" onmouseover="this.style.background='#ffe4e6'; this.style.borderColor='#fda4af';" onmouseout="this.style.background='#f8fafd'; this.style.borderColor='#dce5ef';">
                <span style="font-size: 2vh; margin-bottom:0.5vh;">🗑️</span><span style="font-size:1.1vh; font-weight:bold;">清空所有</span>
            </div>
            <input type="file" id="fileInput" multiple accept="image/*" style="display:none">
        </div>

        <div class="spacing-row">
            <span style="font-weight:bold; color:#4a627a; font-size:1.3vh; white-space:nowrap; margin-right:1vh;">↕ 间距</span>
            <input type="range" min="0" max="1000" value="0" id="spacingSlider" style="margin-right:1vh;">
            <input type="color" value="#ffffff" id="spacingColor" style="width:3.5vh; height:3.5vh; border:none; padding:0; background:none; cursor:pointer;" title="背景及画笔颜色">
        </div>

        <div class="tools-row-2">
            <div class="square-btn" id="colorBtn" title="跟随间距色板颜色，画覆盖涂鸦">
                <span style="font-size: 2.2vh; margin-bottom:0.5vh;">🖌️</span><span style="font-size:1.1vh; font-weight:bold;">画笔</span>
            </div>
            <div class="square-btn" id="invertBtn" title="画笔经过的地方，底层图片颜色反相">
                <span style="font-size: 2.2vh; margin-bottom:0.5vh;">🌗</span><span style="font-size:1.1vh; font-weight:bold;">反向</span>
            </div>
            <div class="square-btn" id="mosaicBtn" title="像素马赛克效果">
                <span style="font-size: 2.2vh; margin-bottom:0.5vh;">🔲</span><span style="font-size:1.1vh; font-weight:bold;">马赛克</span>
            </div>
        </div>

        <div id="brushSizeContainer" class="brush-size-row" style="opacity: 0.5; pointer-events: none;">
            <span style="font-weight:bold; color:#4a627a; font-size:1.3vh; white-space:nowrap; margin-right:1vh;">⚪ 粗细</span>
            <input type="range" min="10" max="150" value="40" id="brushSizeSlider">
        </div>

        <div class="save-row">
            <button class="action-btn-primary" onclick="saveLongImage(1, true)">⬇️ 存长图到[路径1]并清空</button>
        </div>

    </div>
</div>

<div class="thumbnail-sidebar">
    <div class="thumbnail-header">
        <h4>图库 (<span id="imgCount">0</span>)</h4>
        <button class="select-all-btn" id="multiSelectToggleBtn" title="点击开启多选(全选) / 关闭多选(全取消)">多选模式</button>
    </div>
    <div class="thumbnail-list" id="thumbnailList"><div class="empty-thumbnails" style="text-align:center; padding-top:20px; color:#aaa; font-size:12px;">空空如也</div></div>
</div>

<div class="preview-area">
    <div class="preview-header">
        <div class="header-tips">
            <span>🖱️ 直接抓取图片边缘/四角进行裁剪</span>
        </div>
        
        <div class="quick-nav-controls" style="display: flex; gap: 8px;">
            <button class="zoom-btn" style="width: auto; padding: 0 12px; font-size: 12px;" onclick="fitAllView()">显示全部</button>
        </div>

        <div class="zoom-controls">
            <button class="zoom-btn" onclick="changeZoom(-0.1)">−</button>
            <span class="zoom-level" id="zoomLevel" style="font-size: 12px; width: 44px; text-align: center; font-weight:600;">100%</span>
            <button class="zoom-btn" onclick="changeZoom(0.1)">+</button>
            <button class="zoom-btn" onclick="resetView(false)">⟳</button>
        </div>
    </div>
    <div class="preview-content">
        <div class="preview-container" id="previewContainer" style="width:100%; height:100%; position:relative; overflow:hidden;">
            <div class="canvas-wrapper" id="canvasWrapper">
                <canvas id="previewCanvas"></canvas>
                <div id="cutLineGuide"></div>
                <div id="brushCursor"></div>
            </div>
            <div id="emptyUploadOverlay" class="empty-upload-overlay" style="display: none;">
                <div class="big-plus"><span>+</span><div style="margin-top:10px; font-size:14px; font-weight:500; color:#4b6cb7;">点击或拖拽上传</div></div>
            </div>
        </div>
    </div>
</div>

<script>
    const CURSOR_UP = `url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24"><path d="M12 2l-7 8h4.5v12h5V10H19z" fill="%23ff9900" stroke="white" stroke-width="1.5"/></svg>') 14 2, pointer`;
    const CURSOR_DOWN = `url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24"><path d="M12 22l7-8h-4.5V2h-5v12H5z" fill="%23ff9900" stroke="white" stroke-width="1.5"/></svg>') 14 22, pointer`;
    
    let images = []; 
    let historyStack = [];
    let historyIndex = -1;
    let activeTool = null; // 'mosaic', 'color', 'invert'
    let toolState = 0; // 0:关闭, 1:单次, 2:锁定
    let isCutMode = false;
    let isMultiSelectMode = false;
    let transformMatrix = { x: 0, y: 0, scale: 1 };
    let canvasSize = { width: 800, height: 400 };
    let imageHitBoxes = []; 
    let isPanning = false; 
    let isDrawing = false;
    let lastMousePos = { x: 0, y: 0 };
    let lastMouseX = 0, lastMouseY = 0;
    let activeDrag = null;
    let hoverTarget = null;
    
    const previewCanvas = document.getElementById('previewCanvas');
    const canvasWrapper = document.getElementById('canvasWrapper');
    const cutLineGuide = document.getElementById('cutLineGuide');
    const emptyOverlay = document.getElementById('emptyUploadOverlay');

    let pyApiReady = false;
    let lastClipboardText = "";

    window.addEventListener('pywebviewready', function() {
        pyApiReady = true;
        pywebview.api.get_save_paths().then(paths => {}); // Backend handles UI update implicitly now via directory choose
        setInterval(() => {
            pywebview.api.get_clipboard().then(text => {
                if(text !== lastClipboardText) {
                    lastClipboardText = text;
                    if (text && text.trim().length > 0) {
                        document.getElementById('filenameInput').value = text;
                    }
                }
            });
        }, 500);
    });

    function changeDir(index) {
        if(!pyApiReady) return;
        pywebview.api.choose_directory(index).then(path => {
            if(path) showToast(`已更改并记住 路径${index}`);
        });
    }

    function buildBlueprint() {
        return {
            bgColor: document.getElementById('spacingColor').value,
            images: images.map(img => {
                return {
                    path: img.localPath, 
                    crop: img.crop,
                    spacingBottom: img.spacingBottom || 0,
                    masks: img.masks,
                    originalWidth: img.originalWidth,
                    originalHeight: img.originalHeight
                };
            })
        };
    }

    function saveLongImage(pathIndex, autoClear) {
        if(images.length === 0) { showToast("无图片可保存"); return; }
        if(!pyApiReady) return;
        showToast("长图极速处理中...");
        let blueprint = buildBlueprint();
        let customName = document.getElementById('filenameInput').value;
        pywebview.api.save_blueprint(JSON.stringify(blueprint), false, pathIndex, customName).then(res => {
            showToast(res.msg);
            if (res.success && autoClear) {
                images = []; saveHistory(); renderThumbnails(); queueRenderPreview(true);
                showToast("✅ 已自动清空图片 (按 Ctrl+Z 可撤销恢复)");
            }
        });
    }

    document.getElementById('saveSingleBtn').addEventListener('click', () => {
        if (images.length === 0) { showToast("没有图片可供保存"); return; }
        if (!pyApiReady) return;
        showToast("批量保存中...");
        let blueprint = buildBlueprint();
        let customName = document.getElementById('filenameInput').value;
        pywebview.api.save_blueprint(JSON.stringify(blueprint), true, 2, customName).then(res => showToast(res.msg));
    });

    function showToast(msg) {
        const container = document.getElementById('toastContainer');
        const t = document.createElement('div');
        t.className = 'toast'; t.innerText = msg;
        container.appendChild(t); void t.offsetWidth;
        t.classList.add('show');
        setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 300); }, 2500);
    }

    function saveHistory() {
        const state = images.map(img => ({
            id: img.id, name: img.name, imgObj: img.imgObj, pixelCanvas: img.pixelCanvas,
            localPath: img.localPath, originalWidth: img.originalWidth, originalHeight: img.originalHeight,
            crop: { ...img.crop }, spacingBottom: img.spacingBottom, selected: img.selected,
            masks: JSON.parse(JSON.stringify(img.masks)) 
        }));
        if (historyIndex < historyStack.length - 1) historyStack = historyStack.slice(0, historyIndex + 1);
        historyStack.push(state); historyIndex++; updateUI();
    }

    function restoreHistory(index) {
        if (index < 0 || index >= historyStack.length) return;
        historyIndex = index;
        images = historyStack[index].map(img => ({ ...img, crop: { ...img.crop }, masks: JSON.parse(JSON.stringify(img.masks)) }));
        updateUI(); renderThumbnails(); queueRenderPreview(true); showToast("已撤销/重做");
    }

    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); e.shiftKey ? restoreHistory(historyIndex + 1) : restoreHistory(historyIndex - 1); }
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') { e.preventDefault(); restoreHistory(historyIndex + 1); }
        if (e.key === 'Enter' && !e.ctrlKey && !e.shiftKey && !e.altKey) {
            e.preventDefault();
            if (images.length > 0) saveLongImage(1, true); else showToast("没有图片可保存");
        }
    });

    function generatePixelCanvas(imgObj) {
        const c = document.createElement('canvas'); c.width = imgObj.width; c.height = imgObj.height;
        const ctx = c.getContext('2d'); const scale = 0.04;
        const sw = Math.max(1, Math.floor(imgObj.width * scale)); const sh = Math.max(1, Math.floor(imgObj.height * scale));
        ctx.imageSmoothingEnabled = false; ctx.drawImage(imgObj, 0, 0, sw, sh);
        ctx.drawImage(c, 0, 0, sw, sh, 0, 0, imgObj.width, imgObj.height);
        return c;
    }

    function updateUI() {
        emptyOverlay.style.display = images.length === 0 ? 'flex' : 'none';
        document.getElementById('imgCount').innerText = images.length;
        let selectedImgs = images.filter(i => i.selected);
        let spacing = selectedImgs.length > 0 ? (selectedImgs[0].spacingBottom || 0) : 0;
        document.getElementById('spacingSlider').value = spacing;
    }

    document.getElementById('multiSelectToggleBtn').addEventListener('click', (e) => {
        isMultiSelectMode = !isMultiSelectMode; e.target.classList.toggle('active', isMultiSelectMode);
        if (isMultiSelectMode) { images.forEach(img => img.selected = true); showToast("多选模式：已全选"); } 
        else { images.forEach(img => img.selected = false); showToast("单选模式：已取消选中"); }
        updateUI(); renderThumbnails(); queueRenderPreview();
    });

    function renderThumbnails() {
        const container = document.getElementById('thumbnailList');
        if (images.length === 0) { container.innerHTML = '<div class="empty-thumbnails">从左侧添加</div>'; return; }
        container.innerHTML = '';
        images.forEach((item, idx) => {
            if (idx > 0) { const hint = document.createElement('div'); hint.className = 'drag-hint'; container.appendChild(hint); }
            const div = document.createElement('div');
            div.className = `thumbnail-item ${item.selected ? 'selected' : ''}`;
            div.draggable = true; div.dataset.index = idx;
            
            div.addEventListener('dragstart', (e) => { e.dataTransfer.setData('text/plain', idx); div.classList.add('dragging'); document.querySelectorAll('.drag-hint').forEach(h => h.classList.add('active')); });
            div.addEventListener('dragend', () => { div.classList.remove('dragging'); document.querySelectorAll('.drag-hint').forEach(h => h.classList.remove('active')); });
            div.addEventListener('dragover', e => e.preventDefault());
            div.addEventListener('drop', (e) => { e.preventDefault(); const from = parseInt(e.dataTransfer.getData('text/plain')); if (from !== idx) { let moved = images.splice(from, 1)[0]; images.splice(idx, 0, moved); saveHistory(); renderThumbnails(); queueRenderPreview(); } });
            
            div.addEventListener('click', (e) => { 
                if (!e.target.classList.contains('thumbnail-del')) {
                    if (isMultiSelectMode) item.selected = !item.selected; 
                    else { images.forEach(i => i.selected = false); item.selected = true; }
                    updateUI(); renderThumbnails(); queueRenderPreview();
                }
            });
            div.innerHTML = `<div class="thumbnail-img"><canvas class="thumb-canvas" width="130" height="80"></canvas></div><div class="thumbnail-info"><span>${idx+1}. ${item.name.slice(0,10)}</span><span class="thumbnail-del">✕</span></div>`;
            div.querySelector('.thumbnail-del').addEventListener('click', (e) => { e.stopPropagation(); images.splice(idx, 1); saveHistory(); renderThumbnails(); queueRenderPreview(images.length===0); });
            container.appendChild(div);
            
            const tCtx = div.querySelector('.thumb-canvas').getContext('2d');
            const c = item.crop; const sw = Math.max(1, item.originalWidth - c.left - c.right); const sh = Math.max(1, item.originalHeight - c.top - c.bottom);
            const scale = Math.min(130/sw, 80/sh) * 0.9;
            tCtx.fillStyle = '#f1f5f9'; tCtx.fillRect(0,0,130,80);
            tCtx.drawImage(item.imgObj, c.left, c.top, sw, sh, (130-sw*scale)/2, (80-sh*scale)/2, sw*scale, sh*scale);
        });
    }

    function syncSpacing() {
        let val = parseInt(document.getElementById('spacingSlider').value) || 0;
        images.filter(img => img.selected).forEach(img => img.spacingBottom = val);
        queueRenderPreview();
    }
    document.getElementById('spacingSlider').addEventListener('input', syncSpacing);
    document.getElementById('spacingSlider').addEventListener('change', saveHistory);
    document.getElementById('spacingColor').addEventListener('input', queueRenderPreview);

    let toolClickTimer = null;
    function handleToolClick(type) {
        if (activeTool === type && toolClickTimer) {
            clearTimeout(toolClickTimer); toolClickTimer = null;
            toolState = 2; updateToolUI(); showToast("工具已锁定"); return;
        }
        toolClickTimer = setTimeout(() => {
            toolClickTimer = null;
            if (activeTool === type) { if (toolState === 0) toolState = 1; else toolState = 0; }
            else { activeTool = type; toolState = 1; }
            updateToolUI();
        }, 250);
    }
    document.getElementById('colorBtn').addEventListener('click', () => handleToolClick('color'));
    document.getElementById('invertBtn').addEventListener('click', () => handleToolClick('invert'));
    document.getElementById('mosaicBtn').addEventListener('click', () => handleToolClick('mosaic'));
    
    function updateToolUI() {
        ['color', 'invert', 'mosaic'].forEach(t => {
            let btn = document.getElementById(t + 'Btn');
            btn.className = 'square-btn';
            if (activeTool === t) {
                if (toolState === 1) btn.classList.add('active-single');
                if (toolState === 2) btn.classList.add('active-locked');
            }
        });
        const sizeContainer = document.getElementById('brushSizeContainer');
        if (toolState > 0) {
            sizeContainer.style.opacity = '1'; sizeContainer.style.pointerEvents = 'auto';
        } else {
            sizeContainer.style.opacity = '0.5'; sizeContainer.style.pointerEvents = 'none';
        }
        isCutMode = false; cutLineGuide.style.display = 'none';
        updateBrushCursor(); queueRenderPreview();
    }
    
    document.getElementById('brushSizeSlider').addEventListener('input', function() { updateBrushCursor(); });

    let renderFrame = null;
    function queueRenderPreview(viewMode = false) { 
        if (renderFrame) cancelAnimationFrame(renderFrame); 
        renderFrame = requestAnimationFrame(() => renderPreview(viewMode)); 
    }

    function fitAllView() {
        let rect = canvasWrapper.getBoundingClientRect();
        if (canvasSize.width === 0 || canvasSize.height === 0) return;
        let scaleW = (rect.width - 40) / canvasSize.width;
        let scaleH = (rect.height - 40) / canvasSize.height;
        let targetScale = Math.min(scaleW, scaleH);
        transformMatrix.scale = Math.max(0.01, Math.min(20, targetScale));
        transformMatrix.x = (rect.width - canvasSize.width * transformMatrix.scale) / 2;
        transformMatrix.y = (rect.height - canvasSize.height * transformMatrix.scale) / 2;
        updateCanvasDisplay(); updateBrushCursor();
    }

    function fitThirdView() {
        let rect = canvasWrapper.getBoundingClientRect();
        if (canvasSize.width === 0) return;
        let targetScale = (rect.width / 3) / canvasSize.width;
        transformMatrix.scale = Math.max(0.01, Math.min(20, targetScale));
        transformMatrix.x = (rect.width - canvasSize.width * transformMatrix.scale) / 2;
        transformMatrix.y = 20; 
        updateCanvasDisplay(); updateBrushCursor();
    }

    function renderPreview(viewMode = false) {
        imageHitBoxes = [];
        if (images.length === 0) {
            previewCanvas.width = 800; previewCanvas.height = 400; canvasSize = { width: 800, height: 400 };
            const ctx = previewCanvas.getContext('2d'); ctx.fillStyle = '#f5f7fc'; ctx.fillRect(0, 0, 800, 400);
            updateCanvasDisplay(); resetView(); return;
        }
        
        let maxWidth = 0;
        let itemsData = images.map(img => {
            let c = img.crop; let sw = Math.max(1, img.originalWidth - c.left - c.right); let sh = Math.max(1, img.originalHeight - c.top - c.bottom);
            if(sw > maxWidth) maxWidth = sw; return { imgObj: img.imgObj, pixelCanvas: img.pixelCanvas, sw, sh, sx: c.left, sy: c.top, masks: img.masks, selected: img.selected };
        });
        
        let totalH = 0; itemsData.forEach((d, i) => { totalH += d.sh * (maxWidth / d.sw) + (i < itemsData.length - 1 ? (images[i].spacingBottom || 0) : 0); });
        
        canvasSize.width = maxWidth; canvasSize.height = totalH; previewCanvas.width = canvasSize.width; previewCanvas.height = canvasSize.height;
        let ctx = previewCanvas.getContext('2d'); ctx.fillStyle = document.getElementById('spacingColor').value; ctx.fillRect(0, 0, maxWidth, totalH); 
        
        let curY = 0;
        itemsData.forEach((d, i) => {
            let scaleRender = maxWidth / d.sw; let rh = d.sh * scaleRender; let rw = d.sw * scaleRender;
            let handles = { tl: { x: 0, y: curY }, tr: { x: rw, y: curY }, bl: { x: 0, y: curY + rh }, br: { x: rw, y: curY + rh } };
            imageHitBoxes.push({ index: i, x0: 0, x1: rw, y0: curY, y1: curY + rh, scaleRender: scaleRender, handles: handles });
            
            const chunkCanv = document.createElement('canvas'); chunkCanv.width = rw; chunkCanv.height = rh; const chunkCtx = chunkCanv.getContext('2d');
            chunkCtx.drawImage(d.imgObj, d.sx, d.sy, d.sw, d.sh, 0, 0, rw, rh);

            if (d.masks && d.masks.length > 0) {
                d.masks.forEach(stroke => {
                    if (stroke.points.length === 0) return;
                    const strokeCanv = document.createElement('canvas'); strokeCanv.width = rw; strokeCanv.height = rh;
                    const strokeCtx = strokeCanv.getContext('2d');
                    strokeCtx.lineCap = 'round'; strokeCtx.lineJoin = 'round'; strokeCtx.lineWidth = stroke.size * scaleRender;
                    strokeCtx.strokeStyle = 'black'; 
                    strokeCtx.beginPath(); strokeCtx.moveTo((stroke.points[0].x - d.sx) * scaleRender, (stroke.points[0].y - d.sy) * scaleRender);
                    for (let j = 1; j < stroke.points.length; j++) strokeCtx.lineTo((stroke.points[j].x - d.sx) * scaleRender, (stroke.points[j].y - d.sy) * scaleRender);
                    strokeCtx.stroke();

                    if (stroke.type === 'color') {
                        strokeCtx.globalCompositeOperation = 'source-in'; strokeCtx.fillStyle = stroke.color; strokeCtx.fillRect(0,0,rw,rh);
                        chunkCtx.drawImage(strokeCanv, 0, 0);
                    } else if (stroke.type === 'invert') {
                        strokeCtx.globalCompositeOperation = 'source-in'; strokeCtx.fillStyle = 'white'; strokeCtx.fillRect(0,0,rw,rh);
                        chunkCtx.globalCompositeOperation = 'difference'; chunkCtx.drawImage(strokeCanv, 0, 0); chunkCtx.globalCompositeOperation = 'source-over';
                    } else { // mosaic
                        strokeCtx.globalCompositeOperation = 'source-in'; strokeCtx.drawImage(d.pixelCanvas, d.sx, d.sy, d.sw, d.sh, 0, 0, rw, rh);
                        chunkCtx.drawImage(strokeCanv, 0, 0);
                    }
                });
            }
            ctx.drawImage(chunkCanv, 0, curY);

            if (d.selected && !isCutMode) {
                ctx.save(); ctx.lineWidth = 2; ctx.setLineDash([6, 6]); ctx.strokeStyle = '#ff9900'; ctx.strokeRect(1, curY + 1, rw - 2, rh - 2);
                ctx.lineDashOffset = 6; ctx.strokeStyle = '#ffffff'; ctx.strokeRect(1, curY + 1, rw - 2, rh - 2);
                let visualRadius = 7 / transformMatrix.scale;
                ctx.setLineDash([]); ctx.fillStyle = '#ffffff'; ctx.strokeStyle = '#ff9900'; ctx.lineWidth = 2 / transformMatrix.scale;
                for (let corner in handles) { ctx.beginPath(); ctx.arc(handles[corner].x, handles[corner].y, visualRadius, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); }
                ctx.restore();
            }
            curY += rh + (i < itemsData.length - 1 ? (images[i].spacingBottom || 0) : 0);
        });

        if (hoverTarget && hoverTarget.type === 'edge' && !isCutMode && !activeDrag && toolState === 0) {
            let box = imageHitBoxes.find(b => b.index === hoverTarget.index);
            if (box) {
                ctx.save(); ctx.strokeStyle = '#ff9900'; ctx.lineWidth = 5 / transformMatrix.scale; ctx.setLineDash([]); ctx.beginPath();
                if (hoverTarget.edge === 'top') { ctx.moveTo(box.x0, box.y0); ctx.lineTo(box.x1, box.y0); }
                else if (hoverTarget.edge === 'bottom') { ctx.moveTo(box.x0, box.y1); ctx.lineTo(box.x1, box.y1); }
                else if (hoverTarget.edge === 'left') { ctx.moveTo(box.x0, box.y0); ctx.lineTo(box.x0, box.y1); }
                else if (hoverTarget.edge === 'right') { ctx.moveTo(box.x1, box.y0); ctx.lineTo(box.x1, box.y1); }
                ctx.stroke(); ctx.restore();
            }
        }
        
        updateCanvasDisplay();
        if (viewMode === 'all') fitAllView();
        else if (viewMode === 'third') fitThirdView();
        else if (viewMode === true) resetView(true);
    }

    function updateCanvasDisplay() { previewCanvas.style.transform = `translate(${transformMatrix.x}px, ${transformMatrix.y}px) scale(${transformMatrix.scale})`; document.getElementById('zoomLevel').innerText = Math.round(transformMatrix.scale * 100) + '%'; }
    
    function resetView(isInitial = false) { 
        const rect = canvasWrapper.getBoundingClientRect(); if (canvasSize.width === 0) return;
        let targetScale = 1;
        if (isInitial && images.length > 0) {
            let firstImg = images[0];
            let sw = Math.max(1, firstImg.originalWidth - firstImg.crop.left - firstImg.crop.right);
            let sh = Math.max(1, firstImg.originalHeight - firstImg.crop.top - firstImg.crop.bottom);
            let scaleToMaxW = canvasSize.width / sw;
            let firstImgRenderHeight = sh * scaleToMaxW;
            let targetH = firstImgRenderHeight * 1.5;
            if (targetH === 0) targetH = canvasSize.height;
            let scaleByHeight = (rect.height * 0.85) / targetH;
            let scaleByWidth = (rect.width * 0.8) / canvasSize.width;
            targetScale = Math.min(scaleByHeight, scaleByWidth);
        } else {
            targetScale = Math.min(rect.width / canvasSize.width, rect.height / canvasSize.height) * 0.9;
        }
        transformMatrix.scale = Math.max(0.01, Math.min(20, targetScale));
        transformMatrix.x = (rect.width - canvasSize.width * transformMatrix.scale) / 2;
        transformMatrix.y = isInitial ? 20 : (rect.height - canvasSize.height * transformMatrix.scale) / 2;
        updateCanvasDisplay();
    }

    function getMouseCanvasCoords(e) {
        let rect = canvasWrapper.getBoundingClientRect();
        let cx = (e.clientX - rect.left - transformMatrix.x) / transformMatrix.scale;
        let cy = (e.clientY - rect.top - transformMatrix.y) / transformMatrix.scale;
        return { cx, cy, rawX: e.clientX, rawY: e.clientY };
    }

    function getHitTarget(cx, cy) {
        if (isCutMode || toolState > 0) return null;
        let hitRadius = 14 / transformMatrix.scale; 
        for (let i = 0; i < imageHitBoxes.length; i++) {
            let box = imageHitBoxes[i]; if (!images[box.index].selected) continue;
            for (let corner in box.handles) { if (Math.hypot(cx - box.handles[corner].x, cy - box.handles[corner].y) <= hitRadius) return { type: 'corner', index: box.index, corner: corner }; }
        }
        let closestEdge = null; let minVal = hitRadius;
        for (let i = 0; i < imageHitBoxes.length; i++) {
            let box = imageHitBoxes[i]; if (!images[box.index].selected) continue;
            if (cx >= box.x0 && cx <= box.x1) {
                let dTop = Math.abs(cy - box.y0); if (cy > box.y0) dTop -= 0.1; if (dTop < minVal) { minVal = dTop; closestEdge = { type: 'edge', index: box.index, edge: 'top' }; }
                let dBottom = Math.abs(cy - box.y1); if (cy < box.y1) dBottom -= 0.1; if (dBottom < minVal) { minVal = dBottom; closestEdge = { type: 'edge', index: box.index, edge: 'bottom' }; }
            }
            if (cy >= box.y0 && cy <= box.y1) {
                let dLeft = Math.abs(cx - box.x0); if (cx > box.x0) dLeft -= 0.1; if (dLeft < minVal) { minVal = dLeft; closestEdge = { type: 'edge', index: box.index, edge: 'left' }; }
                let dRight = Math.abs(cx - box.x1); if (cx < box.x1) dRight -= 0.1; if (dRight < minVal) { minVal = dRight; closestEdge = { type: 'edge', index: box.index, edge: 'right' }; }
            }
        }
        return closestEdge;
    }

    function updateBrushCursor() {
        const brushCursor = document.getElementById('brushCursor');
        if (toolState === 0) { brushCursor.style.display = 'none'; return; }
        let rect = canvasWrapper.getBoundingClientRect();
        if (lastMouseX < rect.left || lastMouseX > rect.right || lastMouseY < rect.top || lastMouseY > rect.bottom) { brushCursor.style.display = 'none'; return; }
        
        let cx = (lastMouseX - rect.left - transformMatrix.x) / transformMatrix.scale; let cy = (lastMouseY - rect.top - transformMatrix.y) / transformMatrix.scale;
        let box = imageHitBoxes.find(b => cy >= b.y0 && cy <= b.y1 && cx >= b.x0 && cx <= b.x1);
        let brushSize = parseInt(document.getElementById('brushSizeSlider').value) || 40;
        let screenDiameter = brushSize * transformMatrix.scale; if (box) screenDiameter = brushSize * box.scaleRender * transformMatrix.scale;
        brushCursor.style.width = screenDiameter + 'px'; brushCursor.style.height = screenDiameter + 'px';
        brushCursor.style.left = (lastMouseX - rect.left) + 'px'; brushCursor.style.top = (lastMouseY - rect.top) + 'px'; brushCursor.style.display = 'block';
    }

    canvasWrapper.addEventListener('wheel', (e) => {
        e.preventDefault(); const { cx, cy, rawX, rawY } = getMouseCanvasCoords(e);
        let ns = transformMatrix.scale * (e.deltaY > 0 ? 0.95 : 1.05); if (ns < 0.01 || ns > 20) return;
        const rect = canvasWrapper.getBoundingClientRect(); transformMatrix.scale = ns; transformMatrix.x = rawX - rect.left - cx * ns; transformMatrix.y = rawY - rect.top - cy * ns;
        updateCanvasDisplay(); updateCursor(e); updateBrushCursor();
    }, { passive: false });

    function updateCursor(e) {
        if (isCutMode || toolState > 0) { canvasWrapper.style.cursor = 'crosshair'; return; }
        if (isPanning || isDrawing || activeDrag) return; 
        const { cx, cy } = getMouseCanvasCoords(e); hoverTarget = getHitTarget(cx, cy);
        if (hoverTarget) {
            if (hoverTarget.type === 'corner') { canvasWrapper.style.cursor = (hoverTarget.corner === 'tl' || hoverTarget.corner === 'br') ? 'nwse-resize' : 'nesw-resize'; } 
            else { if (hoverTarget.edge === 'bottom') canvasWrapper.style.cursor = CURSOR_UP; else if (hoverTarget.edge === 'top') canvasWrapper.style.cursor = CURSOR_DOWN; else canvasWrapper.style.cursor = 'ew-resize'; }
        } else { canvasWrapper.style.cursor = 'grab'; }
        queueRenderPreview();
    }

    canvasWrapper.addEventListener('contextmenu', (e) => {
        e.preventDefault(); if (toolState > 0) return;
        isCutMode = true; activeDrag = null; hoverTarget = null; cutLineGuide.style.display = 'block';
        const { rawY } = getMouseCanvasCoords(e); cutLineGuide.style.top = (rawY - canvasWrapper.getBoundingClientRect().top) + 'px';
        updateCursor(e); queueRenderPreview();
    });

    canvasWrapper.addEventListener('dblclick', (e) => {
        if (toolState > 0 || isCutMode) return;
        const { cx, cy } = getMouseCanvasCoords(e);
        let box = imageHitBoxes.find(b => cy >= b.y0 && cy <= b.y1 && cx >= b.x0 && cx <= b.x1);
        if (box) { images.forEach(img => img.selected = false); images[box.index].selected = true; updateUI(); renderThumbnails(); queueRenderPreview(); showToast("已选中该图"); }
    });

    canvasWrapper.addEventListener('mousedown', (e) => {
        if (e.button !== 0) return;
        const { cx, cy } = getMouseCanvasCoords(e);
        if (isCutMode) {
            let box = imageHitBoxes.find(b => cy >= b.y0 && cy <= b.y1 && cx >= b.x0 && cx <= b.x1);
            isCutMode = false; cutLineGuide.style.display = 'none'; updateCursor(e); queueRenderPreview();
            if (!box) return; 
            let img = images[box.index]; let cutYOrig = Math.round((cy - box.y0) / box.scaleRender + img.crop.top);
            if (cutYOrig <= img.crop.top + 10 || cutYOrig >= img.originalHeight - img.crop.bottom - 10) { showToast("切割位置太靠近边缘"); return; }
            let bottomImg = { id: Date.now() + Math.random(), imgObj: img.imgObj, pixelCanvas: img.pixelCanvas, name: img.name, localPath: img.localPath, originalWidth: img.originalWidth, originalHeight: img.originalHeight, crop: { ...img.crop, top: cutYOrig }, spacingBottom: img.spacingBottom, selected: img.selected, masks: JSON.parse(JSON.stringify(img.masks)) };
            img.crop.bottom = img.originalHeight - cutYOrig; img.spacingBottom = 0; 
            images.splice(box.index + 1, 0, bottomImg); saveHistory(); renderThumbnails(); queueRenderPreview(); showToast("✂️ 分割成功"); return;
        }

        if (toolState > 0) {
            let box = imageHitBoxes.find(b => cy >= b.y0 && cy <= b.y1 && cx >= b.x0 && cx <= b.x1); if (!box) return;
            isDrawing = true; let img = images[box.index]; let brushSize = parseInt(document.getElementById('brushSizeSlider').value) || 40;
            let origX = (cx - box.x0) / box.scaleRender + img.crop.left; let origY = (cy - box.y0) / box.scaleRender + img.crop.top;
            let stroke = { type: activeTool, size: brushSize, points: [{ x: origX, y: origY }] };
            if (activeTool === 'color') stroke.color = document.getElementById('spacingColor').value;
            img.masks.push(stroke); queueRenderPreview(); return;
        }

        if (hoverTarget) {
            activeDrag = { ...hoverTarget, startX: cx, startY: cy };
            let targets = images.map((_, i) => i).filter(i => images[i].selected);
            activeDrag.startCrops = targets.map(i => ({ index: i, crop: { ...images[i].crop } }));
            activeDrag.startBox = imageHitBoxes.find(b => b.index === hoverTarget.index); return;
        }
        isPanning = true; lastMousePos = { x: e.clientX, y: e.clientY }; canvasWrapper.style.cursor = 'grabbing';
    });

    window.addEventListener('mousemove', (e) => {
        lastMouseX = e.clientX; lastMouseY = e.clientY; updateBrushCursor();
        if (isCutMode) { let rectTop = canvasWrapper.getBoundingClientRect().top; cutLineGuide.style.top = Math.max(0, e.clientY - rectTop) + 'px'; return; }
        const { cx, cy } = getMouseCanvasCoords(e); updateCursor(e);

        if (isDrawing) {
            let box = imageHitBoxes.find(b => cy >= b.y0 && cy <= b.y1 && cx >= b.x0 && cx <= b.x1);
            if (box) {
                let img = images[box.index]; let origX = (cx - box.x0) / box.scaleRender + img.crop.left; let origY = (cy - box.y0) / box.scaleRender + img.crop.top;
                let currentStroke = img.masks[img.masks.length - 1]; if (currentStroke) { currentStroke.points.push({ x: origX, y: origY }); queueRenderPreview(); }
            } return;
        }

        if (activeDrag) {
            let dx = cx - activeDrag.startX; let dy = cy - activeDrag.startY;
            let scaleRender = activeDrag.startBox.scaleRender; let ndx = dx / scaleRender; let ndy = dy / scaleRender;
            activeDrag.startCrops.forEach(item => {
                let img = images[item.index]; let start = item.crop; let maxW = img.originalWidth; let maxH = img.originalHeight;
                let processEdge = (edge) => {
                    if (edge === 'top') { let val = Math.max(0, start.top + ndy); if(val + start.bottom < maxH) img.crop.top = val; }
                    if (edge === 'bottom') { let val = Math.max(0, start.bottom - ndy); if(start.top + val < maxH) img.crop.bottom = val; }
                    if (edge === 'left') { let val = Math.max(0, start.left + ndx); if(val + start.right < maxW) img.crop.left = val; }
                    if (edge === 'right') { let val = Math.max(0, start.right - ndx); if(start.left + val < maxW) img.crop.right = val; }
                };
                if (activeDrag.type === 'edge') processEdge(activeDrag.edge);
                if (activeDrag.type === 'corner') {
                    if(activeDrag.corner.includes('t')) processEdge('top'); if(activeDrag.corner.includes('b')) processEdge('bottom');
                    if(activeDrag.corner.includes('l')) processEdge('left'); if(activeDrag.corner.includes('r')) processEdge('right');
                }
            }); queueRenderPreview(); return;
        }
        if (isPanning) { transformMatrix.x += e.clientX - lastMousePos.x; transformMatrix.y += e.clientY - lastMousePos.y; lastMousePos = { x: e.clientX, y: e.clientY }; updateCanvasDisplay(); }
    });

    window.addEventListener('mouseup', () => {
        if (isDrawing) { isDrawing = false; saveHistory(); if (toolState === 1) { toolState = 0; updateToolUI(); } }
        if (activeDrag) { activeDrag = null; saveHistory(); }
        if (isPanning) { isPanning = false; canvasWrapper.style.cursor = 'grab'; }
    });

    canvasWrapper.addEventListener('mouseleave', () => { document.getElementById('brushCursor').style.display = 'none'; });

    function uploadFiles(files, source = 'drag') {
        if (!files.length) return;
        showToast(`正在导入 ${files.length} 张图片...`);

        const promises = Array.from(files).map(async file => {
            let localPath = file.path; 
            if (!localPath) {
                let b64 = await new Promise(res => { let reader = new FileReader(); reader.onload = e => res(e.target.result); reader.readAsDataURL(file); });
                localPath = await pywebview.api.stash_temp_file(file.name, b64);
            }
            let img = new Image(); img.src = URL.createObjectURL(file);
            await new Promise(res => { img.onload = res; });
            URL.revokeObjectURL(img.src); 
            return { id: Date.now() + Math.random(), localPath: localPath, imgObj: img, originalWidth: img.width, originalHeight: img.height, pixelCanvas: generatePixelCanvas(img), name: file.name, crop: { top: 0, bottom: 0, left: 0, right: 0 }, spacingBottom: 0, masks: [], selected: false };
        });

        Promise.all(promises).then(newImgs => {
            if (isMultiSelectMode) { newImgs.forEach(i => i.selected = true); } 
            else { images.forEach(i => i.selected = false); if (newImgs.length > 0) newImgs[0].selected = true; }
            images.push(...newImgs); saveHistory(); renderThumbnails(); 
            if (source === 'drag') { queueRenderPreview('all'); } 
            else { if (files.length > 1) { queueRenderPreview('third'); } else { queueRenderPreview('all'); } }
            showToast(`导入成功`);
        });
    }
    
    document.getElementById('fileInput').addEventListener('change', e => { uploadFiles(e.target.files, 'click'); e.target.value=''; });
    document.getElementById('compactUploadBtn').addEventListener('click', () => document.getElementById('fileInput').click());
    emptyOverlay.addEventListener('click', () => document.getElementById('fileInput').click());
    window.addEventListener('dragover', e => e.preventDefault()); 
    window.addEventListener('drop', e => { e.preventDefault(); if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files, 'drag'); });
    document.getElementById('clearAllBtn').addEventListener('click', () => { images = []; saveHistory(); renderThumbnails(); queueRenderPreview(true); showToast("已清空"); });

    function changeZoom(delta){ 
        const rect = canvasWrapper.getBoundingClientRect(); let centerX = rect.width/2, centerY = rect.height/2; 
        let cx = (centerX - transformMatrix.x) / transformMatrix.scale, cy = (centerY - transformMatrix.y) / transformMatrix.scale; 
        let ns = transformMatrix.scale + delta; if (ns < 0.01 || ns > 20) return; 
        transformMatrix.scale = ns; transformMatrix.x = centerX - cx * ns; transformMatrix.y = centerY - cy * ns; 
        updateCanvasDisplay(); updateBrushCursor();
    }

    function init() { saveHistory(); updateUI(); renderThumbnails(); queueRenderPreview(true); }
    init();
</script>
</body>
</html>
"""

if __name__ == '__main__':
    api = Api()
    window = webview.create_window(
        '图片合成编辑器 - 混合架构极速版', 
        html=HTML_CONTENT, 
        js_api=api, 
        width=1280, 
        height=800,
        text_select=True 
    )
    webview.start()