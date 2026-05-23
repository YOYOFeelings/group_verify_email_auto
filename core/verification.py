import os
import asyncio
import re
import time
import random
import secrets  # 安全加固：用于生成密码学安全的随机验证码 - 2026-05-23
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from .email_utils import async_send_verification, build_email_html_sync, get_next_bg_url
from astrbot.api.message_components import At, Plain, Image

VERIFY_CODE_LENGTH = 6  # 安全加固：验证码位数常量 - 2026-05-23

logger = logging.getLogger("GroupVerifyEmailAuto.verification")


def generate_code():
    # 安全加固：使用 secrets 模块生成密码学安全的随机验证码 - 2026-05-23
    return str(secrets.randbelow(900000) + 100000)


def _safe_format(s: str, **kwargs) -> str:
    """安全格式化字符串"""
    if not s:
        logger.warning("收到空字符串，返回默认消息")
        return "请查看消息"
    
    if not isinstance(s, str):
        s = str(s)
        
    try:
        result = s.format(**kwargs)
        if not result or result.isspace():
            logger.warning("格式化后结果为空，返回原始字符串")
            return s
        return result
    except KeyError as e:
        logger.warning(f"变量缺失：{e}，使用正则替换")
        def _repl(m):
            key = m.group(1)
            value = kwargs.get(key, m.group(0))
            return str(value)
        result = re.sub(r'\{(\w+)\}', _repl, s)
        if not result or result.isspace():
            return s
        return result
    except Exception as e:
        logger.error(f"格式化字符串失败 | 原始值: {s} | 错误: {e}")
        if not s or s.isspace():
            return "请查看消息"
        return s


