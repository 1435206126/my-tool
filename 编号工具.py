import os
import json
import shutil
import webview
import base64
from pathlib import Path

CONFIG_FILE = 'file_renamer_config.json'


class Api:
    def __init__(self):
        self.files = []  # 文件列表 [{id, name, ext, is_image, original_path, original_name}]
        self.left_slots = []  # 待整理区
        self.right_slots = []  # 已编号区
        self.temp_dir = os.path.join(os.path.expanduser("~"), ".file_renamer_temp")
        self.load_config()

    def load_config(self):
        """加载配置"""
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
        """保存配置"""
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({'last_dir': self.last_dir}, f)

    def is_image_file(self, filename):
        """判断是否为图片文件"""
        image_ext = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.ico'}
        return Path(filename).suffix.lower() in image_ext

    def get_file_ext(self, filename):
        """获取文件扩展名（大写）"""
        ext = Path(filename).suffix
        return ext[1:].upper() if ext else "?"

    def extract_number_prefix(self, filename):
        """提取文件名开头的数字编号"""
        import re
        match = re.match(r'^(\d+)', filename)
        if match:
            return int(match.group(1))
        return None

    def remove_number_prefix(self, filename):
        """去掉文件名开头的数字编号"""
        import re
        return re.sub(r'^\d+', '', filename)

    def choose_files(self):
        """选择多个文件"""
        result = webview.windows[0].create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True)
        if result and len(result) > 0:
            # 创建临时目录用于存放副本（保留原文件）
            os.makedirs(self.temp_dir, exist_ok=True)
            
            # 清空临时目录
            for f in os.listdir(self.temp_dir):
                try:
                    os.remove(os.path.join(self.temp_dir, f))
                except:
                    pass

            # 解析每个文件
            parsed_files = []
            for file_path in result:
                original_name = os.path.basename(file_path)
                number = self.extract_number_prefix(original_name)
                clean_name = self.remove_number_prefix(original_name)
                
                # 复制到临时目录
                temp_path = os.path.join(self.temp_dir, original_name)
                shutil.copy2(file_path, temp_path)
                
                parsed_files.append({
                    "original_path": file_path,
                    "temp_path": temp_path,
                    "original_name": original_name,
                    "clean_name": clean_name,
                    "number": number,
                    "ext": self.get_file_ext(original_name),
                    "is_image": self.is_image_file(original_name)
                })

            # 排序：有编号的按编号排，无编号的放后面
            with_number = [f for f in parsed_files if f["number"] is not None]
            without_number = [f for f in parsed_files if f["number"] is None]
            with_number.sort(key=lambda x: x["number"])

            sorted_files = with_number + without_number

            # 构建左侧槽位
            self.left_slots = []
            # 动态扩充右侧容量以支持无限制上传，至少预留200位，或者是文件总量的2倍
            slot_count = max(200, len(sorted_files) * 2)
            self.right_slots = [None] * slot_count  

            for idx, item in enumerate(sorted_files):
                self.left_slots.append({
                    "id": idx,
                    "display_name": item["clean_name"],
                    "original_name": item["clean_name"],
                    "original_number": item["number"],
                    "ext": item["ext"],
                    "is_image": item["is_image"],
                    "temp_path": item["temp_path"],
                    "original_path": item["original_path"]
                })

            # 保存文件列表供后续使用
            self.files = self.left_slots

            return {"success": True, "count": len(self.left_slots), "files": [f["display_name"] for f in self.left_slots]}

        return None

    def get_slots_data(self):
        """获取左右区域的完整数据"""
        left_data = []
        for slot in self.left_slots:
            if slot is None:
                left_data.append(None)
            else:
                left_data.append({
                    "id": slot["id"],
                    "display_name": slot["display_name"],
                    "original_number": slot.get("original_number"),
                    "ext": slot["ext"],
                    "is_image": slot["is_image"],
                    "temp_path": slot["temp_path"]
                })

        right_data = []
        for slot in self.right_slots:
            if slot is None:
                right_data.append(None)
            else:
                right_data.append({
                    "id": slot["id"],
                    "display_name": slot["display_name"],
                    "original_number": slot.get("original_number"),
                    "ext": slot["ext"],
                    "is_image": slot["is_image"],
                    "temp_path": slot["temp_path"],
                    "original_path": slot["original_path"]
                })

        left_count = len([s for s in self.left_slots if s is not None])
        right_count = len([s for s in self.right_slots if s is not None])

        return {
            "left": left_data,
            "right": right_data,
            "left_count": left_count,
            "right_count": right_count,
            "max_left": len(self.left_slots),
            "max_right": len(self.right_slots)
        }

    def get_image_base64(self, filepath):
        """提供安全的本地图片 Base64 预览（不锁死文件）"""
        try:
            with open(filepath, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception:
            return ""

    def move_to_right(self, left_index, slot_index):
        """将左侧文件移动到右侧指定位置（按槽位编号重命名原文件）"""
        if left_index < 0 or left_index >= len(self.left_slots):
            return {"error": "无效的左侧索引"}

        item = self.left_slots[left_index]
        if item is None:
            return {"error": "该位置没有文件"}

        if slot_index < 0 or slot_index >= len(self.right_slots):
            return {"error": "无效的右侧索引"}

        if self.right_slots[slot_index] is not None:
            return {"error": f"右侧第 {slot_index + 1} 位已有文件"}

        # 新文件名 = 槽位编号 + 原始名称（编号不带补零）
        new_number = slot_index + 1
        new_name = f"{new_number}{item['original_name']}"

        # 获取原文件路径
        original_path = item["original_path"]
        if not original_path or not os.path.exists(original_path):
            return {"error": f"原文件不存在: {original_path}"}

        dir_path = os.path.dirname(original_path)
        new_path = os.path.join(dir_path, new_name)

        try:
            # 如果目标文件名已存在，自动添加后缀
            counter = 1
            final_path = new_path
            while os.path.exists(final_path):
                name_without_ext = os.path.splitext(f"{new_number}{item['original_name']}")[0]
                ext = os.path.splitext(item['original_name'])[1]
                final_name = f"{name_without_ext}_{counter}{ext}"
                final_path = os.path.join(dir_path, final_name)
                counter += 1

            # 重命名原文件
            os.rename(original_path, final_path)

            # 更新内存中的数据
            item["display_name"] = os.path.basename(final_path)
            item["original_path"] = final_path
            item["new_number"] = new_number
            item["renamed"] = True

            self.right_slots[slot_index] = item
            self.left_slots[left_index] = None

            return {"success": True, "new_name": os.path.basename(final_path), "slot": new_number}

        except Exception as e:
            return {"error": f"重命名失败: {str(e)}"}

    def move_to_left(self, right_index, target_left_index=None):
        """将右侧文件移回左侧（恢复原文件名）"""
        if right_index < 0 or right_index >= len(self.right_slots):
            return {"error": "无效的右侧索引"}

        item = self.right_slots[right_index]
        if item is None:
            return {"error": "该位置没有文件"}

        # 恢复原始文件名
        original_name = item["original_name"]
        current_path = item["original_path"]
        dir_path = os.path.dirname(current_path)
        new_path = os.path.join(dir_path, original_name)

        try:
            # 如果原文件名已存在，添加后缀
            counter = 1
            final_path = new_path
            while os.path.exists(final_path) and final_path != current_path:
                name_without_ext = os.path.splitext(original_name)[0]
                ext = os.path.splitext(original_name)[1]
                final_name = f"{name_without_ext}_恢复{counter}{ext}"
                final_path = os.path.join(dir_path, final_name)
                counter += 1

            os.rename(current_path, final_path)

            # 更新内存
            item["display_name"] = os.path.basename(final_path)
            item["original_path"] = final_path
            item["renamed"] = False
            if "new_number" in item:
                del item["new_number"]

            self.right_slots[right_index] = None

            # 找到左侧空位
            if target_left_index is not None and target_left_index < len(self.left_slots) and self.left_slots[target_left_index] is None:
                self.left_slots[target_left_index] = item
            else:
                empty_index = next((i for i, s in enumerate(self.left_slots) if s is None), None)
                if empty_index is not None:
                    self.left_slots[empty_index] = item
                else:
                    self.left_slots.append(item)

            return {"success": True, "restored_name": os.path.basename(final_path)}

        except Exception as e:
            return {"error": f"恢复失败: {str(e)}"}

    def swap_right_items(self, from_index, to_index):
        """交换右侧两个文件的位置（同时重命名）"""
        if from_index == to_index:
            return {"error": "相同位置无需交换"}

        if from_index < 0 or from_index >= len(self.right_slots) or to_index < 0 or to_index >= len(self.right_slots):
            return {"error": "无效的索引"}

        item_from = self.right_slots[from_index]
        item_to = self.right_slots[to_index]

        if item_from is None:
            return {"error": "源位置没有文件"}

        # 交换槽位
        self.right_slots[from_index] = item_to
        self.right_slots[to_index] = item_from

        # 重命名两个文件
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

        return {"success": True, "from_slot": from_index + 1, "to_slot": to_index + 1}

    def clear_all(self):
        """清空所有（将所有右侧文件恢复到左侧）"""
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
        """清空工具面板内所有图片，但不删除本地图片"""
        self.files = []
        self.left_slots = []
        self.right_slots = [None] * 200
        self.cleanup_temp()
        os.makedirs(self.temp_dir, exist_ok=True)
        return {"success": True}

    def cleanup_temp(self):
        """清理临时目录"""
        try:
            if os.path.exists(self.temp_dir):
                for f in os.listdir(self.temp_dir):
                    try:
                        os.remove(os.path.join(self.temp_dir, f))
                    except:
                        pass
        except:
            pass


# ==================== HTML 前端代码 ====================
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>文件编号工具 - 直接重命名原文件</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f0f2f5;
            height: 100vh;
            overflow: hidden;
        }

        .topbar {
            background: white;
            padding: 12px 20px;
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            align-items: center;
            border-bottom: 1px solid #e0e0e0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }

        button {
            padding: 8px 16px;
            cursor: pointer;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s;
        }

        .btn-primary {
            background: #4caf50;
            color: white;
        }
        .btn-primary:hover {
            background: #45a049;
        }

        .btn-secondary {
            background: #2196f3;
            color: white;
        }
        .btn-secondary:hover {
            background: #0b7dda;
        }

        .btn-danger {
            background: #f44336;
            color: white;
        }
        .btn-danger:hover {
            background: #da190b;
        }

        .btn-warning {
            background: #ff9800;
            color: white;
        }
        .btn-warning:hover {
            background: #e68a00;
        }

        .file-info {
            font-size: 13px;
            color: #666;
            margin-left: 10px;
            padding: 5px 12px;
            background: #f5f5f5;
            border-radius: 20px;
        }

        .stats {
            font-size: 13px;
            color: #666;
            margin-left: auto;
            font-weight: 500;
        }

        .main {
            display: flex;
            gap: 20px;
            padding: 20px;
            height: calc(100vh - 60px);
            overflow: hidden;
        }

        .left-panel, .right-panel {
            display: flex;
            flex-direction: column;
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
        }

        .left-panel {
            width: 45%;
        }

        .right-panel {
            width: 55%;
        }

        .panel-header {
            padding: 12px 16px;
            background: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
            font-weight: 600;
            font-size: 15px;
        }

        .panel-header span {
            color: #4caf50;
        }

        .grid-container {
            flex: 1;
            overflow-y: auto;
            padding: 16px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
            gap: 12px;
        }

        .slot-card {
            aspect-ratio: 1 / 1.2;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-start;
            overflow: hidden;
            cursor: pointer;
            transition: all 0.2s;
            background: #fafafa;
            position: relative;
        }

        .slot-card.empty {
            background: #f5f5f5;
            border-style: dashed;
            cursor: default;
        }

        .slot-card.left-filled {
            border-color: #ff9800;
            background: #fff8e1;
        }

        .slot-card.right-filled {
            border-color: #4caf50;
            background: #e8f5e9;
        }

        .slot-card:hover:not(.empty) {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }

        .slot-card.dragging {
            opacity: 0.5;
        }

        .slot-card.drag-over {
            border-color: #2196f3;
            background: #e3f2fd;
        }

        .preview-area {
            width: 100%;
            height: 70px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #e0e0e0;
            margin-bottom: 8px;
            overflow: hidden;
        }

        .preview-img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        .preview-file {
            font-size: 18px;
            font-weight: bold;
            color: #666;
            background: #e0e0e0;
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            text-transform: uppercase;
            word-break: break-all;
            padding: 4px;
            text-align: center;
        }

        .file-name {
            font-size: 11px;
            text-align: center;
            width: 100%;
            padding: 0 4px;
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
            color: #333;
        }

        .slot-number {
            position: absolute;
            top: 4px;
            left: 8px;
            font-size: 16px;
            font-weight: bold;
            color: rgba(0,0,0,0.3);
            pointer-events: none;
            z-index: 10;
            background: rgba(255,255,255,0.7);
            padding: 0 4px;
            border-radius: 4px;
        }

        .right-filled .slot-number {
            color: rgba(76, 175, 80, 0.9);
            background: rgba(232, 245, 233, 0.8);
        }

        .toast {
            position: fixed;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 14px;
            z-index: 1000;
            animation: fadeOut 2s ease forwards;
        }

        .toast.error {
            background: rgba(244, 67, 54, 0.9);
        }

        @keyframes fadeOut {
            0% { opacity: 1; }
            70% { opacity: 1; }
            100% { opacity: 0; visibility: hidden; }
        }
    </style>
</head>
<body>

<div class="topbar">
    <button class="btn-primary" onclick="selectFiles()">📁 选择文件</button>
    <button class="btn-secondary" onclick="refreshData()">🔄 刷新</button>
    <button class="btn-warning" onclick="clearAll()">🗑️ 全部移回左侧</button>
    <button class="btn-danger" onclick="resetWorkspace()">🧹 清空列表(不删本地)</button>
    <div class="file-info" id="fileInfo">未选择文件</div>
    <div class="stats" id="stats">待整理 0 | 已编号 0</div>
</div>

<div class="main">
    <div class="left-panel">
        <div class="panel-header">
            📦 待整理区 <span id="leftCount">0</span>
            <span style="font-size:12px; margin-left:10px; color:#888;">💡 点击卡片移到右侧</span>
        </div>
        <div class="grid-container">
            <div class="grid" id="leftGrid"></div>
        </div>
    </div>

    <div class="right-panel">
        <div class="panel-header">
            ✅ 已编号区 <span id="rightCount">0</span>
            <span style="font-size:12px; margin-left:10px; color:#888;">💡 拖拽卡片调整顺序 | 点击移回左侧</span>
        </div>
        <div class="grid-container">
            <div class="grid" id="rightGrid"></div>
        </div>
    </div>
</div>

<script>
    let pyApi = null;
    let currentData = { left: [], right: [], left_count: 0, right_count: 0 };
    let dragSource = null;
    
    // 图片缓存及队列系统 (保障性能、防卡顿)
    let imageQueue = [];
    let isProcessingQueue = false;
    const imageCache = {};

    window.addEventListener('pywebviewready', function() {
        pyApi = window.pywebview.api;
        console.log('pywebview ready');
    });

    function showToast(message, isError = false) {
        const existing = document.querySelector('.toast');
        if (existing) existing.remove();

        const toast = document.createElement('div');
        toast.className = 'toast' + (isError ? ' error' : '');
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            if (toast && toast.parentNode) toast.remove();
        }, 2000);
    }

    async function selectFiles() {
        if (!pyApi) {
            showToast('正在初始化，请稍后...', true);
            return;
        }

        try {
            const result = await pyApi.choose_files();
            if (result && result.success) {
                showToast(`已导入 ${result.count} 个文件`);
                await refreshData();
            }
        } catch (e) {
            showToast('选择文件失败: ' + e.message, true);
        }
    }

    async function refreshData() {
        if (!pyApi) return;

        try {
            const data = await pyApi.get_slots_data();
            currentData = data;
            document.getElementById('leftCount').innerText = data.left_count;
            document.getElementById('rightCount').innerText = data.right_count;
            document.getElementById('stats').innerHTML = `📦 待整理 ${data.left_count} | ✅ 已编号 ${data.right_count}`;

            if (data.left_count > 0 || data.right_count > 0) {
                document.getElementById('fileInfo').innerHTML = `📄 已导入 ${data.left_count + data.right_count} 个文件`;
            } else {
                document.getElementById('fileInfo').innerHTML = `未选择文件`;
            }

            renderLeftGrid(data.left);
            renderRightGrid(data.right);
            
            // 触发图片异步加载
            triggerImageLoads();
        } catch (e) {
            console.error('刷新失败:', e);
            showToast('刷新失败: ' + e.message, true);
        }
    }

    function renderLeftGrid(slots) {
        const grid = document.getElementById('leftGrid');
        grid.innerHTML = '';

        for (let i = 0; i < slots.length; i++) {
            const slot = slots[i];
            const card = document.createElement('div');
            card.className = 'slot-card';
            card.setAttribute('data-index', i);
            card.setAttribute('data-type', 'left');

            if (!slot) {
                card.classList.add('empty');
                card.innerHTML = `<div class="slot-number">${i + 1}</div>`;
            } else {
                card.classList.add('left-filled');
                card.innerHTML = `
                    <div class="slot-number">${slot.original_number !== null ? slot.original_number : ''}</div>
                    <div class="preview-area">
                        ${getPreviewHtml(slot)}
                    </div>
                    <div class="file-name" title="${escapeHtml(slot.display_name)}">${escapeHtml(truncateName(slot.display_name))}</div>
                `;

                card.onclick = (e) => {
                    e.stopPropagation();
                    moveToRight(i);
                };
            }

            if (slot) {
                card.draggable = true;
                card.ondragstart = (e) => {
                    dragSource = { type: 'left', index: i };
                    e.dataTransfer.setData('text/plain', JSON.stringify(dragSource));
                    card.classList.add('dragging');
                };
                card.ondragend = (e) => {
                    card.classList.remove('dragging');
                    removeDragOverHighlight();
                };
            }

            grid.appendChild(card);
        }
    }

    function renderRightGrid(slots) {
        const grid = document.getElementById('rightGrid');
        grid.innerHTML = '';

        for (let i = 0; i < slots.length; i++) {
            const slot = slots[i];
            const card = document.createElement('div');
            card.className = 'slot-card';
            card.setAttribute('data-index', i);
            card.setAttribute('data-type', 'right');

            if (!slot) {
                card.classList.add('empty');
                card.innerHTML = `<div class="slot-number">${i + 1}</div>`;
            } else {
                card.classList.add('right-filled');
                card.innerHTML = `
                    <div class="slot-number">${i + 1}</div>
                    <div class="preview-area">
                        ${getPreviewHtml(slot)}
                    </div>
                    <div class="file-name" title="${escapeHtml(slot.display_name)}">${escapeHtml(truncateName(slot.display_name))}</div>
                `;

                card.onclick = (e) => {
                    e.stopPropagation();
                    moveToLeft(i);
                };
            }

            if (slot) {
                card.draggable = true;
                card.ondragstart = (e) => {
                    dragSource = { type: 'right', index: i };
                    e.dataTransfer.setData('text/plain', JSON.stringify(dragSource));
                    card.classList.add('dragging');
                };
                card.ondragend = (e) => {
                    card.classList.remove('dragging');
                    removeDragOverHighlight();
                };
                card.ondragover = (e) => {
                    e.preventDefault();
                    if (slot) {
                        card.classList.add('drag-over');
                    }
                };
                card.ondragleave = () => {
                    card.classList.remove('drag-over');
                };
                card.ondrop = async (e) => {
                    e.preventDefault();
                    card.classList.remove('drag-over');
                    if (!dragSource) return;

                    removeDragOverHighlight();

                    if (dragSource.type === 'right') {
                        const fromIndex = dragSource.index;
                        const toIndex = i;
                        if (fromIndex !== toIndex) {
                            await swapRightItems(fromIndex, toIndex);
                        }
                    } else if (dragSource.type === 'left' && slot) {
                        const fromIndex = dragSource.index;
                        await moveToRight(fromIndex, i);
                    }

                    dragSource = null;
                    await refreshData();
                };
            }

            grid.appendChild(card);
        }
    }

    // 返回图片预览的占位符或文件扩展名
    function getPreviewHtml(slot) {
        if (slot.is_image) {
            return `<div class="preview-img-container" data-path="${escapeHtml(slot.temp_path)}" data-ext="${escapeHtml(slot.ext)}" style="width:100%; height:100%; display:flex; align-items:center; justify-content:center; font-size:24px; color:#999;">⏳</div>`;
        } else {
            return `<div class="preview-file">${escapeHtml(slot.ext) || 'FILE'}</div>`;
        }
    }
    
    // 图片加载排队
    function queueImageLoad(container, path, ext) {
        container.setAttribute('data-loading', 'true');
        imageQueue.push({container, path, ext});
        if (!isProcessingQueue) {
            processImageQueue();
        }
    }

    // 异步分批处理图片加载，避免阻塞进程
    async function processImageQueue() {
        isProcessingQueue = true;
        while (imageQueue.length > 0) {
            const batch = imageQueue.splice(0, 5);
            await Promise.all(batch.map(async item => {
                try {
                    if (imageCache[item.path]) {
                        item.container.innerHTML = `<img src="data:image/jpeg;base64,${imageCache[item.path]}" class="preview-img">`;
                        return;
                    }
                    const b64 = await pyApi.get_image_base64(item.path);
                    if (b64) {
                        imageCache[item.path] = b64;
                        item.container.innerHTML = `<img src="data:image/jpeg;base64,${b64}" class="preview-img">`;
                    } else {
                        // 遇到无法预览或错误的文件，显示格式扩展名
                        item.container.innerHTML = `<div class="preview-file">${item.ext || 'FILE'}</div>`;
                    }
                } catch (e) {
                    item.container.innerHTML = `<div class="preview-file">${item.ext || 'FILE'}</div>`;
                }
            }));
        }
        isProcessingQueue = false;
    }

    // 触发图片加载事件
    function triggerImageLoads() {
        const containers = document.querySelectorAll('.preview-img-container:not([data-loading])');
        containers.forEach(container => {
            queueImageLoad(container, container.getAttribute('data-path'), container.getAttribute('data-ext'));
        });
    }

    async function moveToRight(leftIndex, targetSlot = null) {
        if (!pyApi) return;

        let slotIndex = targetSlot;
        if (slotIndex === null) {
            for (let i = 0; i < currentData.right.length; i++) {
                if (currentData.right[i] === null) {
                    slotIndex = i;
                    break;
                }
            }
            if (slotIndex === null) {
                showToast('右侧已满', true);
                return;
            }
        }

        try {
            const result = await pyApi.move_to_right(leftIndex, slotIndex);
            if (result.error) {
                showToast(result.error, true);
            } else {
                showToast(`✅ 已编号为 ${result.slot}: ${result.new_name}`);
                await refreshData();
            }
        } catch (e) {
            showToast('操作失败: ' + e.message, true);
        }
    }

    async function moveToLeft(rightIndex) {
        if (!pyApi) return;

        try {
            const result = await pyApi.move_to_left(rightIndex, null);
            if (result.error) {
                showToast(result.error, true);
            } else {
                showToast(`↩️ 已移回左侧: ${result.restored_name}`);
                await refreshData();
            }
        } catch (e) {
            showToast('操作失败: ' + e.message, true);
        }
    }

    async function swapRightItems(fromIndex, toIndex) {
        if (!pyApi) return;

        try {
            const result = await pyApi.swap_right_items(fromIndex, toIndex);
            if (result.error) {
                showToast(result.error, true);
            } else {
                showToast(`🔄 已交换位置: ${result.from_slot} ↔ ${result.to_slot}`);
                await refreshData();
            }
        } catch (e) {
            showToast('交换失败: ' + e.message, true);
        }
    }

    async function clearAll() {
        if (!confirm('确定要将所有已编号的文件移回左侧吗？文件会恢复原来的名称。')) return;

        if (!pyApi) return;

        try {
            const result = await pyApi.clear_all();
            if (result.error) {
                showToast(result.error, true);
            } else {
                showToast('✅ 已全部移回左侧');
                await refreshData();
            }
        } catch (e) {
            showToast('操作失败: ' + e.message, true);
        }
    }
    
    // 清理列表 (不删本地文件)
    async function resetWorkspace() {
        if (!confirm('确定要清空列表吗？（注：绝不会删除您的本地原文件）')) return;
        if (!pyApi) return;

        try {
            const result = await pyApi.reset_workspace();
            if (result.success) {
                showToast('✅ 列表已清空');
                await refreshData();
            } else {
                showToast('操作失败: 未知错误', true);
            }
        } catch (e) {
            showToast('操作失败: ' + e.message, true);
        }
    }

    function removeDragOverHighlight() {
        document.querySelectorAll('.drag-over').forEach(el => {
            el.classList.remove('drag-over');
        });
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function truncateName(name, maxLen = 18) {
        if (!name) return '';
        if (name.length <= maxLen) return name;
        return name.substring(0, maxLen - 3) + '...';
    }
</script>
</body>
</html>
"""


if __name__ == '__main__':
    api = Api()
    window = webview.create_window(
        '文件编号工具',
        html=HTML_CONTENT,
        js_api=api,
        width=1400,
        height=800,
        text_select=True
    )
    webview.start()
    # 程序关闭时清理临时文件
    api.cleanup_temp()