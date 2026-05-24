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

        # 合并配置：优先使用面板配置，如果有则覆盖数据库配置
        merged_config = merge_config(db_config, flat_config)

        # 从配置文件迁移旧的管理员和群数据到数据库（向后兼容）
        config_enabled_groups = [str(g) for g in get_config_value(merged_config, "enabled_groups", [])]
        config_admin_qqs = [str(q) for q in get_config_value(merged_config, "admin_qqs", [])]
        
        # 迁移旧的管理员数据到新的数据库表
        for admin_qq in config_admin_qqs:
            if not self.db.is_admin(admin_qq):
                self.db.add_admin(admin_qq, added_by="config_migration", permission_level=2)
                logger.info(f"迁移旧配置管理员 | qq={admin_qq}")
        
        # 迁移旧的群数据到新的数据库表
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
        from_name = get_config_value(merged_config, "from_name", "QQ群验证助手")
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

        # 加载消息模板
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
        logger.info("VerificationManager初始化完成")

        # 初始化背景图连接池
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
        logger.info("AdminHandler初始化完成")

        asyncio.create_task(self._startup_check(smtp_host, smtp_port, smtp_user,
                                                smtp_password, smtp_encryption))
        
        # 保存所有配置到数据库
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
        logger.info("开始SMTP连通性检测...")
        await asyncio.sleep(2)
        ok = await init_smtp_check(host, port, user, pwd, encryption)
        if ok:
            logger.info("SMTP连通性检测通过")
        else:
            logger.error("SMTP连通性检测失败，请检查配置")

    def _is_group_enabled(self, gid):
        """检查群是否启用（使用新的数据库管理）"""
        result = self.db.is_group_enabled(str(gid))
        logger.debug(f"群隔离检查 | group={gid} | enabled={result}")
        return result
    
    def _is_admin_user(self, uid):
        """检查用户是否是管理员（使用新的数据库管理）"""
        return self.db.is_admin(str(uid))
    
    def _is_group_admin_user(self, gid, uid):
        """检查用户是否是群专属管理员或全局管理员"""
        if self._is_admin_user(uid):
            return True
        return self.db.is_group_admin(str(gid), str(uid))

    def _extract_admin_command(self, text: str) -> str:
        """从消息中提取管理员指令（去除艾特部分）"""
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
