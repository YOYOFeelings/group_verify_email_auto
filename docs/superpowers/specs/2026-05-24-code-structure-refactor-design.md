# 代码结构重构设计文档

**日期：** 2026-05-24
**项目：** QQ群邮箱验证码插件
**版本：** v1.16.0

## 概述

本次重构为轻量级重构，目标是重组代码结构、建立清晰的分层架构，同时保持功能完全不变、保持向后兼容。

## 问题分析

当前代码结构存在以下问题：

1. **main.py 职责混乱**：同时处理插件初始化、配置管理、事件分发
2. **核心模块过大**：`verification.py` 和 `database.py` 包含过多功能
3. **配置管理分散**：配置来自多个来源，没有统一管理
4. **缺少清晰分层**：没有明确的数据层、业务层、展示层划分
5. **全局状态过多**：如 `_bg_pool_deque`、`_CODE_IMAGE_DIR` 等

## 设计方案

### 目录结构设计

**新的目录结构：**

```
/workspace/
├── main.py                          # 仅保留初始化和事件入口
├── core/
│   ├── __init__.py
│   ├── config.py                  # 新增：配置管理
│   ├── models/                  # 新增：数据模型层
│   │   ├── __init__.py
│   │   └── database.py          # 从 core/database.py 移动
│   ├── services/                # 新增：业务逻辑层
│   │   ├── __init__.py
│   │   ├── verification.py    # 从 core/verification.py 移动
│   │   └── admin.py         # 从 core/admin_commands.py 重命名
│   └── utils/                   # 新增：工具层
│       ├── __init__.py
│       ├── email.py           # 从 core/email_utils.py 拆分
│       ├── image.py         # 从 core/email_utils.py 拆分
│       └── logger.py        # 从 core/logger_setup.py 移动
├── templates/                    # 保持不变
└── ...
```

### 文件说明

| 原文件 | 新位置 | 说明 |
|-------|--------|------|
| `core/database.py` | `core/models/database.py` | 数据模型层 |
| `core/verification.py` | `core/services/verification.py` | 验证业务逻辑 |
| `core/admin_commands.py` | `core/services/admin.py` | 管理员业务逻辑 |
| `core/logger_setup.py` | `core/utils/logger.py` | 日志工具 |
| `core/email_utils.py` | `core/utils/email.py` + `core/utils/image.py` | 邮件和图片工具 |
| （新增） | `core/config.py` | 配置管理 |
| `main.py` | `main.py` | 精简后的入口 |

### 职责划分

#### main.py（精简后）
- 插件注册和初始化入口
- 事件监听和分发
- 调用各 service 层处理业务

#### core/config.py
- `flatten_config()`：配置扁平化
- `merge_config()`：配置合并逻辑
- `load_templates()`：消息模板加载

#### 数据流向示例
```
入群事件 → main.py.handle_event() 
         → verification_service.new_member()
         → database_manager.add_verification_record()
         → email_utils.send_mail()
```

### 向后兼容措施

- 保留原 `core/__init__.py` 中的导出，指向新路径
- 旧代码路径仍可正常 import（添加 alias）

## 实施步骤

1. **创建新目录结构和空文件**
   - 创建 core/models/、core/services/、core/utils/
   - 创建新的 __init__.py 文件

2. **移动和拆分文件**
   - core/database.py → core/models/database.py
   - core/verification.py → core/services/verification.py
   - core/admin_commands.py → core/services/admin.py
   - core/logger_setup.py → core/utils/logger.py
   - 拆分 core/email_utils.py → core/utils/email.py + core/utils/image.py
   - 新建 core/config.py，从 main.py 移动配置处理逻辑

3. **精简 main.py**
   - 移除配置扁平化逻辑
   - 移除消息模板加载逻辑
   - 仅保留初始化和事件处理入口
   - 更新所有 import 路径

4. **更新 core/__init__.py**
   - 保持原有的导出，指向新位置（向后兼容）
   - 添加新模块的导出

5. **更新所有内部 import**
   - 更新各个模块内部的引用
   - 确保依赖关系正确

6. **测试验证**
   - 确保所有功能正常工作
   - 检查导入是否正确

7. **删除旧文件（可选）**
   - 或保留旧文件并添加 deprecated 警告

## 约束和限制

- **不改变功能**：所有功能行为保持不变
- **向后兼容**：外部 API 和导出保持不变
- **轻量级**：避免过度设计，只做必要的结构调整
