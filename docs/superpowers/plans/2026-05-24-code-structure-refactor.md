# 代码结构重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构代码结构，按分层原则重新组织文件，同时保持功能和向后兼容性。

**Architecture:** 采用分层架构，将代码分为 models（数据层）、services（业务层）、utils（工具层）和 config（配置层），main.py 作为入口层。

**Tech Stack:** Python 3.x, AstrBot framework, SQLite, SMTP

---

## File Structure Map

| File | Action | Responsibility |
|------|--------|-----------------|
| `core/models/database.py` | Create from `core/database.py` | Database operations |
| `core/services/verification.py` | Create from `core/verification.py` | Verification logic |
| `core/services/admin.py` | Create from `core/admin_commands.py` | Admin commands |
| `core/utils/logger.py` | Create from `core/logger_setup.py` | Logger setup |
| `core/utils/email.py` | Create from part of `core/email_utils.py` | Email utilities |
| `core/utils/image.py` | Create from part of `core/email_utils.py` | Image generation |
| `core/config.py` | New | Configuration management |
| `main.py` | Modify | Simplified entry point |
| `core/__init__.py` | Modify | Backward compatible exports |
| `core/database.py` | Delete (after verification) | Old location |
| `core/verification.py` | Delete (after verification) | Old location |
| `core/admin_commands.py` | Delete (after verification) | Old location |
| `core/logger_setup.py` | Delete (after verification) | Old location |
| `core/email_utils.py` | Delete (after verification) | Old location |

---

## Task 1: 创建新目录结构

**Files:**
- Create: `core/models/__init__.py`
- Create: `core/services/__init__.py`
- Create: `core/utils/__init__.py`

- [ ] **Step 1: 创建目录和空文件**

```bash
mkdir -p /workspace/core/models /workspace/core/services /workspace/core/utils
touch /workspace/core/models/__init__.py /workspace/core/services/__init__.py /workspace/core/utils/__init__.py
```

- [ ] **Step 2: 验证目录结构**

```bash
ls -la /workspace/core/
```
Expected: 新的子目录 models/、services/、utils/ 已存在

---

## Task 2: 移动数据库模块

**Files:**
- Create: `core/models/database.py` (copy from `core/database.py`)
- Modify: `core/models/__init__.py`

- [ ] **Step 1: 复制 database.py**

```bash
cp /workspace/core/database.py /workspace/core/models/database.py
```

- [ ] **Step 2: 更新 core/models/__init__.py**

```python
from .database import DatabaseManager

__all__ = ['DatabaseManager']
```

- [ ] **Step 3: 验证文件创建**

```bash
ls -la /workspace/core/models/
```
Expected: `__init__.py` 和 `database.py` 存在

---

## Task 3: 移动验证服务模块

**Files:**
- Create: `core/services/verification.py` (copy from `core/verification.py`)
- Modify: `core/services/__init__.py`

- [ ] **Step 1: 复制 verification.py 并重命名**

```bash
cp /workspace/core/verification.py /workspace/core/services/verification.py
```

- [ ] **Step 2: 更新 core/services/__init__.py**

```python
from .verification import VerificationManager, generate_code

__all__ = ['VerificationManager', 'generate_code']
```

---

## Task 4: 移动管理员服务模块

**Files:**
- Create: `core/services/admin.py` (copy from `core/admin_commands.py`)
- Modify: `core/services/__init__.py` (append)

- [ ] **Step 1: 复制 admin_commands.py 并重命名**

```bash
cp /workspace/core/admin_commands.py /workspace/core/services/admin.py
```

- [ ] **Step 2: 更新 core/services/__init__.py**

```python
from .verification import VerificationManager, generate_code
from .admin import AdminHandler

__all__ = ['VerificationManager', 'generate_code', 'AdminHandler']
```

---

## Task 5: 移动日志工具模块

**Files:**
- Create: `core/utils/logger.py` (copy from `core/logger_setup.py`)
- Modify: `core/utils/__init__.py`

- [ ] **Step 1: 复制 logger_setup.py 并重命名**

```bash
cp /workspace/core/logger_setup.py /workspace/core/utils/logger.py
```

- [ ] **Step 2: 更新 core/utils/__init__.py**

```python
from .logger import get_plugin_logger

__all__ = ['get_plugin_logger']
```

---

## Task 6: 拆分 email_utils.py

**Files:**
- Create: `core/utils/email.py` (email-related part)
- Create: `core/utils/image.py` (image-related part)
- Modify: `core/utils/__init__.py`

- [ ] **Step 1: 创建 core/utils/image.py**
Content: 从 `core/email_utils.py` 提取验证码图片生成和背景图池相关代码

