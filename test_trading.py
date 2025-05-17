import asyncio
from datetime import datetime
from decimal import Decimal
from trading_system import TradingSystem
from order import OrderType, OrderStatus

async def test_trading_scenarios():
    # 初始化交易系统
    trading_system = TradingSystem("csvFiles/processed_data.csv")
    
    print("初始账户余额:", trading_system.get_account_balance())
    print("\n开始测试交易场景...\n")

    # 测试场景1: 买入订单，设置止盈止损
    print("测试场景1: 买入订单")
    buy_order_id = await trading_system.place_order(
        timestamp=datetime(2024, 1, 19, 10, 15),  # 使用CSV文件中的第一个时间点
        order_type=OrderType.BUY,
        price=Decimal("148.215"),  # 使用第一个K线的开盘价
        take_profit=Decimal("148.300"),  # 设置止盈
        stop_loss=Decimal("148.150")     # 设置止损
    )
    
    # 测试场景2: 卖出订单，只设置止盈
    print("\n测试场景2: 卖出订单")
    sell_order_id = await trading_system.place_order(
        timestamp=datetime(2024, 1, 19, 10, 15),
        order_type=OrderType.SELL,
        price=Decimal("148.215"),
        take_profit=Decimal("148.150"),  # 只设置止盈
        stop_loss=None                    # 不设置止损
    )

    # 等待一段时间让订单处理
    print("\n等待订单处理...")
    await asyncio.sleep(5)

    # 检查订单状态
    print("\n检查订单状态:")
    for order_id in [buy_order_id, sell_order_id]:
        order = trading_system.get_order_status(order_id)
        if order:
            print(f"\n订单 {order_id}:")
            print(f"类型: {order.order_type.value}")
            print(f"状态: {order.status.value}")
            print(f"开仓价格: {order.price}")
            print(f"数量: {order.quantity}")
            if order.take_profit:
                print(f"止盈价格: {order.take_profit}")
            if order.stop_loss:
                print(f"止损价格: {order.stop_loss}")
            if order.executed_price:
                print(f"市场执行价格: {order.executed_price}")
                print(f"点差: {order.SPREAD}")
                print(f"手续费: {order.COMMISSION}")
                print(f"执行时间: {order.executed_time}")
                print(f"基础盈亏: {(order.executed_price - order.price) * order.quantity if order.order_type == OrderType.BUY else (order.price - order.executed_price) * order.quantity}")
                print(f"扣除手续费后盈亏: {order.calculate_pnl()}")
            print("-" * 50)

    # 打印最终账户余额
    print("\n最终账户余额:", trading_system.get_account_balance())

    # 打印所有订单的汇总信息
    print("\n所有订单汇总:")
    all_orders = trading_system.get_all_orders()
    total_pnl = Decimal('0')
    total_commission = Decimal('0')
    executed_orders = 0
    
    for order in all_orders:
        if order.status == OrderStatus.EXECUTED:
            executed_orders += 1
            pnl = order.calculate_pnl()
            if pnl is not None:
                total_pnl += pnl
                total_commission += order.COMMISSION
    
    print(f"执行订单数: {executed_orders}")
    print(f"总手续费: {total_commission}")
    print(f"总盈亏: {total_pnl}")
    print(f"净盈亏: {total_pnl - total_commission}")

if __name__ == "__main__":
    asyncio.run(test_trading_scenarios()) 