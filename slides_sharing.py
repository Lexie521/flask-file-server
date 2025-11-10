from flask import Flask, request, jsonify, send_from_directory, send_file, render_template_string
from werkzeug.utils import secure_filename
from github import Github
import os, zipfile, io, datetime
import re

# ------------------------------
# 基本配置
# ------------------------------
app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_ROOT = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_ROOT, exist_ok=True)

# GitHub 同步配置（环境变量中设置）

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")          # 在 Render 面板里设置
GITHUB_REPO  = os.getenv("GITHUB_REPO")           # 形如  Lexie521/flask-file-server
# ------------------------------
# 前端 HTML 模板
# ------------------------------
HTML_PAGE = """
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>组会PPT管理系统</title>
<style>
body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
.container { background: white; padding: 20px; border-radius: 12px; max-width: 820px; margin: auto; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
h2 { color: #2a4d8f; }
button { margin: 3px; padding: 6px 12px; border: none; border-radius: 6px; background: #2a4d8f; color: white; cursor: pointer; }
button:hover { background: #1e3571; }
.icon-btn { background: none; border: none; cursor: pointer; color: #2a4d8f; font-size: 16px; margin-left: 4px; }
.icon-btn:hover { color: #1d3b6b; }
input[type=text] { padding: 6px; border-radius: 6px; border: 1px solid #ccc; }
a { text-decoration: none; color: #2a4d8f; }
a:hover { text-decoration: underline; }
.file-list li { margin: 6px 0; }
.new-folder { background: #fafafa; padding: 8px; border-radius: 8px; border: 1px solid #eee; margin-top: 10px; margin-bottom: 10px; }
.path-bar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
</style>
</head>
<body>
<div class="container">
    <h2>📂 组会PPT管理系统</h2>

    <div class="path-bar">
        <p>当前位置：<span id="currentPath">/</span></p>
        <button onclick="downloadAll()">📦 一键下载当前文件夹</button>
    </div>

    <button onclick="goBack()">⬅️ 返回上一级</button>

    <div class="new-folder">
        <b>📁 新建文件夹</b><br>
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
                        <button class="icon-btn" onclick="renameFolderPrompt('${f.name}')">✏️</button>
                        <button class="icon-btn" onclick="deleteFolder('${f.name}')">🗑️</button>
                    </li>`;
            } else {
                ul.innerHTML += `
                    <li>📄 <a href="/download?path=${encodeURIComponent(currentPath)}&name=${encodeURIComponent(f.name)}" target="_blank">${f.name}</a>
                        <button class="icon-btn" onclick="deleteFile('${f.name}')">🗑️</button>
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
    if (!newName || newName.trim() === "") return;
    const res = await fetch('/rename_folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: currentPath, old_name: name, new_name: newName.trim() })
    });
    alert(await res.text());
    loadFiles(currentPath);
}

function downloadAll() {
    const url = `/download_folder?path=${encodeURIComponent(currentPath)}`;
    window.location.href = url;
}

loadFiles();
</script>
</body>
</html>
"""

# ------------------------------
# 辅助函数
# ------------------------------
def safe_join(base, *paths):
    """防止路径穿越攻击"""
    final_path = os.path.abspath(os.path.join(base, *paths))
    if not final_path.startswith(base):
        raise ValueError("非法路径访问")
    return final_path

# ------------------------------
# 路由逻辑
# ------------------------------
@app.route("/")
def home():
    return render_template_string(HTML_PAGE)

@app.route("/files")
def list_files():
    rel_path = request.args.get("path", "").strip("/")
    folder_path = safe_join(UPLOAD_ROOT, rel_path)
    items = []
    if os.path.exists(folder_path):
        for entry in os.listdir(folder_path):
            full_path = os.path.join(folder_path, entry)
            info = {"name": entry}
            if os.path.isdir(full_path):
                info["type"] = "folder"
            else:
                info["type"] = "file"
            items.append(info)
    items.sort(key=lambda x: (x["type"] != "folder", x["name"].lower()))
    return jsonify({"current": rel_path, "items": items})

