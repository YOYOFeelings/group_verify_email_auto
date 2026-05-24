import logging
from typing import Dict, Any

logger = logging.getLogger("GroupVerifyEmailAuto.config")


def _fix_newlines(s: str) -> str:
    if not isinstance(s, str):
        return s
    return s.replace('\\n', '\n')


def _flatten_config(config: Dict[str, Any]) -> Dict[str, Any]:
    if not config:
        logger.debug("传入的配置为空，返回空字典")
        return {}

    logger.debug(f"开始扁平化配置 | 原始配置: {config}")
    result = {}

    def process_dict(d: Dict[str, Any], prefix: str = ""):
        for key, value in d.items():
            logger.debug(f"处理键: {prefix}{key} | 类型: {type(value)} | 值: {value}")
            if isinstance(value, dict):
                if "type" in value:
                    value_type = value["type"]
                    if value_type == "object" and "items" in value:
                        logger.debug(f"发现 object 分组: {prefix}{key}，继续处理 items")
                        if isinstance(value["items"], dict):
                            process_dict(value["items"], prefix)
                        continue
                    elif value_type == "list":
                        if "items" in value and isinstance(value["items"], list):
                            result[key] = value
                            logger.debug(f"添加列表类型配置(数组 items): {key}")
                            continue
                        elif "items" in value and isinstance(value["items"], dict):
                            process_dict(value["items"], prefix)
                            continue
                    if "default" in value:
                        default_val = value["default"]
                        result[key] = default_val
                        logger.debug(f"添加配置项: {key} = {default_val} (类型: {type(default_val)})")
                    else:
                        result[key] = value
                        logger.debug(f"添加配置项(无 default): {key} = {value}")
                elif "default" in value:
                    default_val = value["default"]
                    result[key] = default_val
                    logger.debug(f"添加配置项(直接 default): {key} = {default_val} (类型: {type(default_val)})")
                elif "items" in value:
                    logger.debug(f"发现 items 分组: {prefix}{key}，继续处理")
                    if isinstance(value["items"], dict):
                        process_dict(value["items"], prefix)
                else:
                    result[key] = value
                    logger.debug(f"添加普通配置: {key} = {value}")
            else:
                result[key] = value
                logger.debug(f"添加直接值: {key} = {value} (类型: {type(value)})")

    process_dict(config)
    logger.info(f"扁平化配置完成 | 配置项数量: {len(result)}")
    logger.debug(f"扁平化配置结果: {result}")
    return result


def merge_config(db_config: Dict[str, Any], flat_config: Dict[str, Any]) -> Dict[str, Any]:
    merged = db_config.copy()
    merged.update(flat_config)
    logger.info(f"配置合并完成 | 最终配置项数量: {len(merged)}")
    return merged


def load_message_templates(merged_config: Dict[str, Any]) -> Dict[str, str]:
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
        "trigger": merged_config.get("trigger_prompt", DEFAULT_TEMPLATES["trigger"]),
        "mode_0_menu": merged_config.get("mode_0_menu_prompt", DEFAULT_TEMPLATES["mode_0_menu"]),
        "sent": merged_config.get("email_sent_prompt", DEFAULT_TEMPLATES["sent"]),
        "wrong": merged_config.get("wrong_code_prompt", DEFAULT_TEMPLATES["wrong"]),
        "welcome": merged_config.get("welcome_message", DEFAULT_TEMPLATES["welcome"]),
        "warning": merged_config.get("countdown_warning_prompt", DEFAULT_TEMPLATES["warning"]),
        "failure": merged_config.get("failure_message", DEFAULT_TEMPLATES["failure"]),
        "kick": merged_config.get("kick_message", DEFAULT_TEMPLATES["kick"]),
        "return_user": merged_config.get("return_user_message", DEFAULT_TEMPLATES["return_user"])
    }

    for key, value in msg_templates.items():
        logger.debug(f"消息模板[{key}] 长度: {len(str(value))} | 内容: {str(value)[:50]}...")
    logger.info("消息模板加载完成")

    return msg_templates


def get_config_value(merged_config: Dict[str, Any], key: str, default=None):
    val = merged_config.get(key, default)
    return _fix_newlines(val) if isinstance(val, str) else val