```python
import os
import random
import collections
import asyncio
import urllib.request
import urllib.error
import logging
from PIL import Image, ImageDraw, ImageFont, ImageFilter

logger = logging.getLogger("GroupVerifyEmailAuto.utils.image")
CODE_IMAGE_WIDTH = 400
CODE_IMAGE_HEIGHT = 160

_CODE_IMAGE_DIR = None
_bg_pool_deque = collections.deque()
_bg_pool_lock = asyncio.Lock()
_bg_pool_filling = False
_bg_pool_ready = asyncio.Event()
_bg_pool_api_url = ""


def set_code_image_dir(dir_path: str):
    global _CODE_IMAGE_DIR
    _CODE_IMAGE_DIR = dir_path
    os.makedirs(dir_path, exist_ok=True)
    logger.info(f"验证码图片目录已设置: {dir_path}")


def _find_font() -> str:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            logger.debug(f"找到字体: {path}")
            return path
    try:
        import subprocess
        result = subprocess.run(["fc-list", ":lang=zh", "-f", "%{file}\\n"], capture_output=True, text=True, timeout=3)
        fonts = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        if fonts:
            logger.debug(f"通过 fc-list 找到字体: {fonts[0]}")
            return fonts[0]
    except Exception:
        pass
    logger.warning("未找到中文字体，使用默认字体")
    return None


def _get_font(size: int = 40):
    font_path = _find_font()
    try:
        if font_path:
            return ImageFont.truetype(font_path, size)
    except Exception as e:
        logger.warning(f"加载字体失败: {e}")
    return ImageFont.load_default()


def generate_code_image(code: str, uid: str = "") -> str:
    if _CODE_IMAGE_DIR is None:
        logger.error("验证码图片目录未设置")
        return ""

    width, height = CODE_IMAGE_WIDTH, CODE_IMAGE_HEIGHT
    padding = 20

    img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    for y in range(height):
        r = int(30 + (y / height) * 50)
        g = int(120 + (y / height) * 70)
        b = int(200 + (y / height) * 55)
        draw.rectangle([(0, y), (width, y + 1)], fill=(r, g, b, 230))

    for _ in range(80):
        x = random.randint(0, width)
        y = random.randint(0, height)
        r_size = random.randint(1, 3)
        dot_color = (
            random.randint(180, 255),
            random.randint(180, 255),
            random.randint(180, 255),
            random.randint(60, 150)
        )
        draw.ellipse([(x, y), (x + r_size, y + r_size)], fill=dot_color)

    for _ in range(4):
        line_color = (
            random.randint(200, 255),
            random.randint(200, 255),
            random.randint(200, 255),
            random.randint(40, 80)
        )
        x1 = random.randint(0, width // 3)
        y1 = random.randint(0, height)
        x2 = random.randint(width * 2 // 3, width)
        y2 = random.randint(0, height)
        draw.line([(x1, y1), (x2, y2)], fill=line_color, width=random.randint(1, 2))

    water_font = _get_font(12)
    for i in range(6):
        wx = random.randint(0, width - 50)
        wy = random.randint(0, height - 20)
        draw.text((wx, wy), "VERIFY", fill=(255, 255, 255, 30), font=water_font)

    font_size = 60
    font = _get_font(font_size)
    code_str = str(code)
    total_width = 0
    char_imgs = []

    for i, ch in enumerate(code_str):
        try:
            ch_img = Image.new("RGBA", (font_size + 10, font_size + 10), (0, 0, 0, 0))
            ch_draw = ImageDraw.Draw(ch_img)

            hue_offset = random.randint(-20, 20)
            ch_color = (
                min(255, max(0, 255 + hue_offset)),
                min(255, max(0, 255 - hue_offset)),
                255,
                240
            )

            ch_draw.text((5, 0), ch, fill=ch_color, font=font)

            angle = random.randint(-15, 15)
            ch_img = ch_img.rotate(angle, expand=1, fillcolor=(0, 0, 0, 0))

            char_imgs.append(ch_img)
            total_width += ch_img.width
        except Exception:
            continue

    img_count = max(len(char_imgs), 1)
    total_spacing = total_width + (img_count - 1) * 8
    start_x = (width - total_spacing) // 2
    y_offset = (height - font_size) // 2 - 5

    current_x = start_x
    for ch_img in char_imgs:
        img.paste(ch_img, (current_x, y_offset), ch_img)
        current_x += ch_img.width + 8

    try:
        label_font = _get_font(14)
        draw.text((width // 2 - 30, height - 25), "验证码", fill=(255, 255, 255, 100), font=label_font)
    except Exception:
        pass

    img = img.filter(ImageFilter.GaussianBlur(radius=0.5))

    filename = f"code_{uid}_{code}.png"
    save_path = os.path.join(_CODE_IMAGE_DIR, filename)
    img.save(save_path, "PNG")
    logger.info(f"验证码图片已生成: {save_path}")
    return save_path


def cleanup_code_image(image_path: str):
    try:
        if os.path.exists(image_path):
            os.remove(image_path)
            logger.debug(f"验证码图片已清理: {image_path}")
    except Exception as e:
        logger.error(f"清理验证码图片失败: {image_path} | {e}")


def resolve_final_image_url(original_url: str, timeout: int = 2) -> str:
    if not original_url or not original_url.startswith("http"):
        return original_url
    try:
        req = urllib.request.Request(original_url, method='HEAD')
        resp = urllib.request.urlopen(req, timeout=timeout)
        final = resp.geturl()
        resp.close()
        logger.info(f"[背景图] 解析成功 | source={original_url} | final={final}")
        return final
    except Exception as e:
        logger.warning(f"[背景图] HEAD请求失败，尝试GET请求 | source={original_url} | error={e}")
        try:
            req = urllib.request.Request(original_url)
            resp = urllib.request.urlopen(req, timeout=timeout)
            final = resp.geturl()
            resp.close()
            logger.info(f"[背景图] 解析成功(GET) | source={original_url} | final={final}")
            return final
        except Exception as e2:
            logger.error(f"[背景图] 解析最终失败 | source={original_url} | error={e2}")
            return original_url


async def _fill_pool(api_url: str, count: int = 5):
    global _bg_pool_filling
    async with _bg_pool_lock:
        if _bg_pool_filling:
            return
        _bg_pool_filling = True
    try:
        logger.info(f"[图片池] 开始补充 {count} 张背景图")
        for i in range(count):
            final_url = await asyncio.to_thread(resolve_final_image_url, api_url)
            async with _bg_pool_lock:
                _bg_pool_deque.append(final_url)
            logger.debug(f"[图片池] 已获取第 {i+1}/{count} 张: {final_url}")
        logger.info(f"[图片池] 补充完成，当前池大小: {len(_bg_pool_deque)}")
    except Exception as e:
        logger.exception(f"[图片池] 补充过程出错: {e}")
    finally:
        async with _bg_pool_lock:
            _bg_pool_filling = False


async def init_image_pool(api_url: str, count: int = 5):
    global _bg_pool_api_url
    _bg_pool_api_url = api_url
    async with _bg_pool_lock:
        _bg_pool_deque.clear()
    await _fill_pool(api_url, count)
    _bg_pool_ready.set()
    logger.info(f"[图片池] 初始化完成，已就绪 {len(_bg_pool_deque)} 张背景图")


async def get_next_bg_url(api_url: str) -> str:
    if not api_url or not api_url.startswith("http"):
        return api_url

    if not _bg_pool_ready.is_set():
        try:
            await asyncio.wait_for(_bg_pool_ready.wait(), timeout=10)
        except asyncio.TimeoutError:
            logger.warning("[图片池] 等待初始化超时，将临时解析一张")

    async with _bg_pool_lock:
        need_refill = (len(_bg_pool_deque) <= 2) and not _bg_pool_filling
    if need_refill:
        asyncio.create_task(_fill_pool(api_url, 5))

    async with _bg_pool_lock:
        if _bg_pool_deque:
            url = _bg_pool_deque.popleft()
            logger.info(f"[图片池] 取出背景图，剩余 {len(_bg_pool_deque)} 张")
            return url

    logger.info("[图片池] 池空，临时解析一张背景图")
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(resolve_final_image_url, api_url),
            timeout=5
        )
    except asyncio.TimeoutError:
        logger.warning("[图片池] 临时解析超时，返回原始URL")
        return api_url
    except Exception as e:
        logger.error(f"[图片池] 临时解析出错: {e}")
        return api_url
```

