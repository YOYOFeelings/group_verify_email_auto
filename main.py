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
        logger.debug("传入的配置为空，返回空字典")
        return {}
    
    logger.debug(f"开始扁平化配置 | 原始配置: {config}")
    result = {}
    
    def process_dict(d: Dict[str, Any], prefix: str = ""):
        """递归处理配置字典"""
        for key, value in d.items():
            logger.debug(f"处理键: {prefix}{key} | 类型: {type(value)} | 值: {value}")
            if isinstance(value, dict):
                # 检查是否是配置项类型
                if "type" in value:
                    value_type = value["type"]
                    if value_type == "object" and "items" in value:
                        # 这是分组配置，继续处理 items
                        logger.debug(f"发现 object 分组: {prefix}{key}，继续处理 items")
                        if isinstance(value["items"], dict):
                            process_dict(value["items"], prefix)
                        continue
                    elif value_type == "list":
                        # 列表类型配置项 - 修复：先检查 items 是否为数组
                        if "items" in value and isinstance(value["items"], list):
                            # items 是数组（如枚举选项），保存整个配置结构
                            result[key] = value
                            logger.debug(f"添加列表类型配置(数组 items): {key}")
                            continue
                        elif "items" in value and isinstance(value["items"], dict):
                            # items 是对象（如 schema），递归处理
                            process_dict(value["items"], prefix)
                            continue
                    # 其他类型或有 default 的情况 - 继续执行下面的 default 处理
                    
                    if "default" in value:
                        # 这是单个配置项，从 default 获取值
                        default_val = value["default"]
                        result[key] = default_val
                        logger.debug(f"添加配置项: {key} = {default_val} (类型: {type(default_val)})")
                    else:
                        # 没有 default 的配置项，保存原始值
                        result[key] = value
                        logger.debug(f"添加配置项(无 default): {key} = {value}")
                elif "default" in value:
                    # 直接有 default 的配置
                    default_val = value["default"]
                    result[key] = default_val
                    logger.debug(f"添加配置项(直接 default): {key} = {default_val} (类型: {type(default_val)})")
                elif "items" in value:
                    # 直接有 items 的配置（没有 type）
                    logger.debug(f"发现 items 分组: {prefix}{key}，继续处理")
                    if isinstance(value["items"], dict):
                        process_dict(value["items"], prefix)
                else:
                    # 普通的配置项，直接添加
                    result[key] = value
                    logger.debug(f"添加普通配置: {key} = {value}")
            else:
                # 直接添加值
                result[key] = value
                logger.debug(f"添加直接值: {key} = {value} (类型: {type(value)})")
    
    process_dict(config)
    logger.info(f"扁平化配置完成 | 配置项数量: {len(result)}")
    logger.debug(f"扁平化配置结果: {result}")
    return result


@register("group_verify_email_auto", "感情", "QQ群邮箱验证码插件", "1.12.1",
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
        # 注意：这样确保用户在面板的修改能立即生效
        merged_config = db_config.copy()
        merged_config.update(flat_config)

        def get_conf(key, default=None):
            val = merged_config.get(key, default)
            return _fix_newlines(val) if isinstance(val, str) else val

        self.enabled_groups = [str(g) for g in get_conf("enabled_groups", [])]
        self.admin_qqs = [str(q) for q in get_conf("admin_qqs", [])]
        self.verification_mode = int(get_conf("verification_mode", 0))
        logger.info(f"配置加载 | enabled_groups={self.enabled_groups} | admin_qqs={self.admin_qqs} | mode={self.verification_mode}")

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

        # 定义默认消息模板，防止配置读取失败
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
        
        msg_templates = {
            "trigger": get_conf("trigger_prompt", DEFAULT_TEMPLATES["trigger"]),
            "mode_0_menu": get_conf("mode_0_menu_prompt", DEFAULT_TEMPLATES["mode_0_menu"]),
            "sent": get_conf("email_sent_prompt", DEFAULT_TEMPLATES["sent"]),
            "wrong": get_conf("wrong_code_prompt", DEFAULT_TEMPLATES["wrong"]),
            "welcome": get_conf("welcome_message", DEFAULT_TEMPLATES["welcome"]),
            "warning": get_conf("countdown_warning_prompt", DEFAULT_TEMPLATES["warning"]),
            "failure": get_conf("failure_message", DEFAULT_TEMPLATES["failure"]),
            "kick": get_conf("kick_message", DEFAULT_TEMPLATES["kick"]),
            "return_user": get_conf("return_user_message", DEFAULT_TEMPLATES["return_user"])
        }
        
        # 记录加载的模板
        for key, value in msg_templates.items():
            logger.debug(f"消息模板[{key}] 长度: {len(str(value))} | 内容: {str(value)[:50]}...")
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
        
        # 保存所有配置到数据库
        config_to_save = {
            "enabled_groups": self.enabled_groups,
            "admin_qqs": self.admin_qqs,
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
        if not self.enabled_groups:
            logger.debug(f"群隔离检查 | group={gid} | enabled=True (全群生效)")
            return True
        result = str(gid) in self.enabled_groups
        logger.debug(f"群隔离检查 | group={gid} | enabled={result} | whitelist={self.enabled_groups}")
        return result

    def _extract_admin_command(self, text: str) -> str:
        """从消息中提取管理员指令（去除艾特部分），改进正则匹配"""
        if not text:
            return ""
        text = text.strip()
        # 修复：更全面的 CQ 码匹配，支持 at 后可能有空格或换行 - 2026-05-23
        text = re.sub(r'\[CQ:at,qq=\d+\](\s*)?', '', text)
        # 匹配 @昵称（中文、英文、数字、下划线等），并移除后面的空白
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
                    # 修复：管理员指令不受群隔离限制 - 2026-05-23
                    is_admin = self.admin_handler.is_admin(uid)
                    if not is_admin and gid and not self._is_group_enabled(gid):
                        logger.info(f"群隔离拦截非管理员 | group={gid} | user={uid}")
                        return
                    text = event.message_str.strip() if event.message_str else ""
                    bot_id = str(event.get_self_id())
                    logger.debug(f"收到群消息 | group={gid} | user={uid} | text={text} | bot_id={bot_id}")
                    
                    is_at_me = False
                    at_command = None
                    if isinstance(raw.get("message"), list):
                        for seg in raw.get("message"):
                            if seg.get("type") == "at" and str(seg.get("data", {}).get("qq")) == bot_id:
                                is_at_me = True
                                break
                    
                    if is_at_me:
                        logger.debug(f"检测到艾特机器人 | user={uid} | text={text}")
                        at_command = self._extract_admin_command(text)
                        logger.info(f"提取管理员指令 | user={uid} | cmd={at_command}")
                    
                    if self.admin_handler.is_admin(uid) and is_at_me and at_command:
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
                    if self.admin_handler.is_admin(uid):
                        handled = await self.admin_handler.handle_command(event, uid, text, raw)
                        if handled:
                            event.stop_event()
        except Exception as e:
            logger.exception(f"事件处理异常 | error={e}")
