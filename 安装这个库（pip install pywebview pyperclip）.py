import os
import json
import base64
import re
import time
import pyperclip
import webview

# ========== 核心设置配置文件名 ==========
CONFIG_FILE = 'config.json'

class Api:
    def __init__(self):
        self.save_dir = self.load_config()

    def load_config(self):
        # 启动时读取上一次保存的路径
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f).get('save_dir', '')
            except:
                pass
        return os.path.expanduser("~/Desktop") # 默认输出到桌面

    def save_config(self, path):
        # 记录选中的新路径
        self.save_dir = path
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({'save_dir': path}, f)

    def get_save_path(self):
        return self.save_dir

    def choose_directory(self):
        # 呼出系统的文件夹选择框
        result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
        if result and len(result) > 0:
            self.save_config(result[0])
            return result[0]
        return None

    def get_clipboard(self):
        # 实时读取剪贴板文字（忽略非文字内容）
        try:
            return pyperclip.paste()
        except:
            return ""

    def save_image(self, b64_data, suffix, ext):
        clip_text = self.get_clipboard().strip()
        
        if clip_text:
            # 核心需求：彻底移除所有空格、换行、制表符
            clip_text = re.sub(r'\s+', '', clip_text)
            # 防止剪贴板里的文字带有系统不允许的文件名特殊符号
            clip_text = re.sub(r'[\\/*?:"<>|]', '', clip_text)
            # 防止文字太长导致系统报错，限制最长 100 个字
            clip_text = clip_text[:100]
            
        # 如果剪贴板空了，或者全是特殊字符被删光了，启用备用时间戳命名
        if not clip_text:
            clip_text = "合成图片_" + time.strftime("%H%M%S")

        filename = f"{clip_text}{suffix}{ext}"
        
        # 确保目录存在，否则降级回桌面
        if not self.save_dir or not os.path.exists(self.save_dir):
            self.save_dir = os.path.expanduser("~/Desktop")

        filepath = os.path.join(self.save_dir, filename)

        try:
            # 解码前端传来的 Base64 图片数据并写入硬盘
            header, encoded = b64_data.split(",", 1)
            data = base64.b64decode(encoded)
            with open(filepath, "wb") as f:
                f.write(data)
            return f"成功保存: {filename}"
        except Exception as e:
            return f"保存失败: {str(e)}"

