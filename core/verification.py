import os
import asyncio
import re
import time
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from .email_utils import async_send_verification, build_email_html_sync, get_next_bg_url
from astrbot.api.message_components import At, Plain, Image

logger = logging.getLogger("GroupVerifyEmailAuto.verification")


def generate_code():
    code = str(random.randint(100000, 999999))
    logger.debug(f"生成验证码: {code}")
    return code


def _safe_format(s: str, **kwargs) -> str:
    """安全格式化字符串，避免KeyError"""
    if not s:
        return s
    try:
        return s.format(**kwargs)
    except KeyError:
        # 使用简单的替换
        def _repl(m):
            key = m.group(1)
            return str(kwargs.get(key, m.group(0)))
        return re.sub(r'\{(\w+)\}', _repl, s)
    except Exception as e:
        logger.warning(f"模板格式化失败: {e} | template={s[:50]}")
        return s


class VerificationManager:
    def __init__(self, smtp_config, email_config, time_config, msg_templates, context,
                 admin_qqs: Optional[List[str]] = None,
                 enable_welcome_image: bool = False, welcome_image: str = "",
                 email_bg_url: str = "",
                 verification_mode: int = 0,
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
        self.warning_msg = msg_templates.get("warning", msg_templates["warning"])
        self.failure_msg = msg_templates.get("failure", msg_templates["failure"])
        self.kick_msg = msg_templates.get("kick", msg_templates["kick"])
        self.admin_qqs = set(admin_qqs) if admin_qqs else set()
        self.enable_welcome_image = enable_welcome_image
        self.welcome_image = welcome_image
        self.email_bg_url = email_bg_url
        self.verification_mode = verification_mode
        self.context = context
        self.pending: Dict[str, dict] = {}
        self.pending_mode: Dict[str, int] = {}
        self.math_pending: Dict[str, dict] = {}
        self.last_request: Dict[str, float] = {}

        # 群信息缓存 {gid: {"member_count": int, "admins": str, "name": str, "time": float}}
        self._group_info_cache: Dict[str, dict] = {}
        self._group_cache_ttl = 120  # 缓存120秒

        logger.info(f"VerificationManager初始化 | timeout={self.verify_timeout} | cooldown={self.cooldown} | bg_url={bool(self.email_bg_url)}")

    async def _get_group_info(self, event, gid):
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

    def _format_msg(self, template: str, **kwargs):
        """格式化消息模板，自动补全通用变量"""
        kwargs.setdefault("at_user", "")
        kwargs.setdefault("member_name", kwargs.get("member_name", ""))
        kwargs.setdefault("group_name", kwargs.get("group_name", "本群"))
        kwargs.setdefault("group_member_count", kwargs.get("group_member_count", "?"))
        kwargs.setdefault("admin_list", kwargs.get("admin_list", "无"))
        kwargs.setdefault("email", kwargs.get("email", ""))
        kwargs.setdefault("timeout", str(self.verify_timeout // 60))
        kwargs.setdefault("countdown", kwargs.get("countdown", ""))
        kwargs.setdefault("code", kwargs.get("code", ""))
        kwargs.setdefault("group_image", "")  # 暂时不支持图片
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

    def _generate_math_problem(self):
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
        except Exception as e:
            logger.warning(f"获取昵称失败 | user={uid} | error={e}")

        # 获取群信息
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
        self.pending[uid] = {"gid": gid, "email": None, "code": None, "task": task, "time": time.time()}
        logger.info(f"新成员入群验证启动 | group={gid} | user={uid} | nickname={nickname} | mode={self.verification_mode}")

        if self.verification_mode == 2:
            q, a = self._generate_math_problem()
            self.math_pending[uid] = {"answer": a, "gid": gid}
            timeout_min = self.verify_timeout // 60
            msg = self._format_msg("请在 {timeout} 分钟内 @我 并回答以下问题完成验证：\n" + q,
                                    member_name=nickname, group_name=group_name,
                                    timeout=str(timeout_min))
            segs = [At(qq=int(uid)), Plain(" " + msg)]
            await event.send(event.chain_result(segs))
            return
        elif self.verification_mode == 1:
            msg = self._format_msg(self.trigger_prompt, member_name=nickname,
                                   group_name=group_name, group_member_count=member_count,
                                   admin_list=admin_list)
            segs = [At(qq=int(uid)), Plain(" " + msg)]
        else:
            if self.mode_0_menu_prompt:
                msg = self._format_msg(self.mode_0_menu_prompt,
                                       member_name=nickname, group_name=group_name,
                                       group_member_count=member_count, admin_list=admin_list)
            else:
                msg = self._format_msg("{at_user} 欢迎加入本群！\n本群当前共 {group_member_count} 位群友\n"
                                       "管理员列表：\n{admin_list}\n请 @我 并回复数字选择验证方式：\n"
                                       "1 - 邮箱验证\n2 - 数学题验证",
                                       member_name=nickname, group_name=group_name,
                                       group_member_count=member_count, admin_list=admin_list)
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

    async def handle_message(self, event):
        uid = str(event.get_sender_id())
        if uid not in self.pending:
            return
        raw = event.message_obj.raw_message
        gid = raw.get("group_id")
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
        logger.debug(f"收到待验证用户消息 | group={gid} | user={uid} | text={text}")

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

        # 处理模式选择
        skip_selection = self.verification_mode in (1, 2) or uid in self.pending_mode
        if not skip_selection and info["email"] is None and uid not in self.math_pending:
            if text.strip() == "1":
                self.pending_mode[uid] = 1
                await event.send(event.chain_result([
                    At(qq=int(uid)), Plain(" 已选择邮箱验证，请回复任意消息，我会将验证码发送到您的邮箱~")
                ]))
                return
            elif text.strip() == "2":
                self.pending_mode[uid] = 2
                q, a = self._generate_math_problem()
                self.math_pending[uid] = {"answer": a, "gid": gid}
                await event.send(event.chain_result([
                    At(qq=int(uid)), Plain(" 请回答以下数学题完成验证：\n" + str(q))
                ]))
                return
            else:
                await event.send(event.chain_result([
                    At(qq=int(uid)), Plain(" 请回复 1(邮箱验证) 或 2(数学题验证) 选择验证方式~")
                ]))
                return

        # 处理数学题验证
        if uid in self.math_pending:
            mp = self.math_pending[uid]
            try:
                user_answer = int(text.strip())
                if user_answer == mp["answer"]:
                    del self.math_pending[uid]
                    info["task"].cancel()
                    welcome = self._format_msg(self.welcome_msg, member_name=nickname,
                                               group_name=group_name, group_member_count=member_count,
                                               admin_list=admin_list)
                    segs = [At(qq=int(uid)), Plain(" " + welcome)]
                    if self.enable_welcome_image and self.welcome_image:
                        try:
                            if self.welcome_image.startswith(("http://", "https://")):
                                segs.append(Image.fromURL(self.welcome_image))
                            else:
                                segs.append(Image.fromFileSystem(self.welcome_image))
                        except Exception:
                            pass
                    await event.send(event.chain_result(segs))
                    if uid in self.pending:
                        del self.pending[uid]
                    logger.info(f"数学题验证成功 | user={uid}")
                else:
                    q, a = self._generate_math_problem()
                    self.math_pending[uid] = {"answer": a, "gid": gid}
                    await event.send(event.chain_result([
                        At(qq=int(uid)), Plain(" 答案错误，请重新回答，你的新问题：\n" + str(q))
                    ]))
                    logger.info(f"数学题答案错误 | user={uid}")
            except ValueError:
                await event.send(event.chain_result([
                    At(qq=int(uid)), Plain(" 请输入数字答案。")
                ]))
            return

        # 处理邮箱验证
        if info["email"] is None:
            logger.info(f"准备首次发送验证码 | user={uid}")
            if not self._can_send(uid):
                await event.send(event.chain_result([
                    At(qq=int(uid)), Plain(f" 操作太频繁，请 {self.cooldown} 秒后再试。")
                ]))
                return
            email = f"{uid}{self.email_domain}"
            code = generate_code()
            success = await self._send_mail(email, nickname, group_name, code)
            if not success:
                logger.error(f"验证码邮件首次发送失败 | user={uid} | email={email}")
                await event.send(event.chain_result([
                    At(qq=int(uid)), Plain(" 验证邮件发送失败，请稍后重试或联系管理员。")
                ]))
                return
            info["email"] = email
            info["code"] = code
            info["time"] = time.time()

            fmt = {"email": email, "member_name": nickname, "group_name": group_name}
            sent = self._format_msg(self.sent_prompt, **fmt)
            segs = [At(qq=int(uid)), Plain(" " + sent)]
            await event.send(event.chain_result(segs))
            logger.info(f"验证码发送成功 | user={uid} | email={email} | code={code}")
            return

        # 验证码比对
        m = re.search(r'\b(\d{6})\b', text)
        if not m:
            return
        input_code = m.group(1)
        logger.debug(f"收到验证码输入 | user={uid} | input={input_code} | correct={info['code']}")
        if input_code == info["code"]:
            logger.info(f"验证码正确，验证成功 | user={uid}")
            info["task"].cancel()
            del self.pending[uid]
            welcome = self._format_msg(self.welcome_msg, member_name=nickname,
                                       group_name=group_name, group_member_count=member_count,
                                       admin_list=admin_list)
            segs = [At(qq=int(uid)), Plain(" " + welcome)]
            if self.enable_welcome_image and self.welcome_image:
                try:
                    if self.welcome_image.startswith(("http://", "https://")):
                        segs.append(Image.fromURL(self.welcome_image))
                    else:
                        segs.append(Image.fromFileSystem(self.welcome_image))
                except Exception as img_e:
                    logger.error(f"验证成功添加图片失败，已降级为纯文本 | error={img_e}")
            await event.send(event.chain_result(segs))
        else:
            logger.warning(f"验证码错误，重新生成并发送 | user={uid} | input={input_code} | expected={info['code']}")
            if not self._can_send(uid):
                await event.send(event.chain_result([
                    At(qq=int(uid)), Plain(f" 操作太频繁，请 {self.cooldown} 秒后再试。")
                ]))
                return
            new_code = generate_code()
            info["code"] = new_code
            info["time"] = time.time()
            await self._send_mail(info["email"], nickname, group_name, new_code)

            fmt = {"email": info["email"], "member_name": nickname}
            err = self._format_msg(self.wrong_prompt, **fmt)
            segs = [At(qq=int(uid)), Plain(" " + err)]
            await event.send(event.chain_result(segs))

    async def _send_mail(self, to: str, nickname: str, group_name: str, code: str):
        timeout_min = self.verify_timeout // 60
        subject = self.email_subject.format(group_name=group_name, member_name=nickname, code=code, timeout=timeout_min)
        logger.debug(f"开始构造邮件 | to={to} | subject={subject}")
        final_bg = await get_next_bg_url(self.email_bg_url) if self.email_bg_url else ""
        html = build_email_html_sync(self.email_body, final_bg, group_name, nickname, code, timeout_min)
        result = await async_send_verification(
            self.smtp_host, self.smtp_port, self.smtp_user, self.smtp_password,
            self.smtp_encryption, self.from_name, to, subject, html
        )
        if result:
            logger.info(f"邮件发送成功 | to={to}")
        else:
            logger.error(f"邮件发送失败 | to={to}")
        return result

    async def _timeout_kick(self, uid: str, gid: int, nickname: str):
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
                logger.error("无法获取bot客户端")
                return
            bot = platform.get_client()

            if self.warning_time > 0:
                warn_expire = (datetime.now() + timedelta(seconds=self.warning_time + self.kick_delay)).strftime("%H:%M:%S")
                warn = self._format_msg(self.warning_msg, member_name=nickname, expire_time=warn_expire)
                warn = f"[CQ:at,qq={uid}] " + warn
                try:
                    await bot.api.call_action("send_group_msg", group_id=gid, message=warn)
                    logger.info(f"超时警告已发送 | user={uid} | 到期时间={warn_expire}")
                except Exception as e:
                    logger.error(f"发送超时警告失败 | error={e}")
                await asyncio.sleep(self.warning_time)

            if uid not in self.pending:
                return

            final_expire = (datetime.now() + timedelta(seconds=self.kick_delay)).strftime("%H:%M:%S")
            failure = self._format_msg(self.failure_msg, member_name=nickname,
                                       countdown=str(self.kick_delay), expire_time=final_expire)
            failure = f"[CQ:at,qq={uid}] " + failure
            try:
                await bot.api.call_action("send_group_msg", group_id=gid, message=failure)
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
                await bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] " + kick)
            except Exception as e:
                logger.error(f"踢出执行失败 | error={e}")
        except asyncio.CancelledError:
            logger.info(f"超时任务被取消 | user={uid}")
        except Exception as e:
            logger.exception(f"超时任务异常 | user={uid} | error={e}")
        finally:
            # 只清理自己仍是当前任务对应的pending记录
            # 防止新任务覆盖后旧finally误删新任务的数据
            current = self.pending.get(uid)
            if current and current.get("task") is asyncio.current_task():
                self.pending.pop(uid, None)
                logger.debug(f"待验证队列已清理 | user={uid}")