- [ ] **Step 2: 创建 core/utils/email.py**
Content: 从 `core/email_utils.py` 提取邮件构建和发送相关代码

```python
import re
import asyncio
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr
from .image import get_next_bg_url

logger = logging.getLogger("GroupVerifyEmailAuto.utils.email")
SMTP_TIMEOUT = 5


def build_email_html_sync(template: str, final_bg_url: str, group_name: str,
                          member_name: str, code: str, timeout_min: int) -> str:
    logger.debug(f"构造邮件HTML | final_bg={final_bg_url} | group={group_name} | code=******")
    bg_valid = bool(final_bg_url and final_bg_url.strip() and re.match(r'^https?://', final_bg_url.strip()))
    if not bg_valid and final_bg_url and final_bg_url.strip():
        logger.error(f"背景图链接格式无效 | url={final_bg_url}")
        final_bg_url = ""
    else:
        final_bg_url = final_bg_url.strip() if final_bg_url else ""

    if bg_valid:
        card_style = ("background: rgba(255,255,255,0.75); "
                      "backdrop-filter: blur(10px); "
                      "-webkit-backdrop-filter: blur(10px); "
                      "border-radius: 12px;")
        logger.debug("启用毛玻璃卡片样式")
    else:
        card_style = "background: #fff; border-radius: 12px;"
        logger.debug("降级为纯白卡片")

    html = template

    if not bg_valid:
        html = re.sub(r'background="\{bg_url\}"', '', html, flags=re.IGNORECASE)
        html = re.sub(r"background-image\s*:\s*url\s*\(\s*['\"]?\{bg_url\}['\"]?\s*\)\s*;", '', html, flags=re.IGNORECASE)
        html = re.sub(r'background\s*:\s*[^;]*\{bg_url\}[^;]*;', '', html, flags=re.IGNORECASE)

    html = html.replace('{card_style}', card_style)

    safe_member_name = member_name
    safe_group_name = group_name
    if safe_member_name:
        safe_member_name = safe_member_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    if safe_group_name:
        safe_group_name = safe_group_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    try:
        html = html.format(
            group_name=safe_group_name,
            member_name=safe_member_name,
            code=code,
            timeout=timeout_min,
            bg_url=final_bg_url if bg_valid else ''
        )
    except KeyError as e:
        logger.warning(f"模板变量替换失败，尝试备用方案: {e}")
        html = html.replace('{group_name}', safe_group_name)
        html = html.replace('{member_name}', safe_member_name)
        html = html.replace('{code}', code)
        html = html.replace('{timeout}', str(timeout_min))
        html = html.replace('{bg_url}', final_bg_url if bg_valid else '')

    logger.debug(f"最终HTML长度: {len(html)}")
    return html


def _get_smtp(host, port, encryption, timeout=SMTP_TIMEOUT):
    logger.debug(f"创建SMTP连接 | host={host} | port={port} | encryption={encryption}")
    if encryption == "ssl":
        return smtplib.SMTP_SSL(host, port, timeout=timeout)
    else:
        server = smtplib.SMTP(host, port, timeout=timeout)
        if encryption == "tls":
            server.starttls()
        return server


def send_email_sync(host, port, user, pwd, encryption, from_name, to, subject, html):
    logger.info(f"开始同步发送邮件 | to={to} | subject={subject}")
    msg = MIMEText(html, "html", "utf-8")
    msg["From"] = formataddr((from_name, user))
    msg["To"] = to
    msg["Subject"] = subject
    server = None
    try:
        server = _get_smtp(host, port, encryption)
        server.login(user, pwd)
        server.sendmail(user, [to], msg.as_string())
        logger.info(f"邮件发送成功 | to={to}")
        return True, None
    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"SMTP认证失败，请检查用户名和授权码是否正确"
        logger.error(f"邮件发送失败 - 认证错误 | to={to} | error={e}")
        return False, (error_msg, "auth")
    except smtplib.SMTPConnectError as e:
        error_msg = f"无法连接到SMTP服务器，请检查服务器地址和端口配置"
        logger.error(f"邮件发送失败 - 连接错误 | to={to} | error={e}")
        return False, (error_msg, "connect")
    except smtplib.SMTPException as e:
        error_msg = f"SMTP服务异常: {str(e)}"
        logger.error(f"邮件发送失败 - SMTP错误 | to={to} | error={e}")
        return False, (error_msg, "smtp")
    except TimeoutError as e:
        error_msg = f"连接超时，请检查网络连接或SMTP服务器是否可访问"
        logger.error(f"邮件发送失败 - 超时 | to={to} | error={e}")
        return False, (error_msg, "timeout")
    except Exception as e:
        error_msg = f"发送邮件时出现未知错误: {str(e)}"
        logger.exception(f"邮件发送失败 - 未知错误 | to={to} | error={e}")
        return False, (error_msg, "unknown")
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass


async def async_send_verification(host, port, user, pwd, encryption, from_name, to, subject,
                                  html, bg_url="", use_glass=False):
    logger.info(f"异步发送验证邮件 | to={to} | subject={subject}")
    try:
        success, error_data = await asyncio.to_thread(send_email_sync, host, port, user, pwd, encryption,
                                                      from_name, to, subject, html)
        if success:
            return True, None
        else:
            return False, error_data
    except Exception as e:
        logger.exception(f"异步邮件发送异常 | {e}")
        return False, (f"系统错误: {str(e)}", "system")


async def async_send_log_attachment(host, port, user, pwd, encryption, from_name, to, subject,
                                    body, file_path, fname, bg_url="", use_glass=False):
    logger.info(f"发送日志附件 | to={to} | file={file_path}")
    msg = MIMEMultipart()
    msg["From"] = formataddr((from_name, user))
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html", "utf-8"))
    if file_path:
        try:
            with open(file_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", "attachment", filename=("utf-8", "", fname))
                msg.attach(part)
        except FileNotFoundError:
            logger.warning(f"附件文件不存在，仅发送正文 | file={file_path}")
    server = None
    try:
        server = _get_smtp(host, port, encryption)
        server.login(user, pwd)
        server.sendmail(user, [to], msg.as_string())
        logger.info(f"附件邮件发送成功 | to={to}")
        return True, ""
    except Exception as e:
        logger.exception(f"附件邮件发送失败 | {e}")
        return False, str(e)
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass


async def init_smtp_check(host, port, user, pwd, encryption):
    logger.info(f"SMTP检测开始 | host={host}:{port} | encryption={encryption}")

    def _check():
        server = _get_smtp(host, port, encryption)
        try:
            server.login(user, pwd)
            return True
        finally:
            server.quit()
    try:
        ok = await asyncio.to_thread(_check)
        logger.info(f"SMTP检测结果: {'成功' if ok else '失败'}")
        return ok
    except Exception as e:
        logger.exception(f"SMTP检测异常: {e}")
        return False
```

