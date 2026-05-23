# 📧 QQ群邮箱验证码插件

> ✨ **版本**：v1.10 | 👤 **作者**：感情 | 📜 **协议**：MIT

---

## 📋 目录

- [✨ 功能亮点](#feature-highlights)
- [📦 安装方式](#installation)
- [🚀 快速配置指南](#quick-start)
- [⚙️ 完整配置说明](#configuration)
  - [🔐 基础管理配置](#basic-config)
  - [📧 SMTP邮件服务配置](#smtp-config)
  - [⏱️ 时间配置](#time-config)
  - [📝 入群消息配置](#message-config)
  - [🖼️ 图片配置](#image-config)
- [🎯 三种验证模式详解](#verify-modes)
  - [模式0：用户自由选择](#mode-0)
  - [模式1：仅邮箱验证](#mode-1)
  - [模式2：仅数学题验证](#mode-2)
- [🔄 用户验证流程](#verify-flow)
- [📝 变量模板系统](#variables)
- [⌨️ 管理员指令大全](#admin-commands)
- [🖼️ 视觉特性说明](#visual-features)
- [💾 数据库功能](#database)
- [💡 常见问题](#faq)
- [💖 支持我们](#support)

---

## ✨ 功能亮点 {#feature-highlights}

| 特性 | 说明 |
|------|------|
| 🔐 **双验证体系** | 邮箱验证 + 数学题验证，用户可自选或管理员强制指定 |
| 📧 **邮件美化** | 支持自定义HTML模板 + 二次元背景图 + 毛玻璃效果 |
| ⏰ **超时踢出** | 验证超时自动踢出，带倒计时警告，防死群 |
| 🛡️ **防刷保护** | 邮件发送冷却机制，防止恶意骚扰验证 |
| 🖊️ **引用消息** | 回复采用QQ引用消息样式，美观清晰 |
| 🖼️ **欢迎图片** | 入群欢迎消息可附带自定义图片 |
| 📝 **模板变量** | 所有消息全变量自定义，无死角定制 |
| 🔍 **管理指令** | 测试邮件、查看状态、发送日志、统计数据等完整管理功能 |
| 🌐 **多群支持** | 可指定群开启或全局启用 |
| 💾 **数据库支持** | SQLite持久化存储，验证记录永不丢失 |
| 🔄 **回归用户检测** | 自动识别之前验证成功的用户，跳过验证流程 |
| 📊 **数据统计** | 查看验证统计、用户记录、数据报告发送邮箱 |
| 🎯 **智能验证** | 选择邮箱验证后自动发送，无需再次@机器人 |

---

## 📦 安装方式 {#installation}

### 方式一：AstrBot 市场安装（推荐）

1. 打开 AstrBot 管理面板
2. 进入 **插件市场**
3. 搜索 **"群邮箱验证码"**
4. 点击安装即可

### 方式二：手动安装

1. 将本插件文件夹放入 `AstrBot/data/plugins/` 目录
2. 重启 AstrBot
3. 在管理面板中启用插件

---

## 🚀 快速配置指南 {#quick-start}

> 💡 只需 **3 步** 即可跑起来！

### 第1步：配置SMTP邮箱

> ⚠️ **注意：使用QQ邮箱请填授权码，不是QQ密码！**

以 **QQ邮箱** 为例：

```
登录 QQ邮箱 → 设置 → 账户
    ↓
开启「POP3/SMTP服务」
    ↓
生成授权码（16位字母）
    ↓
填入插件配置
```

最小配置示例：

```json
{
  "smtp_host": "smtp.qq.com",
  "smtp_port": 465,
  "smtp_user": "123456789@qq.com",
  "smtp_password": "你的16位授权码",
  "smtp_encryption": "ssl"
}
```

### 第2步：配置验证群

```json
{
  "enabled_groups": ["123456789", "987654321"]
}
```

> 💡 留空 `[]` 则所有群都生效

### 第3步：添加管理员

```json
{
  "admin_qqs": ["你的QQ号"]
}
```

保存配置 → 重启 AstrBot → ✅ 搞定！

---

## ⚙️ 完整配置说明 {#configuration}

> 所有配置通过 AstrBot 管理面板修改，或编辑 `_conf_schema.json` 文件。

### 🔐 基础管理配置 {#basic-config}

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled_groups` | list | `[]` | 启用验证的群号列表（留空全局生效） |
| `admin_qqs` | list | `[]` | 管理员QQ号列表 |
| `verification_mode` | int | `0` | 验证模式：`0`=用户自选，`1`=仅邮箱，`2`=仅数学题 |

### 📧 SMTP邮件服务配置 {#smtp-config}

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `smtp_host` | string | `smtp.qq.com` | SMTP服务器地址 |
| `smtp_port` | int | `465` | SMTP端口 |
| `smtp_user` | string | `your_email@qq.com` | 发信邮箱账号 |
| `smtp_password` | string | `""` | **邮箱授权码**（不是登录密码！） |
| `smtp_encryption` | string | `ssl` | 加密方式：`ssl` / `tls` / `none` |
| `from_name` | string | `Q群验证助手` | 发件人显示名称 |
| `email_domain` | string | `@qq.com` | 用户邮箱后缀（自动用QQ号拼接） |
| `email_template_choice` | int | `1` | 邮件模板选择：`1`=经典蓝色，`2`=简约风格，`3`=渐变紫色，`4`=卡片风格，`5`=科技风格，`0`=自定义模板 |

<details>
<summary><b>🌐 其他邮箱SMTP配置参考</b></summary>

| 邮箱 | SMTP主机 | 端口 | 加密 | 密码说明 |
|------|----------|------|------|----------|
| QQ邮箱 | smtp.qq.com | 465/587 | ssl/tls | 授权码 |
| 163邮箱 | smtp.163.com | 465/994 | ssl | 授权码 |
| Gmail | smtp.gmail.com | 587/465 | tls/ssl | 应用密码 |

</details>

### 🎯 验证模式与超时配置 {#verify-config}

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `verification_timeout` | int | `600` | 验证超时时间（秒），默认10分钟 |
| `email_cooldown` | int | `60` | 邮件发送冷却时间（秒） |
| `kick_countdown_warning_time` | int | `120` | 踢出前警告倒计时（秒） |
| `kick_delay` | int | `10` | 最后通牒到踢出的延迟（秒） |

### 🎨 视觉与体验配置 {#visual-config}

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_welcome_image` | bool | `false` | 是否附带欢迎图片 |
| `welcome_image` | string | `""` | 欢迎图片路径（本地或URL） |
| `enable_email_background_image` | bool | `false` | 是否启用邮件背景图 |
| `email_background_image_url` | string | `https://t.alcy.cc/moe` | 邮件背景图API地址 |
| `enable_code_image` | bool | `true` | 是否生成验证码图片 |
| `enable_reply_message` | bool | `true` | 是否启用引用消息样式 |

### 📝 消息模板配置 {#template-config}

所有消息模板均支持变量替换，详见下方 [变量模板系统](#variables)。

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `trigger_prompt` | text | 入群提示（邮箱验证模式） |
| `mode_0_menu_prompt` | text | 模式0菜单提示 |
| `email_sent_prompt` | text | 验证码已发送提示 |
| `wrong_code_prompt` | text | 验证码错误提示 |
| `welcome_message` | text | 验证成功欢迎语 |
| `countdown_warning_prompt` | text | 超时警告提示 |
| `failure_message` | text | 超时最后通牒 |
| `kick_message` | text | 踢出公告 |

---

## 🎯 三种验证模式详解 {#verify-modes}

### 模式0：用户自由选择 {#mode-0}

> 默认模式，用户可选择 **邮箱验证** 或 **数学题验证**

**流程：**
1. 新成员入群 → 发送选择菜单
2. 用户回复 `1` → 进入邮箱验证
3. 用户回复 `2` → 进入数学题验证

**适用场景：** 通用，适合大多数群聊

---

### 模式1：仅邮箱验证 {#mode-1}

> 所有新成员必须通过 **邮箱验证码** 完成验证

**流程：**
1. 新成员入群 → 机器人私聊发送验证码
2. 用户在群内 @机器人 回复验证码
3. 验证成功/失败

**适用场景：** 需要验证邮箱真实性的场景

---

### 模式2：仅数学题验证 {#mode-2}

> 所有新成员必须回答 **随机数学加减法**

**流程：**
1. 新成员入群 → 发送数学题
2. 用户在群内 @机器人 回复答案
3. 验证成功/失败

**适用场景：** 快速验证，无需配置邮箱

---

## 🔄 用户验证流程 {#verify-flow}

```
用户入群
    ↓
┌─────────────────────────────────────┐
│ 验证模式 0/1/2                       │
│                                     │
│ 0: 显示选择菜单 → 用户选1或2          │
│ 1: 直接发送验证码邮件                 │
│ 2: 直接发送数学题                    │
└─────────────────────────────────────┘
    ↓
用户 @机器人 回复验证码/答案
    ↓
验证成功 → 发送欢迎语 ✅
    或
验证失败 → 重新发送验证码/答案
    或
超时未验证 → 警告 → 踢出 ❌
```

---

## 📝 变量模板系统 {#variables}

所有消息模板支持以下变量占位符：

| 变量 | 说明 | 示例 |
|------|------|------|
| `{at_user}` | @用户代码 | `[CQ:at,qq=123456]` |
| `{member_name}` | 用户昵称 | 张三 |
| `{group_name}` | 群名称 | 测试群 |
| `{group_member_count}` | 当前群人数 | 520 |
| `{admin_list}` | 管理员列表 | 李四、王五 |
| `{email}` | 用户邮箱 | `123456@qq.com` |
| `{code}` | 验证码 | `888888` |
| `{timeout}` | 超时时间（分钟） | `10` |
| `{countdown}` | 倒计时（秒） | `120` |

**示例：**
```
{at_user} 欢迎 {member_name} 加入 {group_name}！
当前群友：{group_member_count} 人
管理员：{admin_list}
```

---

## ⌨️ 管理员指令大全 {#admin-commands}

> ⚠️ **重要**：管理员指令需要在 **群聊中 @机器人** 或 **私信** 中使用
> 
> 触发方式：**@感情 指令名称**

| 指令 | 说明 |
|------|------|
| `测试新人进群邮箱测试` | 向自己发送测试邮件 |
| `测试新人进群邮箱测试 <验证码>` | 使用指定验证码测试 |
| `发送邮箱测试 <QQ号> [验证码]` | 向指定用户发送测试邮件 |
| `新人进群测试日志` | 发送运行日志到管理员邮箱 |
| `插件状态` | 查看插件当前状态和配置 |
| `查看配置` | 查看简要配置信息 |
| `新人进群验证 [QQ号]` | 手动触发验证菜单 |
| `发送数据到邮箱` | 发送HTML格式的验证数据统计报告到邮箱 |
| `查看统计数据` | 查看验证统计信息（总记录数、成功率等） |
| `查看用户记录` | 查看最近用户验证记录 |
| `查看函数` | 查看可用指令列表 |

### 使用示例

**群聊中使用**：
```
@感情 测试新人进群邮箱测试
```

**私信中使用**：
```
测试新人进群邮箱测试
```

---

## 🖼️ 视觉特性说明 {#visual-features}

### 邮件模板

支持 5 种预设模板 + 1 种自定义模板：
- **模板1**：经典蓝色风格（默认）
- **模板2**：简约白底风格
- **模板3**：渐变紫色风格
- **模板4**：卡片毛玻璃风格
- **模板5**：科技蓝色风格
- **模板0**：完全自定义HTML

### 二次元背景图

可选启用邮件背景图功能：
- 使用 `https://t.alcy.cc/moe` API 获取随机二次元图片
- 支持毛玻璃效果叠加
- 自动缓存图片链接

---

## 💾 数据库功能 {#database}

插件使用 SQLite 数据库持久化存储验证记录，数据永不丢失。

### 数据库表结构

| 表名 | 说明 |
|------|------|
| `verification_records` | 验证记录表 |
| `admin_config` | 管理员信息表 |
| `group_config` | 群聊信息表 |
| `email_config` | 邮件配置表 |
| `user_stats` | 用户统计表 |

### 记录的信息

- ✅ 用户QQ号和昵称
- ✅ 邮箱地址
- ✅ 验证方式（邮箱/数学题/用户自选）
- ✅ 入群时间和验证时间
- ✅ 验证结果（成功/失败/进行中）
- ✅ 退群时间
- ✅ 群聊信息
- ✅ 管理员信息

### 数据用途

1. **回归用户检测**：自动识别之前验证成功的用户，跳过验证
2. **统计分析**：查看验证成功率、用户活跃度等
3. **数据报告**：生成HTML格式的统计报告发送到邮箱
4. **记录追踪**：追踪每个用户的验证历史

---

## 💡 常见问题 {#faq}

<details>
<summary><b>Q1: 邮件发送失败怎么办？</b></summary>

1. 检查SMTP配置是否正确
2. 确认邮箱已开启SMTP服务
3. 确认使用的是**授权码**而非登录密码
4. 检查防火墙是否阻止了SMTP端口

</details>

<details>
<summary><b>Q2: 用户收不到验证码邮件？</b></summary>

1. 确认用户的邮箱后缀配置正确
2. 检查邮件是否被邮箱系统拦截
3. 查看插件日志排查问题

</details>

<details>
<summary><b>Q3: 如何自定义消息模板？</b></summary>

在配置文件中编辑对应模板，支持变量替换。使用HTML编辑模式可获得更好的编辑体验。

</details>

<details>
<summary><b>Q4: 如何关闭验证？</b></summary>

1. 在管理面板中禁用插件
2. 或将 `enabled_groups` 设置为非目标群号

</details>

<details>
<summary><b>Q5: 如何启用回归用户跳过验证？</b></summary>

在配置中设置 `enable_return_user_skip` 为 `true`，已验证成功的用户重新入群时会自动跳过验证流程。

</details>

<details>
<summary><b>Q6: 数据库文件在哪里？</b></summary>

数据库文件位于：`data/plugin_data/group_verify_email_auto/verification.db`

</details>

<details>
<summary><b>Q7: 如何导出验证数据？</b></summary>

管理员发送 `发送数据到邮箱` 指令，插件会将HTML格式的验证数据报告发送到管理员邮箱。

</details>

---

## 📂 项目结构 {#project-structure}

```
group_verify_email_auto/
├── main.py                      # 插件主入口
├── metadata.yaml                # 插件元信息
├── _conf_schema.json            # 配置文件结构
├── requirements.txt             # 依赖列表
├── core/                        # 核心模块
│   ├── __init__.py
│   ├── verification.py          # 验证管理器
│   ├── email_utils.py           # 邮件工具
│   ├── admin_commands.py        # 管理员指令
│   └── logger_setup.py          # 日志配置
└── templates/                   # 邮件模板
    ├── email_template.html      # 默认模板
    ├── email_template_2.html    # 简约模板
    ├── email_template_3.html    # 渐变模板
    ├── email_template_4.html    # 卡片模板
    ├── email_template_5.html    # 科技模板
    └── log_email_template.html # 日志模板
```

---

## 💖 支持我们 {#support}

> 如果这个插件对你有帮助，请给我们一个 ⭐ Star！

- 🐛 **问题反馈**：[GitHub Issues](https://github.com/YOYOFeelings/group_verify_email_auto/issues)
- 📦 **插件市场**：AstrBot 管理面板搜索"群邮箱验证码"
- 💬 **交流群组**：欢迎加入 AstrBot 官方群组讨论

---

> 📌 **版本**：v1.10 | 👤 **作者**：感情 | 📜 **协议**：MIT
