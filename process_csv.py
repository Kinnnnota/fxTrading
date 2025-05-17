import pandas as pd
import random
from datetime import datetime
import calendar
import os

def process_csv_data(input_file, output_file):
    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"输入文件不存在: {input_file}")
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 读取CSV文件
    # 假设CSV格式为: 日期,时间,开盘价,最高价,最低价,收盘价,成交量
    df = pd.read_csv(input_file, header=None, 
                    names=['date', 'time', 'open', 'high', 'low', 'close', 'volume'])
    
    # 将日期列转换为datetime格式
    df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'], format='%Y.%m.%d %H:%M')
    
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
    result_df = monthly_data[['date', 'time', 'weekday', 'open', 'high', 'low', 'close', 'volume']]
    
    # 保存到新的CSV文件
    result_df.to_csv(output_file, index=False, header=False)
    
    print(f"已处理完成！")
    print(f"选中的月份: {calendar.month_name[selected_month]}")
    print(f"数据已保存到: {output_file}")
    print(f"总行数: {len(result_df)}")

if __name__ == "__main__":
    # 使用绝对路径
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(base_dir, "csvFiles", "1.csv")
    output_file = os.path.join(base_dir, "csvFiles", "processed_data.csv")
    
    try:
        process_csv_data(input_file, output_file)
    except FileNotFoundError as e:
        print(f"错误: {e}")
    except Exception as e:
        print(f"处理过程中出现错误: {e}") 