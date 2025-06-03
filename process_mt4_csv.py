import pandas as pd
import random
from datetime import datetime
import calendar
import os
import glob
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging
from dotenv import load_dotenv
import subprocess
import sys

# 加载环境变量
load_dotenv()

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 获取环境变量
MT4_TERMINAL_PATH = os.getenv('MT4_TERMINAL_PATH')
MT4_FILES_DIR = os.getenv('MT4_FILES_DIR')
MT4DATA_DIR = os.getenv('MT4DATA_DIR')

if not all([MT4_TERMINAL_PATH, MT4_FILES_DIR, MT4DATA_DIR]):
    raise ValueError("缺少必要的环境变量配置")

# 监控MT4数据更改，当有新文件时，读取文件，并处理文件，处理完成后，删除原始文件

class MT4FileHandler(FileSystemEventHandler):
    def __init__(self, mt4_dir, output_dir):
        self.mt4_dir = mt4_dir
        self.output_dir = output_dir
        self.last_modified_times = {}  # 用于跟踪文件的最后修改时间
        
        # 处理启动时已存在的文件
        self.process_existing_files()
    
    def process_existing_files(self):
        """处理目录中已存在的CSV文件"""
        csv_files = glob.glob(os.path.join(self.mt4_dir, "*.csv"))
        for file_path in csv_files:
                self.process_file(file_path)
    
    def process_file(self, file_path):
        """处理单个CSV文件"""
        try:
            # 忽略 orders.csv 文件
            if os.path.basename(file_path) == 'orders.csv':
                logging.info(f"忽略文件: {file_path}")
                return
                
            # 检查文件是否可读
            if not os.path.exists(file_path):
                return
                
            # 获取文件当前修改时间
            current_mtime = os.path.getmtime(file_path)
            
            # 如果文件没有被修改过，跳过处理
            if file_path in self.last_modified_times and current_mtime <= self.last_modified_times[file_path]:
                return
                
            # 更新最后修改时间
            self.last_modified_times[file_path] = current_mtime
                
            # 等待文件写入完成
            time.sleep(1)
                
            # 获取输出文件路径
            output_file = os.path.join(self.output_dir, os.path.basename(file_path))
            
            # 处理文件
            process_csv_data(file_path, output_file)
            
            # 删除原始文件
            try:
                os.remove(file_path)
                logging.info(f"已删除原始文件: {file_path}")
            except Exception as e:
                logging.error(f"删除文件失败 {file_path}: {e}")
            
            # 直接触发AI分析
            try:
                subprocess.run([sys.executable, "process_ai_analysis.py", "--file", output_file], check=True)
                logging.info(f"成功触发AI分析: {output_file}")
                os.remove(output_file)
            except subprocess.CalledProcessError as e:
                logging.error(f"触发AI分析时出错: {str(e)}")
            except Exception as e:
                logging.error(f"触发AI分析时发生未知错误: {str(e)}")
            
        except Exception as e:
            logging.error(f"处理文件 {file_path} 时出错: {e}")
    
    def on_created(self, event):
        """当新文件创建时触发"""
        if not event.is_directory and event.src_path.endswith('.csv'):
            # 忽略 orders.csv 文件
            if os.path.basename(event.src_path) == 'orders.csv':
                logging.info(f"忽略新创建的文件: {event.src_path}")
                return
            logging.info(f"检测到新文件: {event.src_path}")
            self.process_file(event.src_path)
    
    def on_modified(self, event):
        """当文件被修改时触发"""
        if not event.is_directory and event.src_path.endswith('.csv'):
            # 忽略 orders.csv 文件
            if os.path.basename(event.src_path) == 'orders.csv':
                logging.info(f"忽略修改的文件: {event.src_path}")
                return
            logging.info(f"检测到文件修改: {event.src_path}")
            self.process_file(event.src_path)

def process_csv_data(input_file, output_file):
    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"输入文件不存在: {input_file}")
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 读取CSV文件，使用表头
    try:
        df = pd.read_csv(input_file, encoding='utf-8')
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(input_file, encoding='gbk')
        except UnicodeDecodeError:
            df = pd.read_csv(input_file, encoding='shift-jis')
    
    # 将Time列转换为datetime格式
    df['datetime'] = pd.to_datetime(df['Time'])
    
    # 分离日期和时间
    df['date'] = df['datetime'].dt.strftime('%Y.%m.%d')
    df['time'] = df['datetime'].dt.strftime('%H:%M')
    
    # 提取月份信息
    df['month'] = df['datetime'].dt.month
    
    # 获取所有唯一的月份
    unique_months = df['month'].unique()
    
    # 随机选择一个月份
    selected_month = random.choice(unique_months)
    
    # 筛选选中月份的数据
    monthly_data = df[df['month'] == selected_month].copy()
    
    # 添加星期几信息
    monthly_data['weekday'] = monthly_data['datetime'].dt.day_name()
    
    # 重新组织列的顺序
    result_df = monthly_data[['date', 'time', 'weekday', 'Open', 'High', 'Low', 'Close', 'Volume']]
    
    # 保存到新的CSV文件，不包含表头
    result_df.to_csv(output_file, index=False, header=False)
    
    logging.info(f"已处理完成！")
    logging.info(f"文件名: {os.path.basename(input_file)}")
    logging.info(f"选中的月份: {calendar.month_name[selected_month]}")
    logging.info(f"数据已保存到: {output_file}")
    logging.info(f"总行数: {len(result_df)}")
    logging.info("-" * 50)

def start_monitoring():
    # MT4数据目录路径
    mt4_dir = os.path.join(MT4_TERMINAL_PATH, MT4_FILES_DIR)
    
    # 输出目录路径
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), MT4DATA_DIR)
    
    # 确保输出目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 创建事件处理器
    event_handler = MT4FileHandler(mt4_dir, output_dir)
    
    # 创建观察者
    observer = Observer()
    observer.schedule(event_handler, mt4_dir, recursive=False)
    
    # 启动观察者
    observer.start()
    logging.info(f"开始监控目录: {mt4_dir}")
    logging.info(f"处理后的文件将保存到: {output_dir}")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logging.info("监控已停止")
    
    observer.join()

if __name__ == "__main__":
    try:
        start_monitoring()
    except Exception as e:
        logging.error(f"程序执行过程中出现错误: {e}") 