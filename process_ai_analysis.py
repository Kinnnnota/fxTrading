import asyncio
import json
import os
import pandas as pd
from datetime import datetime, timedelta
import boto3
from dotenv import load_dotenv
from prompt_utils import PromptManager
import logging
import argparse
import sys
import subprocess
import random
import time

# 加载环境变量
load_dotenv()

# 配置常量
AWS_REGION = os.getenv('AWS_REGION', 'ap-northeast-3')
CLAUDE_MODEL_ID = os.getenv('CLAUDE_MODEL_ID', 'apac.anthropic.claude-3-5-sonnet-20241022-v2:0')
CLAUDE_MAX_TOKENS = int(os.getenv('CLAUDE_MAX_TOKENS', '1000'))
CLAUDE_ANTHROPIC_VERSION = os.getenv('CLAUDE_ANTHROPIC_VERSION', 'bedrock-2023-05-31')

# MT4路径配置
MT4_TERMINAL_PATH = os.getenv('MT4_TERMINAL_PATH')
MT4_FILES_DIR = os.getenv('MT4_FILES_DIR')
MT4DATA_DIR = os.getenv('MT4DATA_DIR')

if not all([MT4_TERMINAL_PATH, MT4_FILES_DIR, MT4DATA_DIR]):
    raise ValueError("缺少必要的环境变量配置")

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
                data_24h="[]",
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
                logging.error(f"调用模型时发生错误: {error_str}")
                
                # 如果是限流错误，添加随机延迟后重试
                if "ThrottlingException" in error_str:
                    retry_count += 1
                    if retry_count < max_retries:
                        # 使用指数退避策略，基础延迟时间随重试次数增加
                        max_delay = base_delay * (2 ** retry_count)  # 1, 2, 4, 8, 16, 32, 64, 128, 256, 512
                        # 在基础延迟和最大延迟之间随机选择
                        delay = random.uniform(base_delay, min(max_delay, 60))  # 限制最大延迟为60秒
                        logging.info(f"遇到限流，第 {retry_count} 次重试，等待 {delay:.2f} 秒...")
                        time.sleep(delay)
                        continue
                return None

    def format_market_context(self, df: pd.DataFrame) -> dict:
        """将数据格式化为市场上下文"""
        if df.empty:
            return None

        # 获取最新数据
        latest_data = df.iloc[-1]
        
        # 获取最近24小时的数据（288个5分钟K线）
        last_24h_data = df.tail(288)
        
        # 格式化K线数据为列表
        klines = []
        for _, row in last_24h_data.iterrows():
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
            "data_24h": klines,
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
                data_24h=json.dumps(market_context["data_24h"]),
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
            
            # 直接调用 process_analysis.py 处理新生成的分析文件
            try:
                result = subprocess.run([sys.executable, "process_analysis.py"], 
                                     check=True, 
                                     capture_output=True, 
                                     text=True)
                if result.returncode == 0:
                    logging.info("成功运行 process_analysis.py 处理分析结果")
                    logging.info(result.stdout)
                else:
                    logging.error(f"process_analysis.py 返回错误: {result.stderr}")
            except subprocess.CalledProcessError as e:
                logging.error(f"运行 process_analysis.py 时出错: {str(e)}")
                if e.stdout:
                    logging.error(f"stdout: {e.stdout}")
                if e.stderr:
                    logging.error(f"stderr: {e.stderr}")
            except Exception as e:
                logging.error(f"运行 process_analysis.py 时发生未知错误: {str(e)}")
            
        except Exception as e:
            logging.error(f"处理文件时出错 {file_path}: {str(e)}")

async def process_single_file(file_path: str):
    """处理单个文件的入口函数"""
    analyzer = AIAnalyzer()
    await analyzer.process_file(file_path)

def main():
    # 设置命令行参数
    parser = argparse.ArgumentParser(description='处理MT4数据文件并进行AI分析')
    parser.add_argument('--file', type=str, help='要处理的文件路径')
    args = parser.parse_args()

    if not args.file:
        logging.error("请提供要处理的文件路径")
        sys.exit(1)

    if not os.path.exists(args.file):
        logging.error(f"文件不存在: {args.file}")
        sys.exit(1)

    try:
        asyncio.run(process_single_file(args.file))
    except Exception as e:
        logging.error(f"处理文件时出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 