- [ ] **Step 3: 更新 core/utils/__init__.py**

```python
from .logger import get_plugin_logger
from .email import (
    async_send_verification,
    async_send_log_attachment,
    build_email_html_sync,
    init_smtp_check
)
from .image import (
    init_image_pool,
    generate_code_image,
    cleanup_code_image,
    set_code_image_dir,
    get_next_bg_url
)

__all__ = [
    'get_plugin_logger',
    'async_send_verification',
    'async_send_log_attachment',
    'build_email_html_sync',
    'init_smtp_check',
    'init_image_pool',
    'generate_code_image',
    'cleanup_code_image',
    'set_code_image_dir',
    'get_next_bg_url'
]
```

---

## Task 7: 创建配置模块

**Files:**
- Create: `core/config.py`

- [ ] **Step 1: 创建 core/config.py**

```python
import logging
from typing import Dict, Any

logger = logging.getLogger("GroupVerifyEmailAuto.config")


def _fix_newlines(s: str) -> str:
    if not isinstance(s, str):
        return s
    return s.replace('\\n', '\n')


def _flatten_config(config: Dict[str, Any]) -> Dict[str, Any]:
    if not config:
        logger.debug("传入的配置为空，返回空字典")
        return {}

    logger.debug(f"开始扁平化配置 | 原始配置: {config}")
    result = {}

    def process_dict(d: Dict[str, Any], prefix: str = ""):
        for key, value in d.items():
            logger.debug(f"处理键: {prefix}{key} | 类型: {type(value)} | 值: {value}")
            if isinstance(value, dict):
                if "type" in value:
                    value_type = value["type"]
                    if value_type == "object" and "items" in value:
                        logger.debug(f"发现 object 分组: {prefix}{key}，继续处理 items")
                        if isinstance(value["items"], dict):
                            process_dict(value["items"], prefix)
                        continue
                    elif value_type == "list":
                        if "items" in value and isinstance(value["items"], list):
                            result[key] = value
                            logger.debug(f"添加列表类型配置(数组 items): {key}")
                            continue
                        elif "items" in value and isinstance(value["items"], dict):
                            process_dict(value["items"], prefix)
                            continue
                    if "default" in value:
                        default_val = value["default"]
                        result[key] = default_val
                        logger.debug(f"添加配置项: {key} = {default_val} (类型: {type(default_val)})")
                    else:
                        result[key] = value
                        logger.debug(f"添加配置项(无 default): {key} = {value}")
                elif "default" in value:
                    default_val = value["default"]
                    result[key] = default_val
                    logger.debug(f"添加配置项(直接 default): {key} = {default_val} (类型: {type(default_val)})")
                elif "items" in value:
                    logger.debug(f"发现 items 分组: {prefix}{key}，继续处理")
                    if isinstance(value["items"], dict):
                        process_dict(value["items"], prefix)
                else:
                    result[key] = value
                    logger.debug(f"添加普通配置: {key} = {value}")
            else:
                result[key] = value
                logger.debug(f"添加直接值: {key} = {value} (类型: {type(value)})")

    process_dict(config)
    logger.info(f"扁平化配置完成 | 配置项数量: {len(result)}")
    logger.debug(f"扁平化配置结果: {result}")
    return result


def merge_config(db_config: Dict[str, Any], flat_config: Dict[str, Any]) -> Dict[str, Any]:
    merged = db_config.copy()
    merged.update(flat_config)
    logger.info(f"配置合并完成 | 最终配置项数量: {len(merged)}")
    return merged


def load_message_templates(merged_config: Dict[str, Any]) -> Dict[str, str]:
    DEFAULT_TEMPLATES = {
        "trigger": "{at_user} 欢迎加入本群！\n本群当前共 {group_member_count} 位群友\n管理员列表：\n{admin_list}\n请 @我 并回复任意消息以接收验证码到您的 QQ 邮箱。",
        "mode_0_menu": "{at_user} 欢迎加入本群！🎉\n本群当前共 {group_member_count} 位群友\n管理员列表：\n{admin_list}\n请 @我 并回复数字选择验证方式：\n1 - 邮箱验证\n2 - 数学题验证",
        "sent": "{at_user} 验证码已发送到 {email}\n请查看邮件并在群内 @我 回复数字验证码。",
        "wrong": "{at_user} 验证码错误，新的验证码已发送到 {email}\n请重新查看并回复。",
        "welcome": "{at_user} 验证成功，欢迎您的加入！🎉\n本群当前共 {group_member_count} 位群友\n管理员：\n{admin_list}",
        "warning": "{at_user} 验证即将超时，请尽快输入收到的验证码！",
        "failure": "{at_user} 验证超时，您将在 {countdown} 秒后被请出本群。",
        "kick": "{at_user} 因未在规定时间内完成验证，已被请出本群。",
        "return_user": "{at_user} 欢迎回来！{member_name}\n\n检测到您之前已经入过群并且验证成功过，\n本次将为您跳过验证流程。\n\n🎉 欢迎重新加入 {group_name}！"
    }

    templates = {
        "trigger": merged_config.get("trigger_prompt", DEFAULT_TEMPLATES["trigger"]),
        "mode_0_menu": merged_config.get("mode_0_menu_prompt", DEFAULT_TEMPLATES["mode_0_menu"]),
        "sent": merged_config.get("email_sent_prompt", DEFAULT_TEMPLATES["sent"]),
        "wrong": merged_config.get("wrong_code_prompt", DEFAULT_TEMPLATES["wrong"]),
        "welcome": merged_config.get("welcome_message", DEFAULT_TEMPLATES["welcome"]),
        "warning": merged_config.get("countdown_warning_prompt", DEFAULT_TEMPLATES["warning"]),
        "failure": merged_config.get("failure_message", DEFAULT_TEMPLATES["failure"]),
        "kick": merged_config.get("kick_message", DEFAULT_TEMPLATES["kick"]),
        "return_user": merged_config.get("return_user_message", DEFAULT_TEMPLATES["return_user"])
    }

    for key, value in templates.items():
        logger.debug(f"消息模板[{key}] 长度: {len(str(value))} | 内容: {str(value)[:50]}...")
    logger.info("消息模板加载完成")

    return templates


def get_config_value(merged_config: Dict[str, Any], key: str, default=None):
    val = merged_config.get(key, default)
    return _fix_newlines(val) if isinstance(val, str) else val
```

