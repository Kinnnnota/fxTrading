import json
import os
from typing import Dict, Any, Optional

class PromptManager:
    def __init__(self, prompt_file: str = "prompts.json"):
        """
        初始化Prompt管理器
        
        Args:
            prompt_file (str): prompt配置文件的路径
        """
        self.prompt_file = prompt_file
        self.prompts = self._load_prompts()
        
    def _load_prompts(self) -> Dict[str, Any]:
        """加载prompt配置文件"""
        try:
            with open(self.prompt_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Prompt文件 {self.prompt_file} 不存在")
        except json.JSONDecodeError as e:
            raise ValueError(f"Prompt文件 {self.prompt_file} 格式错误")
        except Exception as e:
            raise
    
    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        return self.prompts.get('system_prompt', '')
    
    def get_prompt_template(self, prompt_type: str) -> Optional[str]:
        """获取指定类型的prompt模板"""
        return self.prompts.get('prompts', {}).get(prompt_type, {}).get('template')
    
    def format_prompt(self, prompt_type: str, **kwargs) -> str:
        """格式化prompt模板"""
        template = self.get_prompt_template(prompt_type)
        if template is None:
            raise ValueError(f"未知的prompt类型: {prompt_type}")
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"模板参数缺失: {e}")
        except Exception as e:
            raise
    
    def get_example(self, example_type: str) -> Optional[str]:
        """
        获取示例内容
        
        Args:
            example_type (str): 示例类型，如 'question', 'code', 'content' 等
        
        Returns:
            Optional[str]: 示例内容
        """
        return self.prompts.get('examples', {}).get(example_type)
    
    def add_prompt_template(self, prompt_type: str, description: str, template: str) -> None:
        """
        添加新的prompt模板
        
        Args:
            prompt_type (str): prompt类型
            description (str): 描述
            template (str): 模板
        """
        if 'prompts' not in self.prompts:
            self.prompts['prompts'] = {}
            
        self.prompts['prompts'][prompt_type] = {
            'description': description,
            'template': template
        }
        self._save_prompts()
    
    def _save_prompts(self) -> None:
        """保存prompts到文件"""
        with open(self.prompt_file, 'w', encoding='utf-8') as f:
            json.dump(self.prompts, f, ensure_ascii=False, indent=4)
    
    def list_prompt_types(self) -> Dict[str, str]:
        """
        列出所有可用的prompt类型及其描述
        
        Returns:
            Dict[str, str]: prompt类型及其描述的字典
        """
        return {
            prompt_type: prompt_info['description']
            for prompt_type, prompt_info in self.prompts.get('prompts', {}).items()
        } 