# ========== 嵌套的 HTML/CSS/JS 前端代码 ==========
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>图片合成编辑器 - 终极至尊版</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Roboto, system-ui, sans-serif; }
        body { background: #eef2f7; display: flex; height: 100vh; overflow: hidden; user-select: none; }
        .toast-container { position: fixed; top: 24px; left: 50%; transform: translateX(-50%); z-index: 9999; display: flex; flex-direction: column; gap: 12px; pointer-events: none; }
        .toast { background: rgba(31, 42, 68, 0.9); color: white; padding: 12px 24px; border-radius: 8px; font-size: 14px; font-weight: 500; box-shadow: 0 4px 12px rgba(0,0,0,0.15); opacity: 0; transform: translateY(-20px); transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1); }
        .toast.show { opacity: 1; transform: translateY(0); }
        .control-sidebar { width: 280px; background: white; border-right: 1px solid #ddd; display: flex; flex-direction: column; flex-shrink: 0; height: 100vh; overflow-y: auto; }
        .sidebar-inner { display: flex; flex-direction: column; padding: 20px 16px; gap: 18px; flex: 1; }
        .title-section h2 { font-size: 18px; color: #1f2a44; font-weight: 800; margin-bottom: 4px; }
        .hint-text { font-size: 11px; color: #7b8c9e; margin-bottom: 8px; line-height: 1.5; }
        .upload-square { background: #f0f4fe; border: 1.5px dashed #4b6cb7; border-radius: 16px; padding: 12px 0; display: flex; flex-direction: column; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s ease; }
        .upload-square:hover { background: #e6edfc; transform: scale(0.98); }
        .upload-square .plus-icon { font-size: 38px; font-weight: 300; color: #4b6cb7; }
        .upload-square .upload-text-small { font-size: 12px; color: #5a6e9e; margin-top: 6px; font-weight: 500; }
        .control-group { border-bottom: 1px solid #ecf0f3; padding-bottom: 14px; }
        .label { font-size: 13px; font-weight: bold; color: #2c3e58; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: flex-end; }
        .slider-row { display: flex; align-items: center; gap: 6px; font-size: 12px; margin-top: 6px; }
        input[type="range"] { flex: 1; height: 4px; border-radius: 10px; accent-color: #4b6cb7; }
        .slider-num-input { width: 52px; text-align: right; border: 1px solid #cfdfed; border-radius: 8px; padding: 4px 6px; font-size: 12px; font-weight: 500; color: #1e2f45; }
        .square-buttons { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 8px; }
        .square-btn { background: #f8fafd; border: 1px solid #dce5ef; border-radius: 12px; padding: 10px 0; display: flex; flex-direction: column; align-items: center; gap: 6px; cursor: pointer; transition: all 0.2s; font-weight: 600; font-size: 12px; color: #2c3e58; }
        .square-btn span:first-child { font-size: 20px; }
        .square-btn:hover { background: #eef3fc; border-color: #a0bbdf; }
        .square-btn.mosaic-single { background: #e8f0fe; border-color: #4b6cb7; color: #4b6cb7; }
        .square-btn.mosaic-locked { background: #4b6cb7; border-color: #4b6cb7; color: white; box-shadow: 0 4px 12px rgba(75,108,183,0.3); }
        #mosaicControls { background: #f4f7fa; padding: 10px; border-radius: 10px; margin-top: 8px; border: 1px solid #e0e6ed; }
        .action-btn-primary { width: 100%; background: #4b6cb7; color: white; border: none; border-radius: 24px; padding: 12px; font-size: 13px; font-weight: bold; cursor: pointer; display: flex; justify-content: center; align-items: center; gap: 8px; transition: 0.2s; box-shadow: 0 4px 12px rgba(75,108,183,0.2); }
        .action-btn-primary:hover { background: #3a579a; transform: translateY(-1px); }
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
        #cutLineGuide::after { content: '✂️ 单击左键切割'; position: absolute; right: 20px; top: -24px; background: rgba(255,59,48,0.9); color: white; padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: bold; }
        #brushCursor { position: absolute; border: 1.5px solid rgba(0, 0, 0, 0.8); border-radius: 50%; pointer-events: none; display: none; z-index: 999; transform: translate(-50%, -50%); box-shadow: 0 0 0 1.5px rgba(255, 255, 255, 0.8); }
    </style>
</head>
<body>
<div id="toastContainer" class="toast-container"></div>
<div class="control-sidebar">
    <div class="sidebar-inner">
        <div class="title-section">
            <h2>长图排版专家</h2>
            <div class="hint-text"><b>Ctrl+Z 撤销</b> | <b>双击选图</b> | 右键切图</div>
        </div>
        
        <!-- Python 专属新功能区域 -->
        <div class="control-group">
            <span class="label">当前保存路径</span>
            <button class="square-btn" id="chooseDirBtn" style="width:100%; padding: 6px 0; margin-bottom:6px;">📂 更改目录</button>
            <div id="savePathDisplay" style="font-size:11px; color:#5a6e9e; word-break:break-all; background:#f4f7fa; padding:4px 6px; border-radius:6px;">加载中...</div>
        </div>
        
        <div class="control-group">
            <span class="label" style="margin-bottom: 4px;">命名文字 (监听剪贴板)</span>
            <div id="clipboardDisplay" style="font-size:12px; background:#f0f4fe; padding:8px; border-radius:8px; color:#1e2f45; min-height:36px; word-break:break-all;">(空)</div>
            <div style="font-size:10px; color:#a0bbdf; margin-top:4px;">*保存时自动删去空格和禁用符号</div>
        </div>

        <div class="upload-square" id="compactUploadBtn">
            <div class="plus-icon">+</div>
            <div class="upload-text-small">添加图片 (支持拖拽)</div>
        </div>
        <input type="file" id="fileInput" multiple accept="image/*" style="display:none">

        <div class="control-group">
            <span class="label">选图间距调整</span>
            <div class="slider-row">
                <span style="width:24px; font-weight:bold; color:#4a627a;">↕</span>
                <input type="range" min="0" max="1000" value="0" id="spacingSlider">
                <input type="number" class="slider-num-input" id="spacingVal">
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:12px;">
                <span style="font-size:12px; font-weight:600;">背景颜色</span>
                <input type="color" value="#ffffff" id="spacingColor" style="cursor:pointer;">
            </div>
        </div>

        <div class="square-buttons">
            <div class="square-btn" id="mosaicBtn" title="单击单次画，双击锁定连续画">
                <span>🖌️</span><span id="mosaicBtnText">马赛克</span>
            </div>
            <div class="square-btn" id="saveSingleBtn"><span>📸</span><span>批量存单张</span></div>
            <div class="square-btn" id="clearAllBtn" style="grid-column: span 2;"><span>🗑️</span><span>清空所有</span></div>
        </div>

        <div id="mosaicControls" style="display: none;">
            <div class="label" style="margin-bottom: 2px;">画笔粗细</div>
            <div class="slider-row">
                <input type="range" min="10" max="150" value="40" id="brushSizeSlider">
                <input type="number" class="slider-num-input" id="brushSizeVal" value="40">
            </div>
        </div>
        
        <div style="margin-top: auto; padding-top: 6px;">
            <button class="action-btn-primary" id="downloadLongBtn">⬇️ 一键保存长图</button>
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
    let mosaicState = 0;
    let isCutMode = false;
    let isMultiSelectMode = false;
    let transformMatrix = { x: 0, y: 0, scale: 1 };
    let canvasSize = { width: 800, height: 400 };
    let imageHitBoxes = []; 
    let isPanning = false; 
    let isDrawingMosaic = false;
    let lastMousePos = { x: 0, y: 0 };
    let lastMouseX = 0, lastMouseY = 0;
    let activeDrag = null;
    let hoverTarget = null;
    
    const previewCanvas = document.getElementById('previewCanvas');
    const canvasWrapper = document.getElementById('canvasWrapper');
    const cutLineGuide = document.getElementById('cutLineGuide');
    const emptyOverlay = document.getElementById('emptyUploadOverlay');
    const mosaicBtn = document.getElementById('mosaicBtn');
    const mosaicControls = document.getElementById('mosaicControls');

    // ================== Python API 对接 ==================
    let pyApiReady = false;
    let lastClipboardText = "";

    window.addEventListener('pywebviewready', function() {
        pyApiReady = true;
        // 界面加载好，立刻问Python要默认路径
        pywebview.api.get_save_path().then(path => {
            if(path) document.getElementById('savePathDisplay').innerText = path;
        });
        
        // 每隔 0.5 秒问Python要一次剪贴板
        setInterval(() => {
            pywebview.api.get_clipboard().then(text => {
                if(text !== lastClipboardText) {
                    lastClipboardText = text;
                    let disp = document.getElementById('clipboardDisplay');
                    if (text && text.trim().length > 0) {
                        disp.innerText = text.length > 30 ? text.slice(0, 30) + "..." : text;
                    } else {
                        disp.innerText = "(无文本或非文本内容)";
                    }
                }
            });
        }, 500);
    });

    // 更换路径按钮
    document.getElementById('chooseDirBtn').addEventListener('click', () => {
        if(pyApiReady) {
            pywebview.api.choose_directory().then(path => {
                if(path) {
                    document.getElementById('savePathDisplay').innerText = path;
                    showToast("已修改并记住保存路径");
                }
            });
        }
    });

    // ====================================================

    function showToast(msg) {
        const container = document.getElementById('toastContainer');
        const t = document.createElement('div');
        t.className = 'toast'; t.innerText = msg;
        container.appendChild(t); void t.offsetWidth;
        t.classList.add('show');
        setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 300); }, 2000);
    }

    function saveHistory() {
        const state = images.map(img => ({
            id: img.id, name: img.name, imgObj: img.imgObj, pixelCanvas: img.pixelCanvas,
            crop: { ...img.crop }, spacingBottom: img.spacingBottom, selected: img.selected,
            masks: JSON.parse(JSON.stringify(img.masks)) 
        }));
        if (historyIndex < historyStack.length - 1) historyStack = historyStack.slice(0, historyIndex + 1);
        historyStack.push(state);
        historyIndex++; updateUI();
    }

    function restoreHistory(index) {
        if (index < 0 || index >= historyStack.length) return;
        historyIndex = index;
        images = historyStack[index].map(img => ({ ...img, crop: { ...img.crop }, masks: JSON.parse(JSON.stringify(img.masks)) }));
        updateUI(); renderThumbnails(); queueRenderPreview(); showToast("已撤销/重做");
    }

    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); e.shiftKey ? restoreHistory(historyIndex + 1) : restoreHistory(historyIndex - 1); }
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') { e.preventDefault(); restoreHistory(historyIndex + 1); }
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
        document.getElementById('spacingSlider').value = spacing; document.getElementById('spacingVal').value = spacing;
    }

    document.getElementById('multiSelectToggleBtn').addEventListener('click', (e) => {
        isMultiSelectMode = !isMultiSelectMode;
        e.target.classList.toggle('active', isMultiSelectMode);
        if (isMultiSelectMode) { images.forEach(img => img.selected = true); showToast("多选模式：已全选所有图片"); } 
        else { images.forEach(img => img.selected = false); showToast("单选模式：已取消所有选中"); }
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
            const c = item.crop; const sw = Math.max(1, item.imgObj.width - c.left - c.right); const sh = Math.max(1, item.imgObj.height - c.top - c.bottom);
            const scale = Math.min(130/sw, 80/sh) * 0.9;
            tCtx.fillStyle = '#f1f5f9'; tCtx.fillRect(0,0,130,80);
            tCtx.drawImage(item.imgObj, c.left, c.top, sw, sh, (130-sw*scale)/2, (80-sh*scale)/2, sw*scale, sh*scale);
        });
    }

    function syncSpacing() {
        let val = parseInt(document.getElementById('spacingSlider').value) || 0;
        document.getElementById('spacingVal').value = val;
        images.filter(img => img.selected).forEach(img => img.spacingBottom = val);
        queueRenderPreview();
    }
    document.getElementById('spacingSlider').addEventListener('input', syncSpacing);
    document.getElementById('spacingVal').addEventListener('input', () => { document.getElementById('spacingSlider').value = document.getElementById('spacingVal').value; syncSpacing(); });
    document.getElementById('spacingSlider').addEventListener('change', saveHistory);
    document.getElementById('spacingColor').addEventListener('input', queueRenderPreview);

    let mosaicClickTimer = null;
    mosaicBtn.addEventListener('click', (e) => {
        if (mosaicClickTimer) {
            clearTimeout(mosaicClickTimer); mosaicClickTimer = null;
            mosaicState = 2; updateMosaicUI(); showToast("马赛克 [锁定连续模式]"); return;
        }
        mosaicClickTimer = setTimeout(() => {
            mosaicClickTimer = null;
            if (mosaicState === 0) { mosaicState = 1; updateMosaicUI(); showToast("马赛克 [单次涂抹]"); }
            else { mosaicState = 0; updateMosaicUI(); }
        }, 250);
    });
    
    function updateMosaicUI() {
        mosaicBtn.className = 'square-btn';
        if (mosaicState === 1) mosaicBtn.classList.add('mosaic-single');
        if (mosaicState === 2) mosaicBtn.classList.add('mosaic-locked');
        mosaicControls.style.display = mosaicState > 0 ? 'block' : 'none';
        isCutMode = false; cutLineGuide.style.display = 'none';
        updateBrushCursor(); queueRenderPreview();
    }
    
    document.getElementById('brushSizeSlider').addEventListener('input', function() { document.getElementById('brushSizeVal').value = this.value; updateBrushCursor(); });
    document.getElementById('brushSizeVal').addEventListener('input', function() { document.getElementById('brushSizeSlider').value = this.value; updateBrushCursor(); });

    let renderFrame = null;
    function queueRenderPreview(reset = false) { if (renderFrame) cancelAnimationFrame(renderFrame); renderFrame = requestAnimationFrame(() => renderPreview(reset)); }

    function renderPreview(resetViewFlag = false) {
        imageHitBoxes = [];
        if (images.length === 0) {
            previewCanvas.width = 800; previewCanvas.height = 400; canvasSize = { width: 800, height: 400 };
            const ctx = previewCanvas.getContext('2d'); ctx.fillStyle = '#f5f7fc'; ctx.fillRect(0, 0, 800, 400);
            updateCanvasDisplay(); resetView(); return;
        }
        
        let maxWidth = 0;
        let itemsData = images.map(img => {
            let c = img.crop; let sw = Math.max(1, img.imgObj.width - c.left - c.right); let sh = Math.max(1, img.imgObj.height - c.top - c.bottom);
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
            ctx.drawImage(d.imgObj, d.sx, d.sy, d.sw, d.sh, 0, curY, rw, rh);
            
            if (d.masks && d.masks.length > 0) {
                const tCanv = document.createElement('canvas'); tCanv.width = rw; tCanv.height = rh; const tCtx = tCanv.getContext('2d');
                tCtx.lineCap = 'round'; tCtx.lineJoin = 'round'; tCtx.strokeStyle = 'black';
                d.masks.forEach(stroke => {
                    if (stroke.points.length === 0) return;
                    tCtx.lineWidth = stroke.size * scaleRender;
                    tCtx.beginPath(); tCtx.moveTo((stroke.points[0].x - d.sx) * scaleRender, (stroke.points[0].y - d.sy) * scaleRender);
                    for (let j = 1; j < stroke.points.length; j++) tCtx.lineTo((stroke.points[j].x - d.sx) * scaleRender, (stroke.points[j].y - d.sy) * scaleRender);
                    tCtx.stroke();
                });
                tCtx.globalCompositeOperation = 'source-in'; tCtx.drawImage(d.pixelCanvas, d.sx, d.sy, d.sw, d.sh, 0, 0, rw, rh); ctx.drawImage(tCanv, 0, curY);
            }
            
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

        if (hoverTarget && hoverTarget.type === 'edge' && !isCutMode && !activeDrag && mosaicState === 0) {
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
        updateCanvasDisplay(); if (resetViewFlag) resetView(true);
    }

    function updateCanvasDisplay() { previewCanvas.style.transform = `translate(${transformMatrix.x}px, ${transformMatrix.y}px) scale(${transformMatrix.scale})`; document.getElementById('zoomLevel').innerText = Math.round(transformMatrix.scale * 100) + '%'; }
    
    function resetView(isInitial = false) { 
        const rect = canvasWrapper.getBoundingClientRect(); if (canvasSize.width === 0) return;
        let targetScale = isInitial ? (rect.width / 3) / canvasSize.width : Math.min(rect.width / canvasSize.width, rect.height / canvasSize.height) * 0.9;
        transformMatrix.scale = Math.max(0.01, Math.min(20, targetScale));
        transformMatrix.x = (rect.width - canvasSize.width * transformMatrix.scale) / 2;
        transformMatrix.y = isInitial ? 40 : (rect.height - canvasSize.height * transformMatrix.scale) / 2;
        updateCanvasDisplay();
    }

    function getMouseCanvasCoords(e) {
        let rect = canvasWrapper.getBoundingClientRect();
        let cx = (e.clientX - rect.left - transformMatrix.x) / transformMatrix.scale;
        let cy = (e.clientY - rect.top - transformMatrix.y) / transformMatrix.scale;
        return { cx, cy, rawX: e.clientX, rawY: e.clientY };
    }

    function getHitTarget(cx, cy) {
        if (isCutMode || mosaicState > 0) return null;
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
        if (mosaicState === 0) { brushCursor.style.display = 'none'; return; }
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
        if (isCutMode || mosaicState > 0) { canvasWrapper.style.cursor = 'crosshair'; return; }
        if (isPanning || isDrawingMosaic || activeDrag) return; 
        const { cx, cy } = getMouseCanvasCoords(e); hoverTarget = getHitTarget(cx, cy);
        if (hoverTarget) {
            if (hoverTarget.type === 'corner') { canvasWrapper.style.cursor = (hoverTarget.corner === 'tl' || hoverTarget.corner === 'br') ? 'nwse-resize' : 'nesw-resize'; } 
            else { if (hoverTarget.edge === 'bottom') canvasWrapper.style.cursor = CURSOR_UP; else if (hoverTarget.edge === 'top') canvasWrapper.style.cursor = CURSOR_DOWN; else canvasWrapper.style.cursor = 'ew-resize'; }
        } else { canvasWrapper.style.cursor = 'grab'; }
        queueRenderPreview();
    }

    canvasWrapper.addEventListener('contextmenu', (e) => {
        e.preventDefault(); if (mosaicState > 0) return;
        isCutMode = true; activeDrag = null; hoverTarget = null; cutLineGuide.style.display = 'block';
        const { rawY } = getMouseCanvasCoords(e); cutLineGuide.style.top = (rawY - canvasWrapper.getBoundingClientRect().top) + 'px';
        updateCursor(e); queueRenderPreview();
    });

    canvasWrapper.addEventListener('dblclick', (e) => {
        if (mosaicState > 0 || isCutMode) return;
        const { cx, cy } = getMouseCanvasCoords(e);
        let box = imageHitBoxes.find(b => cy >= b.y0 && cy <= b.y1 && cx >= b.x0 && cx <= b.x1);
        if (box) { images.forEach(img => img.selected = false); images[box.index].selected = true; updateUI(); renderThumbnails(); queueRenderPreview(); showToast("已选中该图片"); }
    });

    canvasWrapper.addEventListener('mousedown', (e) => {
        if (e.button !== 0) return;
        const { cx, cy } = getMouseCanvasCoords(e);
        if (isCutMode) {
            let box = imageHitBoxes.find(b => cy >= b.y0 && cy <= b.y1 && cx >= b.x0 && cx <= b.x1);
            isCutMode = false; cutLineGuide.style.display = 'none'; updateCursor(e); queueRenderPreview();
            if (!box) return; 
            let img = images[box.index]; let cutYOrig = Math.round((cy - box.y0) / box.scaleRender + img.crop.top);
            if (cutYOrig <= img.crop.top + 10 || cutYOrig >= img.imgObj.height - img.crop.bottom - 10) { showToast("切割位置太靠近边缘！"); return; }
            let bottomImg = { id: Date.now() + Math.random(), imgObj: img.imgObj, pixelCanvas: img.pixelCanvas, name: img.name, crop: { ...img.crop, top: cutYOrig }, spacingBottom: img.spacingBottom, selected: img.selected, masks: JSON.parse(JSON.stringify(img.masks)) };
            img.crop.bottom = img.imgObj.height - cutYOrig; img.spacingBottom = 0; 
            images.splice(box.index + 1, 0, bottomImg); saveHistory(); renderThumbnails(); queueRenderPreview(); showToast("✂️ 分割成功"); return;
        }

        if (mosaicState > 0) {
            let box = imageHitBoxes.find(b => cy >= b.y0 && cy <= b.y1 && cx >= b.x0 && cx <= b.x1); if (!box) return;
            isDrawingMosaic = true; let img = images[box.index]; let brushSize = parseInt(document.getElementById('brushSizeSlider').value) || 40;
            let origX = (cx - box.x0) / box.scaleRender + img.crop.left; let origY = (cy - box.y0) / box.scaleRender + img.crop.top;
            img.masks.push({ size: brushSize, points: [{ x: origX, y: origY }] }); queueRenderPreview(); return;
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

        if (isDrawingMosaic) {
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
                let img = images[item.index]; let start = item.crop; let maxW = img.imgObj.width; let maxH = img.imgObj.height;
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
        if (isDrawingMosaic) { isDrawingMosaic = false; saveHistory(); if (mosaicState === 1) { mosaicState = 0; updateMosaicUI(); } }
        if (activeDrag) { activeDrag = null; saveHistory(); }
        if (isPanning) { isPanning = false; canvasWrapper.style.cursor = 'grab'; }
    });

    canvasWrapper.addEventListener('mouseleave', () => { document.getElementById('brushCursor').style.display = 'none'; });

    function uploadFiles(files) {
        if (!files.length) return;
        const promises = Array.from(files).map(file => new Promise(resolve => {
            let img = new Image(); img.src = URL.createObjectURL(file);
            img.onload = () => { URL.revokeObjectURL(img.src); resolve({ id: Date.now() + Math.random(), imgObj: img, pixelCanvas: generatePixelCanvas(img), name: file.name, crop: { top: 0, bottom: 0, left: 0, right: 0 }, spacingBottom: 0, masks: [], selected: false }); };
        }));
        Promise.all(promises).then(newImgs => {
            if (isMultiSelectMode) { newImgs.forEach(i => i.selected = true); } 
            else { images.forEach(i => i.selected = false); if (newImgs.length > 0) newImgs[0].selected = true; }
            images.push(...newImgs); saveHistory(); renderThumbnails(); queueRenderPreview(true); showToast(`导入 ${newImgs.length} 张图片`);
        });
    }
    
    document.getElementById('fileInput').addEventListener('change', e => { uploadFiles(e.target.files); e.target.value=''; });
    document.getElementById('compactUploadBtn').addEventListener('click', () => document.getElementById('fileInput').click());
    emptyOverlay.addEventListener('click', () => document.getElementById('fileInput').click());
    window.addEventListener('dragover', e => e.preventDefault()); window.addEventListener('drop', e => { e.preventDefault(); if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files); });
    document.getElementById('clearAllBtn').addEventListener('click', () => { images = []; saveHistory(); renderThumbnails(); queueRenderPreview(true); showToast("已清空"); });

    // ================== 交给 Python 核心去保存文件 ==================
    // 存单张 (PNG 无损)
    document.getElementById('saveSingleBtn').addEventListener('click', () => {
        if (images.length === 0) { showToast("没有图片可供保存"); return; }
        if (!pyApiReady) return;
        showToast("批量保存中...");
        images.forEach((img, idx) => {
            const canvas = document.createElement('canvas'); const ctx = canvas.getContext('2d');
            const c = img.crop; const sw = Math.max(1, img.imgObj.width - c.left - c.right); const sh = Math.max(1, img.imgObj.height - c.top - c.bottom);
            canvas.width = sw; canvas.height = sh;
            ctx.drawImage(img.imgObj, c.left, c.top, sw, sh, 0, 0, sw, sh);
            if(img.masks && img.masks.length>0) {
                const tCanv = document.createElement('canvas'); tCanv.width = sw; tCanv.height = sh; const tCtx = tCanv.getContext('2d');
                tCtx.lineCap = 'round'; tCtx.lineJoin = 'round'; tCtx.strokeStyle = 'black';
                img.masks.forEach(stroke => { if (!stroke.points.length) return; tCtx.lineWidth = stroke.size; tCtx.beginPath(); tCtx.moveTo(stroke.points[0].x - c.left, stroke.points[0].y - c.top); for(let j=1;j<stroke.points.length;j++) tCtx.lineTo(stroke.points[j].x - c.left, stroke.points[j].y - c.top); tCtx.stroke(); });
                tCtx.globalCompositeOperation = 'source-in'; tCtx.drawImage(img.pixelCanvas, c.left, c.top, sw, sh, 0, 0, sw, sh); ctx.drawImage(tCanv, 0, 0);
            }
            let b64 = canvas.toDataURL('image/png');
            pywebview.api.save_image(b64, `_片段${idx+1}`, '.png').then(msg => { console.log(msg); });
        });
    });

    // 存长图 (JPG 压缩)
    document.getElementById('downloadLongBtn').addEventListener('click', () => {
        if(images.length === 0) { showToast("无图片可保存"); return; }
        if(!pyApiReady) return;
        
        let maxW = 0, items = images.map(img => { 
            let c = img.crop; let sw = Math.max(1, img.imgObj.width - c.left - c.right); let sh = Math.max(1, img.imgObj.height - c.top - c.bottom); 
            if(sw > maxW) maxW = sw; return { imgObj: img.imgObj, pixelCanvas: img.pixelCanvas, masks: img.masks, sw, sh, sx: c.left, sy: c.top }; 
        });
        
        let totalH = 0; items.forEach((d, i) => { totalH += d.sh * (maxW / d.sw) + (i < items.length - 1 ? (images[i].spacingBottom || 0) : 0); });
        let canvas = document.createElement('canvas'); canvas.width = maxW; canvas.height = totalH; 
        let ctx = canvas.getContext('2d'); ctx.fillStyle = document.getElementById('spacingColor').value; ctx.fillRect(0, 0, canvas.width, canvas.height); 
        
        let y = 0; 
        items.forEach((d, i) => { 
            let scale = maxW / d.sw; let rh = d.sh * scale; let rw = maxW; 
            ctx.drawImage(d.imgObj, d.sx, d.sy, d.sw, d.sh, 0, y, rw, rh); 
            if (d.masks && d.masks.length > 0) {
                const tCanv = document.createElement('canvas'); tCanv.width = rw; tCanv.height = rh; const tCtx = tCanv.getContext('2d');
                tCtx.lineCap = 'round'; tCtx.lineJoin = 'round'; tCtx.strokeStyle = 'black';
                d.masks.forEach(stroke => { if (!stroke.points.length) return; tCtx.lineWidth = stroke.size * scale; tCtx.beginPath(); tCtx.moveTo((stroke.points[0].x - d.sx) * scale, (stroke.points[0].y - d.sy) * scale); for (let j = 1; j < stroke.points.length; j++) tCtx.lineTo((stroke.points[j].x - d.sx) * scale, (stroke.points[j].y - d.sy) * scale); tCtx.stroke(); });
                tCtx.globalCompositeOperation = 'source-in'; tCtx.drawImage(d.pixelCanvas, d.sx, d.sy, d.sw, d.sh, 0, 0, rw, rh); ctx.drawImage(tCanv, 0, y);
            }
            y += rh + (i < items.length - 1 ? (images[i].spacingBottom || 0) : 0); 
        });
        
        showToast("长图处理中...");
        let b64 = canvas.toDataURL('image/jpeg', 0.95);
        pywebview.api.save_image(b64, '', '.jpg').then(msg => {
            showToast(msg);
        });
    });
    // ====================================================

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
    # 实例化处理逻辑接口
    api = Api()
    # 创建桌面应用窗口
    window = webview.create_window(
        '图片合成编辑器 - 终极至尊版', 
        html=HTML_CONTENT, 
        js_api=api, 
        width=1280, 
        height=800,
        text_select=True # 允许在输入框选文字
    )
    # 启动程序
    webview.start()