import os
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

DATA_DIR = StarTools.get_data_dir("group_verify_email_auto")
os.makedirs(DATA_DIR, exist_ok=True)
get_plugin_logger(log_dir=DATA_DIR)
logger = logging.getLogger("GroupVerifyEmailAuto.main")


def _fix_newlines(s: str) -> str:
    if not isinstance(s, str):
        return s
    return s.replace('\\n', '\n')


def _flatten_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """将分组配置扁平化为一级配置"""
    if not config:
        return {}
    result = {}
    for key, value in config.items():
        if isinstance(value, dict) and "items" in value:
            for sub_key, sub_value in value.get("items", {}).items():
                result[sub_key] = sub_value.get("default")
        elif isinstance(value, dict) and "default" in value:
            result[key] = value["default"]
        else:
            result[key] = value
    return result


@register("group_verify_email_auto", "感情", "QQ群邮箱验证码插件", "1.8",
          "https://github.com/YOYOFeelings/group_verify_email_auto")
class GroupVerifyEmailAuto(Star):
    def __init__(self, context: Context, config: Dict[str, Any]):
        super().__init__(context)
        self.context = context
        logger.info("插件初始化开始 (v1.8)")

        # 扁平化配置
        flat_config = _flatten_config(config)
        
        def get_conf(key, default=None):
            val = flat_config.get(key, default)
            return _fix_newlines(val) if isinstance(val, str) else val

        self.enabled_groups = [str(g) for g in get_conf("enabled_groups", [])]
        self.admin_qqs = [str(q) for q in get_conf("admin_qqs", [])]
        self.verification_mode = int(get_conf("verification_mode", 0))
        logger.info(f"配置加载 | enabled_groups={self.enabled_groups} | admin_qqs={self.admin_qqs} | mode={self.verification_mode}")

        # 初始化数据库
        db_path = os.path.join(DATA_DIR, "verification.db")
        self.db = DatabaseManager(db_path)
        logger.info("数据库初始化完成")

        smtp_host = get_conf("smtp_host", "smtp.qq.com")
        smtp_port = int(get_conf("smtp_port", 465))
        smtp_user = get_conf("smtp_user", "")
        smtp_password = get_conf("smtp_password", "")
        smtp_encryption = get_conf("smtp_encryption", "ssl")
        from_name = get_conf("from_name", "Q群验证助手")
        logger.info(f"SMTP配置 | host={smtp_host} | port={smtp_port} | user={smtp_user}")

        email_domain = get_conf("email_domain", "@qq.com")
        email_subject = get_conf("email_subject", "{group_name} 入群验证码")
        template_choice = int(get_conf("email_template_choice", 1))
        
        if template_choice == 0:
            email_body = get_conf("email_body_html", "...")
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
                email_body = get_conf("email_body_html", "...")
                logger.warning(f"模板文件不存在: {template_filename}")
        
        logger.info(f"邮箱配置 | domain={email_domain} | template={template_choice}")

        verify_timeout = int(get_conf("verification_timeout", 600))
        warning_time = int(get_conf("kick_countdown_warning_time", 120))
        kick_delay = int(get_conf("kick_delay", 10))
        cooldown = int(get_conf("email_cooldown", 60))
        logger.info(f"时间配置 | timeout={verify_timeout}s | cooldown={cooldown}s")

        enable_welcome_image = get_conf("enable_welcome_image", False)
        welcome_image = get_conf("welcome_image", "")
        enable_email_bg_image = get_conf("enable_email_background_image", False)
        email_bg_url = get_conf("email_background_image_url", "") if enable_email_bg_image else ""
        enable_return_skip = get_conf("enable_return_user_skip", True)
        logger.info(f"图片配置 | welcome={enable_welcome_image} | bg={enable_email_bg_image} | return_skip={enable_return_skip}")

        msg_templates = {
            "trigger": get_conf("trigger_prompt", "..."),
            "mode_0_menu": get_conf("mode_0_menu_prompt", "..."),
            "sent": get_conf("email_sent_prompt", "..."),
            "wrong": get_conf("wrong_code_prompt", "..."),
            "welcome": get_conf("welcome_message", "..."),
            "warning": get_conf("countdown_warning_prompt", "..."),
            "failure": get_conf("failure_message", "..."),
            "kick": get_conf("kick_message", "..."),
            "return_user": get_conf("return_user_message", "...")
        }
        logger.info("消息模板加载完成")

        smtp_cfg = {"host": smtp_host, "port": smtp_port, "user": smtp_user,
                    "password": smtp_password, "encryption": smtp_encryption,
                    "from_name": from_name}
        email_cfg = {"domain": email_domain, "subject": email_subject, "body": email_body}
        time_cfg = {"timeout": verify_timeout, "warning": warning_time,
                    "kick_delay": kick_delay, "cooldown": cooldown}

        self.verification = VerificationManager(
            smtp_cfg, email_cfg, time_cfg, msg_templates,
            self.context,
            admin_qqs=self.admin_qqs,
            enable_welcome_image=enable_welcome_image,
            welcome_image=welcome_image,
            email_bg_url=email_bg_url,
            verification_mode=self.verification_mode,
            enable_return_skip=enable_return_skip,
            db_manager=self.db,
            data_dir=DATA_DIR
        )
        logger.info("VerificationManager 初始化完成")

        # 初始化背景图连接池
        if enable_email_bg_image and email_bg_url:
            asyncio.create_task(self._init_bg_pool(email_bg_url))

        async def _add_pending_cb(uid, gid, email, code):
            await self.verification.manual_add(uid, gid, email, code, nickname="管理员")

        log_file_path = os.path.join(DATA_DIR, "email_verify.log")
        self.admin_handler = AdminHandler(
            self.admin_qqs, smtp_cfg, email_cfg, time_cfg, msg_templates,
            _add_pending_cb,
            verification_manager=self.verification,
            log_file_path=log_file_path,
            db_manager=self.db
        )
        logger.info("AdminHandler 初始化完成")

        asyncio.create_task(self._startup_check(smtp_host, smtp_port, smtp_user,
                                                smtp_password, smtp_encryption))
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
        result = not self.enabled_groups or str(gid) in self.enabled_groups
        logger.debug(f"检查群启用状态 | group={gid} | enabled={result}")
        return result

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def handle_event(self, event: AstrMessageEvent):
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
                if gid and not self._is_group_enabled(gid):
                    return
                uid = str(raw.get("user_id"))
                if uid == str(event.get_self_id()):
                    return
                logger.info(f"收到入群事件 | group={gid} | user={uid}")
                await self.verification.new_member(event)
            elif notice_type == "group_decrease":
                uid = str(raw.get("user_id"))
                logger.info(f"收到退群事件 | group={gid} | user={uid}")
                await self.verification.member_decrease(event)
        elif post_type == "message":
            if raw.get("message_type") == "group":
                if gid and not self._is_group_enabled(gid):
                    return
                uid = str(event.get_sender_id())
                text = event.message_str.strip() if event.message_str else ""
                logger.debug(f"收到群消息 | group={gid} | user={uid} | text={text}")
                if self.admin_handler.is_admin(uid):
                    handled = await self.admin_handler.handle_command(event, uid, text, raw)
                    if handled:
                        event.stop_event()
                        return
                await self.verification.handle_message(event)
            elif raw.get("message_type") == "private":
                uid = str(event.get_sender_id())
                text = event.message_str.strip() if event.message_str else ""
                logger.debug(f"收到私信 | user={uid} | text={text}")
                if self.admin_handler.is_admin(uid):
                    handled = await self.admin_handler.handle_command(event, uid, text, raw)
                    if handled:
                        event.stop_event()
