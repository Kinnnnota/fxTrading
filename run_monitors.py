import asyncio
import subprocess
import sys
import os
import logging
from datetime import datetime

# 把多个python脚本整合在一起运行 

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(f'monitor_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

async def run_process(script_name):
    """运行Python脚本并监控其输出"""
    process = await asyncio.create_subprocess_exec(
        sys.executable, script_name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    logging.info(f"启动 {script_name}")
    
    # 读取输出
    while True:
        try:
            # 尝试读取stdout
            output = await process.stdout.readline()
            if output:
                try:
                    # 尝试不同的编码
                    for encoding in ['utf-8', 'gbk', 'shift-jis']:
                        try:
                            decoded = output.decode(encoding)
                            logging.info(f"[{script_name}] {decoded.strip()}")
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        # 如果所有编码都失败，使用二进制方式记录
                        logging.info(f"[{script_name}] [Binary output] {output}")
                except Exception as e:
                    logging.error(f"解码stdout时出错: {str(e)}")
            
            # 尝试读取stderr
            error = await process.stderr.readline()
            if error:
                try:
                    # 尝试不同的编码
                    for encoding in ['utf-8', 'gbk', 'shift-jis']:
                        try:
                            decoded = error.decode(encoding)
                            logging.error(f"[{script_name}] {decoded.strip()}")
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        # 如果所有编码都失败，使用二进制方式记录
                        logging.error(f"[{script_name}] [Binary error] {error}")
                except Exception as e:
                    logging.error(f"解码stderr时出错: {str(e)}")
            
            # 检查进程是否结束
            if process.stdout.at_eof() and process.stderr.at_eof():
                break
                
        except Exception as e:
            logging.error(f"读取 {script_name} 输出时出错: {str(e)}")
            break
    
    # 等待进程结束
    try:
        await process.wait()
        if process.returncode != 0:
            logging.error(f"{script_name} 异常退出，返回码: {process.returncode}")
        else:
            logging.info(f"{script_name} 正常退出")
    except Exception as e:
        logging.error(f"等待 {script_name} 结束时出错: {str(e)}")

async def main():
    """同时运行两个监控脚本"""
    try:
        # 创建任务列表
        tasks = [
            run_process("process_mt4_csv.py"),
            run_process("process_ai_analysis.py")
        ]
        
        # 等待所有任务完成
        await asyncio.gather(*tasks)
        
    except KeyboardInterrupt:
        logging.info("收到停止信号，正在关闭所有进程...")
    except Exception as e:
        logging.error(f"运行过程中出现错误: {e}")
    finally:
        logging.info("所有进程已停止")

if __name__ == "__main__":
    try:
        # 确保工作目录正确
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        # 运行主程序
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("程序被用户中断")
    except Exception as e:
        logging.error(f"程序执行过程中出现错误: {e}") 