@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        f = request.files.get("file")
        if not f:
            return "未检测到上传文件，请重试", 400

        name = request.form.get("name", "unknown").strip()
        rel_path = request.form.get("path", "").strip("/")
        folder_path = os.path.join(UPLOAD_ROOT, rel_path)
        os.makedirs(folder_path, exist_ok=True)

        # ✅ 处理文件名（保留中文，但去掉非法符号）
        raw_filename = os.path.basename(f.filename or "")
        if not raw_filename:
            return "未检测到文件名", 400
        name_root, ext = os.path.splitext(raw_filename)
        safe_root = re.sub(r'[<>:"/\\|?*]', "_", name_root)
        filename = f"{name}_{safe_root}{ext}"

        save_path = os.path.join(folder_path, filename)
        f.save(save_path)
        print(f"✅ 文件已保存到本地: {save_path}")

        # ☁️ GitHub 同步逻辑
        if GITHUB_TOKEN and GITHUB_REPO:
            g = Github(GITHUB_TOKEN)
            repo = g.get_repo(GITHUB_REPO)
            github_path = os.path.join("uploads", rel_path, filename).replace("\\", "/")

            with open(save_path, "rb") as fp:
                content = fp.read()

            try:
                existing_file = repo.get_contents(github_path)
                repo.update_file(github_path, f"Update {filename}", content, existing_file.sha)
                print(f"✅ 已更新 GitHub 文件：{github_path}")
            except Exception as e:
                # 若文件不存在则新建
                repo.create_file(github_path, f"Add {filename}", content)
                print(f"✅ 已创建 GitHub 文件：{github_path}")

        return f"文件 {filename} 上传成功 ✅"

    except Exception as e:
        # 在 Render 日志中能看到详细报错
        print("❌ 上传失败：", e)
        return f"上传时发生错误：{str(e)}", 500

@app.route("/delete", methods=["DELETE"])
def delete_file():
    rel_path = request.args.get("path", "").strip("/")
    name = request.args.get("name", "")
    file_path = safe_join(UPLOAD_ROOT, rel_path, name)
    if os.path.exists(file_path):
        os.remove(file_path)
        return f"文件 {name} 已删除 ✅"
    return "文件不存在", 404

@app.route("/download")
def download_file():
    rel_path = request.args.get("path", "").strip("/")
    name = request.args.get("name", "")
    folder_path = safe_join(UPLOAD_ROOT, rel_path)
    return send_from_directory(folder_path, name, as_attachment=True)

@app.route("/create_folder", methods=["POST"])
def create_folder():
    data = request.get_json()
    rel_path = data.get("path", "").strip("/")
    name = data.get("folder", "").strip()
    if not name:
        return "文件夹名称不能为空", 400
    new_folder = safe_join(UPLOAD_ROOT, rel_path, name)
    os.makedirs(new_folder, exist_ok=True)
    return f"文件夹 {name} 已创建 ✅"

@app.route("/delete_folder", methods=["DELETE"])
def delete_folder():
    rel_path = request.args.get("path", "").strip("/")
    name = request.args.get("name", "")
    folder_path = safe_join(UPLOAD_ROOT, rel_path, name)
    if os.path.isdir(folder_path):
        try:
            os.rmdir(folder_path)
            return f"文件夹 {name} 已删除 ✅"
        except OSError:
            return f"文件夹 {name} 非空，无法删除 ⚠️"
    return "文件夹不存在", 404

@app.route("/rename_folder", methods=["POST"])
def rename_folder():
    data = request.get_json()
    rel_path = data.get("path", "").strip("/")
    old_name, new_name = data.get("old_name", "").strip(), data.get("new_name", "").strip()
    if not old_name or not new_name:
        return "名称不能为空", 400
    old_folder = safe_join(UPLOAD_ROOT, rel_path, old_name)
    new_folder = safe_join(UPLOAD_ROOT, rel_path, new_name)
    if not os.path.exists(old_folder):
        return f"文件夹 {old_name} 不存在", 404
    if os.path.exists(new_folder):
        return f"目标名称 {new_name} 已存在", 400
    os.rename(old_folder, new_folder)
    return f"文件夹 {old_name} 已重命名为 {new_name} ✅"

@app.route("/download_folder")
def download_folder():
    rel_path = request.args.get("path", "").strip("/")
    folder_path = safe_join(UPLOAD_ROOT, rel_path)
    if not os.path.exists(folder_path):
        return "文件夹不存在", 404
    zip_buffer = io.BytesIO()
    zip_name = (os.path.basename(folder_path) or "root") + ".zip"
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                fp = os.path.join(root, file)
                arc = os.path.relpath(fp, folder_path)
                zipf.write(fp, arc)
    zip_buffer.seek(0)
    return send_file(zip_buffer, mimetype="application/zip", as_attachment=True, download_name=zip_name)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)








