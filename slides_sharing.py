from flask import Flask, request, jsonify, send_from_directory, send_file, render_template_string
import os, zipfile, io, datetime

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_ROOT = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_ROOT, exist_ok=True)

# --- 网页模板 ---
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>组会PPT管理系统</title>
<style>
body { font-family: Arial; margin: 40px; background: #f5f5f5; }
.container { background: white; padding: 20px; border-radius: 12px; max-width: 800px; margin: auto; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
h2 { color: #2a4d8f; margin-bottom: 10px; }
.subtle-title { font-weight: normal; font-size: 16px; color: #666; margin-bottom: 6px; display: flex; align-items: center; }
.subtle-title span { margin-left: 6px; color: #2a4d8f; font-weight: bold; }
button { margin: 3px; padding: 6px 10px; border: none; border-radius: 6px; background: #2a4d8f; color: white; cursor: pointer; }
button:hover { background: #1d3b6b; }
.icon-btn { background: none; border: none; cursor: pointer; color: #2a4d8f; font-size: 16px; margin-left: 4px; }
.icon-btn:hover { color: #1d3b6b; }
.file-list li { margin: 6px 0; }
input[type=text] { padding: 6px; border-radius: 6px; border: 1px solid #ccc; }
a { text-decoration: none; color: #2a4d8f; }
a:hover { text-decoration: underline; }
.new-folder { margin-top: 10px; margin-bottom: 10px; padding: 6px 10px; background: #fafafa; border-radius: 8px; border: 1px solid #eee; }
.path-bar { display: flex; align-items: center; justify-content: space-between; }
</style>
</head>
<body>
<div class="container">
    <h2>📂 组会PPT管理系统</h2>

    <div class="path-bar">
        <p>当前位置：<span id="currentPath">/</span></p>
        <button onclick="downloadAll()">📦 一键下载此文件夹</button>
    </div>

    <button onclick="goBack()">⬅️ 返回上一级</button>

    <div class="new-folder">
        <div class="subtle-title">📁 <span>新建文件夹</span></div>
        <input type="text" id="folderName" placeholder="请输入文件夹名称">
        <button onclick="createFolder()">新建</button>
    </div>

    <h3>📄 当前目录内容</h3>
    <ul id="fileList" class="file-list"></ul>

    <h3>⬆️ 上传文件</h3>
    <input type="file" id="uploadInput">
    <input type="text" id="uploaderName" placeholder="请输入姓名">
    <button onclick="uploadFile()">上传</button>
</div>

<script>
let currentPath = "";

async function loadFiles(path="") {
    const res = await fetch('/files?path=' + encodeURIComponent(path));
    const data = await res.json();
    currentPath = data.current;
    document.getElementById('currentPath').innerText = '/' + (currentPath || '');
    const ul = document.getElementById('fileList');
    ul.innerHTML = '';
    if (data.items.length === 0) {
        ul.innerHTML = '<li>暂无文件</li>';
    } else {
        data.items.forEach(f => {
            if (f.type === 'folder') {
                ul.innerHTML += `
                    <li>📁 <a href="#" onclick="enterFolder('${f.name}')">${f.name}</a>
                        <button class="icon-btn" title="重命名" onclick="renameFolderPrompt('${f.name}')">✏️</button>
                        <button class="icon-btn" title="删除" onclick="deleteFolder('${f.name}')">🗑️</button>
                    </li>`;
            } else {
                ul.innerHTML += `
                    <li>📄 <a href="/download?path=${encodeURIComponent(currentPath)}&name=${encodeURIComponent(f.name)}" target="_blank">${f.name}</a>
                        <button class="icon-btn" title="删除" onclick="deleteFile('${f.name}')">🗑️</button>
                    </li>`;
            }
        });
    }
}

function enterFolder(name) {
    const newPath = currentPath ? currentPath + '/' + name : name;
    loadFiles(newPath);
}

function goBack() {
    if (!currentPath) return;
    const parts = currentPath.split('/');
    parts.pop();
    const newPath = parts.join('/');
    loadFiles(newPath);
}

async function uploadFile() {
    const fileInput = document.getElementById('uploadInput');
    const nameInput = document.getElementById('uploaderName');
    if (!fileInput.files.length || !nameInput.value.trim()) {
        alert('请填写姓名并选择文件');
        return;
    }
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('name', nameInput.value.trim());
    formData.append('path', currentPath);
    const res = await fetch('/upload', { method: 'POST', body: formData });
    alert(await res.text());
    fileInput.value = '';
    nameInput.value = '';
    loadFiles(currentPath);
}

async function deleteFile(filename) {
    if (!confirm(`确定要删除 ${filename} 吗？`)) return;
    const res = await fetch(`/delete?path=${encodeURIComponent(currentPath)}&name=${encodeURIComponent(filename)}`, { method: 'DELETE' });
    alert(await res.text());
    loadFiles(currentPath);
}

async function createFolder() {
    const name = document.getElementById('folderName').value.trim();
    if (!name) { alert('请输入文件夹名称'); return; }
    const res = await fetch('/create_folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: currentPath, folder: name })
    });
    alert(await res.text());
    document.getElementById('folderName').value = '';
    loadFiles(currentPath);
}

async function deleteFolder(name) {
    if (!confirm(`确定要删除文件夹 ${name} 吗？`)) return;
    const res = await fetch(`/delete_folder?path=${encodeURIComponent(currentPath)}&name=${encodeURIComponent(name)}`, { method: 'DELETE' });
    alert(await res.text());
    loadFiles(currentPath);
}

async function renameFolderPrompt(name) {
    const newName = prompt("请输入新的文件夹名称：", name);
    if (!newName || newName.trim() === "") return alert("名称不能为空！");
    const res = await fetch('/rename_folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: currentPath, old_name: name, new_name: newName.trim() })
    });
    alert(await res.text());
    loadFiles(currentPath);
}

// 🆕 一键下载功能
function downloadAll() {
    const url = `/download_folder?path=${encodeURIComponent(currentPath)}`;
    window.location.href = url;
}

loadFiles();
</script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_PAGE)

@app.route('/files')
def list_files():
    rel_path = request.args.get('path', '').strip('/')
    folder_path = os.path.join(UPLOAD_ROOT, rel_path)
    if not os.path.exists(folder_path):
        return jsonify({'current': rel_path, 'items': []})
    items = []
    for entry in os.listdir(folder_path):
        full_path = os.path.join(folder_path, entry)
        if os.path.isdir(full_path):
            items.append({'name': entry, 'type': 'folder'})
        else:
            items.append({'name': entry, 'type': 'file'})
    items.sort(key=lambda x: (x['type'] != 'folder', x['name'].lower()))
    return jsonify({'current': rel_path, 'items': items})

@app.route('/upload', methods=['POST'])
def upload():
    f = request.files['file']
    name = request.form.get('name', 'unknown').strip()
    rel_path = request.form.get('path', '').strip('/')
    folder_path = os.path.join(UPLOAD_ROOT, rel_path)
    os.makedirs(folder_path, exist_ok=True)
    filename = f"{name}_{f.filename}"
    save_path = os.path.join(folder_path, filename)
    f.save(save_path)
    return f"文件 {filename} 上传成功（如有同名已覆盖）"

@app.route('/delete', methods=['DELETE'])
def delete_file():
    rel_path = request.args.get('path', '').strip('/')
    name = request.args.get('name', '')
    path = os.path.join(UPLOAD_ROOT, rel_path, name)
    if os.path.exists(path):
        os.remove(path)
        return f"文件 {name} 已删除"
    else:
        return "文件不存在", 404

@app.route('/download')
def download():
    rel_path = request.args.get('path', '').strip('/')
    name = request.args.get('name', '')
    folder_path = os.path.join(UPLOAD_ROOT, rel_path)
    return send_from_directory(folder_path, name, as_attachment=True)

@app.route('/create_folder', methods=['POST'])
def create_folder():
    data = request.get_json()
    rel_path = data.get('path', '').strip('/')
    folder_name = data.get('folder', '').strip()
    if not folder_name:
        return "文件夹名称不能为空", 400
    new_folder = os.path.join(UPLOAD_ROOT, rel_path, folder_name)
    if not os.path.exists(new_folder):
        os.makedirs(new_folder)
        return f"文件夹 {folder_name} 已创建 ✅"
    else:
        return f"文件夹 {folder_name} 已存在 ⚠️"

@app.route('/delete_folder', methods=['DELETE'])
def delete_folder():
    rel_path = request.args.get('path', '').strip('/')
    name = request.args.get('name', '')
    folder_path = os.path.join(UPLOAD_ROOT, rel_path, name)
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        try:
            os.rmdir(folder_path)
            return f"文件夹 {name} 已删除 ✅"
        except OSError:
            return f"文件夹 {name} 非空，无法删除 ⚠️"
    return "文件夹不存在", 404

@app.route('/rename_folder', methods=['POST'])
def rename_folder():
    data = request.get_json()
    rel_path = data.get('path', '').strip('/')
    old_name = data.get('old_name', '').strip()
    new_name = data.get('new_name', '').strip()
    if not old_name or not new_name:
        return "名称不能为空", 400

    old_folder = os.path.join(UPLOAD_ROOT, rel_path, old_name)
    new_folder = os.path.join(UPLOAD_ROOT, rel_path, new_name)

    if not os.path.exists(old_folder):
        return f"文件夹 {old_name} 不存在", 404
    if os.path.exists(new_folder):
        return f"目标名称 {new_name} 已存在", 400

    os.rename(old_folder, new_folder)
    return f"文件夹 {old_name} 已重命名为 {new_name} ✅"

# 🆕 一键下载功能
@app.route('/download_folder')
def download_folder():
    rel_path = request.args.get('path', '').strip('/')
    folder_path = os.path.join(UPLOAD_ROOT, rel_path)
    if not os.path.exists(folder_path):
        return "文件夹不存在", 404

    # 内存中创建 zip 文件
    zip_buffer = io.BytesIO()
    zip_name = (os.path.basename(folder_path) or "root") + ".zip"
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                zipf.write(file_path, arcname)
    zip_buffer.seek(0)
    return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name=zip_name)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
