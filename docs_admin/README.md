# 文档管理后台

使用说明：

## 安装依赖
```bash
pip install -r requirements.txt
```

## 启动后台
```bash
python app.py
```

默认账号密码：admin / admin123

访问地址：http://localhost:5000

## 功能
- 登录认证
- 文档列表
- 新建文档
- 编辑文档
- 删除文档
- Ctrl+S 快捷键保存

## 文件说明
```
docs_admin/
├── app.py          # Flask 主应用
├── db.py           # 数据库操作
├── requirements.txt
├── templates/      # 页面模板
│   ├── login.html
│   ├── admin.html
│   └── edit.html
└── static/
    └── admin.css   # 后台样式
```
