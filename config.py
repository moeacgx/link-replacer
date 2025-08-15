"""
配置管理模块
负责读取和管理机器人的各种配置信息
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    """配置管理类"""
    
    def __init__(self):
        self.bot_token = os.getenv('BOT_TOKEN')
        self.admin_ids = self._parse_admin_ids()
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.channels_file = 'channels.txt'
        self.settings_file = 'settings.json'
        
        # 验证必要配置
        self._validate_config()
        
    def _parse_admin_ids(self) -> List[int]:
        """解析管理员ID列表"""
        admin_ids_str = os.getenv('ADMIN_IDS', '')
        if not admin_ids_str:
            logger.warning("未设置管理员ID，所有用户都将被视为管理员")
            return []
        
        try:
            return [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]
        except ValueError as e:
            logger.error(f"管理员ID格式错误: {e}")
            return []
    
    def _validate_config(self):
        """验证配置的有效性"""
        if not self.bot_token:
            raise ValueError("BOT_TOKEN 环境变量未设置")
        
        if not self.admin_ids:
            logger.warning("未设置有效的管理员ID")
    
    def is_admin(self, user_id: int) -> bool:
        """检查用户是否为管理员"""
        if not self.admin_ids:  # 如果没有设置管理员，所有人都是管理员
            return True
        return user_id in self.admin_ids
    
    def get_channels(self) -> List[str]:
        """读取频道列表"""
        channels = []
        
        if not Path(self.channels_file).exists():
            logger.info(f"频道配置文件 {self.channels_file} 不存在，创建空文件")
            Path(self.channels_file).touch()
            return channels
        
        try:
            with open(self.channels_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释行
                    if line and not line.startswith('#'):
                        channels.append(line)
        except Exception as e:
            logger.error(f"读取频道配置文件失败: {e}")
        
        return channels
    
    def add_channel(self, channel: str) -> bool:
        """添加频道到配置文件"""
        try:
            # 检查频道是否已存在
            existing_channels = self.get_channels()
            if channel in existing_channels:
                return False
            
            # 添加到文件
            with open(self.channels_file, 'a', encoding='utf-8') as f:
                f.write(f"{channel}\n")
            
            logger.info(f"成功添加频道: {channel}")
            return True
        except Exception as e:
            logger.error(f"添加频道失败: {e}")
            return False
    
    def remove_channel(self, channel: str) -> bool:
        """从配置文件中移除频道"""
        try:
            channels = self.get_channels()
            if channel not in channels:
                return False
            
            # 重写文件，排除要删除的频道
            with open(self.channels_file, 'w', encoding='utf-8') as f:
                f.write("# Telegram频道监听配置文件\n")
                f.write("# 每行一个频道，支持以下格式：\n")
                f.write("# 1. 频道ID格式: -1001234567890\n")
                f.write("# 2. 用户名格式: @channel_username\n")
                f.write("# 3. 注释行以#开头\n\n")
                
                for ch in channels:
                    if ch != channel:
                        f.write(f"{ch}\n")
            
            logger.info(f"成功移除频道: {channel}")
            return True
        except Exception as e:
            logger.error(f"移除频道失败: {e}")
            return False
    
    def get_settings(self) -> Dict[str, Any]:
        """读取动态设置"""
        default_settings = {
            "detection_text": "▶️加入会员观看完整版",
            "link_text": "观看完整版",
            "created_at": "2025-08-15",
            "last_updated": "2025-08-15"
        }
        
        if not Path(self.settings_file).exists():
            # 创建默认设置文件
            self.save_settings(default_settings)
            return default_settings
        
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                # 确保所有必要的键都存在
                for key, value in default_settings.items():
                    if key not in settings:
                        settings[key] = value
                return settings
        except Exception as e:
            logger.error(f"读取设置文件失败: {e}")
            return default_settings
    
    def save_settings(self, settings: Dict[str, Any]) -> bool:
        """保存动态设置"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            logger.info("设置保存成功")
            return True
        except Exception as e:
            logger.error(f"保存设置失败: {e}")
            return False
    
    def update_detection_text(self, new_text: str) -> bool:
        """更新检测文本"""
        settings = self.get_settings()
        settings['detection_text'] = new_text
        settings['last_updated'] = "2025-08-15"  # 实际应用中应使用当前时间
        return self.save_settings(settings)
    
    def update_link_text(self, new_text: str) -> bool:
        """更新链接文本"""
        settings = self.get_settings()
        settings['link_text'] = new_text
        settings['last_updated'] = "2025-08-15"  # 实际应用中应使用当前时间
        return self.save_settings(settings)


# 全局配置实例
config = Config()
