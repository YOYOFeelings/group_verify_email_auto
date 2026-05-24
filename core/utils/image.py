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
