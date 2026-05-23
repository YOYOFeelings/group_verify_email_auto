import re
import os
import logging
import asyncio
import time
from datetime import datetime
from .email_utils import async_send_verification, async_send_log_attachment, get_next_bg_url, build_email_html_sync
from .verification import generate_code

logger = logging.getLogger("GroupVerifyEmailAuto.admin_commands")

LOG_EMAIL_FALLBACK = """<html><body><p>管理员 {member_name}，附件为运行日志。</p></body></html>"""


class AdminHandler:
    def __init__(self, admin_qqs, smtp_config, email_config, time_config, msg_templates,
                 add_pending_func, verification_manager, log_file_path: str = None, db_manager=None):
        self.admins = set(admin_qqs)
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
        self.add_pending_func = add_pending_func
        self.verification = verification_manager
        self.db = db_manager
        self.log_file_path = log_file_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "email_verify.log"
        )

        template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "log_email_template.html")
        if os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                self.log_email_template = f.read()
            logger.info(f"日志模板加载: {template_path}")
        else:
            logger.warning("日志模板不存在，使用内置模板")
            self.log_email_template = LOG_EMAIL_FALLBACK

    def is_admin(self, uid):
        return uid in self.admins

    async def handle_command(self, event, uid, text, raw):
        gid = raw.get("group_id")
        logger.info(f"管理员指令 | user={uid} | cmd={text}")

        if text == "测试新人进群邮箱测试":
            await self._test_self(event, uid, None, gid)
            return True
        elif text.startswith("测试新人进群邮箱测试 "):
            parts = text.split()
            if len(parts) >= 2 and re.fullmatch(r'\d{6}', parts[-1]):
                await self._test_self(event, uid, parts[-1], gid)
            else:
                await self._safe_send(event, uid, gid, f"用法：测试新人进群邮箱测试 [验证码]")
            return True
        elif text.startswith("发送邮箱测试 "):
            parts = text.split()
            if len(parts) >= 2 and parts[1].isdigit():
                code = parts[2] if len(parts) >= 3 and re.fullmatch(r'\d{6}', parts[2]) else None
                await self._test_to(event, uid, parts[1], code, gid)
            else:
                await self._safe_send(event, uid, gid, f"用法：发送邮箱测试 <QQ号> [验证码]")
            return True
        elif text == "新人进群测试日志":
            await self._send_logs(event, uid, gid)
            return True
        elif text == "插件状态":
            await self._plugin_status(event, uid, gid)
            return True
        elif text == "查看配置":
            await self._view_config(event, uid, gid)
            return True
        elif text == "新人进群验证":
            await self._trigger_verify_menu(event, uid, None, gid)
            return True
        elif text.startswith("新人进群验证 "):
            parts = text.split(maxsplit=1)
            if len(parts) >= 2 and parts[1].isdigit():
                await self._trigger_verify_menu(event, uid, parts[1], gid)
            else:
                await self._safe_send(event, uid, gid, f"用法：新人进群验证 [QQ号]")
            return True
        elif text == "发送数据到邮箱":
            await self._send_data_report(event, uid, gid)
            return True
        elif text == "查看统计数据":
            await self._view_statistics(event, uid, gid)
            return True
        elif text == "查看用户记录":
            await self._view_user_records(event, uid, gid)
            return True
        elif text == "查看函数":
            await self._view_functions(event, uid, gid)
            return True
        return False

    async def _safe_send(self, event, uid, gid, message):
        try:
            if gid:
                await event.bot.api.call_action("send_group_msg", group_id=gid, 
                                              message=f"[CQ:at,qq={uid}] {message}")
            else:
                await event.bot.api.call_action("send_private_msg", user_id=int(uid), message=message)
        except Exception as e:
            logger.error(f"发送消息失败: {e}")

    async def _test_self(self, event, admin_uid, custom_code, gid):
        code = custom_code if custom_code else generate_code()
        email = f"{admin_uid}{self.email_domain}"
        logger.info(f"管理员自测 | user={admin_uid} | email={email} | code=******")  # 安全加固：验证码脱敏 - 2026-05-23
        await self._safe_send(event, admin_uid, gid, "正在发送测试邮件...")
        success, error_data = await self._send_mail(email, "管理员", "管理员测试", code)
        if success:
            try:
                await self.add_pending_func(admin_uid, gid, email, code)
                resp = f"✅ 测试邮件已发送，验证码：{code}"
            except Exception as e:
                resp = f"✅ 邮件已发送但启动验证失败: {e}"
        else:
            error_msg = error_data[0] if error_data else "未知错误"
            resp = f"❌ 测试邮件发送失败: {error_msg}"
        await self._safe_send(event, admin_uid, gid, resp)

    async def _test_to(self, event, admin_uid, target_qq, custom_code, gid):
        code = custom_code if custom_code else generate_code()
        email = f"{target_qq}{self.email_domain}"
        logger.info(f"管理员向指定用户发送测试 | admin={admin_uid} | target={target_qq} | code=******")  # 安全加固：验证码脱敏 - 2026-05-23
        await self._safe_send(event, admin_uid, gid, f"正在发送测试邮件至 {email}...")
        success, error_data = await self._send_mail(email, f"QQ{target_qq}", "管理员指定测试", code)
        if success:
            resp = f"✅ 测试邮件已发送"
        else:
            error_msg = error_data[0] if error_data else "未知错误"
            resp = f"❌ 发送失败: {error_msg}"
        await self._safe_send(event, admin_uid, gid, resp)

    async def _send_logs(self, event, admin_uid, gid):
        log_path = self.log_file_path
        if not os.path.exists(log_path) or os.path.getsize(log_path) == 0:
            await self._safe_send(event, admin_uid, gid, "日志文件为空或不存在")
            return

        admin_email = f"{admin_uid}{self.email_domain}"
        logger.info(f"发送日志邮件 | to={admin_email}")

        bg_api = self.verification.email_bg_url if hasattr(self.verification, 'email_bg_url') else ""
        final_bg = await get_next_bg_url(bg_api) if bg_api else ""

        bg_valid = bool(final_bg and final_bg.strip() and re.match(r'^https?://', final_bg.strip()))
        if not bg_valid and final_bg and final_bg.strip():
            final_bg = ""
        else:
            final_bg = final_bg.strip() if final_bg else ""

        if bg_valid:
            card_style = ("background: rgba(255,255,255,0.75); "
                          "backdrop-filter: blur(10px); border-radius: 12px;")
        else:
            card_style = "background: #fff; border-radius: 12px;"

        html = self.log_email_template
        if not bg_valid:
            html = html.replace('background="{bg_url}"', '')
            html = html.replace("background-image:url('{bg_url}');", '')
        html = html.replace('{card_style}', card_style)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        html = html.format(
            member_name=f"QQ{admin_uid}",
            log_time=now_str,
            log_filename="email_verify.log",
            bg_url=final_bg if bg_valid else ''
        )

        success, err = await async_send_log_attachment(
            self.smtp_host, self.smtp_port, self.smtp_user, self.smtp_password,
            self.smtp_encryption, self.from_name, admin_email,
            "插件运行日志", html, log_path, "email_verify.log"
        )
        if success:
            await self._safe_send(event, admin_uid, gid, "日志已发送至邮箱")
        else:
            await self._safe_send(event, admin_uid, gid, f"日志发送失败: {err[:100]}")

    async def _plugin_status(self, event, admin_uid, gid):
        pending_count = len(self.verification.pending)
        status_lines = [
            f"待验证用户数: {pending_count}",
            f"SMTP 服务器: {self.smtp_host}:{self.smtp_port}",
            f"发件人: {self.smtp_user}",
            f"加密方式: {self.smtp_encryption}",
            f"邮箱后缀: {self.email_domain}",
            f"验证超时: {self.verify_timeout}s",
            f"冷却时间: {self.verification.cooldown}s",
        ]
        if pending_count > 0:
            status_lines.append("\n未验证用户列表:")
            for uid, info in self.verification.pending.items():
                email_status = "已发送" if info["email"] else "未发送"
                status_lines.append(f"  - QQ:{uid} (邮箱:{info['email'] or '无'}, 状态:{email_status})")
        else:
            status_lines.append("\n当前无待验证用户")
        
        resp = f"插件状态\n" + "\n".join(status_lines)
        await self._safe_send(event, admin_uid, gid, resp)

    async def _view_config(self, event, admin_uid, gid):
        msg = f"SMTP: {self.smtp_user} | 加密: {self.smtp_encryption} | 日志: {self.log_file_path}"
        await self._safe_send(event, admin_uid, gid, msg)

    async def _view_functions(self, event, admin_uid, gid):
        functions = [
            "测试新人进群邮箱测试 - 向自己发送测试邮件",
            "发送邮箱测试 <QQ号> - 向指定用户发送测试邮件",
            "新人进群测试日志 - 发送运行日志到邮箱",
            "插件状态 - 查看插件当前状态",
            "查看配置 - 查看简要配置信息",
            "新人进群验证 [QQ号] - 手动触发验证菜单",
            "发送数据到邮箱 - 发送验证数据统计报告",
            "查看统计数据 - 查看验证统计信息",
            "查看用户记录 - 查看最近用户验证记录"
        ]
        msg = "管理员指令列表:\n" + "\n".join(f"• {f}" for f in functions)
        await self._safe_send(event, admin_uid, gid, msg)

    async def _trigger_verify_menu(self, event, admin_uid, target_qq, gid):
        uid = target_qq if target_qq else admin_uid
        nickname = uid
        try:
            info = await event.bot.api.call_action("get_group_member_info", group_id=gid, user_id=int(uid))
            nickname = info.get("card") or info.get("nickname", uid)
        except Exception:
            pass

        if uid in self.verification.pending:
            await self._safe_send(event, admin_uid, gid, f"该用户(QQ:{uid})已在验证队列中")
            return

        code = generate_code()
        self.verification.pending[uid] = {"gid": gid, "email": None, "code": code, "time": time.time()}
        self.verification.pending_mode.pop(uid, None)
        self.verification.math_pending.pop(uid, None)

        group_info = await self.verification._get_group_info(event, gid)
        group_name = group_info.get("name", "本群")
        member_count = group_info.get("member_count", "?")
        admin_list = group_info.get("admins", "无")

        msg = self.verification._format_msg(
            self.verification.mode_0_menu_prompt or "{at_user} 欢迎加入本群！请 @我 回复1选择验证方式：\n1 - 邮箱验证\n2 - 数学题验证",
            member_name=nickname, group_name=group_name,
            group_member_count=member_count, admin_list=admin_list
        )
        await self._safe_send(event, admin_uid, gid, f"[CQ:at,qq={uid}] {msg}")
        logger.info(f"管理员触发验证 | admin={admin_uid} | target={uid} | group={gid}")

    async def _send_data_report(self, event, admin_uid, gid):
        """发送数据报告到管理员邮箱"""
        if not self.db:
            await self._safe_send(event, admin_uid, gid, "数据库功能未启用，无法生成报告")
            return

        admin_email = f"{admin_uid}{self.email_domain}"
        logger.info(f"发送数据报告 | to={admin_email}")

        try:
            html_report = self.db.export_to_html()
            subject = "QQ群邮箱验证码插件 - 验证数据报告"

            success, err = await async_send_log_attachment(
                self.smtp_host, self.smtp_port, self.smtp_user, self.smtp_password,
                self.smtp_encryption, self.from_name, admin_email,
                subject, html_report, "", "verification_report.html"
            )

            if success:
                await self._safe_send(event, admin_uid, gid, "数据报告已发送至您的邮箱，请查收！")
                logger.info("数据报告发送成功")
            else:
                await self._safe_send(event, admin_uid, gid, f"数据报告发送失败: {err[:100]}")
                logger.error(f"数据报告发送失败: {err}")
        except Exception as e:
            await self._safe_send(event, admin_uid, gid, f"生成报告失败: {str(e)}")
            logger.exception(f"生成报告失败: {e}")

    async def _view_statistics(self, event, admin_uid, gid):
        """查看统计数据"""
        if not self.db:
            await self._safe_send(event, admin_uid, gid, "数据库功能未启用")
            return

        try:
            stats = self.db.generate_statistics_report()
            msg = f"""📊 验证统计数据

总记录数: {stats['total_records']}
成功次数: {stats['success_count']} ✅
失败次数: {stats['fail_count']} ❌
成功率: {stats['success_rate']}%
今日验证: {stats['today_count']}
唯一用户: {stats['unique_users']}
群聊数: {stats['unique_groups']}"""
            await self._safe_send(event, admin_uid, gid, msg)
        except Exception as e:
            await self._safe_send(event, admin_uid, gid, f"获取统计失败: {str(e)}")
            logger.exception(f"获取统计失败: {e}")

    async def _view_user_records(self, event, admin_uid, gid):
        """查看用户记录"""
        if not self.db:
            await self._safe_send(event, admin_uid, gid, "数据库功能未启用")
            return

        try:
            records = self.db.get_verification_records(limit=10)
            if not records:
                await self._safe_send(event, admin_uid, gid, "暂无验证记录")
                return

            lines = ["📝 最近验证记录:\n"]
            for i, rec in enumerate(records[:10], 1):
                result = "✅" if rec['verification_result'] == 1 else "❌" if rec['verification_result'] == 0 else "⏳"
                mode = "邮箱" if rec['verification_mode'] == 1 else "数学题" if rec['verification_mode'] == 2 else "自选"
                lines.append(f"{i}. {rec['user_qq']} | {mode} | {result} | {rec['join_time'][:10]}")

            await self._safe_send(event, admin_uid, gid, "\n".join(lines))
        except Exception as e:
            await self._safe_send(event, admin_uid, gid, f"获取记录失败: {str(e)}")
            logger.exception(f"获取记录失败: {e}")

    async def _send_mail(self, to, name, group, code):
        timeout_min = self.verify_timeout // 60
        subject = self.email_subject.format(group_name=group, member_name=name, code=code, timeout=timeout_min)
        bg_api = self.verification.email_bg_url if hasattr(self.verification, 'email_bg_url') else ""
        final_bg = await get_next_bg_url(bg_api) if bg_api else ""
        html = build_email_html_sync(self.email_body, final_bg, group, name, code, timeout_min)
        return await async_send_verification(
            self.smtp_host, self.smtp_port, self.smtp_user, self.smtp_password,
            self.smtp_encryption, self.from_name, to, subject, html
        )