---

## Task 8: 更新 core/__init__.py 实现向后兼容

**Files:**
- Modify: `core/__init__.py`

- [ ] **Step 1: 更新 core/__init__.py**

```python
from .models.database import DatabaseManager
from .services.verification import VerificationManager, generate_code
from .services.admin import AdminHandler
from .utils.logger import get_plugin_logger
from .utils.email import (
    async_send_verification,
    async_send_log_attachment,
    build_email_html_sync,
    init_smtp_check
)
from .utils.image import (
    init_image_pool,
    generate_code_image,
    cleanup_code_image,
    set_code_image_dir,
    get_next_bg_url
)
from .config import _flatten_config, merge_config, load_message_templates, get_config_value

# Backward compatibility exports
VerificationManager = VerificationManager
AdminHandler = AdminHandler
get_plugin_logger = get_plugin_logger
init_smtp_check = init_smtp_check
init_image_pool = init_image_pool
async_send_verification = async_send_verification
build_email_html_sync = build_email_html_sync
generate_code_image = generate_code_image
cleanup_code_image = cleanup_code_image
set_code_image_dir = set_code_image_dir
get_next_bg_url = get_next_bg_url
async_send_log_attachment = async_send_log_attachment

__all__ = [
    'VerificationManager',
    'AdminHandler',
    'get_plugin_logger',
    'init_smtp_check',
    'init_image_pool',
    'async_send_verification',
    'build_email_html_sync',
    'generate_code_image',
    'cleanup_code_image',
    'set_code_image_dir',
    'get_next_bg_url',
    'async_send_log_attachment',
    'DatabaseManager',
    'generate_code',
    '_flatten_config',
    'merge_config',
    'load_message_templates',
    'get_config_value'
]
```

---

## Task 9: 更新内部模块导入

**Files:**
- Modify: `core/services/verification.py`
- Modify: `core/services/admin.py`

- [ ] **Step 1: 更新 core/services/verification.py 的导入**

找到原导入行：
```python
from .email_utils import async_send_verification, build_email_html_sync, get_next_bg_url
```

替换为：
```python
from ..utils.email import async_send_verification, build_email_html_sync
from ..utils.image import get_next_bg_url
```

- [ ] **Step 2: 更新 core/services/admin.py 的导入**

找到原导入行：
```python
from .email_utils import async_send_verification, async_send_log_attachment, get_next_bg_url, build_email_html_sync
from .verification import generate_code
```

替换为：
```python
from ..utils.email import async_send_verification, async_send_log_attachment, build_email_html_sync
from ..utils.image import get_next_bg_url
from .verification import generate_code
```

---

## Task 10: 重构 main.py

**Files:**
- Modify: `main.py`

- [ ] **Step 1: 更新 main.py 的导入**

原导入：
```python
import os
import re
import asyncio
import logging
from typing import Dict, Any
from astrbot.api import logger as api_logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.core.star.star_tools import StarTools
from .core.logger_setup import get_plugin_logger
from .core.email_utils import init_smtp_check, init_image_pool
from .core.admin_commands import AdminHandler
from .core.verification import VerificationManager
from .core.database import DatabaseManager
```

新导入：
```python
import os
import re
import asyncio
import logging
from typing import Dict, Any
from astrbot.api import logger as api_logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.core.star.star_tools import StarTools
from .core.utils.logger import get_plugin_logger
from .core.utils.email import init_smtp_check
from .core.utils.image import init_image_pool
from .core.services.admin import AdminHandler
from .core.services.verification import VerificationManager
from .core.models.database import DatabaseManager
from .core.config import _flatten_config, merge_config, load_message_templates, get_config_value
```

