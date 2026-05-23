from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger
from astrbot.core.star.star_tools import StarTools
import os
import asyncio
from typing import Dict, Any

from .core import VerificationManager, EmailSender

DATA_DIR = StarTools.get_data_dir("group_verify_email_auto")
os.makedirs(DATA_DIR, exist_ok=True)

def get_conf(config: Dict[str, Any], key: str, default: Any) -> Any:
    """获取配置"""
    return config.get(key, default)

@filter.command_group("verify")
def verify_group():
    """验证相关命令组"""
    pass

class GroupVerifyEmailAuto(Star):
    """QQ群邮箱验证码插件"""
    
    def __init__(self, context: Context):
        super().__init__(context)
        self.context = context
        self.verification_manager: VerificationManager = None
        self.email_sender: EmailSender = None
        self.config: Dict[str, Any] = {}
        self.admin_qqs: list = []
        self.enabled_groups: list = []
        
    async def initialize(self):
        """插件初始化"""
        config = await self.context.get_plugin_config()
        self.config = config or {}
        
        enabled_groups = get_conf(config, 'enabled_groups', [])
        admin_qqs = get_conf(config, 'admin_qqs', [])
        self.enabled_groups = [str(g) for g in enabled_groups]
        self.admin_qqs = [str(q) for q in admin_qqs]
        
        smtp_host = get_conf(config, 'smtp_host', 'smtp.qq.com')
        smtp_port = get_conf(config, 'smtp_port', 465)
        smtp_user = get_conf(config, 'smtp_user', '')
        smtp_password = get_conf(config, 'smtp_password', '')
        smtp_encryption = get_conf(config, 'smtp_encryption', 'ssl')
        from_name = get_conf(config, 'from_name', '验证助手')
        
        timeout = get_conf(config, 'verification_timeout', 600)
        self.verification_manager = VerificationManager(timeout=timeout)
        
        if smtp_user and smtp_password:
            self.email_sender = EmailSender(
                host=smtp_host,
                port=smtp_port,
                user=smtp_user,
                password=smtp_password,
                encryption=smtp_encryption,
                from_name=from_name
            )
        
        logger.info(f"[GroupVerifyEmailAuto] 插件初始化完成")
    
    def is_admin(self, uid: str) -> bool:
        """检查是否为管理员"""
        return str(uid) in self.admin_qqs
    
    def is_group_enabled(self, gid: str) -> bool:
        """检查群是否启用"""
        return not self.enabled_groups or str(gid) in self.enabled_groups
    
    @verify_group.command("test")
    async def test_handler(self, event: AstrMessageEvent):
        """测试命令"""
        if not self.is_admin(event.get_sender_id()):
            yield event.plain_result("❌ 此命令仅管理员可用")
            return
        
        if not self.email_sender:
            yield event.plain_result("❌ 邮件功能未配置")
            return
        
        yield event.plain_result("✅ 插件运行正常，邮件功能已就绪")
    
    @verify_group.command("status")
    async def status_handler(self, event: AstrMessageEvent):
        """查看状态"""
        if not self.is_admin(event.get_sender_id()):
            yield event.plain_result("❌ 此命令仅管理员可用")
            return
        
        pending_count = len(self.verification_manager.pending)
        status = f"""📊 插件状态:
- 待验证用户: {pending_count}
- 管理员数量: {len(self.admin_qqs)}
- 启用群数量: {len(self.enabled_groups) if self.enabled_groups else '全部群'}"""
        
        yield event.plain_result(status)
    
    @verify_group.command("reload")
    async def reload_handler(self, event: AstrMessageEvent):
        """重载配置"""
        if not self.is_admin(event.get_sender_id()):
            yield event.plain_result("❌ 此命令仅管理员可用")
            return
        
        await self.initialize()
        yield event.plain_result("✅ 配置已重载")
    
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all_events(self, event: AstrMessageEvent):
        """处理所有事件"""
        raw = event.message_obj.raw_message
        if not isinstance(raw, dict):
            return
        
        notice_type = raw.get("notice_type")
        if notice_type != "group_increase":
            return
        
        gid = str(raw.get("group_id"))
        uid = str(raw.get("user_id"))
        
        if uid == str(event.get_self_id()):
            return
        
        if not self.is_group_enabled(gid):
            return
        
        logger.info(f"[GroupVerifyEmailAuto] 新用户入群: {uid} in {gid}")
    
    async def terminate(self):
        """插件卸载时调用"""
        logger.info("[GroupVerifyEmailAuto] 插件已卸载")
