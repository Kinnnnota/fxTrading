import boto3
import json
from dotenv import load_dotenv
import os
from prompt_utils import PromptManager
from datetime import datetime, timedelta
from decimal import Decimal
import asyncio
from trading_system import TradingSystem
from order import OrderType
import pandas as pd
import pytz
import re
import random
import time

# 加载环境变量
load_dotenv()

# 配置常量
AWS_REGION = os.getenv('AWS_REGION', 'ap-northeast-3')
CLAUDE_MODEL_ID = os.getenv('CLAUDE_MODEL_ID', 'apac.anthropic.claude-3-5-sonnet-20241022-v2:0')
CLAUDE_MAX_TOKENS = int(os.getenv('CLAUDE_MAX_TOKENS', '1000'))
CLAUDE_ANTHROPIC_VERSION = os.getenv('CLAUDE_ANTHROPIC_VERSION', 'bedrock-2023-05-31')

class TradingAI:
    def __init__(self, csv_file: str = "csvFiles/processed_data.csv"):
        self.trading_system = TradingSystem(csv_file)
        self.prompt_manager = PromptManager()
        self.bedrock_client = self._create_claude_client()
        self.data_df = None
        self._load_market_data()
        self._verify_prompt_manager()

    def _create_claude_client(self):
        """创建AWS Bedrock客户端"""
        return boto3.client(
            service_name='bedrock-runtime',
            region_name=AWS_REGION
        )

    def _verify_prompt_manager(self):
        """验证提示管理器是否正确加载"""
        try:
            trading_prompt = self.prompt_manager.format_prompt(
                'trading_decision',
                current_time="2024-02-12T04:00:00",  # 添加测试用的时间点
                pair="USD/JPY",
                data_12h="[]",
                current_price="150.00",
                current_balance="10000"
            )
            print("提示管理器加载成功")
            return True
        except Exception as e:
            print(f"提示管理器加载失败: {str(e)}")
            return False

    def _invoke_claude(self, prompt: str) -> str:
        """调用Claude模型"""
        body = {
            "anthropic_version": CLAUDE_ANTHROPIC_VERSION,
            "max_tokens": CLAUDE_MAX_TOKENS,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        max_retries = 10  # 增加到10次重试
        retry_count = 0
        base_delay = 1  # 基础延迟时间（秒）
        
        while retry_count < max_retries:
            try:
                response = self.bedrock_client.invoke_model(
                    modelId=CLAUDE_MODEL_ID,
                    body=json.dumps(body)
                )
                response_body = json.loads(response['body'].read())
                return response_body['content'][0]['text']
            except Exception as e:
                error_str = str(e)
                print(f"调用模型时发生错误: {error_str}")
                
                # 如果是限流错误，添加随机延迟后重试
                if "ThrottlingException" in error_str:
                    retry_count += 1
                    if retry_count < max_retries:
                        # 使用指数退避策略，基础延迟时间随重试次数增加
                        max_delay = base_delay * (2 ** retry_count)  # 1, 2, 4, 8, 16, 32, 64, 128, 256, 512
                        # 在基础延迟和最大延迟之间随机选择
                        delay = random.uniform(base_delay, min(max_delay, 60))  # 限制最大延迟为60秒
                        print(f"遇到限流，第 {retry_count} 次重试，等待 {delay:.2f} 秒...")
                        time.sleep(delay)
                        continue
                return None

    def _parse_ai_response(self, response: str) -> dict:
        """解析AI的响应，提取交易参数"""
        if not response or response.strip() == "":
            print("AI返回空响应，表示当前无交易机会")
            return None
            
        try:
            # 尝试从响应中提取 JSON 部分
            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                print("AI响应中未找到有效的JSON数据")
                return None
                
            json_str = json_match.group(0)
            # 尝试解析JSON响应
            data = json.loads(json_str)
            required_fields = ['timestamp', 'order_type', 'price', 'quantity', 'take_profit', 'stop_loss']
            
            # 验证必要字段
            for field in required_fields:
                if field not in data:
                    print(f"AI响应缺少必要字段: {field}")
                    return None
                    
            return {
                'timestamp': datetime.fromisoformat(data['timestamp']),
                'order_type': OrderType[data['order_type']],
                'price': Decimal(str(data['price'])),
                'quantity': Decimal(str(data['quantity'])),
                'take_profit': Decimal(str(data['take_profit'])) if data.get('take_profit') else None,
                'stop_loss': Decimal(str(data['stop_loss'])) if data.get('stop_loss') else None
            }
        except json.JSONDecodeError as e:
            print(f"AI响应中的JSON格式无效: {str(e)}")
            return None
        except Exception as e:
            print(f"解析AI响应时发生错误: {str(e)}")
            return None

    def _load_market_data(self):
        """加载并预处理市场数据"""
        try:
            # 读取CSV文件
            self.data_df = pd.read_csv("csvFiles/processed_data.csv", 
                                     header=None,
                                     names=['date', 'time', 'day', 'open', 'high', 'low', 'close', 'volume'])
            
            # 合并日期和时间列，创建datetime列
            self.data_df['timestamp'] = pd.to_datetime(self.data_df['date'] + ' ' + self.data_df['time'], 
                                                      format='%Y.%m.%d %H:%M')
            
            # 设置timestamp为索引
            self.data_df.set_index('timestamp', inplace=True)
            
            # 确保数据按时间排序
            self.data_df.sort_index(inplace=True)
            
        except Exception as e:
            print(f"加载市场数据时发生错误: {str(e)}")
            raise

    def get_historical_data(self, current_time: datetime, hours: int = 72) -> pd.DataFrame:
        """获取指定时间戳前N小时的数据"""
        try:
            # 计算开始时间
            start_time = current_time - timedelta(hours=hours)
            
            # 获取时间范围内的数据
            mask = (self.data_df.index >= start_time) & (self.data_df.index <= current_time)
            historical_data = self.data_df[mask].copy()
            
            return historical_data
        except Exception as e:
            print(f"获取历史数据时发生错误: {str(e)}")
            return pd.DataFrame()

    def format_market_context(self, historical_data: pd.DataFrame) -> dict:
        """将历史数据格式化为市场上下文"""
        if historical_data.empty:
            return None

        # 获取最新数据
        latest_data = historical_data.iloc[-1]
        
        # 获取最近12小时的数据（144个5分钟K线）
        last_12h_data = historical_data.tail(144)
        
        # 格式化K线数据为列表
        klines = []
        for _, row in last_12h_data.iterrows():
            kline = {
                "timestamp": row.name.strftime('%Y-%m-%dT%H:%M:%S'),
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close']),
                "volume": int(row['volume'])
            }
            klines.append(kline)
        
        # 构建市场上下文
        context = {
            "pair": "USD/JPY",  # 根据实际交易对设置
            "data_12h": klines,
            "current_price": float(latest_data['close']),
            "current_balance": float(self.trading_system.get_account_balance())
        }
        
        return context

    async def process_trading_decision(self, current_time: datetime) -> str:
        """处理指定时间点的AI交易决策"""
        # 获取历史数据
        historical_data = self.get_historical_data(current_time)
        if historical_data.empty:
            return "无法获取足够的历史数据进行分析"

        # 格式化市场上下文
        market_context = self.format_market_context(historical_data)
        if market_context is None:
            return "无法格式化市场数据"
        
        # 获取交易提示模板
        try:
            trading_prompt = self.prompt_manager.format_prompt(
                'trading_decision',
                current_time=current_time.strftime('%Y-%m-%dT%H:%M:%S'),  # 添加当前模拟时间点
                pair=market_context["pair"],
                data_12h=json.dumps(market_context["data_12h"]),
                current_price=str(market_context["current_price"]),
                current_balance=str(market_context["current_balance"])
            )
            
            # 打印格式化后的提示词
            print("\n=== AI 提示词 ===")
            print(trading_prompt)
            print("\n=== AI 响应 ===")
            
        except Exception as e:
            print(f"格式化交易提示时发生错误: {str(e)}")
            return "无法生成交易提示"
        
        # 调用AI获取交易决策
        ai_response = self._invoke_claude(trading_prompt)
        if not ai_response:
            return "AI未能生成有效的交易决策"
            
        print(ai_response)  # 打印 AI 的响应
        print("\n=== 交易结果 ===")

        # 解析AI响应
        trade_params = self._parse_ai_response(ai_response)
        if not trade_params:
            return "当前市场条件下无交易机会"

        # 执行交易
        order_id = await self.trading_system.place_order(**trade_params)
        
        # 等待一段时间让订单处理
        await asyncio.sleep(2)
        
        # 获取订单状态
        order = self.trading_system.get_order_status(order_id)
        if not order:
            return "订单创建失败"

        # 返回交易结果
        result = {
            "timestamp": current_time.strftime('%Y-%m-%d %H:%M:%S'),
            "order_id": order_id,
            "status": order.status.value,
            "type": order.order_type.value,
            "price": str(order.price),
            "quantity": str(order.quantity),
            "take_profit": str(order.take_profit) if order.take_profit else None,
            "stop_loss": str(order.stop_loss) if order.stop_loss else None,
            "executed_price": str(order.executed_price) if order.executed_price else None,
            "executed_time": order.executed_time.isoformat() if order.executed_time else None,
            "pnl": str(order.calculate_pnl()) if order.calculate_pnl() else None,
            "current_balance": str(self.trading_system.get_account_balance())
        }
        
        return json.dumps(result, indent=2)

async def main():
    # 初始化交易AI系统
    trading_ai = TradingAI()
    
    # 验证提示管理器
    if not trading_ai._verify_prompt_manager():
        print("提示管理器验证失败，程序退出")
        return
        
    if trading_ai.data_df is None or trading_ai.data_df.empty:
        print("无法加载市场数据，程序退出")
        return

    # 获取数据的时间范围
    start_time = trading_ai.data_df.index[0]
    end_time = trading_ai.data_df.index[-1]
    
    # 设置初始模拟时间（确保有足够的历史数据）
    current_sim_time = start_time + timedelta(hours=72)
    
    print(f"开始模拟交易，时间范围：{start_time} 到 {end_time}")
    print(f"初始模拟时间：{current_sim_time}")
    
    # 以4小时为间隔进行模拟
    while current_sim_time <= end_time:
        print(f"\n正在处理时间点：{current_sim_time}")
        result = await trading_ai.process_trading_decision(current_sim_time)
        print("\n交易结果：")
        print(result)
        
        # 移动到下一个时间点（4小时后）
        current_sim_time += timedelta(hours=4)
        
        # 添加短暂延迟以避免过快处理
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