- [ ] **Step 2: 简化 main.py 的初始化代码**
移除 `_flatten_config` 和 `_fix_newlines` 函数（已移动到 config.py），使用 config.py 中的函数。初始化部分修改为：

```python
DATA_DIR = StarTools.get_data_dir("group_verify_email_auto")
os.makedirs(DATA_DIR, exist_ok=True)
get_plugin_logger(log_dir=DATA_DIR)
logger = logging.getLogger("GroupVerifyEmailAuto.main")


@register("group_verify_email_auto", "感情", "QQ群邮箱验证码插件", "1.16.0",
          "https://github.com/YOYOFeelings/group_verify_email_auto")
class GroupVerifyEmailAuto(Star):
    def __init__(self, context: Context, config: Dict[str, Any]):
        super().__init__(context)
        self.context = context
        logger.info("插件初始化开始 (v1.8)")

        # 扁平化配置
        flat_config = _flatten_config(config)
        logger.info(f"从面板读取配置 | count={len(flat_config)}")

        # 初始化数据库
        db_path = os.path.join(DATA_DIR, "verification.db")
        self.db = DatabaseManager(db_path)
        logger.info("数据库初始化完成")

        # 获取数据库中的配置
        db_config = self.db.get_all_config()
        logger.info(f"从数据库获取配置 | count={len(db_config)}")

        # 合并配置
        merged_config = merge_config(db_config, flat_config)

        # 迁移旧的管理员和群数据到数据库（向后兼容）
        config_enabled_groups = [str(g) for g in get_config_value(merged_config, "enabled_groups", [])]
        config_admin_qqs = [str(q) for q in get_config_value(merged_config, "admin_qqs", [])]

        for admin_qq in config_admin_qqs:
            if not self.db.is_admin(admin_qq):
                self.db.add_admin(admin_qq, added_by="config_migration", permission_level=2)
                logger.info(f"迁移旧配置管理员 | qq={admin_qq}")

        for group_id in config_enabled_groups:
            if not self.db.is_group_enabled(group_id):
                self.db.add_group_to_whitelist(group_id, added_by="config_migration", description="从旧配置迁移")
                logger.info(f"迁移旧配置群 | group={group_id}")

        self.verification_mode = int(get_config_value(merged_config, "verification_mode", 0))
        logger.info(f"配置加载 | 使用新的数据库管理系统 | mode={self.verification_mode}")

        smtp_host = get_config_value(merged_config, "smtp_host", "smtp.qq.com")
        smtp_port = int(get_config_value(merged_config, "smtp_port", 465))
        smtp_user = get_config_value(merged_config, "smtp_user", "")
        smtp_password = get_config_value(merged_config, "smtp_password", "")
        smtp_encryption = get_config_value(merged_config, "smtp_encryption", "ssl")
        from_name = get_config_value(merged_config, "from_name", "Q群验证助手")
        logger.info(f"SMTP配置 | host={smtp_host} | port={smtp_port} | user={smtp_user}")

        email_domain = get_config_value(merged_config, "email_domain", "@qq.com")
        email_subject = get_config_value(merged_config, "email_subject", "{group_name} 入群验证码")
        template_choice = int(get_config_value(merged_config, "email_template_choice", 1))

        if template_choice == 0:
            email_body = get_config_value(merged_config, "email_body_html", "...")
            logger.info("使用自定义邮件模板")
        else:
            template_filename = {
                1: "email_template.html",
                2: "email_template_2.html",
                3: "email_template_3.html",
                4: "email_template_4.html",
                5: "email_template_5.html"
            }.get(template_choice, "email_template.html")

            template_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", template_filename)
            if os.path.exists(template_file):
                with open(template_file, "r", encoding="utf-8") as f:
                    email_body = f.read()
                logger.info(f"邮件模板加载: {template_filename}")
            else:
                email_body = get_config_value(merged_config, "email_body_html", "...")
                logger.warning(f"模板文件不存在: {template_filename}")

        logger.info(f"邮箱配置 | domain={email_domain} | template={template_choice}")

        verify_timeout = int(get_config_value(merged_config, "verification_timeout", 600))
        warning_time = int(get_config_value(merged_config, "kick_countdown_warning_time", 120))
        kick_delay = int(get_config_value(merged_config, "kick_delay", 10))
        cooldown = int(get_config_value(merged_config, "email_cooldown", 60))
        logger.info(f"时间配置 | timeout={verify_timeout}s | cooldown={cooldown}s")

        enable_welcome_image = get_config_value(merged_config, "enable_welcome_image", False)
        welcome_image = get_config_value(merged_config, "welcome_image", "")
        enable_email_bg_image = get_config_value(merged_config, "enable_email_background_image", False)
        email_bg_url = get_config_value(merged_config, "email_background_image_url", "") if enable_email_bg_image else ""
        enable_return_skip = get_config_value(merged_config, "enable_return_user_skip", True)
        logger.info(f"图片配置 | welcome={enable_welcome_image} | bg={enable_email_bg_image} | return_skip={enable_return_skip}")

        msg_templates = load_message_templates(merged_config)

        smtp_cfg = {"host": smtp_host, "port": smtp_port, "user": smtp_user,
                    "password": smtp_password, "encryption": smtp_encryption,
                    "from_name": from_name}
        email_cfg = {"domain": email_domain, "subject": email_subject, "body": email_body}
        time_cfg = {"timeout": verify_timeout, "warning": warning_time,
                    "kick_delay": kick_delay, "cooldown": cooldown}

        self.verification = VerificationManager(
            smtp_cfg, email_cfg, time_cfg, msg_templates,
            self.context,
            admin_qqs=config_admin_qqs,
            enable_welcome_image=enable_welcome_image,
            welcome_image=welcome_image,
            email_bg_url=email_bg_url,
            verification_mode=self.verification_mode,
            enable_return_skip=enable_return_skip,
            db_manager=self.db,
            data_dir=DATA_DIR
        )
        logger.info("VerificationManager 初始化完成")

        if enable_email_bg_image and email_bg_url:
            asyncio.create_task(self._init_bg_pool(email_bg_url))

        async def _add_pending_cb(uid, gid, email, code):
            await self.verification.manual_add(uid, gid, email, code, nickname="管理员")

        log_file_path = os.path.join(DATA_DIR, "email_verify.log")
        self.admin_handler = AdminHandler(
            config_admin_qqs, smtp_cfg, email_cfg, time_cfg, msg_templates,
            _add_pending_cb,
            verification_manager=self.verification,
            log_file_path=log_file_path,
            db_manager=self.db
        )
        logger.info("AdminHandler 初始化完成")

        asyncio.create_task(self._startup_check(smtp_host, smtp_port, smtp_user,
                                                smtp_password, smtp_encryption))

        config_to_save = {
            "enabled_groups": config_enabled_groups,
            "admin_qqs": config_admin_qqs,
            "verification_mode": self.verification_mode,
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "smtp_user": smtp_user,
            "smtp_password": smtp_password,
            "smtp_encryption": smtp_encryption,
            "from_name": from_name,
            "email_domain": email_domain,
            "email_subject": email_subject,
            "email_template_choice": template_choice,
            "email_body_html": email_body,
            "verification_timeout": verify_timeout,
            "kick_countdown_warning_time": warning_time,
            "kick_delay": kick_delay,
            "email_cooldown": cooldown,
            "enable_welcome_image": enable_welcome_image,
            "welcome_image": welcome_image,
            "enable_email_background_image": enable_email_bg_image,
            "email_background_image_url": email_bg_url,
            "enable_return_user_skip": enable_return_skip,
            "trigger_prompt": msg_templates["trigger"],
            "mode_0_menu_prompt": msg_templates["mode_0_menu"],
            "email_sent_prompt": msg_templates["sent"],
            "wrong_code_prompt": msg_templates["wrong"],
            "welcome_message": msg_templates["welcome"],
            "countdown_warning_prompt": msg_templates["warning"],
            "failure_message": msg_templates["failure"],
            "kick_message": msg_templates["kick"],
            "return_user_message": msg_templates["return_user"]
        }

        self.db.save_all_config(config_to_save)
        logger.info("所有配置已保存到数据库")

        logger.info("插件初始化完成")

    async def _init_bg_pool(self, api_url):
        logger.info("开始初始化背景图连接池...")
        await init_image_pool(api_url, 5)
        logger.info("背景图连接池已就绪")

    async def _startup_check(self, host, port, user, pwd, encryption):
        logger.info("开始 SMTP 连通性检测...")
        await asyncio.sleep(2)
        ok = await init_smtp_check(host, port, user, pwd, encryption)
        if ok:
            logger.info("SMTP 连通性检测通过")
        else:
            logger.error("SMTP 连通性检测失败，请检查配置")

    def _is_group_enabled(self, gid):
        result = self.db.is_group_enabled(str(gid))
        logger.debug(f"群隔离检查 | group={gid} | enabled={result}")
        return result

    def _is_admin_user(self, uid):
        return self.db.is_admin(str(uid))

    def _is_group_admin_user(self, gid, uid):
        if self._is_admin_user(uid):
            return True
        return self.db.is_group_admin(str(gid), str(uid))

    def _extract_admin_command(self, text: str) -> str:
        if not text:
            return ""
        text = text.strip()
        text = re.sub(r'\[CQ:at,qq=\d+\](\s*)?', '', text)
        text = re.sub(r'@[\w\u4e00-\u9fa5]+(\s*)?', '', text)
        text = text.strip()
        if not text:
            return ""
        return text

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def handle_event(self, event: AstrMessageEvent):
        try:
            if event.get_platform_name() != "aiocqhttp":
                return
            if not event.message_obj or not event.message_obj.raw_message:
                return
            raw = event.message_obj.raw_message
            if not isinstance(raw, dict):
                return
            post_type = raw.get("post_type")
            gid = raw.get("group_id")

            if post_type == "notice":
                notice_type = raw.get("notice_type")
                if notice_type == "group_increase":
                    uid = str(raw.get("user_id"))
                    if uid == str(event.get_self_id()):
                        logger.debug(f"忽略机器人自身入群事件 | group={gid}")
                        return

                    logger.info(f"收到入群事件 | group={gid} | user={uid}")

                    if gid and not self._is_group_enabled(gid):
                        logger.info(f"群隔离拦截入群事件 | group={gid} | user={uid}")
                        return

                    await self.verification.new_member(event)
                elif notice_type == "group_decrease":
                    uid = str(raw.get("user_id"))
                    logger.info(f"收到退群事件 | group={gid} | user={uid}")
                    await self.verification.member_decrease(event)
            elif post_type == "message":
                if raw.get("message_type") == "group":
                    uid = str(event.get_sender_id())
                    is_admin = self._is_admin_user(uid)
                    is_group_admin = self._is_group_admin_user(gid, uid) if gid else False

                    if not is_admin and not is_group_admin and gid and not self._is_group_enabled(gid):
                        logger.info(f"群隔离拦截非管理员 | group={gid} | user={uid}")
                        return
                    text = event.message_str.strip() if event.message_str else ""
                    bot_id = str(event.get_self_id())
                    logger.debug(f"收到群消息 | group={gid} | user={uid} | text={text} | bot_id={bot_id}")

                    is_at_me = False
                    if isinstance(raw.get("message"), list):
                        for seg in raw.get("message"):
                            if seg.get("type") == "at" and str(seg.get("data", {}).get("qq")) == bot_id:
                                is_at_me = True
                                break

                    at_command = None
                    if is_at_me:
                        logger.debug(f"检测到艾特机器人 | user={uid} | text={text}")
                        at_command = self._extract_admin_command(text)
                        logger.info(f"提取管理员指令 | user={uid} | cmd={at_command}")

                    if (is_admin or is_group_admin) and is_at_me and at_command:
                        logger.info(f"管理员触发指令 | user={uid} | cmd={at_command}")
                        handled = await self.admin_handler.handle_command(event, uid, at_command, raw)
                        if handled:
                            event.stop_event()
                            return

                    await self.verification.handle_message(event)
                elif raw.get("message_type") == "private":
                    uid = str(event.get_sender_id())
                    text = event.message_str.strip() if event.message_str else ""
                    logger.debug(f"收到私信 | user={uid} | text={text}")
                    if self._is_admin_user(uid):
                        handled = await self.admin_handler.handle_command(event, uid, text, raw)
                        if handled:
                            event.stop_event()
        except Exception as e:
            logger.exception(f"事件处理异常 | error={e}")
```

