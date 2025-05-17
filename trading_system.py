import asyncio
import csv
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
import uuid
import pandas as pd

from account import Account
from order import Order, OrderType, OrderStatus

class TradingSystem:
    # 添加默认交易手数常量
    DEFAULT_QUANTITY = Decimal('10000')

    def __init__(self, csv_file: str, account_file: str = "account.json"):
        self.csv_file = csv_file
        self.account = Account(account_file)
        self.orders: Dict[str, Order] = {}
        self._load_market_data()

    def _load_market_data(self):
        """加载市场数据到内存"""
        # 读取CSV文件，指定列名
        self.market_data = pd.read_csv(
            self.csv_file,
            names=['Date', 'Time', 'DayOfWeek', 'Open', 'High', 'Low', 'Close', 'Volume'],
            header=None  # 指定没有header
        )
        
        # 合并日期和时间列，创建timestamp
        self.market_data['timestamp'] = pd.to_datetime(
            self.market_data['Date'] + ' ' + self.market_data['Time'],
            format='%Y.%m.%d %H:%M'
        )
        
        # 设置timestamp为索引并排序
        self.market_data.set_index('timestamp', inplace=True)
        self.market_data.sort_index(inplace=True)
        
        # 确保价格列使用Decimal类型
        price_columns = ['Open', 'High', 'Low', 'Close']
        for col in price_columns:
            self.market_data[col] = self.market_data[col].apply(lambda x: Decimal(str(x)))

    async def place_order(self, 
                         timestamp: datetime,
                         order_type: OrderType,
                         price: Decimal,
                         quantity: Decimal = DEFAULT_QUANTITY,  # 设置默认值
                         take_profit: Optional[Decimal] = None,
                         stop_loss: Optional[Decimal] = None) -> str:
        """异步下单"""
        order_id = str(uuid.uuid4())
        order = Order(
            order_id=order_id,
            timestamp=timestamp,
            order_type=order_type,
            price=price,
            quantity=quantity,
            take_profit=take_profit,
            stop_loss=stop_loss
        )
        self.orders[order_id] = order
        
        # 启动异步任务处理订单
        asyncio.create_task(self._process_order(order))
        return order_id

    async def _process_order(self, order: Order):
        """异步处理订单"""
        # 获取订单时间戳之后的数据
        future_data = self.market_data[order.timestamp:]
        
        for timestamp, row in future_data.iterrows():
            # 使用当前K线的价格范围检查是否触发订单
            current_high = row['High']
            current_low = row['Low']
            
            if order.is_executable(current_high) or order.is_executable(current_low):
                # 确定执行价格
                if order.order_type == OrderType.BUY:
                    # 买入订单在触发时使用当前K线的最高价
                    execute_price = current_high
                else:  # SELL
                    # 卖出订单在触发时使用当前K线的最低价
                    execute_price = current_low
                
                # 执行订单
                order.execute(execute_price, timestamp)
                # 计算盈亏并更新账户
                pnl = order.calculate_pnl()
                if pnl is not None:
                    self.account.update_balance(pnl)
                break

    def get_order_status(self, order_id: str) -> Optional[Order]:
        """获取订单状态"""
        return self.orders.get(order_id)

    def get_all_orders(self) -> List[Order]:
        """获取所有订单"""
        return list(self.orders.values())

    def get_account_balance(self) -> Decimal:
        """获取账户余额"""
        return self.account.get_balance()

    async def cancel_order(self, order_id: str) -> bool:
        """取消订单"""
        if order_id in self.orders:
            order = self.orders[order_id]
            if order.status == OrderStatus.PENDING:
                order.status = OrderStatus.CANCELLED
                return True
        return False 