"""
管理员命令处理模块
实现机器人的交互式管理功能
"""

from typing import List
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from config import config
from message_handler import message_processor
from link_processor import link_processor
from forward_mode import forward_mode
from logger_config import get_logger

logger = get_logger(__name__)


class AdminCommandHandler:
    """管理员命令处理器"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def is_admin(self, user_id: int) -> bool:
        """检查用户是否为管理员"""
        return config.is_admin(user_id)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """开始命令 - 显示内联键盘主菜单"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 您没有权限使用此机器人")
            return

        # 导入内联键盘管理器并发送主菜单
        from inline_keyboard import inline_keyboard_manager
        await inline_keyboard_manager.send_main_menu(update, context)
    
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
        forward_stats = forward_mode.get_status()

        # 当前工作模式
        current_mode = "转发模式" if forward_stats['is_active'] else "监听模式"

        status_message = (
            "📊 机器人运行状态\n\n"
            f"🔄 当前模式: {current_mode}\n\n"
            f"🔧 配置信息:\n"
            f"• 监听频道数: {len(channels)}\n"
            f"• 检测文本: {settings.get('detection_text', '未设置')}\n"
            f"• 链接文本: {settings.get('link_text', '未设置')}\n\n"
            f"📈 监听模式统计:\n"
            f"• 已处理消息: {message_stats.get('processed_count', 0)}\n"
            f"• 处理错误: {message_stats.get('error_count', 0)}\n"
            f"• 已处理链接: {link_stats.get('processed_links_count', 0)}\n\n"
        )

        # 添加转发模式状态
        if forward_stats['is_active']:
            batch_status = "开启" if forward_stats['is_batch_mode'] else "关闭"
            schedule_info = forward_stats['scheduled_time'] or "未设置"

            status_message += (
                f"📤 转发模式状态:\n"
                f"• 批量模式: {batch_status}\n"
                f"• 待处理消息: {forward_stats['pending_messages_count']}\n"
                f"• 已转发消息: {forward_stats['processed_count']}\n"
                f"• 转发错误: {forward_stats['error_count']}\n"
                f"• 定时发送: {schedule_info}\n\n"
            )

        status_message += (
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
            "🔄 模式切换:\n"
            "• /switch_mode <模式> - 切换工作模式(listen/forward)\n\n"
            "📤 转发模式:\n"
            "• /batch_start - 开始批量转发模式\n"
            "• /batch_end - 结束批量转发模式\n"
            "• /set_schedule <时间> - 设置定时发送\n\n"
            "📊 状态查询:\n"
            "• /status - 查看机器人运行状态\n"
            "• /test - 测试机器人功能\n"
            "• /help - 显示此帮助信息\n\n"
            "💡 使用提示:\n"
            "• 监听模式：自动处理指定频道消息\n"
            "• 转发模式：转发消息给bot，自动发送到所有频道\n"
            "• 批量模式：收集多条消息后统一处理\n"
            "• 定时发送：使用TG原生定时功能"
        )

        await update.message.reply_text(help_message)

    # ==================== 转发模式命令 ====================

    async def switch_mode_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """切换工作模式命令"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 您没有权限执行此操作")
            return

        if not context.args:
            current_mode = "转发模式" if forward_mode.is_active else "监听模式"
            await update.message.reply_text(
                f"📋 当前模式: {current_mode}\n\n"
                f"使用方法: /switch_mode <模式>\n"
                f"可用模式:\n"
                f"• listen - 监听模式\n"
                f"• forward - 转发模式"
            )
            return

        mode = context.args[0].lower()

        if mode == "listen":
            forward_mode.deactivate()
            await update.message.reply_text("✅ 已切换到监听模式")
            self.logger.info(f"管理员切换到监听模式，管理员ID: {update.effective_user.id}")
        elif mode == "forward":
            forward_mode.activate()
            await update.message.reply_text("✅ 已切换到转发模式")
            self.logger.info(f"管理员切换到转发模式，管理员ID: {update.effective_user.id}")
        else:
            await update.message.reply_text("❌ 无效的模式，请使用 listen 或 forward")

    async def batch_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """开始批量模式命令"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 您没有权限执行此操作")
            return

        if not forward_mode.is_active:
            await update.message.reply_text("❌ 请先切换到转发模式")
            return

        forward_mode.start_batch()
        await update.message.reply_text("✅ 批量模式已开始\n📝 现在可以转发多条消息给我")
        self.logger.info(f"管理员开始批量模式，管理员ID: {update.effective_user.id}")

    async def batch_end_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """结束批量模式命令"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 您没有权限执行此操作")
            return

        if not forward_mode.is_active:
            await update.message.reply_text("❌ 请先切换到转发模式")
            return

        if not forward_mode.is_batch_mode:
            await update.message.reply_text("❌ 当前不在批量模式")
            return

        # 处理批量消息
        processed_count = await forward_mode.process_batch_messages(context)
        message_count = forward_mode.end_batch()

        await update.message.reply_text(
            f"✅ 批量模式已结束\n"
            f"📊 共处理 {processed_count} 条消息\n"
            f"📤 已发送到 {len(config.get_channels())} 个频道"
        )
        self.logger.info(f"管理员结束批量模式，处理了 {processed_count} 条消息")

    async def set_schedule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """设置定时发送命令"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 您没有权限执行此操作")
            return

        if not forward_mode.is_active:
            await update.message.reply_text("❌ 请先切换到转发模式")
            return

        if not context.args:
            current_time = forward_mode.scheduled_time
            if current_time:
                await update.message.reply_text(
                    f"⏰ 当前定时: {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"使用方法: /set_schedule <时间>\n"
                    f"时间格式: YYYY-MM-DD HH:MM\n"
                    f"示例: /set_schedule 2025-08-15 10:00\n"
                    f"清除定时: /set_schedule clear"
                )
            else:
                await update.message.reply_text(
                    f"⏰ 当前无定时设置\n\n"
                    f"使用方法: /set_schedule <时间>\n"
                    f"时间格式: YYYY-MM-DD HH:MM\n"
                    f"示例: /set_schedule 2025-08-15 10:00"
                )
            return

        time_str = ' '.join(context.args)

        if time_str.lower() == 'clear':
            forward_mode.clear_scheduled_time()
            await update.message.reply_text("✅ 定时发送已清除")
            return

        try:
            # 解析时间格式
            scheduled_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M')

            # 检查时间是否在未来
            if scheduled_time <= datetime.now():
                await update.message.reply_text("❌ 定时时间必须在未来")
                return

            forward_mode.set_scheduled_time(scheduled_time)
            await update.message.reply_text(
                f"✅ 定时发送已设置\n"
                f"⏰ 时间: {scheduled_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            self.logger.info(f"管理员设置定时发送: {scheduled_time}")

        except ValueError:
            await update.message.reply_text(
                "❌ 时间格式错误\n"
                "正确格式: YYYY-MM-DD HH:MM\n"
                "示例: 2025-08-15 10:00"
            )
    
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
            CommandHandler("start", self.start_command),
            CommandHandler("add_channel", self.add_channel_command),
            CommandHandler("remove_channel", self.remove_channel_command),
            CommandHandler("list_channels", self.list_channels_command),
            CommandHandler("set_text", self.set_text_command),
            CommandHandler("set_link_text", self.set_link_text_command),
            CommandHandler("switch_mode", self.switch_mode_command),
            CommandHandler("batch_start", self.batch_start_command),
            CommandHandler("batch_end", self.batch_end_command),
            CommandHandler("set_schedule", self.set_schedule_command),
            CommandHandler("status", self.status_command),
            CommandHandler("test", self.test_command),
            CommandHandler("help", self.help_command),
        ]


# 全局管理员命令处理器实例
admin_handler = AdminCommandHandler()