class VerificationManager:
    def __init__(self, smtp_config, email_config, time_config, msg_templates, context,
                 admin_qqs: Optional[List[str]] = None,
                 enable_welcome_image: bool = False, welcome_image: str = "",
                 email_bg_url: str = "",
                 verification_mode: int = 0,
                 enable_return_skip: bool = True,
                 db_manager=None,
                 data_dir: str = ""):
        self.smtp_host = smtp_config["host"]
        self.smtp_port = smtp_config["port"]
        self.smtp_user = smtp_config["user"]
        self.smtp_password = smtp_config["password"]
        self.smtp_encryption = smtp_config["encryption"]
        self.from_name = smtp_config["from_name"]
        self.email_domain = email_config["domain"]
        self.email_subject = email_config["subject"]
        self.email_body = email_config["body"]
        self.verify_timeout = time_config["timeout"]
        self.warning_time = time_config["warning"]
        self.kick_delay = time_config["kick_delay"]
        self.cooldown = time_config["cooldown"]
        self.trigger_prompt = msg_templates.get("trigger", "")
        self.mode_0_menu_prompt = msg_templates.get("mode_0_menu", "")
        self.sent_prompt = msg_templates.get("sent", "")
        self.wrong_prompt = msg_templates.get("wrong", "")
        self.welcome_msg = msg_templates.get("welcome", "")
        self.warning_msg = msg_templates.get("warning", "")
        self.failure_msg = msg_templates.get("failure", "")
        self.kick_msg = msg_templates.get("kick", "")
        self.return_user_msg = msg_templates.get("return_user", "")
        self.admin_qqs = set(admin_qqs) if admin_qqs else set()
        self.enable_welcome_image = enable_welcome_image
        self.welcome_image = welcome_image
        self.email_bg_url = email_bg_url
        self.verification_mode = verification_mode
        self.enable_return_skip = enable_return_skip
        self.db = db_manager
        self.context = context
        self.pending: Dict[str, dict] = {}
        self.pending_mode: Dict[str, int] = {}
        self.math_pending: Dict[str, dict] = {}
        self.last_request: Dict[str, float] = {}
        self._group_info_cache: Dict[str, dict] = {}
        self._group_cache_ttl = 120
        
        # 记录加载的模板
        logger.info(f"VerificationManager初始化 | mode={verification_mode}")
        logger.debug(f"trigger_prompt: {self.trigger_prompt[:50]}...")
        logger.debug(f"mode_0_menu_prompt: {self.mode_0_menu_prompt[:50]}...")
        logger.debug(f"sent_prompt: {self.sent_prompt[:50]}...")
        logger.debug(f"welcome_msg: {self.welcome_msg[:50]}...")
        
        # 如果模板为空，设置默认值
        if not self.trigger_prompt:
            self.trigger_prompt = "{at_user} 欢迎加入本群！\n本群当前共 {group_member_count} 位群友\n管理员列表：\n{admin_list}\n请 @我 并回复任意消息以接收验证码到您的 QQ 邮箱。"
        if not self.mode_0_menu_prompt:
            self.mode_0_menu_prompt = "{at_user} 欢迎加入本群！🎉\n本群当前共 {group_member_count} 位群友\n管理员列表：\n{admin_list}\n请 @我 并回复数字选择验证方式：\n1 - 邮箱验证\n2 - 数学题验证"
        if not self.sent_prompt:
            self.sent_prompt = "{at_user} 验证码已发送到 {email}\n请查看邮件并在群内 @我 回复数字验证码。"
        if not self.welcome_msg:
            self.welcome_msg = "{at_user} 验证成功，欢迎您的加入！🎉\n本群当前共 {group_member_count} 位群友\n管理员：\n{admin_list}"
        if not self.return_user_msg:
            self.return_user_msg = "{at_user} 欢迎回来！{member_name}\n\n检测到您之前已经入过群并且验证成功过，\n本次将为您跳过验证流程。\n\n🎉 欢迎重新加入 {group_name}！"

    async def _get_group_info(self, event, gid):
        """获取群信息（带缓存）"""
        now = time.time()
        cached = self._group_info_cache.get(str(gid))
        if cached and (now - cached["time"]) < self._group_cache_ttl:
            return cached
        
        info = {"member_count": "?", "admins": "无", "name": "本群"}
        try:
            group_info = await event.bot.api.call_action("get_group_info", group_id=gid)
            if group_info:
                info["member_count"] = str(group_info.get("member_count", "?"))
                info["name"] = group_info.get("group_name", "本群")
        except Exception as e:
            logger.warning(f"获取群信息失败 | group={gid} | error={e}")
        
        try:
            members = await event.bot.api.call_action("get_group_member_list", group_id=gid)
            admin_names = []
            if members:
                for m in members:
                    role = m.get("role", "")
                    if role in ("admin", "owner"):
                        card = m.get("card") or m.get("nickname", "")
                        if card:
                            admin_names.append(card)
            if admin_names:
                info["admins"] = "\n".join(admin_names)
        except Exception as e:
            logger.warning(f"获取管理员列表失败 | error={e}")
        
        info["time"] = now
        self._group_info_cache[str(gid)] = info
        return info

    def _format_msg(self, template: str, **kwargs):
        """格式化消息模板"""
        kwargs.setdefault("at_user", "")
        kwargs.setdefault("member_name", "")
        kwargs.setdefault("group_name", "本群")
        kwargs.setdefault("group_member_count", "?")
        kwargs.setdefault("admin_list", "无")
        kwargs.setdefault("email", "")
        kwargs.setdefault("timeout", str(self.verify_timeout // 60))
        kwargs.setdefault("countdown", "")
        kwargs.setdefault("code", "")
        return _safe_format(template, **kwargs)

    def _can_send(self, uid):
        now = time.time()
        last = self.last_request.get(uid, 0)
        if now - last < self.cooldown:
            logger.info(f"冷却中 | user={uid}")
            return False
        self.last_request[uid] = now
        return True

    def _generate_math_problem(self):
        op_type = random.choice(['add', 'sub'])
        if op_type == 'add':
            num1 = random.randint(0, 100)
            num2 = random.randint(0, 100 - num1)
            answer = num1 + num2
            return f"{num1} + {num2} = ?", answer
        else:
            num1 = random.randint(1, 100)
            num2 = random.randint(0, num1)
            answer = num1 - num2
            return f"{num1} - {num2} = ?", answer

    async def manual_add(self, uid: str, gid: int, email: str, code: str, nickname: str = ""):
        logger.info(f"手动添加待验证 | user={uid} | group={gid} | email={email}")
        if uid in self.pending:
            old = self.pending[uid].get("task")
            if old and not old.done():
                old.cancel()
        is_admin = uid in self.admin_qqs
        join_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task = asyncio.create_task(asyncio.sleep(0)) if is_admin else asyncio.create_task(self._timeout_kick(uid, gid, nickname))
        self.pending[uid] = {"gid": gid, "email": email, "code": code, "task": task, "time": time.time(), "join_time": join_time}
        logger.info(f"待验证队列添加成功 | user={uid}")

    async def new_member(self, event):
        raw = event.message_obj.raw_message
        uid = str(raw.get("user_id"))
        gid = raw.get("group_id")
        nickname = uid
        try:
            info = await event.bot.api.call_action("get_group_member_info", group_id=gid, user_id=int(uid))
            nickname = info.get("card") or info.get("nickname", uid)
        except Exception as e:
            logger.warning(f"获取昵称失败 | user={uid} | error={e}")
        
        logger.info(f"新成员入群事件 | group={gid} | user={uid} | nickname={nickname}")
        
        group_info = await self._get_group_info(event, gid)
        group_name = group_info.get("name", "本群")
        member_count = group_info.get("member_count", "?")
        admin_list = group_info.get("admins", "无")
        
        logger.debug(f"检查回归用户 | user={uid} | group={gid} | enable_return_skip={self.enable_return_skip} | db={bool(self.db)}")
        
        # 检查是否启用回归用户跳过
        if self.enable_return_skip and self.db:
            history = self.db.check_user_history(uid, str(gid))
            if history and history.get("verification_result") == 1:
                # 用户之前验证成功过，跳过验证
                logger.info(f"检测到回归用户，自动跳过验证 | user={uid} | group={gid}")
                msg = self._format_msg(self.return_user_msg, member_name=nickname,
                                      group_name=group_name, group_member_count=member_count,
                                      admin_list=admin_list)
                segs = [At(qq=int(uid)), Plain(" " + msg)]
                if self.enable_welcome_image and self.welcome_image:
                    logger.info(f"尝试添加欢迎图片 | path={self.welcome_image}")
                    try:
                        if self.welcome_image.startswith(("http://", "https://")):
                            logger.debug(f"使用网络图片URL")
                            segs.append(Image.fromURL(self.welcome_image))
                        else:
                            logger.debug(f"使用本地文件 | exists={os.path.exists(self.welcome_image)}")
                            segs.append(Image.fromFileSystem(self.welcome_image))
                        logger.info(f"欢迎图片添加成功")
                    except Exception as e:
                        logger.error(f"欢迎图片失败: {e}", exc_info=True)
                await event.send(event.chain_result(segs))
                
                # 记录到数据库
                self.db.add_verification_record(uid, str(gid), verification_mode=0,
                                               user_nickname=nickname, group_name=group_name)
                self.db.update_verification_result(uid, str(gid), history.get("join_time", ""), 1,
                                                  email=history.get("email"))
                return
        
        logger.debug(f"创建验证记录 | user={uid} | group={gid} | mode={self.verification_mode}")
        
        # 记录到数据库
        record_id = None
        join_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if self.db:
            record_id = self.db.add_verification_record(uid, str(gid), self.verification_mode,
                                                        nickname, group_name)
        
        # 统一创建超时踢出任务（所有模式都需要）
        if uid in self.pending:
            old = self.pending[uid].get("task")
            if old and not old.done():
                old.cancel()
        task = asyncio.create_task(self._timeout_kick(uid, gid, nickname))
        
        pending_entry = {"gid": gid, "email": None, "code": None,
                        "task": task, "time": time.time(),
                        "join_time": join_time}
        if record_id:
            pending_entry["record_id"] = record_id
        self.pending[uid] = pending_entry
        
        logger.info(f"新成员入群验证启动 | group={gid} | user={uid} | mode={self.verification_mode}")
        
        if self.verification_mode == 2:
            logger.debug(f"使用数学题验证模式")
            q, a = self._generate_math_problem()
            self.math_pending[uid] = {"answer": a, "gid": gid}
            timeout_min = self.verify_timeout // 60
            msg = self._format_msg("请在 {timeout} 分钟内 @我 并回答以下问题完成验证：\n" + q,
                                    timeout=str(timeout_min))
            segs = [At(qq=int(uid)), Plain(" " + msg)]
            
            logger.debug(f"准备发送数学题验证消息 | user={uid} | group={gid} | msg长度: {len(msg)}")
            logger.debug(f"消息内容: {msg[:100]}...")
            
            await event.send(event.chain_result(segs))
            logger.info(f"数学题验证消息发送成功 | user={uid} | group={gid}")
            return
        elif self.verification_mode == 1:
            logger.debug(f"使用纯邮箱验证模式")
            msg = self._format_msg(self.trigger_prompt, member_name=nickname,
                                  group_name=group_name, group_member_count=member_count,
                                  admin_list=admin_list)
            segs = [At(qq=int(uid)), Plain(" " + msg)]
        else:
            logger.debug(f"使用模式0(用户自选) - 模式值: {self.verification_mode}")
            if self.mode_0_menu_prompt:
                msg = self._format_msg(self.mode_0_menu_prompt, member_name=nickname,
                                      group_name=group_name, group_member_count=member_count,
                                      admin_list=admin_list)
            else:
                msg = self._format_msg("{at_user} 欢迎加入本群！\n本群当前共 {group_member_count} 位群友\n"
                                       "管理员列表：\n{admin_list}\n请 @我 并回复数字选择验证方式：\n"
                                       "1 - 邮箱验证\n2 - 数学题验证",
                                       member_name=nickname, group_name=group_name,
                                       group_member_count=member_count, admin_list=admin_list)
            segs = [At(qq=int(uid)), Plain(" " + msg)]
        
        if self.enable_welcome_image and self.welcome_image:
            logger.info(f"尝试添加欢迎图片 | path={self.welcome_image}")
            try:
                if self.welcome_image.startswith(("http://", "https://")):
                    logger.debug(f"使用网络图片URL")
                    segs.append(Image.fromURL(self.welcome_image))
                else:
                    logger.debug(f"使用本地文件 | exists={os.path.exists(self.welcome_image)}")
                    segs.append(Image.fromFileSystem(self.welcome_image))
                logger.info(f"欢迎图片添加成功")
            except Exception as e:
                logger.error(f"欢迎图片失败: {e}", exc_info=True)
        
        logger.debug(f"准备发送消息 | user={uid} | group={gid} | msg长度: {len(msg)}")
        logger.debug(f"消息内容: {msg[:100]}...")
        
        if not msg or msg.isspace():
            logger.warning("消息为空，使用默认消息")
            msg = f"{At(qq=int(uid))} 欢迎加入本群！请 @我 选择验证方式。"
        
        await event.send(event.chain_result(segs))
        logger.info(f"消息发送成功 | user={uid} | group={gid}")

    async def member_decrease(self, event):
        uid = str(event.message_obj.raw_message.get("user_id"))
        if uid in self.pending:
            if self.pending[uid].get("task"):
                self.pending[uid]["task"].cancel()
            del self.pending[uid]
        if uid in self.math_pending:
            del self.math_pending[uid]
        if uid in self.pending_mode:
            del self.pending_mode[uid]
        if self.db:
            self.db.update_leave_time(uid, str(event.message_obj.raw_message.get("group_id")))
        logger.info(f"退群清理 | user={uid}")

    async def handle_message(self, event):
        uid = str(event.get_sender_id())
        if uid not in self.pending:
            logger.debug(f"用户不在待验证队列 | user={uid}")
            return
        
        raw = event.message_obj.raw_message
        text = event.message_str.strip() if event.message_str else ""
        bot_id = str(event.get_self_id())
        at_me = False
        if isinstance(raw.get("message"), list):
            for seg in raw.get("message"):
                if seg.get("type") == "at" and str(seg.get("data", {}).get("qq")) == bot_id:
                    at_me = True
                    break
        if not at_me:
            logger.debug(f"用户消息未艾特机器人 | user={uid}")
            return
        
        info = self.pending[uid]
        gid = info["gid"]
        logger.info(f"收到待验证用户消息 | user={uid} | group={gid} | text={text}")
        
        group_info = await self._get_group_info(event, gid)
        group_name = group_info.get("name", "本群")
        member_count = group_info.get("member_count", "?")
        admin_list = group_info.get("admins", "无")
        
        nickname = uid
        try:
            ui = await event.bot.api.call_action("get_group_member_info", group_id=gid, user_id=int(uid))
            nickname = ui.get("card") or ui.get("nickname", uid)
        except Exception:
            pass
        
        logger.debug(f"验证状态检查 | user={uid} | mode={self.verification_mode} | pending_mode={self.pending_mode.get(uid)} | email={info.get('email')} | math_pending={uid in self.math_pending}")
        
        skip_selection = self.verification_mode in (1, 2) or uid in self.pending_mode
        if not skip_selection and info["email"] is None and uid not in self.math_pending:
            logger.debug(f"用户需要选择验证方式 | user={uid} | text={text}")
            if text.strip() == "1":
                self.pending_mode[uid] = 1
                logger.info(f"用户选择邮箱验证 | user={uid}")
                await event.send(event.chain_result([
                    At(qq=int(uid)), Plain(" 已选择邮箱验证，正在为您发送验证码到邮箱...")
                ]))
                await self._send_email_verification(event, uid, nickname, group_name)
                return
            elif text.strip() == "2":
                self.pending_mode[uid] = 2
                logger.info(f"用户选择数学题验证 | user={uid}")
                q, a = self._generate_math_problem()
                self.math_pending[uid] = {"answer": a, "gid": gid}
                await event.send(event.chain_result([
                    At(qq=int(uid)), Plain(" 请回答以下数学题完成验证：\n" + str(q))
                ]))
                return
            else:
                logger.warning(f"用户输入无效选项 | user={uid} | text={text}")
                await event.send(event.chain_result([
                    At(qq=int(uid)), Plain(" 请回复 1(邮箱验证) 或 2(数学题验证)")
                ]))
                return
        
        if uid in self.math_pending:
            logger.debug(f"处理数学题验证 | user={uid} | text={text}")
            mp = self.math_pending[uid]
            try:
                user_answer = int(text.strip())
                if user_answer == mp["answer"]:
                    del self.math_pending[uid]
                    if info.get("task"):
                        info["task"].cancel()
                    logger.info(f"数学题验证成功 | user={uid}")
                    welcome = self._format_msg(self.welcome_msg, member_name=nickname,
                                              group_name=group_name, group_member_count=member_count,
                                              admin_list=admin_list)
                    segs = [At(qq=int(uid)), Plain(" " + welcome)]
                    await event.send(event.chain_result(segs))
                    
                    if self.db:
                        join_time = info.get("join_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        self.db.update_verification_result(uid, str(gid), join_time, 1)
                    
                    del self.pending[uid]
                else:
                    logger.warning(f"数学题答案错误 | user={uid} | expected={mp['answer']} | got={user_answer}")
                    q, a = self._generate_math_problem()
                    self.math_pending[uid] = {"answer": a, "gid": gid}
                    await event.send(event.chain_result([
                        At(qq=int(uid)), Plain(" 答案错误，请重新回答：\n" + str(q))
                    ]))
            except ValueError:
                logger.warning(f"用户输入非数字 | user={uid} | text={text}")
                await event.send(event.chain_result([
                    At(qq=int(uid)), Plain(" 请输入数字答案")
                ]))
            return
        
        if info["email"] is None:
            logger.debug(f"自动触发邮箱验证 | user={uid}")
            await self._send_email_verification(event, uid, nickname, group_name)
            return
        
        m = re.search(r'\b(\d{6})\b', text)
        if not m:
            logger.debug(f"消息中未找到6位验证码 | user={uid} | text={text}")
            return
        input_code = m.group(1)
        logger.info(f"收到验证码 | user={uid} | input=******")
        
        if input_code == info["code"]:
            logger.info(f"验证成功 | user={uid}")
            if info.get("task"):
                info["task"].cancel()
            
            welcome = self._format_msg(self.welcome_msg, member_name=nickname,
                                       group_name=group_name, group_member_count=member_count,
                                       admin_list=admin_list)
            segs = [At(qq=int(uid)), Plain(" " + welcome)]
            await event.send(event.chain_result(segs))
            
            if self.db:
                join_time = info.get("join_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                self.db.update_verification_result(uid, str(gid), join_time, 1, email=info["email"])
            
            del self.pending[uid]
        else:
            logger.warning(f"验证码错误 | user={uid} | input=****** | expected=******")
            if not self._can_send(uid):
                logger.warning(f"验证码错误但冷却中 | user={uid}")
                await event.send(event.chain_result([
                    At(qq=int(uid)), Plain(f" 操作太频繁，请 {self.cooldown} 秒后再试")
                ]))
                return
            
            logger.info(f"重新发送验证码 | user={uid}")
            new_code = generate_code()
            info["code"] = new_code
            await self._send_mail(info["email"], nickname, group_name, new_code)
            
            err = self._format_msg(self.wrong_prompt, email=info["email"], member_name=nickname)
            segs = [At(qq=int(uid)), Plain(" " + err)]
            await event.send(event.chain_result(segs))

    async def _send_email_verification(self, event, uid, nickname, group_name):
        """自动发送邮箱验证"""
        logger.info(f"邮箱验证开始 | user={uid} | nickname={nickname} | group={group_name}")
        
        if not self._can_send(uid):
            logger.warning(f"邮箱验证冷却中 | user={uid}")
            await event.send(event.chain_result([
                At(qq=int(uid)), Plain(f" 操作太频繁，请 {self.cooldown} 秒后再试")
            ]))
            return
        
        email = f"{uid}{self.email_domain}"
        code = generate_code()
        
        logger.info(f"准备发送验证码邮件 | user={uid} | email={email} | code=******")
        
        success, error_data = await self._send_mail(email, nickname, group_name, code)
        if not success:
            logger.error(f"邮件发送失败 | user={uid} | email={email} | error={error_data}")
            error_msg = error_data[0] if error_data else "邮件发送失败，请稍后重试或联系管理员"
            await event.send(event.chain_result([
                At(qq=int(uid)), Plain(f" {error_msg}")
            ]))
            return
        
        logger.info(f"邮件发送成功，更新 pending 记录 | user={uid}")
        
        if uid in self.pending:
            self.pending[uid]["email"] = email
            self.pending[uid]["code"] = code
            self.pending[uid]["time"] = time.time()
            if not self.pending[uid].get("task"):
                task = asyncio.create_task(self._timeout_kick(uid, self.pending[uid]["gid"], nickname))
                self.pending[uid]["task"] = task
        else:
            logger.error(f"用户不在待验证队列中！| user={uid} | 这不应该发生")
        
        sent = self._format_msg(self.sent_prompt, email=email, member_name=nickname)
        segs = [At(qq=int(uid)), Plain(" " + sent)]
        await event.send(event.chain_result(segs))
        logger.info(f"验证码发送成功 | user={uid} | email={email} | code=******")  # 安全加固：验证码脱敏 - 2026-05-23

    async def _send_mail(self, to: str, nickname: str, group_name: str, code: str):
        timeout_min = self.verify_timeout // 60
        logger.info(f"构建邮件内容 | to={to} | group={group_name} | nickname={nickname} | timeout={timeout_min}")
        
        subject = self.email_subject.format(group_name=group_name, member_name=nickname,
                                          code=code, timeout=timeout_min)
        logger.debug(f"邮件主题: {subject}")
        
        final_bg = await get_next_bg_url(self.email_bg_url) if self.email_bg_url else ""
        logger.debug(f"背景图URL: {final_bg or '无'}")
        
        html = build_email_html_sync(self.email_body, final_bg, group_name, nickname, code, timeout_min)
        logger.debug(f"邮件HTML长度: {len(html)} 字符")
        
        logger.info(f"开始发送邮件 | smtp={self.smtp_host}:{self.smtp_port} | from={self.smtp_user} | to={to}")
        success, error_data = await async_send_verification(
            self.smtp_host, self.smtp_port, self.smtp_user, self.smtp_password,
            self.smtp_encryption, self.from_name, to, subject, html
        )
        
        if success:
            logger.info(f"邮件发送成功 | to={to}")
        else:
            logger.error(f"邮件发送失败 | to={to} | error={error_data}")
        
        return success, error_data

    async def _timeout_kick(self, uid: str, gid: int, nickname: str):
        if uid in self.admin_qqs:
            self.pending.pop(uid, None)
            return
        
        logger.info(f"启动超时计时器 | user={uid} | group={gid}")
        try:
            wait = self.verify_timeout - self.warning_time
            if wait > 0:
                await asyncio.sleep(wait)
            if uid not in self.pending:
                return
            
            platform = self.context.get_platform("aiocqhttp")
            if not platform:
                return
            bot = platform.get_client()
            
            if self.warning_time > 0:
                warn = self._format_msg(self.warning_msg, member_name=nickname)
                await bot.api.call_action("send_group_msg", group_id=gid,
                                         message=f"[CQ:at,qq={uid}] " + warn)
                await asyncio.sleep(self.warning_time)
            
            if uid not in self.pending:
                return
            
            failure = self._format_msg(self.failure_msg, member_name=nickname,
                                      countdown=str(self.kick_delay))
            await bot.api.call_action("send_group_msg", group_id=gid,
                                     message=f"[CQ:at,qq={uid}] " + failure)
            await asyncio.sleep(self.kick_delay)
            
            if uid not in self.pending:
                return
            
            await bot.api.call_action("set_group_kick", group_id=gid, user_id=int(uid),
                                     reject_add_request=False)
            
            kick = self._format_msg(self.kick_msg, member_name=nickname)
            await bot.api.call_action("send_group_msg", group_id=gid,
                                     message=f"[CQ:at,qq={uid}] " + kick)
            
            # 更新数据库
            if self.db:
                join_time = self.pending[uid].get("join_time", "")
                self.db.update_verification_result(uid, str(gid), join_time, 0)
            
            logger.info(f"用户被踢出 | user={uid}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"超时任务异常 | error={e}")
        finally:
            current = self.pending.get(uid)
            if current and current.get("task") is asyncio.current_task():
                self.pending.pop(uid, None)
