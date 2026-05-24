import re
import asyncio
import smtplib
import logging
import html
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

    html_content = template

    if not bg_valid:
        html_content = re.sub(r'background="\{bg_url\}"', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r"background-image\s*:\s*url\s*\(\s*['\"]?\{bg_url\}['\"]?\s*\)\s*;", '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'background\s*:\s*[^;]*\{bg_url\}[^;]*;', '', html_content, flags=re.IGNORECASE)

    html_content = html_content.replace('{card_style}', card_style)

    safe_member_name = html.escape(member_name) if member_name else member_name
    safe_group_name = html.escape(group_name) if group_name else group_name

    try:
        html_content = html_content.format(
            group_name=safe_group_name,
            member_name=safe_member_name,
            code=code,
            timeout=timeout_min,
            bg_url=final_bg_url if bg_valid else ''
        )
    except KeyError as e:
        logger.warning(f"模板变量替换失败，尝试备用方案: {e}")
        html_content = html_content.replace('{group_name}', safe_group_name)
        html_content = html_content.replace('{member_name}', safe_member_name)
        html_content = html_content.replace('{code}', code)
        html_content = html_content.replace('{timeout}', str(timeout_min))
        html_content = html_content.replace('{bg_url}', final_bg_url if bg_valid else '')

    logger.debug(f"最终HTML长度: {len(html_content)}")
    return html_content


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
            except:
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
