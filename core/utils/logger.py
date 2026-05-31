import logging
import os
import traceback
import asyncio
from logging.handlers import RotatingFileHandler
from datetime import datetime


class ErrorEmailHandler(logging.Handler):
    """错误日志邮件发送处理器"""
    
    def __init__(self, dev_email: str, log_dir: str, smtp_config=None):
        super().__init__(level=logging.ERROR)
        self.dev_email = dev_email
        self.log_dir = log_dir
        self.smtp_config = smtp_config
        self.last_sent_time = 0
        self.min_interval = 300  # 5分钟内不重复发送相同类型的错误
        self.error_cache = {}
        
    def emit(self, record):
        """当有ERROR级别日志时触发"""
        try:
            # 记录错误信息
            error_key = f"{record.name}:{record.funcName}"
            current_time = datetime.now().timestamp()
            
            # 检查是否在冷却时间内
            if error_key in self.error_cache:
                last_time = self.error_cache[error_key]
                if current_time - last_time < self.min_interval:
                    return
            
            # 更新缓存
            self.error_cache[error_key] = current_time
            
            # 获取错误堆栈
            exc_info = record.exc_info
            if exc_info:
                tb_str = ''.join(traceback.format_exception(*exc_info))
            else:
                tb_str = self.format(record)
            
            # 尝试发送邮件
            asyncio.create_task(self._send_error_email(record, tb_str))
        except Exception:
            # 避免邮件发送错误导致程序崩溃
            pass
    
    async def _send_error_email(self, record, tb_str):
        """异步发送错误邮件"""
        try:
            # 检查是否有SMTP配置
            if not self.smtp_config or not self.smtp_config.get("user"):
                return
            
            # 延迟导入避免循环依赖
            from .email import async_send_log_attachment
            
            log_file = os.path.join(self.log_dir, "email_verify.log")
            
            # 构建邮件内容
            subject = f"⚠️ 插件错误警报 - {record.levelname}"
            
            html_content = f"""
            <html>
            <body style="font-family: 'Microsoft YaHei', sans-serif; background-color: #f4f7fc; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; padding: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <h2 style="color: #dc3545; margin-top: 0;">⚠️ 插件运行错误警报</h2>
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0;">
                        <p style="margin: 8px 0;"><strong>错误时间：</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                        <p style="margin: 8px 0;"><strong>错误级别：</strong> {record.levelname}</p>
                        <p style="margin: 8px 0;"><strong>模块名称：</strong> {record.name}</p>
                        <p style="margin: 8px 0;"><strong>函数位置：</strong> {record.funcName} (第{record.lineno}行)</p>
                        <p style="margin: 8px 0;"><strong>错误消息：</strong> {record.getMessage()}</p>
                    </div>
                    <div style="margin: 15px 0;">
                        <h3 style="color: #495057;">详细堆栈信息：</h3>
                        <pre style="background: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 8px; overflow-x: auto; font-size: 12px; line-height: 1.5;">{tb_str}</pre>
                    </div>
                    <p style="color: #6c757d; font-size: 12px; margin-top: 20px;">此邮件由QQ群邮箱验证插件自动发送，请勿直接回复。</p>
                </div>
            </body>
            </html>
            """
            
            # 发送邮件
            await async_send_log_attachment(
                self.smtp_config["host"],
                self.smtp_config["port"],
                self.smtp_config["user"],
                self.smtp_config["password"],
                self.smtp_config["encryption"],
                self.smtp_config.get("from_name", "QQ群验证助手"),
                self.dev_email,
                subject,
                html_content,
                log_file if os.path.exists(log_file) else None,
                "email_verify.log"
            )
        except Exception:
            # 避免邮件发送错误影响主程序
            pass


def get_plugin_logger(log_dir: str = None, dev_email: str = None, smtp_config: dict = None):
    root_logger = logging.getLogger("GroupVerifyEmailAuto")
    root_logger.setLevel(logging.DEBUG)
    
    # 检查是否已经有处理器
    has_file_handler = any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers)
    has_email_handler = any(isinstance(h, ErrorEmailHandler) for h in root_logger.handlers)
    
    if has_file_handler and (has_email_handler or not dev_email):
        return root_logger
    
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    if log_dir:
        plugin_dir = log_dir
    else:
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
    
    log_file = os.path.join(plugin_dir, "email_verify.log")
    os.makedirs(plugin_dir, exist_ok=True)
    
    if not os.path.exists(log_file):
        try:
            with open(log_file, "w", encoding="utf-8") as f:
                pass
        except Exception as e:
            print(f"创建日志文件失败: {e}")
    
    # 添加文件处理器（如果还没有）
    if not has_file_handler:
        fh = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
        fh.setFormatter(formatter)
        root_logger.addHandler(fh)
        root_logger.info("日志系统初始化完成")
    
    # 添加错误邮件处理器
    if dev_email and not has_email_handler and smtp_config:
        email_handler = ErrorEmailHandler(dev_email, plugin_dir, smtp_config)
        email_handler.setFormatter(formatter)
        root_logger.addHandler(email_handler)
        root_logger.info(f"错误邮件通知已启用，收件人: {dev_email}")
    
    return root_logger
