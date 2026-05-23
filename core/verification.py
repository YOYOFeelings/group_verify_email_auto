import asyncio
import random
import string
from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

@dataclass
class PendingVerification:
    """待验证用户"""
    uid: str
    gid: str
    email: str
    code: str
    mode: str  # 'email' or 'math'
    math_question: Optional[str] = None
    math_answer: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)

class VerificationManager:
    """验证管理器"""
    
    def __init__(self, timeout: int = 600):
        self.pending: Dict[str, PendingVerification] = {}
        self.timeout = timeout
        self.cooldowns: Dict[str, datetime] = {}
        self.cooldown_seconds = 60
    
    def generate_code(self, length: int = 6) -> str:
        """生成验证码"""
        return ''.join(random.choices(string.digits, k=length))
    
    def generate_math(self) -> tuple[str, int]:
        """生成数学题"""
        a = random.randint(10, 99)
        b = random.randint(10, 99)
        op = random.choice(['+', '-'])
        if op == '+':
            return f"{a} + {b} = ?", a + b
        else:
            if a < b:
                a, b = b, a
            return f"{a} - {b} = ?", a - b
    
    def add_pending(self, uid: str, gid: str, mode: str = 'email', email: str = None) -> PendingVerification:
        """添加待验证用户"""
        if mode == 'email':
            code = self.generate_code()
            pending = PendingVerification(
                uid=uid, gid=gid, email=email, code=code, mode='email'
            )
        else:
            question, answer = self.generate_math()
            pending = PendingVerification(
                uid=uid, gid=gid, email="", code="", mode='math',
                math_question=question, math_answer=answer
            )
        
        self.pending[f"{uid}_{gid}"] = pending
        return pending
    
    def check_code(self, uid: str, gid: str, code: str) -> bool:
        """验证验证码"""
        key = f"{uid}_{gid}"
        if key not in self.pending:
            return False
        
        pending = self.pending[key]
        if pending.mode == 'email':
            return pending.code == code
        else:
            try:
                return pending.math_answer == int(code)
            except:
                return False
    
    def check_cooldown(self, uid: str) -> bool:
        """检查冷却时间"""
        if uid not in self.cooldowns:
            return True
        
        elapsed = (datetime.now() - self.cooldowns[uid]).total_seconds()
        return elapsed >= self.cooldown_seconds
    
    def set_cooldown(self, uid: str):
        """设置冷却时间"""
        self.cooldowns[uid] = datetime.now()
    
    def remove_pending(self, uid: str, gid: str):
        """移除待验证用户"""
        key = f"{uid}_{gid}"
        if key in self.pending:
            del self.pending[key]
    
    def get_pending(self, uid: str, gid: str) -> Optional[PendingVerification]:
        """获取待验证用户"""
        return self.pending.get(f"{uid}_{gid}")
    
    def is_timeout(self, pending: PendingVerification) -> bool:
        """检查是否超时"""
        elapsed = (datetime.now() - pending.timestamp).total_seconds()
        return elapsed >= self.timeout
    
    def cleanup(self):
        """清理超时用户"""
        to_remove = []
        for key, pending in self.pending.items():
            if self.is_timeout(pending):
                to_remove.append(key)
        
        for key in to_remove:
            del self.pending[key]
        
        return len(to_remove)