---

## Task 11: 验证导入完整性

**Files:**
- Test: All modules

- [ ] **Step 1: 运行 Python 导入测试**

```python
import sys
sys.path.insert(0, '/workspace')

# 测试新的分层导入
try:
    from core.models.database import DatabaseManager
    print("✓ DatabaseManager imported successfully")
except Exception as e:
    print(f"✗ DatabaseManager import failed: {e}")

try:
    from core.services.verification import VerificationManager, generate_code
    print("✓ VerificationManager imported successfully")
except Exception as e:
    print(f"✗ VerificationManager import failed: {e}")

try:
    from core.services.admin import AdminHandler
    print("✓ AdminHandler imported successfully")
except Exception as e:
    print(f"✗ AdminHandler import failed: {e}")

try:
    from core.utils.logger import get_plugin_logger
    print("✓ get_plugin_logger imported successfully")
except Exception as e:
    print(f"✗ get_plugin_logger import failed: {e}")

try:
    from core.utils.email import async_send_verification, build_email_html_sync, init_smtp_check
    print("✓ Email utilities imported successfully")
except Exception as e:
    print(f"✗ Email utilities import failed: {e}")

try:
    from core.utils.image import init_image_pool, generate_code_image
    print("✓ Image utilities imported successfully")
except Exception as e:
    print(f"✗ Image utilities import failed: {e}")

try:
    from core.config import _flatten_config, merge_config, load_message_templates
    print("✓ Config module imported successfully")
except Exception as e:
    print(f"✗ Config module import failed: {e}")

# 测试向后兼容的导入
try:
    from core import VerificationManager, AdminHandler, DatabaseManager
    print("✓ Backward-compatible imports successful")
except Exception as e:
    print(f"✗ Backward-compatible imports failed: {e}")

print("\nImport test complete.")
```

