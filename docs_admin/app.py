from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import sqlite3
from functools import wraps
import db

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SESSION_TYPE'] = 'filesystem'

DOCS_DIR = os.path.join(os.path.dirname(__file__), '../docs')


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('admin'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if db.verify_user(username, password):
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('admin'))
        return render_template('login.html', error='用户名或密码错误')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/admin')
@login_required
def admin():
    docs = []
    if os.path.exists(DOCS_DIR):
        for filename in os.listdir(DOCS_DIR):
            if filename.endswith('.html'):
                filepath = os.path.join(DOCS_DIR, filename)
                mtime = os.path.getmtime(filepath)
                docs.append({'filename': filename, 'mtime': mtime})
    docs.sort(key=lambda x: x['mtime'], reverse=True)
    return render_template('admin.html', docs=docs)


@app.route('/edit/<filename>')
@login_required
def edit(filename):
    filepath = os.path.join(DOCS_DIR, filename)
    if not os.path.exists(filepath):
        return redirect(url_for('admin'))
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    return render_template('edit.html', filename=filename, content=content)


@app.route('/save', methods=['POST'])
@login_required
def save():
    filename = request.form.get('filename')
    content = request.form.get('content', '')
    if not filename:
        return jsonify({'success': False, 'message': '文件名不能为空'})
    filepath = os.path.join(DOCS_DIR, filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'success': True, 'message': '保存成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/create', methods=['POST'])
@login_required
def create():
    filename = request.form.get('filename', '').strip()
    if not filename:
        return jsonify({'success': False, 'message': '文件名不能为空'})
    if not filename.endswith('.html'):
        filename = f'{filename}.html'
    filepath = os.path.join(DOCS_DIR, filename)
    if os.path.exists(filepath):
        return jsonify({'success': False, 'message': '文件已存在'})
    template = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{title}}</title>
    <link rel="stylesheet" href="./css/style.css">
</head>
<body>
    <nav class="navbar"></nav>
    <main>
        <h1>新文档</h1>
        <p>在这里写文档内容...</p>
    </main>
    <footer class="footer"></footer>
    <script src="./js/main.js"></script>
</body>
</html>'''.replace('{{title}}', filename.replace('.html', ''))
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(template)
    return jsonify({'success': True, 'filename': filename})


@app.route('/delete/<filename>')
@login_required
def delete(filename):
    filepath = os.path.join(DOCS_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    return redirect(url_for('admin'))


if __name__ == '__main__':
    db.init_db()
    if not db.user_exists('admin'):
        db.add_user('admin', 'admin123')
        print('默认管理员账号: admin / admin123')
    app.run(debug=True, host='0.0.0.0', port=5000)
