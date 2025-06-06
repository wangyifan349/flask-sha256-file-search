import os
import hashlib
from flask import Flask, request, abort, send_file, render_template_string
app = Flask(__name__)
# -------------------------------------------------------------------
# 配置项
# -------------------------------------------------------------------
# 启动后要扫描的根目录，请根据实际情况修改
ROOT_DIR = '/path/to/your/scan/directory'
# 哈希到文件路径的全局映射表
hash_to_path = {}
# -------------------------------------------------------------------
# 计算 SHA-256 哈希
# -------------------------------------------------------------------
def compute_sha256(file_path, chunk_size=8192):
    """
    计算给定文件的 SHA-256 值。
    分块读取以节省内存，对大文件也适用。
    """
    hasher = hashlib.sha256()
    file_obj = open(file_path, 'rb')
    while True:
        chunk = file_obj.read(chunk_size)
        if not chunk:
            break
        hasher.update(chunk)
    file_obj.close()
    return hasher.hexdigest()
# -------------------------------------------------------------------
# 构建文件索引
# -------------------------------------------------------------------
def build_index(root_dir):
    """
    遍历 root_dir 下的所有文件，计算它们的 SHA-256，
    并将结果存入全局字典 hash_to_path 中。
    """
    # os.walk 返回三元组 (当前目录路径, 子目录列表, 文件名列表)
    for dirpath, subdirs, filenames in os.walk(root_dir):
        # 依次处理文件列表
        for filename in filenames:
            # 拼接出文件的绝对路径
            full_path = os.path.join(dirpath, filename)
            
            try:
                # 计算 SHA-256
                sha_value = compute_sha256(full_path)
            except Exception as e:
                # 读取或计算失败时记录日志，跳过该文件
                app.logger.error(f"无法处理文件 {full_path}：{e}")
                continue
            
            # 如果哈希已存在，则报告冲突（但仍保留首个映射）
            if sha_value in hash_to_path:
                existing = hash_to_path[sha_value]
                app.logger.warning(f"哈希冲突：{sha_value} 对应 {existing} 和 {full_path}")
            else:
                # 新增映射
                hash_to_path[sha_value] = full_path
# -------------------------------------------------------------------
# Flask 启动前：构建索引
# -------------------------------------------------------------------
@app.before_first_request
def initialize_index():
    app.logger.info(f"开始扫描目录：{ROOT_DIR}")
    build_index(ROOT_DIR)
    total = len(hash_to_path)
    app.logger.info(f"扫描完成，共索引文件数：{total}")
# -------------------------------------------------------------------
# HTML 模板（内嵌 CSS）
# -------------------------------------------------------------------
PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>文件 SHA-256 查找</title>
  <style>
    body { font-family: sans-serif; background: #f4f7f8; color: #333; }
    .container { width: 90%; max-width: 600px; margin: 40px auto;
                 background: #fff; padding: 30px; border-radius: 8px;
                 box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
    h1 { margin-top: 0; }
    form { margin-bottom: 20px; }
    input[type=text] { width: 100%; padding: 8px; font-size: 14px;
                       border: 1px solid #ccc; border-radius: 4px; }
    input[type=submit] { margin-top: 8px; padding: 8px 16px; font-size: 14px;
                         background: #28a745; color: #fff; border: none;
                         border-radius: 4px; cursor: pointer; }
    input[type=submit]:hover { background: #218838; }
    .result { padding: 12px; background: #e9ecef; border-radius: 4px; }
    .error { color: #c00; }
    a { color: #007bff; text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="container">
    <h1>文件 SHA-256 查找</h1>
    <form method="get" action="/">
      <label for="hash">输入 SHA-256 哈希：</label>
      <input type="text" id="hash" name="hash"
             placeholder="例如：e3b0c44298fc1c149af..." required
             value="{{ hash_value|default('') }}">
      <input type="submit" value="查找">
    </form>

    {% if hash_value is defined %}
      {% if file_path %}
        <div class="result">
          找到文件：<strong>{{ file_name }}</strong><br>
          <a href="/download?hash={{ hash_value }}">点击下载</a>
        </div>
      {% else %}
        <div class="result error">
          未找到对应的文件。
        </div>
      {% endif %}
    {% endif %}
  </div>
</body>
</html>
"""
# -------------------------------------------------------------------
# 路由：主页（查找界面）
# -------------------------------------------------------------------
@app.route('/', methods=['GET'])
def index():
    # 从 URL 参数中获取 hash
    hash_value = request.args.get('hash', '').strip().lower()
    # 根据 hash_value 查找映射表
    if hash_value == '':
        # 未提交时，file_path 保持 None
        file_path = None
    else:
        file_path = hash_to_path.get(hash_value)
    
    # 提取文件名用于展示
    if file_path:
        file_name = os.path.basename(file_path)
    else:
        file_name = None
    # 渲染页面
    return render_template_string(
        PAGE_TEMPLATE,
        hash_value=hash_value,
        file_path=file_path,
        file_name=file_name
    )
# -------------------------------------------------------------------
# 路由：下载文件
# -------------------------------------------------------------------
@app.route('/download', methods=['GET'])
def download_file():
    # 获取并验证参数
    hash_value = request.args.get('hash', '').strip().lower()
    if hash_value == '':
        abort(400, "缺少参数：hash")
    # 查找对应路径并发送文件
    file_path = hash_to_path.get(hash_value)
    if not file_path or not os.path.isfile(file_path):
        abort(404, "未找到对应的文件")
    # 以附件形式发送
    return send_file(file_path, as_attachment=True)
# -------------------------------------------------------------------
# 启动应用
# -------------------------------------------------------------------
if __name__ == '__main__':
    # 开发时使用 Flask 自带服务器；生产环境请换成 gunicorn 或 uWSGI
    app.run(host='0.0.0.0', port=5000, debug=True)
