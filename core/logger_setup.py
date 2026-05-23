import logging
import os
from logging.handlers import RotatingFileHandler


def get_plugin_logger(log_dir: str = None):
    root_logger = logging.getLogger("GroupVerifyEmailAuto")
    root_logger.setLevel(logging.DEBUG)
    if root_logger.handlers:
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
    fh = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
    fh.setFormatter(formatter)
    root_logger.addHandler(fh)
    root_logger.info("日志系统初始化完成")
    return root_logger
