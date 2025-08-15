"""
内联键盘管理模块
提供机器人管理的内联键盘界面
"""

import logging
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from config import config
from forward_mode import forward_mode

logger = logging.getLogger(__name__)


class InlineKeyboardManager:
    """内联键盘管理器"""
    
    def __init__(self):
        self.admin_ids = config.admin_ids
    
    def is_admin(self, user_id: int) -> bool:
        """检查用户是否为管理员"""
        return user_id in self.admin_ids
    
    def get_main_menu_keyboard(self) -> InlineKeyboardMarkup:
        """获取主菜单键盘"""
        current_mode = "转发模式" if forward_mode.is_active else "监听模式"
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 切换模式", callback_data="switch_mode"),
                InlineKeyboardButton("📊 查看状态", callback_data="status")
            ],
            [
                InlineKeyboardButton("📝 文本设置", callback_data="text_settings"),
                InlineKeyboardButton("📢 频道管理", callback_data="channel_management")
            ]
        ]
        
        # 根据当前模式添加相应按钮
        if forward_mode.is_active:
            keyboard.append([
                InlineKeyboardButton("📦 批量模式", callback_data="batch_mode"),
                InlineKeyboardButton("⏰ 定时设置", callback_data="schedule_settings")
            ])
        
        keyboard.append([InlineKeyboardButton("❓ 帮助", callback_data="help")])
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_mode_switch_keyboard(self) -> InlineKeyboardMarkup:
        """获取模式切换键盘"""
        keyboard = [
            [
                InlineKeyboardButton("👂 监听模式", callback_data="mode_listen"),
                InlineKeyboardButton("📤 转发模式", callback_data="mode_forward")
            ],
            [InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_text_settings_keyboard(self) -> InlineKeyboardMarkup:
        """获取文本设置键盘"""
        keyboard = [
            [InlineKeyboardButton("🎯 设置检测文本", callback_data="set_detection_text")],
            [InlineKeyboardButton("🔗 设置链接文本", callback_data="set_link_text")],
            [InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_channel_management_keyboard(self) -> InlineKeyboardMarkup:
        """获取频道管理键盘"""
        keyboard = [
            [InlineKeyboardButton("➕ 添加频道", callback_data="add_channel")],
            [InlineKeyboardButton("➖ 移除频道", callback_data="remove_channel")],
            [InlineKeyboardButton("📋 查看频道列表", callback_data="list_channels")],
            [InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_batch_mode_keyboard(self) -> InlineKeyboardMarkup:
        """获取批量模式键盘"""
        batch_status = "开启" if forward_mode.is_batch_mode else "关闭"
        
        keyboard = [
            [InlineKeyboardButton(f"📦 批量模式: {batch_status}", callback_data="toggle_batch")],
        ]
        
        if forward_mode.is_batch_mode:
            keyboard.append([InlineKeyboardButton("🏁 结束批量模式", callback_data="end_batch")])
        else:
            keyboard.append([InlineKeyboardButton("🚀 开始批量模式", callback_data="start_batch")])
        
        keyboard.append([InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")])
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_schedule_settings_keyboard(self) -> InlineKeyboardMarkup:
        """获取定时设置键盘"""
        current_schedule = forward_mode.scheduled_time
        schedule_text = current_schedule.strftime('%Y-%m-%d %H:%M') if current_schedule else "未设置"
        
        keyboard = [
            [InlineKeyboardButton(f"⏰ 当前定时: {schedule_text}", callback_data="current_schedule")],
            [InlineKeyboardButton("🕐 设置定时", callback_data="set_schedule")],
        ]
        
        if current_schedule:
            keyboard.append([InlineKeyboardButton("🗑️ 清除定时", callback_data="clear_schedule")])
        
        keyboard.append([InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")])
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_confirmation_keyboard(self, action: str) -> InlineKeyboardMarkup:
        """获取确认操作键盘"""
        keyboard = [
            [
                InlineKeyboardButton("✅ 确认", callback_data=f"confirm_{action}"),
                InlineKeyboardButton("❌ 取消", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def send_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """发送主菜单"""
        if not self.is_admin(update.effective_user.id):
            return
        
        current_mode = "转发模式" if forward_mode.is_active else "监听模式"
        text = f"🤖 Telegram频道消息处理机器人\n\n📍 当前模式: {current_mode}\n\n请选择操作："
        
        keyboard = self.get_main_menu_keyboard()
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text=text, reply_markup=keyboard)
        else:
            await update.message.reply_text(text=text, reply_markup=keyboard)
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理回调查询"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_admin(query.from_user.id):
            await query.answer("❌ 您没有权限执行此操作", show_alert=True)
            return
        
        data = query.data
        logger.info(f"收到回调查询: {data}")
        
        # 路由到相应的处理方法
        if data == "main_menu":
            await self.send_main_menu(update, context)
        elif data == "switch_mode":
            await self._handle_switch_mode_menu(update, context)
        elif data == "status":
            await self._handle_status(update, context)
        elif data == "text_settings":
            await self._handle_text_settings_menu(update, context)
        elif data == "channel_management":
            await self._handle_channel_management_menu(update, context)
        elif data == "batch_mode":
            await self._handle_batch_mode_menu(update, context)
        elif data == "schedule_settings":
            await self._handle_schedule_settings_menu(update, context)
        elif data == "help":
            await self._handle_help(update, context)
        elif data.startswith("mode_"):
            await self._handle_mode_switch(update, context, data)
        elif data in ["set_schedule", "clear_schedule", "current_schedule"]:
            await self._handle_schedule_operations(update, context, data)
        elif data in ["add_channel", "remove_channel", "list_channels"]:
            await self._handle_channel_operations(update, context, data)
        elif data.startswith("set_"):
            await self._handle_text_input_request(update, context, data)
        elif data.startswith("confirm_"):
            await self._handle_confirmation(update, context, data)
        elif data.startswith("delete_channel_"):
            await self._handle_delete_channel(update, context, data)
        else:
            await self._handle_other_actions(update, context, data)
    
    async def _handle_switch_mode_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理模式切换菜单"""
        current_mode = "转发模式" if forward_mode.is_active else "监听模式"
        text = f"🔄 模式切换\n\n📍 当前模式: {current_mode}\n\n请选择要切换的模式："
        
        keyboard = self.get_mode_switch_keyboard()
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard)
    
    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理状态查询"""
        from message_handler import message_processor
        from link_processor import link_processor
        
        # 获取各种统计信息
        channels = config.get_channels()
        settings = config.get_settings()
        message_stats = message_processor.get_stats()
        link_stats = link_processor.get_stats()
        forward_stats = forward_mode.get_status()
        
        # 当前工作模式
        current_mode = "转发模式" if forward_stats['is_active'] else "监听模式"
        
        status_text = (
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
            
            status_text += (
                f"📤 转发模式状态:\n"
                f"• 批量模式: {batch_status}\n"
                f"• 待处理消息: {forward_stats['pending_messages_count']}\n"
                f"• 已转发消息: {forward_stats['processed_count']}\n"
                f"• 转发错误: {forward_stats['error_count']}\n"
                f"• 定时发送: {schedule_info}\n\n"
            )
        
        status_text += f"⚙️ 系统信息:\n• 配置更新时间: {settings.get('last_updated', '未知')}"
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")]])
        await update.callback_query.edit_message_text(text=status_text, reply_markup=keyboard)

    async def _handle_text_settings_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理文本设置菜单"""
        settings = config.get_settings()
        detection_text = settings.get('detection_text', '未设置')
        link_text = settings.get('link_text', '未设置')

        text = (
            "📝 文本设置\n\n"
            f"🎯 当前检测文本: {detection_text}\n"
            f"🔗 当前链接文本: {link_text}\n\n"
            "请选择要设置的项目："
        )

        keyboard = self.get_text_settings_keyboard()
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

    async def _handle_channel_management_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理频道管理菜单"""
        channels = config.get_channels()

        text = (
            "📢 频道管理\n\n"
            f"📊 当前配置频道数: {len(channels)}\n\n"
            "请选择操作："
        )

        keyboard = self.get_channel_management_keyboard()
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

    async def _handle_batch_mode_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理批量模式菜单"""
        batch_status = "开启" if forward_mode.is_batch_mode else "关闭"
        pending_count = len(forward_mode.pending_messages)

        text = (
            "📦 批量模式设置\n\n"
            f"📊 当前状态: {batch_status}\n"
            f"📋 待处理消息: {pending_count}\n\n"
            "批量模式允许您收集多条消息后一次性发送。"
        )

        keyboard = self.get_batch_mode_keyboard()
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

    async def _handle_schedule_settings_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理定时设置菜单"""
        current_schedule = forward_mode.scheduled_time
        schedule_text = current_schedule.strftime('%Y-%m-%d %H:%M') if current_schedule else "未设置"

        text = (
            "⏰ 定时发送设置\n\n"
            f"📅 当前定时: {schedule_text}\n\n"
            "定时发送允许您设置消息的发送时间。"
        )

        keyboard = self.get_schedule_settings_keyboard()
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理帮助信息"""
        help_text = (
            "❓ 帮助信息\n\n"
            "🤖 这是一个Telegram频道消息处理机器人\n\n"
            "📋 主要功能:\n"
            "• 监听模式: 监听频道消息并处理链接\n"
            "• 转发模式: 转发消息到指定频道\n"
            "• 批量处理: 收集多条消息后批量发送\n"
            "• 定时发送: 设置消息发送时间\n\n"
            "🔧 使用方法:\n"
            "1. 使用 /start 打开主菜单\n"
            "2. 选择相应的模式和设置\n"
            "3. 发送消息给机器人进行处理\n\n"
            "⚠️ 注意: 只有管理员可以使用此机器人"
        )

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")]])
        await update.callback_query.edit_message_text(text=help_text, reply_markup=keyboard)

    async def _handle_mode_switch(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
        """处理模式切换"""
        if data == "mode_listen":
            if forward_mode.is_active:
                forward_mode.deactivate()
                text = "✅ 已切换到监听模式"
            else:
                text = "ℹ️ 当前已经是监听模式"
        elif data == "mode_forward":
            if not forward_mode.is_active:
                forward_mode.activate()
                text = "✅ 已切换到转发模式"
            else:
                text = "ℹ️ 当前已经是转发模式"
        else:
            text = "❌ 未知的模式"

        # 显示结果并返回主菜单
        await update.callback_query.edit_message_text(text=text)
        await asyncio.sleep(1.5)
        await self.send_main_menu(update, context)

    async def _handle_text_input_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
        """处理文本输入请求"""
        if data == "set_detection_text":
            text = "🎯 请发送新的检测文本:"
            context.user_data['waiting_for'] = 'detection_text'
        elif data == "set_link_text":
            text = "🔗 请发送新的链接文本:"
            context.user_data['waiting_for'] = 'link_text'
        else:
            text = "❌ 未知的设置项"

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="main_menu")]])
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

    async def _handle_other_actions(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
        """处理其他操作"""
        if data == "toggle_batch":
            if forward_mode.is_batch_mode:
                forward_mode.is_batch_mode = False
                text = "✅ 批量模式已关闭"
            else:
                forward_mode.is_batch_mode = True
                text = "✅ 批量模式已开启"

            await update.callback_query.edit_message_text(text=text)
            await asyncio.sleep(1.5)
            await self._handle_batch_mode_menu(update, context)

        elif data == "start_batch":
            forward_mode.is_batch_mode = True
            text = "✅ 批量模式已开启，现在可以发送消息进行收集"
            await update.callback_query.edit_message_text(text=text)
            await asyncio.sleep(1.5)
            await self._handle_batch_mode_menu(update, context)

        elif data == "end_batch":
            if forward_mode.pending_messages:
                text = f"📦 即将发送 {len(forward_mode.pending_messages)} 条消息，请确认："
                keyboard = self.get_confirmation_keyboard("send_batch")
                await update.callback_query.edit_message_text(text=text, reply_markup=keyboard)
            else:
                forward_mode.is_batch_mode = False
                text = "ℹ️ 批量队列为空，已关闭批量模式"
                await update.callback_query.edit_message_text(text=text)
                await asyncio.sleep(1.5)
                await self._handle_batch_mode_menu(update, context)
        else:
            text = "❌ 未知的操作"
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")]])
            await update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

    async def _handle_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
        """处理确认操作"""
        action = data.replace("confirm_", "")

        if action == "send_batch":
            # 执行批量发送
            count = len(forward_mode.pending_messages)
            await forward_mode.send_batch_messages(context)
            text = f"✅ 已发送 {count} 条消息"

            await update.callback_query.edit_message_text(text=text)
            await asyncio.sleep(1.5)
            await self.send_main_menu(update, context)
        else:
            text = "❌ 未知的确认操作"
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")]])
            await update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

    async def _handle_channel_operations(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
        """处理频道操作"""
        if data == "list_channels":
            await self._handle_list_channels(update, context)
        elif data == "add_channel":
            await self._handle_add_channel_request(update, context)
        elif data == "remove_channel":
            await self._handle_remove_channel_request(update, context)

    async def _handle_list_channels(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理查看频道列表"""
        channels = config.get_channels()

        if not channels:
            text = "📢 频道列表\n\n❌ 当前没有配置任何频道"
        else:
            text = f"📢 频道列表\n\n📊 共 {len(channels)} 个频道:\n\n"
            for i, channel in enumerate(channels, 1):
                text += f"{i}. {channel}\n"

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回频道管理", callback_data="channel_management")]])
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

    async def _handle_add_channel_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理添加频道请求"""
        text = (
            "➕ 添加频道\n\n"
            "请发送要添加的频道ID或用户名:\n\n"
            "格式示例:\n"
            "• @channel_username\n"
            "• -1001234567890\n\n"
            "⚠️ 确保机器人已被添加到该频道并具有发送消息权限"
        )

        context.user_data['waiting_for'] = 'add_channel'
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="channel_management")]])
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

    async def _handle_remove_channel_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理删除频道请求"""
        channels = config.get_channels()

        if not channels:
            text = "❌ 当前没有配置任何频道"
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回频道管理", callback_data="channel_management")]])
        else:
            text = f"➖ 删除频道\n\n📊 当前频道列表:\n\n"
            keyboard_buttons = []

            for i, channel in enumerate(channels):
                text += f"{i+1}. {channel}\n"
                keyboard_buttons.append([InlineKeyboardButton(f"删除 {channel}", callback_data=f"delete_channel_{i}")])

            text += "\n请选择要删除的频道:"
            keyboard_buttons.append([InlineKeyboardButton("🔙 返回频道管理", callback_data="channel_management")])
            keyboard = InlineKeyboardMarkup(keyboard_buttons)

        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

    async def _handle_schedule_operations(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
        """处理定时操作"""
        if data == "current_schedule":
            # 避免重复调用，直接显示当前状态
            current_schedule = forward_mode.scheduled_time
            schedule_text = current_schedule.strftime('%Y-%m-%d %H:%M') if current_schedule else "未设置"
            text = f"⏰ 当前定时发送时间\n\n📅 {schedule_text}"
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回定时设置", callback_data="schedule_settings")]])
            await update.callback_query.edit_message_text(text=text, reply_markup=keyboard)
        elif data == "set_schedule":
            await self._handle_set_schedule_request(update, context)
        elif data == "clear_schedule":
            forward_mode.scheduled_time = None
            text = "✅ 定时发送已清除"
            await update.callback_query.edit_message_text(text=text)
            await asyncio.sleep(1.5)
            await self._handle_schedule_settings_menu(update, context)

    async def _handle_set_schedule_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理设置定时请求"""
        text = (
            "⏰ 设置定时发送\n\n"
            "请发送定时发送的时间:\n\n"
            "格式: YYYY-MM-DD HH:MM\n"
            "示例: 2024-12-25 15:30\n\n"
            "⚠️ 请使用24小时制格式"
        )

        context.user_data['waiting_for'] = 'set_schedule'
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消", callback_data="schedule_settings")]])
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

    async def _handle_delete_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
        """处理删除频道"""
        try:
            # 从回调数据中提取频道索引
            channel_index = int(data.replace("delete_channel_", ""))
            channels = config.get_channels()

            if 0 <= channel_index < len(channels):
                channel_to_delete = channels[channel_index]

                # 删除频道
                if config.remove_channel(channel_to_delete):
                    text = f"✅ 频道已删除: {channel_to_delete}"
                else:
                    text = f"❌ 删除频道失败: {channel_to_delete}"
            else:
                text = "❌ 无效的频道索引"

            await update.callback_query.edit_message_text(text=text)
            await asyncio.sleep(1.5)
            await self._handle_channel_management_menu(update, context)

        except (ValueError, IndexError):
            text = "❌ 删除频道时发生错误"
            await update.callback_query.edit_message_text(text=text)
            await asyncio.sleep(1.5)
            await self._handle_channel_management_menu(update, context)

    def get_handlers(self):
        """获取回调查询处理器"""
        return [CallbackQueryHandler(self.handle_callback_query)]


# 全局内联键盘管理器实例
inline_keyboard_manager = InlineKeyboardManager()
