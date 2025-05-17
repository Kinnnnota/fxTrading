import json
import os
from typing import Dict
from decimal import Decimal

class Account:
    def __init__(self, account_file: str = "account.json"):
        self.account_file = account_file
        self.balance = Decimal('0')
        self._load_account()

    def _load_account(self):
        """从文件加载账户余额"""
        if os.path.exists(self.account_file):
            try:
                with open(self.account_file, 'r') as f:
                    data = json.load(f)
                    self.balance = Decimal(str(data.get('balance', '0')))
            except Exception as e:
                print(f"Error loading account: {e}")
                self.balance = Decimal('0')
        else:
            # 如果文件不存在，创建新账户
            self.balance = Decimal('100000')  # 默认初始资金10万
            self._save_account()

    def _save_account(self):
        """保存账户余额到文件"""
        try:
            with open(self.account_file, 'w') as f:
                json.dump({'balance': str(self.balance)}, f)
        except Exception as e:
            print(f"Error saving account: {e}")

    def update_balance(self, amount: Decimal):
        """更新账户余额"""
        self.balance += amount
        self._save_account()

    def get_balance(self) -> Decimal:
        """获取当前账户余额"""
        return self.balance 