import sqlite3
import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger("GroupVerifyEmailAuto.database")


class DatabaseManager:
    """SQLite数据库管理器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_database()
        logger.info(f"数据库初始化完成 | path={db_path}")
    
    def _get_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)
    
    def _init_database(self):
        """初始化数据库表结构"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 用户验证记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS verification_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_qq TEXT NOT NULL,
                user_nickname TEXT,
                group_id TEXT NOT NULL,
                group_name TEXT,
                email TEXT,
                verification_mode INTEGER,
                verification_result INTEGER,
                join_time TEXT NOT NULL,
                verify_time TEXT,
                leave_time TEXT,
                create_time TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_qq, group_id, join_time)
            )
        ''')
        
        # 新的管理员表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_qq TEXT UNIQUE NOT NULL,
                admin_nickname TEXT,
                added_by TEXT,
                add_time TEXT DEFAULT CURRENT_TIMESTAMP,
                permission_level INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # 新的群隔离表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_whitelist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT UNIQUE NOT NULL,
                group_name TEXT,
                is_enabled INTEGER DEFAULT 1,
                added_by TEXT,
                add_time TEXT DEFAULT CURRENT_TIMESTAMP,
                update_time TEXT,
                description TEXT
            )
        ''')
        
        # 群管理员映射表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                admin_qq TEXT NOT NULL,
                added_by TEXT,
                add_time TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(group_id, admin_qq)
            )
        ''')
        
        # 邮件配置表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key TEXT UNIQUE NOT NULL,
                config_value TEXT,
                update_time TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 插件通用配置表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS plugin_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key TEXT UNIQUE NOT NULL,
                config_value TEXT,
                config_type TEXT DEFAULT 'string',
                update_time TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 用户统计表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_qq TEXT UNIQUE NOT NULL,
                user_nickname TEXT,
                total_verifications INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                first_join_time TEXT,
                last_join_time TEXT,
                last_verify_time TEXT
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_qq ON verification_records(user_qq)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_group_id ON verification_records(group_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_join_time ON verification_records(join_time)')
        
        conn.commit()
        conn.close()
        # 安全加固：数据库文件权限加固，仅所有者可读写 - 2026-05-23
        if os.name == 'posix':
            try:
                os.chmod(self.db_path, 0o600)
            except Exception:
                pass
        logger.info("数据库表结构初始化完成")
    
    def add_verification_record(self, user_qq: str, group_id: str, 
                                verification_mode: int = 0,
                                user_nickname: str = None,
                                group_name: str = None,
                                email: str = None) -> int:
        """添加验证记录"""
        conn = self._get_connection()
        cursor = conn.cursor()
        join_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute('''
            INSERT INTO verification_records 
            (user_qq, user_nickname, group_id, group_name, email, 
             verification_mode, join_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_qq, user_nickname, group_id, group_name, email,
              verification_mode, join_time))
        
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # 更新用户统计
        self.update_user_stats(user_qq, user_nickname, is_join=True)
        
        logger.info(f"添加验证记录 | user={user_qq} | group={group_id} | record_id={record_id}")
        return record_id
    
    def update_verification_result(self, user_qq: str, group_id: str,
                                  join_time: str, result: int,
                                  email: str = None):
        """更新验证结果"""
        conn = self._get_connection()
        cursor = conn.cursor()
        verify_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute('''
            UPDATE verification_records
            SET verification_result = ?, verify_time = ?, email = ?
            WHERE user_qq = ? AND group_id = ? AND join_time = ?
        ''', (result, verify_time, email, user_qq, group_id, join_time))
        
        conn.commit()
        conn.close()
        
        # 更新用户统计
        self.update_user_stats(user_qq, result=result)
        
        logger.info(f"更新验证结果 | user={user_qq} | result={result}")
    
    def update_leave_time(self, user_qq: str, group_id: str):
        """更新退群时间"""
        conn = self._get_connection()
        cursor = conn.cursor()
        leave_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute('''
            UPDATE verification_records
            SET leave_time = ?
            WHERE user_qq = ? AND group_id = ?
            ORDER BY join_time DESC
            LIMIT 1
        ''', (leave_time, user_qq, group_id))
        
        conn.commit()
        conn.close()
        logger.info(f"更新退群时间 | user={user_qq} | group={group_id}")
    
    def check_user_history(self, user_qq: str, group_id: str = None) -> Optional[Dict]:
        """检查用户历史记录"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if group_id:
            cursor.execute('''
                SELECT user_qq, user_nickname, group_id, group_name, 
                       verification_mode, verification_result, join_time, 
                       verify_time, leave_time, email
                FROM verification_records
                WHERE user_qq = ? AND group_id = ?
                ORDER BY join_time DESC
                LIMIT 1
            ''', (user_qq, group_id))
        else:
            cursor.execute('''
                SELECT user_qq, user_nickname, group_id, group_name,
                       verification_mode, verification_result, join_time,
                       verify_time, leave_time, email
                FROM verification_records
                WHERE user_qq = ?
                ORDER BY join_time DESC
                LIMIT 1
            ''', (user_qq,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "user_qq": row[0],
                "user_nickname": row[1],
                "group_id": row[2],
                "group_name": row[3],
                "verification_mode": row[4],
                "verification_result": row[5],
                "join_time": row[6],
                "verify_time": row[7],
                "leave_time": row[8],
                "email": row[9]
            }
        return None
    
    def get_user_stats(self, user_qq: str) -> Optional[Dict]:
        """获取用户统计信息"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_qq, user_nickname, total_verifications,
                   success_count, fail_count, first_join_time,
                   last_join_time, last_verify_time
            FROM user_stats
            WHERE user_qq = ?
        ''', (user_qq,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "user_qq": row[0],
                "user_nickname": row[1],
                "total_verifications": row[2],
                "success_count": row[3],
                "fail_count": row[4],
                "first_join_time": row[5],
                "last_join_time": row[6],
                "last_verify_time": row[7]
            }
        return None
    
    def update_user_stats(self, user_qq: str, user_nickname: str = None,
                         is_join: bool = False, result: int = None):
        """更新用户统计"""
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute('SELECT 1 FROM user_stats WHERE user_qq = ?', (user_qq,))
        exists = cursor.fetchone()
        
        if exists:
            if is_join:
                cursor.execute('''
                    UPDATE user_stats
                    SET total_verifications = total_verifications + 1,
                        last_join_time = ?
                    WHERE user_qq = ?
                ''', (now, user_qq))
            if result is not None:
                if result == 1:
                    cursor.execute('''
                        UPDATE user_stats
                        SET success_count = success_count + 1,
                            last_verify_time = ?
                        WHERE user_qq = ?
                    ''', (now, user_qq))
                else:
                    cursor.execute('''
                        UPDATE user_stats
                        SET fail_count = fail_count + 1,
                            last_verify_time = ?
                        WHERE user_qq = ?
                    ''', (now, user_qq))
        else:
            cursor.execute('''
                INSERT INTO user_stats (user_qq, user_nickname, total_verifications,
                                       success_count, fail_count, first_join_time, last_join_time)
                VALUES (?, ?, 1, 0, 0, ?, ?)
            ''', (user_qq, user_nickname, now, now))
        
        conn.commit()
        conn.close()
    
    # ==================== 管理员管理方法 ====================
    
    def add_admin(self, admin_qq: str, admin_nickname: str = None, added_by: str = None, permission_level: int = 1):
        """添加管理员"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO admin_list (admin_qq, admin_nickname, added_by, add_time, permission_level, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        ''', (admin_qq, admin_nickname, added_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), permission_level))
        
        conn.commit()
        conn.close()
        logger.info(f"添加管理员 | qq={admin_qq} | level={permission_level}")
    
    def remove_admin(self, admin_qq: str):
        """移除管理员"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM admin_list WHERE admin_qq = ?', (admin_qq,))
        
        conn.commit()
        conn.close()
        logger.info(f"移除管理员 | qq={admin_qq}")
    
    def is_admin(self, admin_qq: str) -> bool:
        """检查是否是管理员"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT 1 FROM admin_list WHERE admin_qq = ? AND is_active = 1', (admin_qq,))
        result = cursor.fetchone()
        conn.close()
        
        return result is not None
    
    def get_all_admins(self) -> List[Dict]:
        """获取所有活跃管理员"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT admin_qq, admin_nickname, added_by, add_time, permission_level FROM admin_list WHERE is_active = 1')
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {"admin_qq": r[0], "admin_nickname": r[1], "added_by": r[2], 
             "add_time": r[3], "permission_level": r[4]} for r in rows
        ]
    
    def get_admin_info(self, admin_qq: str) -> Optional[Dict]:
        """获取指定管理员信息"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT admin_qq, admin_nickname, added_by, add_time, permission_level FROM admin_list WHERE admin_qq = ? AND is_active = 1', (admin_qq,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {"admin_qq": row[0], "admin_nickname": row[1], "added_by": row[2], 
                    "add_time": row[3], "permission_level": row[4]}
        return None
    
    # ==================== 群隔离管理方法 ====================
    
    def add_group_to_whitelist(self, group_id: str, group_name: str = None, added_by: str = None, description: str = None):
        """添加群到白名单"""
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute('''
            INSERT OR REPLACE INTO group_whitelist (group_id, group_name, is_enabled, added_by, add_time, update_time, description)
            VALUES (?, ?, 1, ?, ?, ?, ?)
        ''', (group_id, group_name, added_by, now, now, description))
        
        conn.commit()
        conn.close()
        logger.info(f"添加群到白名单 | group={group_id} | name={group_name}")
    
    def remove_group_from_whitelist(self, group_id: str):
        """从白名单移除群"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM group_whitelist WHERE group_id = ?', (group_id,))
        
        conn.commit()
        conn.close()
        logger.info(f"从白名单移除群 | group={group_id}")
    
    def enable_group(self, group_id: str):
        """启用群"""
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute('UPDATE group_whitelist SET is_enabled = 1, update_time = ? WHERE group_id = ?', (now, group_id))
        
        conn.commit()
        conn.close()
        logger.info(f"启用群 | group={group_id}")
    
    def disable_group(self, group_id: str):
        """禁用群"""
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute('UPDATE group_whitelist SET is_enabled = 0, update_time = ? WHERE group_id = ?', (now, group_id))
        
        conn.commit()
        conn.close()
        logger.info(f"禁用群 | group={group_id}")
    
    def is_group_enabled(self, group_id: str) -> bool:
        """检查群是否启用"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT is_enabled FROM group_whitelist WHERE group_id = ?', (group_id,))
        row = cursor.fetchone()
        conn.close()
        
        # 如果群不在白名单中，默认返回False（严格模式）
        if row is None:
            return False
        
        return row[0] == 1
    
    def get_all_whitelist_groups(self) -> List[Dict]:
        """获取所有白名单群"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT group_id, group_name, is_enabled, added_by, add_time, update_time, description
            FROM group_whitelist
            ORDER BY update_time DESC
        ''')
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            "group_id": r[0], "group_name": r[1], "is_enabled": r[2],
            "added_by": r[3], "add_time": r[4], "update_time": r[5], 
            "description": r[6]
        } for r in rows]
    
    # ==================== 群管理员映射方法 ====================
    
    def add_group_admin(self, group_id: str, admin_qq: str, added_by: str = None):
        """添加群专属管理员"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO group_admins (group_id, admin_qq, added_by, add_time)
            VALUES (?, ?, ?, ?)
        ''', (group_id, admin_qq, added_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        conn.close()
        logger.info(f"添加群管理员 | group={group_id} | admin={admin_qq}")
    
    def remove_group_admin(self, group_id: str, admin_qq: str):
        """移除群专属管理员"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM group_admins WHERE group_id = ? AND admin_qq = ?', (group_id, admin_qq))
        
        conn.commit()
        conn.close()
        logger.info(f"移除群管理员 | group={group_id} | admin={admin_qq}")
    
    def is_group_admin(self, group_id: str, admin_qq: str) -> bool:
        """检查是否是群专属管理员"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT 1 FROM group_admins WHERE group_id = ? AND admin_qq = ?', (group_id, admin_qq))
        result = cursor.fetchone()
        conn.close()
        
        return result is not None
    
    def get_group_admins(self, group_id: str) -> List[str]:
        """获取群的专属管理员列表"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT admin_qq FROM group_admins WHERE group_id = ?', (group_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [r[0] for r in rows]
    
    # ==================== 兼容性方法（保留原有的方法名） ====================
    
    def add_or_update_group(self, group_id: str, group_name: str = None):
        """添加或更新群聊信息（兼容性方法）"""
        self.add_group_to_whitelist(group_id, group_name)
    
    def get_all_groups(self) -> List[Dict]:
        """获取所有群聊信息（兼容性方法）"""
        return self.get_all_whitelist_groups()
    
    def save_email_config(self, config_key: str, config_value: str):
        """保存邮件配置"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO email_config (config_key, config_value, update_time)
            VALUES (?, ?, ?)
            ON CONFLICT(config_key) DO UPDATE SET
                config_value = excluded.config_value,
                update_time = excluded.update_time
        ''', (config_key, config_value, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        conn.close()
        logger.info(f"保存邮件配置 | key={config_key}")
    
    def get_email_config(self, config_key: str) -> Optional[str]:
        """获取邮件配置"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT config_value FROM email_config WHERE config_key = ?', (config_key,))
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else None
    
    def get_verification_records(self, user_qq: str = None, group_id: str = None,
                                limit: int = 100) -> List[Dict]:
        """获取验证记录"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT user_qq, user_nickname, group_id, group_name,
                   verification_mode, verification_result, join_time,
                   verify_time, leave_time, email
            FROM verification_records
            WHERE 1=1
        '''
        params = []
        
        if user_qq:
            query += ' AND user_qq = ?'
            params.append(user_qq)
        if group_id:
            query += ' AND group_id = ?'
            params.append(group_id)
        
        query += ' ORDER BY join_time DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            "user_qq": r[0], "user_nickname": r[1], "group_id": r[2],
            "group_name": r[3], "verification_mode": r[4],
            "verification_result": r[5], "join_time": r[6],
            "verify_time": r[7], "leave_time": r[8], "email": r[9]
        } for r in rows]
    
    def generate_statistics_report(self) -> Dict[str, Any]:
        """生成统计报告"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 总记录数
        cursor.execute('SELECT COUNT(*) FROM verification_records')
        total_records = cursor.fetchone()[0]
        
        # 成功次数
        cursor.execute('SELECT COUNT(*) FROM verification_records WHERE verification_result = 1')
        success_count = cursor.fetchone()[0]
        
        # 失败次数
        cursor.execute('SELECT COUNT(*) FROM verification_records WHERE verification_result = 0')
        fail_count = cursor.fetchone()[0]
        
        # 今日记录
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute('''
            SELECT COUNT(*) FROM verification_records 
            WHERE join_time LIKE ?
        ''', (f"{today}%",))
        today_count = cursor.fetchone()[0]
        
        # 唯一用户数
        cursor.execute('SELECT COUNT(DISTINCT user_qq) FROM verification_records')
        unique_users = cursor.fetchone()[0]
        
        # 群聊数
        cursor.execute('SELECT COUNT(DISTINCT group_id) FROM verification_records')
        unique_groups = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_records": total_records,
            "success_count": success_count,
            "fail_count": fail_count,
            "success_rate": round(success_count / total_records * 100, 2) if total_records > 0 else 0,
            "today_count": today_count,
            "unique_users": unique_users,
            "unique_groups": unique_groups
        }
    
    def export_to_html(self) -> str:
        """导出数据为HTML报告"""
        report = self.generate_statistics_report()
        records = self.get_verification_records(limit=50)
        
        html = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>验证数据报告</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .stats {{ display: flex; flex-wrap: wrap; gap: 20px; margin: 20px 0; }}
        .stat-box {{ background: #f5f5f5; padding: 15px; border-radius: 8px; min-width: 150px; }}
        .stat-box h3 {{ margin: 0 0 10px 0; color: #666; font-size: 14px; }}
        .stat-box .value {{ font-size: 24px; font-weight: bold; color: #333; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .success {{ color: green; }}
        .fail {{ color: red; }}
    </style>
</head>
<body>
    <h1>📊 验证数据统计报告</h1>
    <p>生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <div class="stats">
        <div class="stat-box">
            <h3>总记录数</h3>
            <div class="value">{report['total_records']}</div>
        </div>
        <div class="stat-box">
            <h3>成功次数</h3>
            <div class="value success">{report['success_count']}</div>
        </div>
        <div class="stat-box">
            <h3>失败次数</h3>
            <div class="value fail">{report['fail_count']}</div>
        </div>
        <div class="stat-box">
            <h3>成功率</h3>
            <div class="value">{report['success_rate']}%</div>
        </div>
        <div class="stat-box">
            <h3>今日验证</h3>
            <div class="value">{report['today_count']}</div>
        </div>
        <div class="stat-box">
            <h3>唯一用户</h3>
            <div class="value">{report['unique_users']}</div>
        </div>
        <div class="stat-box">
            <h3>群聊数</h3>
            <div class="value">{report['unique_groups']}</div>
        </div>
    </div>
    
    <h2>最近验证记录</h2>
    <table>
        <tr>
            <th>用户QQ</th>
            <th>昵称</th>
            <th>群聊</th>
            <th>验证方式</th>
            <th>结果</th>
            <th>入群时间</th>
            <th>邮箱</th>
        </tr>
'''
        
        for record in records:
            result_text = "✅ 成功" if record['verification_result'] == 1 else "❌ 失败" if record['verification_result'] == 0 else "⏳ 进行中"
            mode_text = "邮箱" if record['verification_mode'] == 1 else "数学题" if record['verification_mode'] == 2 else "用户自选"
            
            html += f'''
        <tr>
            <td>{record['user_qq']}</td>
            <td>{record['user_nickname'] or '未知'}</td>
            <td>{record['group_name'] or record['group_id']}</td>
            <td>{mode_text}</td>
            <td class="{'success' if record['verification_result'] == 1 else 'fail'}">{result_text}</td>
            <td>{record['join_time']}</td>
            <td>{record['email'] or '-'}</td>
        </tr>
'''
        
        html += '''
    </table>
</body>
</html>
'''
        return html
    
    def save_config(self, config_key: str, config_value: Any, config_type: str = 'string'):
        """保存单个配置项"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 转换值为字符串
        if isinstance(config_value, bool):
            config_value = str(1 if config_value else 0)
            config_type = 'bool'
        elif isinstance(config_value, int):
            config_value = str(config_value)
            config_type = 'int'
        elif isinstance(config_value, list):
            config_value = json.dumps(config_value, ensure_ascii=False)
            config_type = 'list'
        else:
            config_value = str(config_value)
        
        cursor.execute('''
            INSERT INTO plugin_config (config_key, config_value, config_type, update_time)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(config_key) DO UPDATE SET
                config_value = excluded.config_value,
                config_type = excluded.config_type,
                update_time = excluded.update_time
        ''', (config_key, config_value, config_type, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        conn.close()
        logger.info(f"保存配置 | key={config_key} | type={config_type}")
    
    def get_config(self, config_key: str, default_value: Any = None) -> Any:
        """获取单个配置项"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT config_value, config_type FROM plugin_config WHERE config_key = ?', (config_key,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return default_value
        
        config_value, config_type = row
        
        # 根据类型转换
        if config_type == 'bool':
            return config_value == '1'
        elif config_type == 'int':
            try:
                return int(config_value)
            except:
                return default_value
        elif config_type == 'list':
            try:
                return json.loads(config_value)
            except:
                return default_value
        
        return config_value
    
    def save_all_config(self, config_dict: Dict[str, Any]):
        """批量保存所有配置"""
        for key, value in config_dict.items():
            self.save_config(key, value)
        logger.info(f"批量保存配置完成 | count={len(config_dict)}")
    
    def get_all_config(self) -> Dict[str, Any]:
        """获取所有配置项"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT config_key, config_value, config_type FROM plugin_config')
        rows = cursor.fetchall()
        conn.close()
        
        result = {}
        for key, value, config_type in rows:
            if config_type == 'bool':
                result[key] = value == '1'
            elif config_type == 'int':
                try:
                    result[key] = int(value)
                except:
                    result[key] = value
            elif config_type == 'list':
                try:
                    result[key] = json.loads(value)
                except:
                    result[key] = []
            else:
                result[key] = value
        
        logger.info(f"获取所有配置完成 | count={len(result)}")
        return result
    
    def get_config_version(self) -> Optional[str]:
        """获取配置版本（如果有）"""
        return self.get_config('config_version')
    
    def update_config_version(self, version: str):
        """更新配置版本"""
        self.save_config('config_version', version, 'string')
