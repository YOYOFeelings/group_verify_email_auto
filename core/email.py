import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import os

class EmailSender:
    """邮件发送器"""
    
    def __init__(self, host: str, port: int, user: str, password: str, 
                 encryption: str = 'ssl', from_name: str = "验证助手"):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.encryption = encryption
        self.from_name = from_name
    
    async def send(self, to_email: str, subject: str, body: str) -> bool:
        """发送邮件"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.user}>"
            msg['To'] = to_email
            
            html_part = MIMEText(body, 'html', 'utf-8')
            msg.attach(html_part)
            
            if self.encryption == 'ssl':
                server = smtplib.SMTP_SSL(self.host, self.port)
            else:
                server = smtplib.SMTP(self.host, self.port)
                if self.encryption == 'tls':
                    server.starttls()
            
            server.login(self.user, self.password)
            server.sendmail(self.user, [to_email], msg.as_string())
            server.quit()
            
            return True
        except Exception as e:
            print(f"[EmailSender] 发送失败: {e}")
            return False
    
    @staticmethod
    async def test_connection(host: str, port: int, user: str, 
                            password: str, encryption: str) -> bool:
        """测试连接"""
        try:
            if encryption == 'ssl':
                server = smtplib.SMTP_SSL(host, port, timeout=5)
            else:
                server = smtplib.SMTP(host, port, timeout=5)
                if encryption == 'tls':
                    server.starttls()
            
            server.login(user, password)
            server.quit()
            return True
        except Exception as e:
            print(f"[EmailSender] 连接测试失败: {e}")
            return False
