import os
import json
import webview
import base64
from pathlib import Path

CONFIG_FILE = 'file_renamer_config.json'

class Api:
    def __init__(self):
        self.files = []
        self.left_slots = []
        self.right_slots = []
        self.load_config()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.last_dir = data.get('last_dir', "")
            except:
                self.last_dir = ""
        else:
            self.last_dir = ""

    def save_config(self):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({'last_dir': self.last_dir}, f)

    def is_image_file(self, filename):
        image_ext = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.ico'}
        return Path(filename).suffix.lower() in image_ext

    def get_file_ext(self, filename):
        ext = Path(filename).suffix
        return ext[1:].upper() if ext else "?"

    def extract_number_prefix(self, filename):
        import re
        match = re.match(r'^(\d+)', filename)
        if match:
            return int(match.group(1))
        return None

    def remove_number_prefix(self, filename):
        import re
        return re.sub(r'^\d+', '', filename)

    def choose_files(self):
        result = webview.windows[0].create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True)
        if result and len(result) > 0:
            parsed_files = []
            for file_path in result:
                original_name = os.path.basename(file_path)
                number = self.extract_number_prefix(original_name)
                clean_name = self.remove_number_prefix(original_name)
                
                parsed_files.append({
                    "original_path": file_path,
                    "original_name": original_name,
                    "clean_name": clean_name,
                    "number": number,
                    "ext": self.get_file_ext(original_name),
                    "is_image": self.is_image_file(original_name)
                })

            with_number = [f for f in parsed_files if f["number"] is not None]
            without_number = [f for f in parsed_files if f["number"] is None]
            with_number.sort(key=lambda x: x["number"])

            sorted_files = with_number + without_number

            self.left_slots = []
            slot_count = max(200, len(sorted_files) * 2)
            self.right_slots = [None] * slot_count  

            for idx, item in enumerate(sorted_files):
                self.left_slots.append({
                    "id": f"file_{idx}_{hash(item['original_path'])}",  # 生成唯一ID保障缓存不出错
                    "display_name": item["clean_name"],
                    "original_name": item["clean_name"],
                    "original_number": item["number"],
                    "ext": item["ext"],
                    "is_image": item["is_image"],
                    "original_path": item["original_path"]
                })

            self.files = self.left_slots

            return {"success": True, "count": len(self.left_slots)}

        return None

    def get_slots_data(self):
        left_count = len([s for s in self.left_slots if s is not None])
        right_count = len([s for s in self.right_slots if s is not None])
        return {
            "left": self.left_slots,
            "right": self.right_slots,
            "left_count": left_count,
            "right_count": right_count,
            "max_left": len(self.left_slots),
            "max_right": len(self.right_slots)
        }

    def get_image_base64(self, filepath):
        try:
            with open(filepath, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception:
            return ""

    def move_to_right(self, left_index, slot_index):
        if left_index < 0 or left_index >= len(self.left_slots):
            return {"error": "无效的左侧索引"}
        item = self.left_slots[left_index]
        if item is None:
            return {"error": "该位置没有文件"}
        if slot_index < 0 or slot_index >= len(self.right_slots):
            return {"error": "无效的右侧索引"}
        if self.right_slots[slot_index] is not None:
            return {"error": f"右侧第 {slot_index + 1} 位已有文件"}

        new_number = slot_index + 1
        new_name = f"{new_number}{item['original_name']}"

        original_path = item["original_path"]
        if not original_path or not os.path.exists(original_path):
            return {"error": f"原文件不存在: {original_path}"}

        dir_path = os.path.dirname(original_path)
        new_path = os.path.join(dir_path, new_name)

        try:
            counter = 1
            final_path = new_path
            while os.path.exists(final_path):
                name_without_ext = os.path.splitext(f"{new_number}{item['original_name']}")[0]
                ext = os.path.splitext(item['original_name'])[1]
                final_name = f"{name_without_ext}_{counter}{ext}"
                final_path = os.path.join(dir_path, final_name)
                counter += 1

            os.rename(original_path, final_path)

            item["display_name"] = os.path.basename(final_path)
            item["original_path"] = final_path
            item["new_number"] = new_number
            item["renamed"] = True

            self.right_slots[slot_index] = item
            self.left_slots[left_index] = None

            return {"success": True, "left_index": left_index, "right_index": slot_index, "item": item}
        except Exception as e:
            return {"error": f"重命名失败: {str(e)}"}

    def move_to_left(self, right_index, target_left_index=None):
        if right_index < 0 or right_index >= len(self.right_slots):
            return {"error": "无效的右侧索引"}
        item = self.right_slots[right_index]
        if item is None:
            return {"error": "该位置没有文件"}

        original_name = item["original_name"]
        current_path = item["original_path"]
        dir_path = os.path.dirname(current_path)
        new_path = os.path.join(dir_path, original_name)

        try:
            counter = 1
            final_path = new_path
            while os.path.exists(final_path) and final_path != current_path:
                name_without_ext = os.path.splitext(original_name)[0]
                ext = os.path.splitext(original_name)[1]
                final_name = f"{name_without_ext}_恢复{counter}{ext}"
                final_path = os.path.join(dir_path, final_name)
                counter += 1

            os.rename(current_path, final_path)

            item["display_name"] = os.path.basename(final_path)
            item["original_path"] = final_path
            item["renamed"] = False
            if "new_number" in item:
                del item["new_number"]

            self.right_slots[right_index] = None

            if target_left_index is not None and target_left_index < len(self.left_slots) and self.left_slots[target_left_index] is None:
                self.left_slots[target_left_index] = item
                final_left_index = target_left_index
            else:
                empty_index = next((i for i, s in enumerate(self.left_slots) if s is None), None)
                if empty_index is not None:
                    self.left_slots[empty_index] = item
                    final_left_index = empty_index
                else:
                    final_left_index = len(self.left_slots)
                    self.left_slots.append(item)

            return {"success": True, "right_index": right_index, "left_index": final_left_index, "item": item}
        except Exception as e:
            return {"error": f"恢复失败: {str(e)}"}

    def swap_right_items(self, from_index, to_index):
        if from_index == to_index:
            return {"error": "相同位置无需交换"}
        if from_index < 0 or from_index >= len(self.right_slots) or to_index < 0 or to_index >= len(self.right_slots):
            return {"error": "无效的索引"}

        item_from = self.right_slots[from_index]
        item_to = self.right_slots[to_index]
        if item_from is None:
            return {"error": "源位置没有文件"}

        self.right_slots[from_index] = item_to
        self.right_slots[to_index] = item_from
        errors = []

        if item_from:
            new_name_from = f"{to_index + 1}{item_from['original_name']}"
            old_path_from = item_from["original_path"]
            dir_path = os.path.dirname(old_path_from)
            new_path_from = os.path.join(dir_path, new_name_from)
            try:
                counter = 1
                final_path = new_path_from
                while os.path.exists(final_path) and final_path != old_path_from:
                    name_without_ext = os.path.splitext(f"{to_index + 1}{item_from['original_name']}")[0]
                    ext = os.path.splitext(item_from['original_name'])[1]
                    final_name = f"{name_without_ext}_{counter}{ext}"
                    final_path = os.path.join(dir_path, final_name)
                    counter += 1
                os.rename(old_path_from, final_path)
                item_from["display_name"] = os.path.basename(final_path)
                item_from["original_path"] = final_path
                item_from["new_number"] = to_index + 1
            except Exception as e:
                errors.append(f"重命名 {item_from['original_name']} 失败: {str(e)}")

        if item_to:
            new_name_to = f"{from_index + 1}{item_to['original_name']}"
            old_path_to = item_to["original_path"]
            dir_path = os.path.dirname(old_path_to)
            new_path_to = os.path.join(dir_path, new_name_to)
            try:
                counter = 1
                final_path = new_path_to
                while os.path.exists(final_path) and final_path != old_path_to:
                    name_without_ext = os.path.splitext(f"{from_index + 1}{item_to['original_name']}")[0]
                    ext = os.path.splitext(item_to['original_name'])[1]
                    final_name = f"{name_without_ext}_{counter}{ext}"
                    final_path = os.path.join(dir_path, final_name)
                    counter += 1
                os.rename(old_path_to, final_path)
                item_to["display_name"] = os.path.basename(final_path)
                item_to["original_path"] = final_path
                item_to["new_number"] = from_index + 1
            except Exception as e:
                errors.append(f"重命名 {item_to['original_name']} 失败: {str(e)}")

        if errors:
            return {"error": "; ".join(errors)}
        return {"success": True, "from_index": from_index, "to_index": to_index, "item_from": item_from, "item_to": item_to}

    def clear_all(self):
        errors = []
        for i in range(len(self.right_slots) - 1, -1, -1):
            if self.right_slots[i] is not None:
                result = self.move_to_left(i)
                if "error" in result:
                    errors.append(result["error"])
        if errors:
            return {"error": "; ".join(errors)}
        return {"success": True}

    def reset_workspace(self):
        self.files = []
        self.left_slots = []
        self.right_slots = [None] * 200
        return {"success": True}

# ==================== HTML 前端代码 ====================
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>极速文件编号工具</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f0f2f5; height: 100vh; overflow: hidden; }
        .topbar { background: white; padding: 12px 20px; display: flex; gap: 12px; flex-wrap: wrap; align-items: center; border-bottom: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        button { padding: 8px 16px; cursor: pointer; border: none; border-radius: 6px; font-size: 14px; font-weight: 500; transition: all 0.2s; }
        .btn-primary { background: #4caf50; color: white; }
        .btn-primary:hover { background: #45a049; }
        .btn-secondary { background: #2196f3; color: white; }
        .btn-secondary:hover { background: #0b7dda; }
        .btn-danger { background: #f44336; color: white; }
        .btn-danger:hover { background: #da190b; }
        .btn-warning { background: #ff9800; color: white; }
        .btn-warning:hover { background: #e68a00; }
        .file-info { font-size: 13px; color: #666; margin-left: 10px; padding: 5px 12px; background: #f5f5f5; border-radius: 20px; }
        .stats { font-size: 13px; color: #666; margin-left: auto; font-weight: 500; }
        .main { display: flex; gap: 20px; padding: 20px; height: calc(100vh - 60px); overflow: hidden; }
        .left-panel, .right-panel { display: flex; flex-direction: column; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); overflow: hidden; }
        .left-panel { width: 45%; }
        .right-panel { width: 55%; }
        .panel-header { padding: 12px 16px; background: #f8f9fa; border-bottom: 1px solid #e0e0e0; font-weight: 600; font-size: 15px; }
        .panel-header span { color: #4caf50; }
        .grid-container { flex: 1; overflow-y: auto; padding: 16px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 12px; }
        .slot-card { aspect-ratio: 1 / 1.2; border: 2px solid #e0e0e0; border-radius: 10px; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; overflow: hidden; cursor: pointer; transition: all 0.2s; background: #fafafa; position: relative; }
        .slot-card.empty { background: #f5f5f5; border-style: dashed; cursor: default; }
        .slot-card.left-filled { border-color: #ff9800; background: #fff8e1; }
        .slot-card.right-filled { border-color: #4caf50; background: #e8f5e9; }
        .slot-card:hover:not(.empty) { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
        .slot-card.dragging { opacity: 0.5; }
        .slot-card.drag-over { border-color: #2196f3; background: #e3f2fd; }
        .preview-area { width: 100%; height: 70px; display: flex; align-items: center; justify-content: center; background: #e0e0e0; margin-bottom: 8px; overflow: hidden; }
        .preview-img { width: 100%; height: 100%; object-fit: cover; }
        .preview-file { font-size: 18px; font-weight: bold; color: #666; background: #e0e0e0; width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; text-transform: uppercase; word-break: break-all; padding: 4px; text-align: center; }
        .file-name { font-size: 11px; text-align: center; width: 100%; padding: 0 4px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; color: #333; }
        .slot-number { position: absolute; top: 4px; left: 8px; font-size: 16px; font-weight: bold; color: rgba(0,0,0,0.3); pointer-events: none; z-index: 10; background: rgba(255,255,255,0.7); padding: 0 4px; border-radius: 4px; }
        .right-filled .slot-number { color: rgba(76, 175, 80, 0.9); background: rgba(232, 245, 233, 0.8); }
        .toast { position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%); background: rgba(244, 67, 54, 0.9); color: white; padding: 10px 20px; border-radius: 8px; font-size: 14px; z-index: 1000; animation: fadeOut 2.5s ease forwards; pointer-events: none;}
        @keyframes fadeOut { 0% { opacity: 1; } 70% { opacity: 1; } 100% { opacity: 0; visibility: hidden; } }
    </style>
</head>
<body>

<div class="topbar">
    <button class="btn-primary" onclick="selectFiles()">📁 选择文件</button>
    <button class="btn-secondary" onclick="refreshData(true)">🔄 刷新</button>
    <button class="btn-warning" onclick="clearAll()">🗑️ 全部移回左侧</button>
    <button class="btn-danger" onclick="resetWorkspace()">🧹 清空列表</button>
    <div class="file-info" id="fileInfo">未选择文件</div>
    <div class="stats" id="stats">待整理 0 | 已编号 0</div>
</div>

<div class="main">
    <div class="left-panel">
        <div class="panel-header">📦 待整理区 <span id="leftCount">0</span></div>
        <div class="grid-container"><div class="grid" id="leftGrid"></div></div>
    </div>
    <div class="right-panel">
        <div class="panel-header">✅ 已编号区 <span id="rightCount">0</span></div>
        <div class="grid-container"><div class="grid" id="rightGrid"></div></div>
    </div>
</div>

<script>
    let pyApi = null;
    let currentData = { left: [], right: [] };
    let dragSource = null;
    let imageQueue = [];
    let isProcessingQueue = false;
    let imageCache = {}; // 图片指纹极速缓存

    window.addEventListener('pywebviewready', function() {
        pyApi = window.pywebview.api;
    });

    function showError(message) {
        const existing = document.querySelector('.toast');
        if (existing) existing.remove();
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => { if (toast && toast.parentNode) toast.remove(); }, 2500);
    }

    async function selectFiles() {
        if (!pyApi) return;
        try {
            const result = await pyApi.choose_files();
            if (result && result.success) await refreshData(true);
        } catch (e) {
            showError('选择文件失败: ' + e.message);
        }
    }

    function updateCounts() {
        const leftCount = currentData.left.filter(s => s !== null).length;
        const rightCount = currentData.right.filter(s => s !== null).length;
        document.getElementById('leftCount').innerText = leftCount;
        document.getElementById('rightCount').innerText = rightCount;
        document.getElementById('stats').innerHTML = `📦 待整理 ${leftCount} | ✅ 已编号 ${rightCount}`;
        document.getElementById('fileInfo').innerHTML = (leftCount || rightCount) ? `📄 共载入 ${leftCount + rightCount} 个文件` : `未选择文件`;
    }

    function updateSlotDOM(type, index, slotData) {
        const grid = document.getElementById(type === 'left' ? 'leftGrid' : 'rightGrid');
        
        while(index >= grid.children.length) {
            const temp = document.createElement('div');
            grid.appendChild(temp);
            currentData[type].push(null);
        }

        const card = grid.children[index];
        currentData[type][index] = slotData;

        if (!slotData) {
            card.className = 'slot-card empty';
            card.innerHTML = `<div class="slot-number">${index + 1}</div>`;
            card.draggable = false;
            card.onclick = null;
            card.ondragstart = null;
            card.ondragend = null;
        } else {
            card.className = `slot-card ${type}-filled`;
            const numDisplay = type === 'left' ? (slotData.original_number !== null ? slotData.original_number : '') : (index + 1);
            card.innerHTML = `
                <div class="slot-number">${numDisplay}</div>
                <div class="preview-area">${getPreviewHtml(slotData)}</div>
                <div class="file-name" title="${escapeHtml(slotData.display_name)}">${escapeHtml(truncateName(slotData.display_name))}</div>
            `;
            card.draggable = true;
            card.onclick = (e) => {
                e.stopPropagation();
                if (type === 'left') moveToRight(index); else moveToLeft(index);
            };
            card.ondragstart = (e) => {
                dragSource = { type: type, index: index };
                e.dataTransfer.setData('text/plain', JSON.stringify(dragSource));
                card.classList.add('dragging');
            };
            card.ondragend = () => {
                card.classList.remove('dragging');
                removeDragOverHighlight();
            };
        }

        if (type === 'right') {
            card.ondragover = (e) => { e.preventDefault(); card.classList.add('drag-over'); };
            card.ondragleave = () => { card.classList.remove('drag-over'); };
            card.ondrop = async (e) => {
                e.preventDefault();
                card.classList.remove('drag-over');
                if (!dragSource) return;
                removeDragOverHighlight();
                if (dragSource.type === 'right' && dragSource.index !== index) {
                    await swapRightItems(dragSource.index, index);
                } else if (dragSource.type === 'left') {
                    await moveToRight(dragSource.index, index);
                }
                dragSource = null;
            };
        }
        triggerImageLoads();
    }

    async function refreshData(full = false) {
        if (!pyApi) return;
        try {
            const data = await pyApi.get_slots_data();
            currentData.left = data.left;
            currentData.right = data.right;
            if (full) {
                const lg = document.getElementById('leftGrid');
                const rg = document.getElementById('rightGrid');
                lg.innerHTML = ''; rg.innerHTML = '';
                for (let i = 0; i < data.left.length; i++) lg.appendChild(document.createElement('div'));
                for (let i = 0; i < data.right.length; i++) rg.appendChild(document.createElement('div'));
                for (let i = 0; i < data.left.length; i++) updateSlotDOM('left', i, data.left[i]);
                for (let i = 0; i < data.right.length; i++) updateSlotDOM('right', i, data.right[i]);
            }
            updateCounts();
        } catch (e) {
            showError('获取数据失败: ' + e.message);
        }
    }

    function getPreviewHtml(slot) {
        if (slot.is_image) {
            return `<div class="preview-img-container" data-id="${slot.id}" data-path="${escapeHtml(slot.original_path)}" data-ext="${escapeHtml(slot.ext)}" style="font-size:24px; color:#999;">⏳</div>`;
        }
        return `<div class="preview-file">${escapeHtml(slot.ext) || 'FILE'}</div>`;
    }
    
    function queueImageLoad(container, id, path, ext) {
        container.setAttribute('data-loading', 'true');
        imageQueue.push({container, id, path, ext});
        if (!isProcessingQueue) processImageQueue();
    }

    async function processImageQueue() {
        isProcessingQueue = true;
        while (imageQueue.length > 0) {
            const batch = imageQueue.splice(0, 5);
            await Promise.all(batch.map(async item => {
                try {
                    // 如果缓存里有，直接秒读不调用Python
                    if (imageCache[item.id]) {
                        item.container.innerHTML = `<img src="data:image/jpeg;base64,${imageCache[item.id]}" class="preview-img">`;
                        return;
                    }
                    const b64 = await pyApi.get_image_base64(item.path);
                    if (b64) {
                        imageCache[item.id] = b64;
                        item.container.innerHTML = `<img src="data:image/jpeg;base64,${b64}" class="preview-img">`;
                    } else {
                        item.container.innerHTML = `<div class="preview-file">${item.ext || 'FILE'}</div>`;
                    }
                } catch (e) {
                    item.container.innerHTML = `<div class="preview-file">${item.ext || 'FILE'}</div>`;
                }
            }));
        }
        // 【关键修复点】：之前我在这里误写成了 true，导致沙漏堵塞！现在改回 false
        isProcessingQueue = false; 
    }

    function triggerImageLoads() {
        document.querySelectorAll('.preview-img-container:not([data-loading])').forEach(c => {
            queueImageLoad(c, c.getAttribute('data-id'), c.getAttribute('data-path'), c.getAttribute('data-ext'));
        });
    }

    async function moveToRight(leftIndex, targetSlot = null) {
        if (!pyApi) return;
        let slotIndex = targetSlot;
        if (slotIndex === null) {
            for (let i = 0; i < currentData.right.length; i++) {
                if (currentData.right[i] === null) { slotIndex = i; break; }
            }
            if (slotIndex === null) { showError('右侧已满'); return; }
        }

        try {
            const res = await pyApi.move_to_right(leftIndex, slotIndex);
            if (res.error) {
                showError(res.error);
            } else {
                updateSlotDOM('left', res.left_index, null);
                updateSlotDOM('right', res.right_index, res.item);
                updateCounts();
            }
        } catch (e) { showError('操作失败: ' + e.message); }
    }

    async function moveToLeft(rightIndex) {
        if (!pyApi) return;
        try {
            const res = await pyApi.move_to_left(rightIndex, null);
            if (res.error) {
                showError(res.error);
            } else {
                updateSlotDOM('right', res.right_index, null);
                updateSlotDOM('left', res.left_index, res.item);
                updateCounts();
            }
        } catch (e) { showError('操作失败: ' + e.message); }
    }

    async function swapRightItems(fromIndex, toIndex) {
        if (!pyApi) return;
        try {
            const res = await pyApi.swap_right_items(fromIndex, toIndex);
            if (res.error) {
                showError(res.error);
            } else {
                updateSlotDOM('right', res.from_index, res.item_from);
                updateSlotDOM('right', res.to_index, res.item_to);
            }
        } catch (e) { showError('交换失败: ' + e.message); }
    }

    async function clearAll() {
        if (!confirm('确定要将所有文件移回左侧(恢复原名)吗？')) return;
        if (!pyApi) return;
        try {
            const res = await pyApi.clear_all();
            if (res.error) showError(res.error);
            await refreshData(true);
        } catch (e) { showError('操作失败: ' + e.message); }
    }
    
    async function resetWorkspace() {
        if (!confirm('确定清空列表吗？（不删除本地文件）')) return;
        if (!pyApi) return;
        try {
            // 清空缓存释放内存
            imageCache = {}; 
            await pyApi.reset_workspace();
            await refreshData(true);
        } catch (e) { showError('操作失败: ' + e.message); }
    }

    function removeDragOverHighlight() { document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over')); }
    function escapeHtml(text) { const div = document.createElement('div'); div.textContent = text || ''; return div.innerHTML; }
    function truncateName(name, maxLen = 18) { return (!name || name.length <= maxLen) ? name : name.substring(0, maxLen - 3) + '...'; }
</script>
</body>
</html>
"""

if __name__ == '__main__':
    api = Api()
    window = webview.create_window(
        '极速文件编号工具',
        html=HTML_CONTENT,
        js_api=api,
        width=1400,
        height=800,
        text_select=False 
    )
    webview.start()