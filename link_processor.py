"""
链接处理模块
专门负责处理Telegram链接的替换和转换逻辑
"""

import re
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class LinkProcessor:
    """链接处理器类"""
    
    # Telegram链接的正则表达式模式
    TELEGRAM_LINK_PATTERN = r'https://t\.me/c/(\d+)/(\d+)'
    
    def __init__(self):
        self.processed_links_count = 0
    
    def process_text_links(self, text: str, target_chat_id: int) -> str:
        """
        处理文本中的所有Telegram链接
        
        Args:
            text: 原始文本
            target_chat_id: 目标频道ID
            
        Returns:
            处理后的文本
        """
        if not text:
            return text
        
        # 查找所有匹配的链接
        matches = list(re.finditer(self.TELEGRAM_LINK_PATTERN, text))
        
        if not matches:
            logger.debug("文本中未找到需要处理的Telegram链接")
            return text
        
        # 从后往前替换，避免位置偏移问题
        processed_text = text
        for match in reversed(matches):
            original_link = match.group(0)
            original_channel_id = match.group(1)
            message_id = match.group(2)
            
            # 生成新链接
            new_link = self._generate_new_link(
                original_channel_id, 
                message_id, 
                target_chat_id
            )
            
            if new_link != original_link:
                # 替换链接
                start, end = match.span()
                processed_text = processed_text[:start] + new_link + processed_text[end:]
                
                self.processed_links_count += 1
                logger.info(f"链接替换: {original_link} -> {new_link}")
        
        return processed_text
    
    def _generate_new_link(self, original_channel_id: str, message_id: str, target_chat_id: int) -> str:
        """
        生成新的Telegram链接
        
        Args:
            original_channel_id: 原始频道ID
            message_id: 消息ID
            target_chat_id: 目标频道ID
            
        Returns:
            新的链接
        """
        # 处理目标频道ID格式
        new_channel_id = self._format_channel_id(target_chat_id)
        
        # 构建新链接
        new_link = f"https://t.me/c/{new_channel_id}/{message_id}"
        
        return new_link
    
    def _format_channel_id(self, chat_id: int) -> str:
        """
        格式化频道ID，处理-100前缀
        
        Args:
            chat_id: 频道ID
            
        Returns:
            格式化后的频道ID字符串
        """
        chat_id_str = str(chat_id)
        
        # 如果是负数且以-100开头，移除-100前缀
        if chat_id_str.startswith('-100'):
            return chat_id_str[4:]  # 移除'-100'
        elif chat_id_str.startswith('-'):
            # 其他负数情况，移除负号
            return chat_id_str[1:]
        else:
            # 正数直接返回
            return chat_id_str
    
    def extract_links(self, text: str) -> List[Tuple[str, str, str]]:
        """
        提取文本中的所有Telegram链接信息
        
        Args:
            text: 要分析的文本
            
        Returns:
            链接信息列表，每个元素为(完整链接, 频道ID, 消息ID)
        """
        if not text:
            return []
        
        matches = re.finditer(self.TELEGRAM_LINK_PATTERN, text)
        links = []
        
        for match in matches:
            full_link = match.group(0)
            channel_id = match.group(1)
            message_id = match.group(2)
            links.append((full_link, channel_id, message_id))
        
        return links
    
    def validate_telegram_link(self, link: str) -> bool:
        """
        验证是否为有效的Telegram链接
        
        Args:
            link: 要验证的链接
            
        Returns:
            是否为有效链接
        """
        if not link:
            return False
        
        return bool(re.match(self.TELEGRAM_LINK_PATTERN, link))
    
    def get_channel_id_from_link(self, link: str) -> Optional[str]:
        """
        从Telegram链接中提取频道ID
        
        Args:
            link: Telegram链接
            
        Returns:
            频道ID，如果链接无效则返回None
        """
        match = re.match(self.TELEGRAM_LINK_PATTERN, link)
        if match:
            return match.group(1)
        return None
    
    def get_message_id_from_link(self, link: str) -> Optional[str]:
        """
        从Telegram链接中提取消息ID
        
        Args:
            link: Telegram链接
            
        Returns:
            消息ID，如果链接无效则返回None
        """
        match = re.match(self.TELEGRAM_LINK_PATTERN, link)
        if match:
            return match.group(2)
        return None
    
    def get_stats(self) -> dict:
        """获取处理统计信息"""
        return {
            'processed_links_count': self.processed_links_count
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self.processed_links_count = 0


# 全局链接处理器实例
link_processor = LinkProcessor()


# 便捷函数
def process_telegram_links(text: str, target_chat_id: int) -> str:
    """
    便捷函数：处理文本中的Telegram链接
    
    Args:
        text: 原始文本
        target_chat_id: 目标频道ID
        
    Returns:
        处理后的文本
    """
    return link_processor.process_text_links(text, target_chat_id)


def extract_telegram_links(text: str) -> List[Tuple[str, str, str]]:
    """
    便捷函数：提取文本中的Telegram链接
    
    Args:
        text: 要分析的文本
        
    Returns:
        链接信息列表
    """
    return link_processor.extract_links(text)
