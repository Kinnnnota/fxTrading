import asyncio
import json
import os
import pandas as pd
from datetime import datetime, timedelta
import boto3
from dotenv import load_dotenv
from prompt_utils import PromptManager
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import glob
import subprocess
import sys

# 加载环境变量
load_dotenv()

# 配置常量
AWS_REGION = os.getenv('AWS_REGION', 'ap-northeast-3')
CLAUDE_MODEL_ID = os.getenv('CLAUDE_MODEL_ID', 'apac.anthropic.claude-3-5-sonnet-20241022-v2:0')
CLAUDE_MAX_TOKENS = int(os.getenv('CLAUDE_MAX_TOKENS', '1000'))
CLAUDE_ANTHROPIC_VERSION = os.getenv('CLAUDE_ANTHROPIC_VERSION', 'bedrock-2023-05-31')

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class AIAnalyzer:
    def __init__(self):
        self.prompt_manager = PromptManager()
        self.bedrock_client = self._create_claude_client()
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
                current_time="2024-02-12T04:00:00",
                pair="USD/JPY",
                data_12h="[]",
                current_price="150.00",
                current_balance="10000"
            )
            logging.info("提示管理器加载成功")
            return True
        except Exception as e:
            logging.error(f"提示管理器加载失败: {str(e)}")
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
        
        try:
            response = self.bedrock_client.invoke_model(
                modelId=CLAUDE_MODEL_ID,
                body=json.dumps(body)
            )
            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text']
        except Exception as e:
            logging.error(f"调用模型时发生错误: {str(e)}")
            return None

    def format_market_context(self, df: pd.DataFrame) -> dict:
        """将数据格式化为市场上下文"""
        if df.empty:
            return None

        # 获取最新数据
        latest_data = df.iloc[-1]
        
        # 获取最近12小时的数据（144个5分钟K线）
        last_12h_data = df.tail(144)
        
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
            "pair": "USD/JPY",  # 根据文件名判断货币对
            "data_12h": klines,
            "current_price": float(latest_data['close']),
            "current_balance": 10000.0  # 固定初始余额
        }
        
        return context

    async def process_file(self, file_path: str):
        """处理单个文件"""
        try:
            # 读取CSV文件
            try:
                df = pd.read_csv(file_path, header=None, encoding='utf-8',
                               names=['date', 'time', 'day', 'open', 'high', 'low', 'close', 'volume'])
            except UnicodeDecodeError:
                try:
                    df = pd.read_csv(file_path, header=None, encoding='gbk',
                                   names=['date', 'time', 'day', 'open', 'high', 'low', 'close', 'volume'])
                except UnicodeDecodeError:
                    df = pd.read_csv(file_path, header=None, encoding='shift-jis',
                                   names=['date', 'time', 'day', 'open', 'high', 'low', 'close', 'volume'])
            
            # 合并日期和时间列，创建datetime列
            df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'], 
                                           format='%Y.%m.%d %H:%M')
            
            # 设置timestamp为索引
            df.set_index('timestamp', inplace=True)
            
            # 确保数据按时间排序
            df.sort_index(inplace=True)
            
            # 获取货币对名称（从文件名）
            pair = os.path.splitext(os.path.basename(file_path))[0]
            
            # 获取当前时间（使用数据中的最新时间）
            current_time = df.index[-1]
            
            # 格式化市场上下文
            market_context = self.format_market_context(df)
            if market_context is None:
                logging.error(f"无法格式化市场数据: {file_path}")
                return
            
            # 获取交易提示模板
            trading_prompt = self.prompt_manager.format_prompt(
                'trading_decision',
                current_time=current_time.strftime('%Y-%m-%dT%H:%M:%S'),
                pair=pair,
                data_12h=json.dumps(market_context["data_12h"]),
                current_price=str(market_context["current_price"]),
                current_balance=str(market_context["current_balance"])
            )
            
            # 调用AI获取分析结果
            ai_response = self._invoke_claude(trading_prompt)
            if not ai_response:
                logging.error(f"AI未能生成有效的分析结果: {file_path}")
                return
            
            # 保存AI分析结果
            output_file = os.path.join(os.path.dirname(file_path), f"{pair}_analysis.txt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"=== 分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                f.write(f"=== 数据文件: {file_path} ===\n")
                f.write(f"=== 当前时间点: {current_time} ===\n")
                f.write("\n=== AI 提示词 ===\n")
                f.write(trading_prompt)
                f.write("\n\n=== AI 分析结果 ===\n")
                f.write(ai_response)
            
            logging.info(f"已完成文件分析: {file_path}")
            logging.info(f"分析结果已保存到: {output_file}")
            
            # 运行 process_analysis.py 处理新生成的分析文件
            try:
                subprocess.run([sys.executable, "process_analysis.py"], check=True)
                logging.info("成功运行 process_analysis.py 处理分析结果")
                
                # 删除原始CSV文件
                try:
                    os.remove(file_path)
                    logging.info(f"已删除原始文件: {file_path}")
                except Exception as e:
                    logging.error(f"删除原始文件时出错 {file_path}: {str(e)}")
                    
            except subprocess.CalledProcessError as e:
                logging.error(f"运行 process_analysis.py 时出错: {str(e)}")
            except Exception as e:
                logging.error(f"运行 process_analysis.py 时发生未知错误: {str(e)}")
            
        except Exception as e:
            logging.error(f"处理文件时出错 {file_path}: {str(e)}")

class MT4DataHandler(FileSystemEventHandler):
    def __init__(self, mt4data_dir):
        self.mt4data_dir = mt4data_dir
        self.analyzer = AIAnalyzer()
        self.processing_files = set()
        self.processed_files = set()
        # 定义需要忽略的文件
        self.ignored_files = {'orders.csv', 'trading_signals.csv'}
        
        # 处理启动时已存在的文件
        self.process_existing_files()
    
    def process_existing_files(self):
        """处理目录中已存在的CSV文件"""
        csv_files = [f for f in glob.glob(os.path.join(self.mt4data_dir, "*.csv"))
                    if not f.endswith('_analysis.txt') and 
                    os.path.basename(f) not in self.ignored_files]
        for file_path in csv_files:
            if file_path not in self.processed_files and file_path not in self.processing_files:
                asyncio.create_task(self.process_file(file_path))
    
    async def process_file(self, file_path):
        """异步处理单个文件"""
        if file_path in self.processing_files or file_path in self.processed_files:
            return
            
        # 检查是否是忽略的文件
        if os.path.basename(file_path) in self.ignored_files:
            logging.info(f"忽略处理文件: {file_path}")
            return
            
        self.processing_files.add(file_path)
        try:
            await self.analyzer.process_file(file_path)
            self.processed_files.add(file_path)
        finally:
            self.processing_files.remove(file_path)
    
    def on_created(self, event):
        """当新文件创建时触发"""
        if not event.is_directory and event.src_path.endswith('.csv'):
            # 检查是否是忽略的文件
            if os.path.basename(event.src_path) in self.ignored_files:
                logging.info(f"忽略新创建的文件: {event.src_path}")
                return
                
            if not event.src_path.endswith('_analysis.txt'):
                logging.info(f"检测到新文件: {event.src_path}")
                asyncio.create_task(self.process_file(event.src_path))

async def start_monitoring():
    # MT4data目录路径
    mt4data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MT4data")
    
    # 确保目录存在
    if not os.path.exists(mt4data_dir):
        os.makedirs(mt4data_dir)
    
    # 创建事件处理器
    event_handler = MT4DataHandler(mt4data_dir)
    
    # 创建观察者
    observer = Observer()
    observer.schedule(event_handler, mt4data_dir, recursive=False)
    
    # 启动观察者
    observer.start()
    logging.info(f"开始监控目录: {mt4data_dir}")
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logging.info("监控已停止")
    
    observer.join()

if __name__ == "__main__":
    try:
        asyncio.run(start_monitoring())
    except Exception as e:
        logging.error(f"程序执行过程中出现错误: {e}") 