- [ ] **Step 2: 保存为 test_imports.py 并运行**

```bash
cat > /workspace/test_imports.py << 'EOF'
import sys
sys.path.insert(0, '/workspace')

# 测试新的分层导入
try:
    from core.models.database import DatabaseManager
    print("✓ DatabaseManager imported successfully")
except Exception as e:
    print(f"✗ DatabaseManager import failed: {e}")

try:
    from core.services.verification import VerificationManager, generate_code
    print("✓ VerificationManager imported successfully")
except Exception as e:
    print(f"✗ VerificationManager import failed: {e}")

try:
    from core.services.admin import AdminHandler
    print("✓ AdminHandler imported successfully")
except Exception as e:
    print(f"✗ AdminHandler import failed: {e}")

try:
    from core.utils.logger import get_plugin_logger
    print("✓ get_plugin_logger imported successfully")
except Exception as e:
    print(f"✗ get_plugin_logger import failed: {e}")

try:
    from core.utils.email import async_send_verification, build_email_html_sync, init_smtp_check
    print("✓ Email utilities imported successfully")
except Exception as e:
    print(f"✗ Email utilities import failed: {e}")

try:
    from core.utils.image import init_image_pool, generate_code_image
    print("✓ Image utilities imported successfully")
except Exception as e:
    print(f"✗ Image utilities import failed: {e}")

try:
    from core.config import _flatten_config, merge_config, load_message_templates
    print("✓ Config module imported successfully")
except Exception as e:
    print(f"✗ Config module import failed: {e}")

# 测试向后兼容的导入
try:
    from core import VerificationManager, AdminHandler, DatabaseManager
    print("✓ Backward-compatible imports successful")
except Exception as e:
    print(f"✗ Backward-compatible imports failed: {e}")

print("\nImport test complete.")
EOF

python /workspace/test_imports.py
```

Expected: 所有 ✓ 检查通过，无错误

---

## Task 12: 删除旧文件

**Files:**
- Delete: `core/database.py`
- Delete: `core/verification.py`
- Delete: `core/admin_commands.py`
- Delete: `core/logger_setup.py`
- Delete: `core/email_utils.py`
- Delete: `test_imports.py`

- [ ] **Step 1: 删除旧文件**

```bash
rm -f /workspace/core/database.py \
      /workspace/core/verification.py \
      /workspace/core/admin_commands.py \
      /workspace/core/logger_setup.py \
      /workspace/core/email_utils.py \
      /workspace/test_imports.py
```

- [ ] **Step 2: 验证最终结构**

```bash
find /workspace/core -type f -name "*.py" | sort
```

Expected:
```
/workspace/core/__init__.py
/workspace/core/config.py
/workspace/core/models/__init__.py
/workspace/core/models/database.py
/workspace/core/services/__init__.py
/workspace/core/services/admin.py
/workspace/core/services/verification.py
/workspace/core/utils/__init__.py
/workspace/core/utils/email.py
/workspace/core/utils/image.py
/workspace/core/utils/logger.py
```

---

## Self-Review

**1. Spec coverage:** ✓ All requirements covered
- Directory restructuring ✓
- Layer separation ✓
- Backward compatibility ✓
- Functionality preservation ✓

**2. Placeholder scan:** ✓ No placeholders, all code complete
- All file paths are exact ✓
- All code blocks complete ✓
- All commands exact ✓

**3. Type consistency:** ✓ All names consistent
- Module names consistent ✓
- Import paths consistent ✓
- Function/class names preserved ✓
