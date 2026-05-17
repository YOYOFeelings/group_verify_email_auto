import os
import asyncio
import re
import time
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from .email_utils import async_send_verification, build_email_html_sync, get_next_bg_url
from .email_utils import generate_code_image, cleanup_code_image, set_code_image_dir
from astrbot.api.message_components import At, Plain, Image

logger = logging.getLogger("GroupVerifyEmailAuto.verification")

def generate_code():
    code = str(random.randint(100000, 999999))
    logger.debug(f"生成验证码: {code}")
    return code


def _safe_format(template: str, **kwargs) -> str:
    """安全格式化字符串，忽略不存在的变量"""
    if not template:
        return ""
    try:
        return template.format(**kwargs)
    except KeyError:
        def _replacer(m):
            key = m.group(1)
            return str(kwargs.get(key, m.group(0)))
        return re.sub(r'\{(\w+)\}', _replacer, template)
    except Exception as e:
        logger.warning(f"模板格式化异常: {e} | template={template[:50]}")
        return template


class VerificationManager:
    def __init__(self, smtp_config, email_config, time_config, msg_templates, context,
                 admin_qqs: Optional[List[str]] = None,
                 enable_welcome_image: bool = False, welcome_image: str = "",
                 email_bg_url: str = "",
                 verification_mode: int = 0,
                 enable_code_image: bool = True,
                 enable_reply_message: bool = True,
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
        self.trigger_prompt = msg_templates.get("trigger", msg_templates["trigger"])
        self.mode_0_menu_prompt = msg_templates.get("mode_0_menu", "")
        self.sent_prompt = msg_templates.get("sent", msg_templates["sent"])
        self.wrong_prompt = msg_templates.get("wrong", msg_templates["wrong"])
        self.welcome_msg = msg_templates.get("welcome", msg_templates["welcome"])
        self.warning_prompt = msg_templates.get("warning", msg_templates["warning"])
        self.failure_msg = msg_templates.get("failure", msg_templates["failure"])
        self.kick_msg = msg_templates.get("kick", msg_templates["kick"])
        self.admin_qqs = set(admin_qqs) if admin_qqs else set()
        self.enable_welcome_image = enable_welcome_image
        self.welcome_image = welcome_image
        self.email_bg_url = email_bg_url
        self.verification_mode = verification_mode
        self.enable_code_image = enable_code_image
        self.enable_reply_message = enable_reply_message
        self.pending_mode: Dict[str, int] = {}
        self.math_pending: Dict[str, dict] = {}
        self.context = context
        self.pending: Dict[str, dict] = {}
        self.last_request: Dict[str, float] = {}

        # 群信息缓存 {gid: {"member_count": int, "admins": str, "name": str, "time": float}}
        self._group_info_cache: Dict[str, dict] = {}
        self._group_cache_ttl = 120  # 缓存120秒

        # 初始化验证码图片目录
        if data_dir:
            code_img_dir = os.path.join(data_dir, "code_images")
        else:
            code_img_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "code_images")
        set_code_image_dir(code_img_dir)
        logger.info(f"验证码图片目录已设置: {code_img_dir}")

        logger.info(f"VerificationManager 参数 | timeout={self.verify_timeout} | cooldown={self.cooldown} | "
                    f"bg_url={self.email_bg_url} | code_img={self.enable_code_image} | reply={self.enable_reply_message}")

    async def _get_group_info(self, event, gid) -> dict:
        """获取群信息（带缓存），返回 {member_count, admins, name}"""
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
            logger.warning(f"获取管理员列表失败 | group={gid} | error={e}")

        info["time"] = now
        self._group_info_cache[str(gid)] = info
        logger.info(f"群信息已更新 | group={gid} | 人数={info['member_count']} | 管理员={info['admins']}")
        return info

    def _format_msg(self, template: str, **overrides) -> str:
        """格式化消息模板，自动补全通用变量"""
        kwargs = {
            "at_user": "",
            "member_name": overrides.get("member_name", ""),
            "group_name": overrides.get("group_name", "本群"),
            "group_member_count": overrides.get("group_member_count", "?"),
            "admin_list": overrides.get("admin_list", "无"),
            "email": overrides.get("email", ""),
            "timeout": overrides.get("timeout", str(self.verify_timeout // 60)),
            "countdown": overrides.get("countdown", ""),
            "code": overrides.get("code", ""),
        }
        kwargs.update(overrides)
        return _safe_format(template, **kwargs)

    def _can_send(self, uid):
        now = time.time()
        last = self.last_request.get(uid, 0)
        if now - last < self.cooldown:
            logger.info(f"冷却中拒绝请求 | user={uid} | cooldown={self.cooldown}")
            return False
        logger.debug(f"冷却通过 | user={uid}")
        self.last_request[uid] = now
        return True

    def _generate_math_problem(self) -> tuple:
        op_type = random.choice(['add', 'sub'])
        if op_type == 'add':
            num1 = random.randint(0, 100)
            num2 = random.randint(0, 100 - num1)
            answer = num1 + num2
            question = f"{num1} + {num2} = ?"
            return question, answer
        else:
            num1 = random.randint(1, 100)
            num2 = random.randint(0, num1)
            answer = num1 - num2
            question = f"{num1} - {num2} = ?"
            return question, answer

    async def manual_add(self, uid: str, gid: int, email: str, code: str, nickname: str = ""):
        logger.info(f"手动添加待验证 | user={uid} | group={gid} | email={email} | code={code}")
        if uid in self.pending:
            old = self.pending[uid].get("task")
            if old and not old.done():
                old.cancel()
        is_admin = uid in self.admin_qqs
        if not is_admin:
            task = asyncio.create_task(self._timeout_kick(uid, gid, nickname))
        else:
            task = asyncio.create_task(asyncio.sleep(0))
        self.pending[uid] = {"gid": gid, "email": email, "code": code, "task": task, "time": time.time()}
        logger.info(f"待验证队列添加成功 | user={uid} | group={gid}")

    async def new_member(self, event):
        raw = event.message_obj.raw_message
        uid = str(raw.get("user_id"))
        gid = raw.get("group_id")
        nickname = uid
        try:
            info = await event.bot.api.call_action("get_group_member_info", group_id=gid, user_id=int(uid))
            nickname = info.get("card") or info.get("nickname", uid)
            logger.debug(f"获取昵称成功 | user={uid} | nickname={nickname}")
        except Exception as e:
            logger.warning(f"获取昵称失败 | user={uid} | error={e}")

        # 获取群信息（人数、管理员列表等）
        group_info = await self._get_group_info(event, gid)
        group_name = group_info.get("name", "本群")
        member_count = group_info.get("member_count", "?")
        admin_list = group_info.get("admins", "无")

        if uid in self.pending:
            logger.info(f"新成员已在队列中，取消旧任务 | user={uid}")
            old = self.pending[uid].get("task")
            if old and not old.done():
                old.cancel()

        task = asyncio.create_task(self._timeout_kick(uid, gid, nickname))
        self.pending[uid] = {"gid": gid, "email": None, "code": None, "task": task, "time": 0}
        logger.info(f"新成员入群验证启动 | group={gid} | user={uid} | nickname={nickname} | mode={self.verification_mode}")

        fmt_kwargs = {
            "member_name": nickname,
            "timeout": str(self.verify_timeout // 60),
            "group_name": group_name,
            "group_member_count": member_count,
            "admin_list": admin_list
        }

        if self.verification_mode == 2:
            q, a = self._generate_math_problem()
            self.math_pending[uid] = {"answer": a, "gid": gid}
            timeout_min = self.verify_timeout // 60
            msg = self._format_msg(
                " 欢迎加入本群！请在 {timeout} 分钟内 @我 并回答以下问题完成验证：",
                **fmt_kwargs, timeout=timeout_min
            )
            msg = msg + "\n" + q
            segs = [At(qq=int(uid)), Plain(msg)]
            # 入群通知没有可引用的消息ID，不加 Reply
            await event.send(event.chain_result(segs))
            return
        elif self.verification_mode == 1:
            msg = self._format_msg(self.trigger_prompt, **fmt_kwargs)
            segs = [At(qq=int(uid)), Plain(" " + msg)]
        else:
            if self.mode_0_menu_prompt:
                msg = self._format_msg(self.mode_0_menu_prompt, **fmt_kwargs)
            else:
                msg = self._format_msg(
                    "{at_user} 欢迎加入本群！🎉\n本群当前共 {group_member_count} 位群友\n管理员列表：\n{admin_list}\n请 @我 并回复数字选择验证方式：\n1 - 邮箱验证\n2 - 数学题验证",
                    **fmt_kwargs
                )
            segs = [At(qq=int(uid)), Plain(" " + msg)]

        if self.enable_welcome_image and self.welcome_image:
            try:
                if self.welcome_image.startswith(("http://", "https://")):
                    segs.append(Image.fromURL(self.welcome_image))
                else:
                    segs.append(Image.fromFileSystem(self.welcome_image))
            except Exception as e:
                logger.error(f"欢迎图片加载失败，已降级为纯文本 | url={self.welcome_image} | error={e}")

        logger.info(f"发送入群欢迎消息 | group={gid} | user={uid}")
        await event.send(event.chain_result(segs))

    def _get_message_id(self, event) -> Optional[str]:
        """从事件中提取消息ID（用于引用消息）"""
        try:
            raw = event.message_obj.raw_message
            if isinstance(raw, dict):
                mid = raw.get("message_id")
                if mid is not None:
                    return str(mid)
            if hasattr(event, "message_id") and event.message_id:
                return str(event.message_id)
        except Exception as e:
            logger.debug(f"获取消息ID失败: {e}")
        return None

    async def member_decrease(self, event):
        uid = str(event.message_obj.raw_message.get("user_id"))
        if uid in self.pending:
            self.pending[uid]["task"].cancel()
            del self.pending[uid]
        if uid in self.math_pending:
            del self.math_pending[uid]
        if uid in self.pending_mode:
            del self.pending_mode[uid]
            logger.info(f"退群清理待验证用户 | user={uid}")

    async def _send_with_reply(self, event, uid: str, segments: list):
        """发送消息并添加引用消息样式"""
        if self.enable_reply_message:
            reply_id = self._get_message_id(event)
            if reply_id:
                from astrbot.api.message_components import Reply
                segments.insert(0, Reply(id=reply_id))
        await event.send(event.chain_result(segments))

    async def handle_message(self, event):
        uid = str(event.get_sender_id())
        if uid not in self.pending:
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
            return
        info = self.pending[uid]
        gid = info["gid"]
        logger.info(f"收到待验证用户消息 | group={gid} | user={uid} | text={text}")

        # 获取群信息
        group_info = await self._get_group_info(event, gid)
        group_name = group_info.get("name", "本群")
        member_count = group_info.get("member_count", "?")
        admin_list = group_info.get("admins", "无")

        # 获取用户昵称
        nickname = uid
        try:
            ui = await event.bot.api.call_action("get_group_member_info", group_id=gid, user_id=int(uid))
            nickname = ui.get("card") or ui.get("nickname", uid)
        except Exception:
            pass

        fmt_kwargs = {
            "member_name": nickname,
            "timeout": str(self.verify_timeout // 60),
            "group_name": group_name,
            "group_member_count": member_count,
            "admin_list": admin_list
        }

        # 处理模式选择（仅 Mode 0 且未选过）
        skip_selection = self.verification_mode in (1, 2) or uid in self.pending_mode
        if not skip_selection and info["email"] is None and info["code"] is None and uid not in self.math_pending:
            if text.strip() == "1":
                self.pending_mode[uid] = 1
                await self._send_with_reply(event, uid, [
                    At(qq=int(uid)),
                    Plain(" 已选择邮箱验证，请回复任意消息，我会将验证码发送到你的QQ邮箱~")
                ])
                event.stop_event()
                return
            elif text.strip() == "2":
                self.pending_mode[uid] = 2
                q, a = self._generate_math_problem()
                self.math_pending[uid] = {"answer": a, "gid": gid}
                await self._send_with_reply(event, uid, [
                    At(qq=int(uid)),
                    Plain(" 请回答以下数学题完成验证：\n" + str(q))
                ])
                event.stop_event()
                return
            else:
                await self._send_with_reply(event, uid, [
                    At(qq=int(uid)),
                    Plain(" 请回复 1(邮箱验证) 或 2(数学题验证) 选择方式~")
                ])
                event.stop_event()
                return

        # 数学题验证
        if uid in self.math_pending:
            mp = self.math_pending[uid]
            try:
                user_answer = int(text.strip())
                if user_answer == mp["answer"]:
                    del self.math_pending[uid]
                    info["task"].cancel()
                    welcome = self._format_msg(self.welcome_msg, **fmt_kwargs)
                    segs = [At(qq=int(uid)), Plain(" " + welcome)]
                    if self.enable_welcome_image and self.welcome_image:
                        try:
                            if self.welcome_image.startswith(("http://", "https://")):
                                segs.append(Image.fromURL(self.welcome_image))
                            else:
                                segs.append(Image.fromFileSystem(self.welcome_image))
                        except Exception:
                            pass
                    await self._send_with_reply(event, uid, segs)
                    if uid in self.pending:
                        del self.pending[uid]
                    logger.info(f"数学题验证成功 | user={uid}")
                else:
                    q, a = self._generate_math_problem()
                    self.math_pending[uid] = {"answer": a, "gid": gid}
                    await self._send_with_reply(event, uid, [
                        At(qq=int(uid)),
                        Plain(" 答案错误，请重新回答，你的新问题：\n" + str(q))
                    ])
                    logger.info(f"数学题答案错误 | user={uid}")
            except ValueError:
                await self._send_with_reply(event, uid, [
                    At(qq=int(uid)),
                    Plain(" 请输入数字答案。")
                ])
            event.stop_event()
            return

        # 邮箱验证
        if info["email"] is None:
            logger.info(f"准备首次发送验证码 | user={uid}")
            if not self._can_send(uid):
                await self._send_with_reply(event, uid, [
                    At(qq=int(uid)),
                    Plain(f" 操作太频繁，请 {self.cooldown} 秒后再试。")
                ])
                event.stop_event()
                return
            email = f"{uid}{self.email_domain}"
            code = generate_code()
            success = await self._send_mail(email, nickname, "本群", code)
            if not success:
                logger.error(f"验证码邮件首次发送失败 | user={uid} | email={email}")
                await self._send_with_reply(event, uid, [
                    At(qq=int(uid)),
                    Plain(" 验证邮件发送失败，请稍后重试或联系管理员。")
                ])
                event.stop_event()
                return
            info["email"] = email
            info["code"] = code
            info["time"] = time.time()

            fmt_kwargs["email"] = email
            sent = self._format_msg(self.sent_prompt, **fmt_kwargs)
            segs = [At(qq=int(uid)), Plain(" " + sent)]

            # 生成并显示验证码图片 ✨
            if self.enable_code_image:
                try:
                    img_path = await asyncio.to_thread(generate_code_image, code, uid)
                    if img_path and os.path.exists(img_path):
                        segs.append(Image.fromFileSystem(img_path))
                        logger.info(f"验证码图片已附加到消息 | user={uid}")
                except Exception as e:
                    logger.error(f"验证码图片生成失败 | user={uid} | error={e}")

            await self._send_with_reply(event, uid, segs)
            logger.info(f"验证码发送成功 | user={uid} | email={email} | code={code}")
            event.stop_event()
            return

        # 验证码比对
        m = re.search(r'\b(\d{6})\b', text)
        if not m:
            return
        input_code = m.group(1)
        logger.info(f"收到验证码输入 | user={uid} | input={input_code} | correct={info['code']}")
        if input_code == info["code"]:
            logger.info(f"验证码正确，验证成功 | user={uid}")
            info["task"].cancel()
            del self.pending[uid]
            welcome = self._format_msg(self.welcome_msg, **fmt_kwargs)
            segs = [At(qq=int(uid)), Plain(" " + welcome)]
            if self.enable_welcome_image and self.welcome_image:
                try:
                    if self.welcome_image.startswith(("http://", "https://")):
                        segs.append(Image.fromURL(self.welcome_image))
                    else:
                        segs.append(Image.fromFileSystem(self.welcome_image))
                except Exception as img_e:
                    logger.error(f"验证成功添加图片失败，已降级为纯文本 | error={img_e}")
            await self._send_with_reply(event, uid, segs)
            event.stop_event()
        else:
            logger.warning(f"验证码错误，重新生成并发送 | user={uid} | input={input_code} | expected={info['code']}")
            if not self._can_send(uid):
                await self._send_with_reply(event, uid, [
                    At(qq=int(uid)),
                    Plain(f" 操作太频繁，请 {self.cooldown} 秒后再试。")
                ])
                event.stop_event()
                return
            new_code = generate_code()
            info["code"] = new_code
            info["time"] = time.time()
            await self._send_mail(info["email"], nickname, "本群", new_code)
            fmt_kwargs["email"] = info["email"]
            err = self._format_msg(self.wrong_prompt, **fmt_kwargs)

            segs = [At(qq=int(uid)), Plain(" " + err)]
            if self.enable_code_image:
                try:
                    img_path = await asyncio.to_thread(generate_code_image, new_code, uid)
                    if img_path and os.path.exists(img_path):
                        segs.append(Image.fromFileSystem(img_path))
                except Exception as e:
                    logger.error(f"验证码图片生成失败(重发) | user={uid} | error={e}")
            await self._send_with_reply(event, uid, segs)
            event.stop_event()

    async def _send_mail(self, to, name, group, code):
        timeout_min = self.verify_timeout // 60
        subject = self.email_subject.format(group_name=group, member_name=name, code=code, timeout=timeout_min)
        logger.info(f"开始构造邮件 | to={to} | subject={subject}")
        final_bg = await get_next_bg_url(self.email_bg_url) if self.email_bg_url else ""
        html = build_email_html_sync(self.email_body, final_bg, group, name, code, timeout_min)
        result = await async_send_verification(
            self.smtp_host, self.smtp_port, self.smtp_user, self.smtp_password,
            self.smtp_encryption, self.from_name, to, subject, html
        )
        if result:
            logger.info(f"邮件发送成功 | to={to}")
        else:
            logger.error(f"邮件发送失败 | to={to}")
        return result

    async def _timeout_kick(self, uid, gid, nickname):
        if uid in self.admin_qqs:
            logger.info(f"管理员验证超时，跳过踢出 | user={uid}")
            self.pending.pop(uid, None)
            return
        logger.info(f"启动超时计时器 | user={uid} | group={gid} | timeout={self.verify_timeout}s")
        try:
            expire_str = (datetime.now() + timedelta(seconds=self.verify_timeout)).strftime("%H:%M:%S")
            logger.debug(f"到期时间: {expire_str}")

            wait = self.verify_timeout - self.warning_time
            if wait > 0:
                await asyncio.sleep(wait)
            if uid not in self.pending:
                return

            platform = self.context.get_platform("aiocqhttp")
            if not platform:
                logger.error("无法获取 bot 客户端")
                return
            bot = platform.get_client()
            at = f"[CQ:at,qq={uid}]"

            if self.warning_time > 0:
                warn_expire = (datetime.now() + timedelta(seconds=self.warning_time + self.kick_delay)).strftime("%H:%M:%S")
                warn_msg = self._format_msg(self.warning_prompt, member_name=nickname, expire_time=warn_expire)
                warn_msg = at + " " + warn_msg
                try:
                    await bot.api.call_action("send_group_msg", group_id=gid, message=warn_msg)
                    logger.info(f"超时警告已发送 | user={uid} | 到期时间={warn_expire}")
                except Exception as e:
                    logger.error(f"发送超时警告失败 | error={e}")
                await asyncio.sleep(self.warning_time)

            if uid not in self.pending:
                return

            final_expire = (datetime.now() + timedelta(seconds=self.kick_delay)).strftime("%H:%M:%S")
            fail_msg = self._format_msg(self.failure_msg, member_name=nickname,
                                         countdown=str(self.kick_delay), expire_time=final_expire)
            fail_msg = at + " " + fail_msg
            try:
                await bot.api.call_action("send_group_msg", group_id=gid, message=fail_msg)
                logger.info(f"最后通牒已发送 | user={uid} | 踢出时间={final_expire}")
            except Exception as e:
                logger.error(f"发送最后通牒失败 | error={e}")
            await asyncio.sleep(self.kick_delay)

            if uid not in self.pending:
                return
            try:
                await bot.api.call_action("set_group_kick", group_id=gid, user_id=int(uid), reject_add_request=False)
                logger.info(f"用户被踢出 | user={uid} | group={gid}")
                kick = self._format_msg(self.kick_msg, member_name=nickname)
                await bot.api.call_action("send_group_msg", group_id=gid,
                    message=at + " " + kick)
            except Exception as e:
                logger.error(f"踢出执行失败 | error={e}")
        except asyncio.CancelledError:
            logger.info(f"超时任务被取消 | user={uid}")
        except Exception as e:
            logger.exception(f"超时任务异常 | user={uid} | error={e}")
        finally:
            # 只清理自己仍是当前任务对应的 pending 记录
            # 防止新任务覆盖后旧 finally 误删新任务的数据
            current = self.pending.get(uid)
            if current and current.get("task") is asyncio.current_task():
                self.pending.pop(uid, None)
                logger.debug(f"待验证队列已清理 | user={uid}")
