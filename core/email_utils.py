import smtplib
import asyncio
import re
import os
import random
import collections
import urllib.request
import urllib.error
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO

logger = logging.getLogger("GroupVerifyEmailAuto.email_utils")
SMTP_TIMEOUT = 5

# ==================== 验证码图片生成 ====================

_CODE_IMAGE_DIR = None


def set_code_image_dir(dir_path: str):
    global _CODE_IMAGE_DIR
    _CODE_IMAGE_DIR = dir_path
    os.makedirs(dir_path, exist_ok=True)
    logger.info(f"验证码图片目录已设置: {dir_path}")


def _find_font() -> str:
    """查找系统中可用的中文字体"""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
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
    # 尝试系统字体
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
    """获取指定大小的字体对象"""
    font_path = _find_font()
    try:
        if font_path:
            return ImageFont.truetype(font_path, size)
    except Exception as e:
        logger.warning(f"加载字体失败: {e}")
    return ImageFont.load_default()


def generate_code_image(code: str, uid: str = "") -> str:
    """
    生成一张美观的验证码图片，保存到本地文件
    返回图片文件的绝对路径
    """
    if _CODE_IMAGE_DIR is None:
        logger.error("验证码图片目录未设置")
        return ""

    # 图片尺寸
    width, height = 400, 160
    padding = 20

    # 创建画布 - 渐变色背景
    img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # 绘制渐变背景
    for y in range(height):
        r = int(30 + (y / height) * 50)
        g = int(120 + (y / height) * 70)
        b = int(200 + (y / height) * 55)
        draw.rectangle([(0, y), (width, y + 1)], fill=(r, g, b, 230))

    # 添加噪点（小圆点）
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

    # 添加干扰线
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

    # 在背景上绘制半透明的小字水印
    water_font = _get_font(12)
    for i in range(6):
        wx = random.randint(0, width - 50)
        wy = random.randint(0, height - 20)
        draw.text((wx, wy), "VERIFY", fill=(255, 255, 255, 30), font=water_font)

    # 绘制验证码数字 - 每个数字单独处理，增加随机偏移和旋转
    font_size = 60
    font = _get_font(font_size)
    code_str = str(code)
    total_width = 0
    char_imgs = []

    for i, ch in enumerate(code_str):
        try:
            ch_img = Image.new("RGBA", (font_size + 10, font_size + 10), (0, 0, 0, 0))
            ch_draw = ImageDraw.Draw(ch_img)

            # 每个数字颜色略有不同
            hue_offset = random.randint(-20, 20)
            ch_color = (
                min(255, max(0, 255 + hue_offset)),
                min(255, max(0, 255 - hue_offset)),
                255,
                240
            )

            ch_draw.text((5, 0), ch, fill=ch_color, font=font)

            # 随机旋转
            angle = random.randint(-15, 15)
            ch_img = ch_img.rotate(angle, expand=1, fillcolor=(0, 0, 0, 0))

            char_imgs.append(ch_img)
            total_width += ch_img.width
        except Exception:
            continue

    # 居中绘制所有数字
    img_count = max(len(char_imgs), 1)
    total_spacing = total_width + (img_count - 1) * 8
    start_x = (width - total_spacing) // 2
    y_offset = (height - font_size) // 2 - 5

    current_x = start_x
    for ch_img in char_imgs:
        img.paste(ch_img, (current_x, y_offset), ch_img)
        current_x += ch_img.width + 8

    # 添加底部的小标签文字
    try:
        label_font = _get_font(14)
        draw.text((width // 2 - 30, height - 25), "验证码", fill=(255, 255, 255, 100), font=label_font)
    except Exception:
        pass

    # 轻微的模糊效果增加美观度
    img = img.filter(ImageFilter.GaussianBlur(radius=0.5))

    # 保存图片
    filename = f"code_{uid}_{code}.png"
    save_path = os.path.join(_CODE_IMAGE_DIR, filename)
    img.save(save_path, "PNG")
    logger.info(f"验证码图片已生成: {save_path}")
    return save_path


def cleanup_code_image(image_path: str):
    """清理验证码图片文件"""
    try:
        if os.path.exists(image_path):
            os.remove(image_path)
            logger.debug(f"验证码图片已清理: {image_path}")
    except Exception as e:
        logger.error(f"清理验证码图片失败: {image_path} | {e}")

# ==================== 背景图连接池 ====================
_bg_pool_deque = collections.deque()
_bg_pool_lock = asyncio.Lock()
_bg_pool_filling = False
_bg_pool_ready = asyncio.Event()
_bg_pool_api_url = ""


def resolve_final_image_url(original_url: str, timeout: int = 2) -> str:
    """同步解析：获取重定向后的最终图片直链（供池填充使用）"""
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
        logger.error(f"[背景图] 解析失败 | source={original_url} | error={e}")
        return original_url


async def _fill_pool(api_url: str, count: int = 5):
    """后台任务：向池中补充 count 张已解析的图片链接"""
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
    """插件启动时调用，初始化图片池并等待第一批图片就绪"""
    global _bg_pool_api_url
    _bg_pool_api_url = api_url
    async with _bg_pool_lock:
        _bg_pool_deque.clear()
    await _fill_pool(api_url, count)
    _bg_pool_ready.set()
    logger.info(f"[图片池] 初始化完成，已就绪 {len(_bg_pool_deque)} 张背景图")


async def get_next_bg_url(api_url: str) -> str:
    """
    从池中获取下一个背景图链接。若池空则临时解析一个。
    当剩余 <= 2 时自动触发补充 5 张。
    """
    if not api_url or not api_url.startswith("http"):
        return api_url

    # 等待首次初始化完成（最长 10 秒）
    if not _bg_pool_ready.is_set():
        try:
            await asyncio.wait_for(_bg_pool_ready.wait(), timeout=10)
        except asyncio.TimeoutError:
            logger.warning("[图片池] 等待初始化超时，将临时解析一张")

    # 检查补充条件
    async with _bg_pool_lock:
        need_refill = (len(_bg_pool_deque) <= 2) and not _bg_pool_filling
    if need_refill:
        asyncio.create_task(_fill_pool(api_url, 5))

    # 取出一个链接
    async with _bg_pool_lock:
        if _bg_pool_deque:
            url = _bg_pool_deque.popleft()
            logger.info(f"[图片池] 取出背景图，剩余 {len(_bg_pool_deque)} 张")
            return url

    # 池空时的应急方案
    logger.info("[图片池] 池空，临时解析一张背景图")
    return await asyncio.to_thread(resolve_final_image_url, api_url)

# ==================== 邮件构建 ====================


def build_email_html_sync(template: str, final_bg_url: str, group_name: str,
                          member_name: str, code: str, timeout_min: int) -> str:
    """同步构造验证邮件HTML，final_bg_url 为最终背景图链接（可空）"""
    logger.debug(f"构造邮件HTML | final_bg={final_bg_url} | group={group_name} | code={code}")
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
        html = html.replace('background="{bg_url}"', '')
        html = html.replace("background-image:url('{bg_url}');", '')

    html = html.replace('{card_style}', card_style)
    html = html.format(
        group_name=group_name,
        member_name=member_name,
        code=code,
        timeout=timeout_min,
        bg_url=final_bg_url if bg_valid else ''
    )
    logger.debug(f"最终HTML长度: {len(html)}")
    return html

# ==================== SMTP 发送 ====================


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
    except Exception as e:
        logger.exception(f"邮件发送失败 | to={to} | error={e}")
        raise
    finally:
        if server:
            server.quit()


async def async_send_verification(host, port, user, pwd, encryption, from_name, to, subject,
                                  html, bg_url="", use_glass=False):
    logger.info(f"异步发送验证邮件 | to={to} | subject={subject}")
    try:
        await asyncio.to_thread(send_email_sync, host, port, user, pwd, encryption,
                                from_name, to, subject, html)
        return True
    except Exception as e:
        logger.error(f"异步邮件发送异常 | {e}")
        return False


async def async_send_log_attachment(host, port, user, pwd, encryption, from_name, to, subject,
                                    body, file_path, fname, bg_url="", use_glass=False):
    logger.info(f"发送日志附件 | to={to} | file={file_path}")
    msg = MIMEMultipart()
    msg["From"] = formataddr((from_name, user))
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html", "utf-8"))
    with open(file_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=("utf-8", "", fname))
        msg.attach(part)
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
            server.quit()


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
