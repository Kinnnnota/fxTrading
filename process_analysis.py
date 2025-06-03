import json
import os
import glob
import csv
import time
import sys
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取环境变量
MT4_TERMINAL_PATH = os.getenv('MT4_TERMINAL_PATH')
MT4_FILES_DIR = os.getenv('MT4_FILES_DIR')
MT4DATA_DIR = os.getenv('MT4DATA_DIR')

if not all([MT4_TERMINAL_PATH, MT4_FILES_DIR, MT4DATA_DIR]):
    raise ValueError("缺少必要的环境变量配置")

def extract_json_from_file(file_path):
    """从文件中提取JSON数据，支持多种编码"""
    encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
                if "=== AI 分析结果 ===" in content:
                    json_str = content.split("=== AI 分析结果 ===")[-1].strip()
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        print(f"Error parsing JSON in {file_path}")
                        return None
            break  # 如果成功读取，跳出循环
        except UnicodeDecodeError:
            continue  # 尝试下一个编码
        except Exception as e:
            print(f"Error reading file {file_path}: {str(e)}")
            return None
    
    print(f"Could not read file {file_path} with any of the attempted encodings")
    return None

def write_to_csv(file_path, output_rows, is_new_file=False, max_retries=3):
    """写入CSV文件，支持重试机制"""
    for attempt in range(max_retries):
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # 如果是新文件，写入列名
                if is_new_file:
                    pass # 暂时不写入列名
                    # writer.writerow(['Currency Pair', 'Order Type', 'Entry Price', 'Take Profit'])
                writer.writerows(output_rows)
            return True
        except PermissionError:
            if attempt < max_retries - 1:
                print(f"文件 {file_path} 被占用 (尝试 {attempt + 1}/{max_retries})")
                print("等待5秒后重试...")
                time.sleep(5)
            else:
                print(f"文件 {file_path} 持续被占用，无法写入")
                return False
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"写入文件 {file_path} 失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                print("等待5秒后重试...")
                time.sleep(5)
            else:
                print(f"写入文件 {file_path} 最终失败: {str(e)}")
                return False
    return False

def process_analysis_files():
    """处理分析文件的主函数"""
    try:
        # 获取所有 *_analysis.txt 文件
        analysis_files = glob.glob(os.path.join(MT4DATA_DIR, '*_analysis.txt'))
        
        if not analysis_files:
            print("没有找到需要处理的文件")
            return True
        
        # 准备CSV输出
        output_rows = []
        processed_files = []  # 用于跟踪成功处理的文件
        
        for file_path in analysis_files:
            try:
                # 从文件名获取货币对名称
                currency_pair = os.path.basename(file_path).split('_')[0]
                
                # 提取JSON数据
                data = extract_json_from_file(file_path)
                if data:
                    # 提取所需字段
                    order_type = data.get('order_type', '')
                    price = data.get('price', '')
                    take_profit = data.get('take_profit', '')
                    
                    # 添加到输出行
                    output_rows.append([
                        currency_pair,
                        order_type,
                        str(price),
                        str(take_profit)
                    ])
                    processed_files.append(file_path)  # 记录成功处理的文件
            except Exception as e:
                print(f"处理文件 {file_path} 时出错: {str(e)}")
                continue
        
        if not output_rows:
            print("没有新的数据需要处理")
            return True

        # 定义两个输出路径
        output_paths = [
            os.path.join(MT4DATA_DIR, 'orders.csv'),
            os.path.join(MT4_TERMINAL_PATH, MT4_FILES_DIR, 'orders.csv')
        ]
        
        # 检查每个文件是否存在
        file_exists = {path: os.path.exists(path) for path in output_paths}
        
        # 写入所有输出文件
        all_success = True
        for output_path in output_paths:
            success = write_to_csv(output_path, output_rows, not file_exists[output_path])
            if success:
                print(f"成功写入文件: {output_path}")
            else:
                all_success = False
                print(f"写入文件失败: {output_path}")
        
        # 只有在所有文件都成功写入后才删除原始文件
        if all_success:
            for file_path in processed_files:
                try:
                    os.remove(file_path)
                    print(f"已删除文件: {file_path}")
                except Exception as e:
                    print(f"删除文件 {file_path} 时出错: {str(e)}")
        else:
            print("由于部分文件写入失败，未删除原始文件")
        
        return all_success
        
    except Exception as e:
        print(f"处理过程中出现错误: {str(e)}")
        return False

if __name__ == "__main__":
    try:
        success = process_analysis_files()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"程序执行过程中出现错误: {str(e)}")
        sys.exit(1) 