from .models.database import DatabaseManager
from .services.verification import VerificationManager, generate_code
from .services.admin import AdminHandler
from .utils.logger import get_plugin_logger
from .utils.email import (
    async_send_verification,
    async_send_log_attachment,
    build_email_html_sync,
    init_smtp_check
)
from .utils.image import (
    init_image_pool,
    generate_code_image,
    cleanup_code_image,
    set_code_image_dir,
    get_next_bg_url
)
from .config import _flatten_config, merge_config, load_message_templates, get_config_value

# 向后兼容的导出，保持原来的导入路径仍然有效
VerificationManager = VerificationManager
AdminHandler = AdminHandler
get_plugin_logger = get_plugin_logger
init_smtp_check = init_smtp_check
init_image_pool = init_image_pool
async_send_verification = async_send_verification
build_email_html_sync = build_email_html_sync
generate_code_image = generate_code_image
cleanup_code_image = cleanup_code_image
set_code_image_dir = set_code_image_dir
get_next_bg_url = get_next_bg_url
async_send_log_attachment = async_send_log_attachment
DatabaseManager = DatabaseManager
generate_code = generate_code
_flatten_config = _flatten_config
merge_config = merge_config
load_message_templates = load_message_templates
get_config_value = get_config_value

__all__ = [
    'VerificationManager',
    'AdminHandler',
    'get_plugin_logger',
    'init_smtp_check',
    'init_image_pool',
    'async_send_verification',
    'build_email_html_sync',
    'generate_code_image',
    'cleanup_code_image',
    'set_code_image_dir',
    'get_next_bg_url',
    'async_send_log_attachment',
    'DatabaseManager',
    'generate_code',
    '_flatten_config',
    'merge_config',
    'load_message_templates',
    'get_config_value'
]
