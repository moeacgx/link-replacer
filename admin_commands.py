"""
管理员命令处理模块
实现机器人的交互式管理功能
"""

from typing import List
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from config import config
from message_handler import message_processor
from link_processor import link_processor
from logger_config import get_logger

logger = get_logger(__name__)


class AdminCommandHandler:
    """管理员命令处理器"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def is_admin(self, user_id: int) -> bool:
        """检查用户是否为管理员"""
        return config.is_admin(user_id)
    
    async def add_channel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """添加频道命令处理器"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 您没有权限执行此操作")
            return
        
        if not context.args:
            await update.message.reply_text(
                "📝 使用方法: /add_channel <频道ID或用户名>\n\n"
                "示例:\n"
                "• /add_channel -1001234567890\n"
                "• /add_channel @channel_username"
            )
            return
        
        channel = context.args[0].strip()
        
        # 验证频道格式
        if not self._validate_channel_format(channel):
            await update.message.reply_text(
                "❌ 频道格式无效\n\n"
                "支持的格式:\n"
                "• 频道ID: -1001234567890\n"
                "• 用户名: @channel_username"
            )
            return
        
        # 添加频道
        if config.add_channel(channel):
            await update.message.reply_text(f"✅ 成功添加频道: {channel}")
            self.logger.info(f"管理员添加频道: {channel}, 管理员ID: {update.effective_user.id}")
        else:
            await update.message.reply_text(f"⚠️ 频道已存在: {channel}")
    
    async def remove_channel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """移除频道命令处理器"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 您没有权限执行此操作")
            return
        
        if not context.args:
            await update.message.reply_text(
                "📝 使用方法: /remove_channel <频道ID或用户名>\n\n"
                "示例:\n"
                "• /remove_channel -1001234567890\n"
                "• /remove_channel @channel_username"
            )
            return
        
        channel = context.args[0].strip()
        
        # 移除频道
        if config.remove_channel(channel):
            await update.message.reply_text(f"✅ 成功移除频道: {channel}")
            self.logger.info(f"管理员移除频道: {channel}, 管理员ID: {update.effective_user.id}")
        else:
            await update.message.reply_text(f"⚠️ 频道不存在: {channel}")
    
    async def list_channels_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """列出所有频道命令处理器"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 您没有权限执行此操作")
            return
        
        channels = config.get_channels()
        
        if not channels:
            await update.message.reply_text("📋 当前没有监听任何频道")
            return
        
        message = "📋 当前监听的频道列表:\n\n"
        for i, channel in enumerate(channels, 1):
            message += f"{i}. {channel}\n"
        
        message += f"\n总计: {len(channels)} 个频道"
        
        await update.message.reply_text(message)
    
    async def set_text_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """设置检测文本命令处理器"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 您没有权限执行此操作")
            return
        
        if not context.args:
            current_settings = config.get_settings()
            current_text = current_settings.get('detection_text', '未设置')
            await update.message.reply_text(
                f"📝 使用方法: /set_text <新的检测文本>\n\n"
                f"当前检测文本: {current_text}\n\n"
                f"示例: /set_text ▶️加入会员观看完整版"
            )
            return
        
        new_text = ' '.join(context.args)
        
        if config.update_detection_text(new_text):
            await update.message.reply_text(f"✅ 检测文本已更新为: {new_text}")
            self.logger.info(f"管理员更新检测文本: {new_text}, 管理员ID: {update.effective_user.id}")
        else:
            await update.message.reply_text("❌ 更新检测文本失败")
    
    async def set_link_text_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """设置链接文本命令处理器"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 您没有权限执行此操作")
            return
        
        if not context.args:
            current_settings = config.get_settings()
            current_text = current_settings.get('link_text', '未设置')
            await update.message.reply_text(
                f"📝 使用方法: /set_link_text <新的链接文本>\n\n"
                f"当前链接文本: {current_text}\n\n"
                f"示例: /set_link_text 观看完整版"
            )
            return
        
        new_text = ' '.join(context.args)
        
        if config.update_link_text(new_text):
            await update.message.reply_text(f"✅ 链接文本已更新为: {new_text}")
            self.logger.info(f"管理员更新链接文本: {new_text}, 管理员ID: {update.effective_user.id}")
        else:
            await update.message.reply_text("❌ 更新链接文本失败")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """状态查询命令处理器"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 您没有权限执行此操作")
            return
        
        # 获取各种统计信息
        channels = config.get_channels()
        settings = config.get_settings()
        message_stats = message_processor.get_stats()
        link_stats = link_processor.get_stats()
        
        status_message = (
            "📊 机器人运行状态\n\n"
            f"🔧 配置信息:\n"
            f"• 监听频道数: {len(channels)}\n"
            f"• 检测文本: {settings.get('detection_text', '未设置')}\n"
            f"• 链接文本: {settings.get('link_text', '未设置')}\n\n"
            f"📈 处理统计:\n"
            f"• 已处理消息: {message_stats.get('processed_count', 0)}\n"
            f"• 处理错误: {message_stats.get('error_count', 0)}\n"
            f"• 已处理链接: {link_stats.get('processed_links_count', 0)}\n\n"
            f"⚙️ 系统信息:\n"
            f"• 配置更新时间: {settings.get('last_updated', '未知')}\n"
            f"• 日志级别: {config.log_level}"
        )
        
        await update.message.reply_text(status_message)
    
    async def test_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """测试命令处理器"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 您没有权限执行此操作")
            return

        # 获取当前聊天信息
        chat = update.effective_chat
        user = update.effective_user

        test_info = (
            "🧪 机器人测试信息\n\n"
            f"📍 当前聊天:\n"
            f"• ID: {chat.id}\n"
            f"• 类型: {chat.type}\n"
            f"• 标题: {chat.title or '无'}\n"
            f"• 用户名: @{chat.username or '无'}\n\n"
            f"👤 发送者:\n"
            f"• ID: {user.id}\n"
            f"• 姓名: {user.full_name}\n"
            f"• 用户名: @{user.username or '无'}\n\n"
            f"🔧 机器人状态: 正常运行\n"
            f"📨 消息接收: 正常"
        )

        await update.message.reply_text(test_info)
        self.logger.info(f"测试命令被调用 - 聊天ID: {chat.id}, 用户ID: {user.id}")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """帮助命令处理器"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 您没有权限执行此操作")
            return

        help_message = (
            "🤖 Telegram频道消息处理机器人\n\n"
            "📋 管理员命令列表:\n\n"
            "🔧 频道管理:\n"
            "• /add_channel <频道> - 添加监听频道\n"
            "• /remove_channel <频道> - 移除监听频道\n"
            "• /list_channels - 查看所有监听频道\n\n"
            "📝 文本配置:\n"
            "• /set_text <文本> - 设置检测文本\n"
            "• /set_link_text <文本> - 设置链接文本\n\n"
            "📊 状态查询:\n"
            "• /status - 查看机器人运行状态\n"
            "• /test - 测试机器人功能\n"
            "• /help - 显示此帮助信息\n\n"
            "💡 使用提示:\n"
            "• 频道格式支持ID(-1001234567890)和用户名(@channel)\n"
            "• 所有配置修改立即生效，无需重启\n"
            "• 定期查看状态了解处理情况"
        )

        await update.message.reply_text(help_message)
    
    def _validate_channel_format(self, channel: str) -> bool:
        """验证频道格式"""
        if not channel:
            return False
        
        # 检查用户名格式
        if channel.startswith('@'):
            return len(channel) > 1 and channel[1:].replace('_', '').isalnum()
        
        # 检查频道ID格式
        if channel.startswith('-'):
            return channel[1:].isdigit()
        
        return False
    
    def get_handlers(self) -> List[CommandHandler]:
        """获取所有命令处理器"""
        return [
            CommandHandler("add_channel", self.add_channel_command),
            CommandHandler("remove_channel", self.remove_channel_command),
            CommandHandler("list_channels", self.list_channels_command),
            CommandHandler("set_text", self.set_text_command),
            CommandHandler("set_link_text", self.set_link_text_command),
            CommandHandler("status", self.status_command),
            CommandHandler("test", self.test_command),
            CommandHandler("help", self.help_command),
        ]


# 全局管理员命令处理器实例
admin_handler = AdminCommandHandler()
