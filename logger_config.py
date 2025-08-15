"""
日志配置模块
配置结构化日志系统
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from config import config


def setup_logging():
    """设置日志系统"""

    # 创建logs目录
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # 配置日志级别
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)

    # 配置标准库logging
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                logs_dir / f"bot_{datetime.now().strftime('%Y%m%d')}.log",
                encoding='utf-8'
            )
        ]
    )

    # 设置第三方库的日志级别
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.INFO)

    logger = logging.getLogger(__name__)
    logger.info("日志系统初始化完成")


class ErrorHandler:
    """错误处理器类"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.error_count = 0
        self.retry_count = 0
    
    async def handle_telegram_error(self, error: Exception, context: str = "") -> bool:
        """
        处理Telegram API错误
        
        Args:
            error: 异常对象
            context: 错误上下文
            
        Returns:
            是否应该重试
        """
        self.error_count += 1
        
        error_type = type(error).__name__
        error_msg = str(error)
        
        self.logger.error(
            f"Telegram API错误 - 类型: {error_type}, 消息: {error_msg}, "
            f"上下文: {context}, 错误次数: {self.error_count}"
        )
        
        # 根据错误类型决定是否重试
        if "rate limit" in error_msg.lower():
            self.logger.warning("遇到频率限制，建议稍后重试")
            return True
        elif "network" in error_msg.lower() or "timeout" in error_msg.lower():
            self.logger.warning("网络错误，可以重试")
            return True
        elif "forbidden" in error_msg.lower() or "unauthorized" in error_msg.lower():
            self.logger.error("权限错误，无法重试")
            return False
        else:
            # 其他错误，谨慎重试
            return self.error_count < 3
    
    async def retry_with_backoff(self, func, max_retries: int = 3, base_delay: float = 1.0):
        """
        带退避策略的重试机制
        
        Args:
            func: 要重试的异步函数
            max_retries: 最大重试次数
            base_delay: 基础延迟时间（秒）
            
        Returns:
            函数执行结果
        """
        import asyncio
        
        for attempt in range(max_retries + 1):
            try:
                result = await func()
                if attempt > 0:
                    self.logger.info(f"重试成功，尝试次数: {attempt}")
                return result
            except Exception as e:
                if attempt == max_retries:
                    self.logger.error(
                        f"重试次数已达上限，最大重试次数: {max_retries}, 错误: {str(e)}"
                    )
                    raise
                
                delay = base_delay * (2 ** attempt)  # 指数退避
                self.retry_count += 1
                
                self.logger.warning(
                    f"操作失败，准备重试 - 尝试: {attempt + 1}/{max_retries}, "
                    f"延迟: {delay}秒, 错误: {str(e)}"
                )
                
                await asyncio.sleep(delay)
    
    def get_stats(self) -> dict:
        """获取错误统计信息"""
        return {
            'error_count': self.error_count,
            'retry_count': self.retry_count
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self.error_count = 0
        self.retry_count = 0


# 全局错误处理器实例
error_handler = ErrorHandler()


def get_logger(name: str):
    """获取日志器"""
    return logging.getLogger(name)


# 装饰器：自动错误处理
def handle_errors(context: str = ""):
    """错误处理装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                await error_handler.handle_telegram_error(e, context)
                raise
        return wrapper
    return decorator
