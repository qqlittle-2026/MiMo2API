"""配置管理模块"""

import json
import threading
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, asdict


@dataclass
class MimoAccount:
    """Mimo账号配置"""
    service_token: str
    user_id: str
    xiaomichatbot_ph: str
    login_time: str = ""
    last_test: str = ""
    is_valid: bool = False

    def to_dict(self):
        d = asdict(self)
        d["token_masked"] = self.service_token[:16] + "..." + self.service_token[-6:] if len(self.service_token) > 22 else "***"
        return d


@dataclass
class Config:
    """应用配置"""
    api_keys: str = "sk-default"
    mimo_accounts: List[MimoAccount] = None
    models: List[str] = None  # 自定义模型列表，None 表示自动探测

    def __post_init__(self):
        if self.mimo_accounts is None:
            self.mimo_accounts = []
        if self.models is None:
            self.models = []

    def to_dict(self):
        d = {
            "api_keys": self.api_keys,
            "mimo_accounts": [acc.to_dict() for acc in self.mimo_accounts],
        }
        if self.models:
            d["models"] = self.models
        return d

    def to_save_dict(self):
        """用于保存到文件的格式（不含 token_masked）"""
        d = {
            "api_keys": self.api_keys,
            "mimo_accounts": [
                {k: v for k, v in acc.to_dict().items() if k != "token_masked"}
                for acc in self.mimo_accounts
            ],
        }
        if self.models:
            d["models"] = self.models
        return d


class ConfigManager:
    """配置管理器 - 线程安全"""

    def __init__(self, config_file: str = "config.json"):
        self.config_file = Path(config_file)
        self.config = Config()
        self.lock = threading.RLock()
        self.account_idx = 0
        self.load()

    def _load_from_env(self):
        """从环境变量加载配置"""
        import os
        service_token = os.environ.get('MIMO_SERVICE_TOKEN')
        user_id = os.environ.get('MIMO_USER_ID')
        xiaomichatbot_ph = os.environ.get('MIMO_XIAOMICHATBOT_PH')
        api_keys = os.environ.get('MIMO_API_KEYS')
        admin_password = os.environ.get('MIMO_ADMIN_PASSWORD')

        if service_token and user_id and xiaomichatbot_ph:
            accounts = [MimoAccount(
                service_token=service_token,
                user_id=user_id,
                xiaomichatbot_ph=xiaomichatbot_ph
            )]
            self.config = Config(
                api_keys=api_keys or 'sk-mimo',
                admin_password=admin_password or 'admin',
                mimo_accounts=accounts
            )
            print("[Config] Loaded from environment variables")
            return True
        return False

    def load(self):
        """加载配置（优先环境变量，其次文件）"""
        if self._load_from_env():
            return
        if not self.config_file.exists():
            self.save()
            return
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                accounts = [
                    MimoAccount(**{k: v for k, v in acc.items() if k in MimoAccount.__dataclass_fields__})
                    for acc in data.get('mimo_accounts', [])
                ]
                self.config = Config(
                    api_keys=data.get('api_keys', 'sk-default'),
                    mimo_accounts=accounts,
                    models=data.get('models', [])
                )
        except Exception as e:
            print(f"加载配置失败: {e}")
            self.config = Config()
            self.save()

    def save(self):
        """保存配置"""
        with self.lock:
            try:
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(self.config.to_save_dict(), f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"保存配置失败: {e}")

    def validate_api_key(self, key: str) -> bool:
        """验证API Key"""
        with self.lock:
            keys = [k.strip() for k in self.config.api_keys.split(',')]
            return key in keys

    def get_next_account(self) -> Optional[MimoAccount]:
        """获取下一个账号（轮询）"""
        with self.lock:
            if not self.config.mimo_accounts:
                return None
            account = self.config.mimo_accounts[self.account_idx % len(self.config.mimo_accounts)]
            self.account_idx += 1
            return account

    def update_config(self, new_config: dict):
        """更新配置"""
        with self.lock:
            accounts = [
                MimoAccount(**{k: v for k, v in acc.items() if k in MimoAccount.__dataclass_fields__})
                for acc in new_config.get('mimo_accounts', [])
            ]
            self.config = Config(
                api_keys=new_config.get('api_keys', 'sk-default'),
                mimo_accounts=accounts,
                models=new_config.get('models', [])
            )
            self.save()

    def get_config(self) -> dict:
        """获取配置"""
        with self.lock:
            return self.config.to_dict()


# 全局配置管理器实例
config_manager = ConfigManager()
