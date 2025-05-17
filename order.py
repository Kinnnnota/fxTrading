from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional
from datetime import datetime

class OrderType(Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderStatus(Enum):
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    CANCELLED = "CANCELLED"

@dataclass
class Order:
    order_id: str
    timestamp: datetime
    order_type: OrderType
    price: Decimal
    quantity: Decimal
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    status: OrderStatus = OrderStatus.PENDING
    executed_price: Optional[Decimal] = None
    executed_time: Optional[datetime] = None

    # 点差和手续费常量
    SPREAD = Decimal('0.2')  # 0.2点差
    COMMISSION = Decimal('100')  # 100手续费

    def get_execution_price(self, market_price: Decimal) -> Decimal:
        """根据订单类型和市场价计算实际执行价格（考虑点差）"""
        if self.order_type == OrderType.BUY:
            # 买入时，实际价格 = 市场价 + 点差/2
            return market_price + (self.SPREAD / Decimal('2'))
        else:  # SELL
            # 卖出时，实际价格 = 市场价 - 点差/2
            return market_price - (self.SPREAD / Decimal('2'))

    def is_executable(self, current_price: Decimal) -> bool:
        """检查订单是否应该执行（触发止盈或止损）"""
        if self.status != OrderStatus.PENDING:
            return False

        # 计算考虑点差后的实际价格
        execution_price = self.get_execution_price(current_price)

        if self.order_type == OrderType.BUY:
            # 买入订单的止盈止损逻辑
            if self.take_profit and execution_price >= self.take_profit:
                return True
            if self.stop_loss and execution_price <= self.stop_loss:
                return True
        else:  # SELL
            # 卖出订单的止盈止损逻辑
            if self.take_profit and execution_price <= self.take_profit:
                return True
            if self.stop_loss and execution_price >= self.stop_loss:
                return True

        return False

    def execute(self, market_price: Decimal, timestamp: datetime):
        """执行订单"""
        self.executed_price = self.get_execution_price(market_price)
        self.executed_time = timestamp
        self.status = OrderStatus.EXECUTED

    def calculate_pnl(self) -> Optional[Decimal]:
        """计算订单的盈亏（考虑点差和手续费）"""
        if not self.executed_price or self.status != OrderStatus.EXECUTED:
            return None

        # 计算基础盈亏
        if self.order_type == OrderType.BUY:
            base_pnl = (self.executed_price - self.price) * self.quantity
        else:  # SELL
            base_pnl = (self.price - self.executed_price) * self.quantity

        # 减去手续费
        total_pnl = base_pnl - self.COMMISSION

        return total_pnl

    def get_trade_details(self) -> dict:
        """获取交易详情"""
        if not self.executed_price or self.status != OrderStatus.EXECUTED:
            return None

        return {
            "order_id": self.order_id,
            "type": self.order_type.value,
            "status": self.status.value,
            "entry_price": self.price,
            "executed_price": self.executed_price,
            "quantity": self.quantity,
            "spread": self.SPREAD,
            "commission": self.COMMISSION,
            "pnl": self.calculate_pnl(),
            "executed_time": self.executed_time.isoformat() if self.executed_time else None
        } 