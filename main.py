"""
Telegram频道消息处理机器人主程序
"""

import sys
import asyncio
from telegram.ext import Application, MessageHandler, filters
from config import config
from message_handler import message_processor
from admin_commands import admin_handler
from forward_mode import forward_mode
from inline_keyboard import inline_keyboard_manager
from logger_config import setup_logging, get_logger, error_handler


class TelegramBot:
    """Telegram机器人主类"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.application = None
        self.is_running = False
    
    def initialize(self):
        """初始化机器人"""
        try:
            # 设置日志系统
            setup_logging()
            self.logger.info("正在初始化Telegram机器人...")

            # 创建应用程序
            self.application = Application.builder().token(config.bot_token).build()

            # 添加消息处理器
            message_handler = MessageHandler(
                filters.ALL & ~filters.COMMAND,  # 处理所有非命令消息
                self._handle_all_messages
            )
            self.application.add_handler(message_handler)
            self.logger.info("已添加消息处理器")

            # 添加管理员命令处理器
            handlers = admin_handler.get_handlers()
            for handler in handlers:
                self.application.add_handler(handler)
            self.logger.info(f"已添加 {len(handlers)} 个管理员命令处理器")

            # 添加内联键盘处理器
            keyboard_handlers = inline_keyboard_manager.get_handlers()
            for handler in keyboard_handlers:
                self.application.add_handler(handler)
            self.logger.info(f"已添加 {len(keyboard_handlers)} 个内联键盘处理器")

            # 添加错误处理器
            self.application.add_error_handler(self.error_callback)

            self.logger.info("机器人初始化完成")

        except Exception as e:
            self.logger.error(f"机器人初始化失败: {e}")
            raise
    
    async def error_callback(self, _, context):
        """错误回调处理器"""
        try:
            error_msg = str(context.error)
            self.logger.error(f"Telegram错误: {error_msg}")

            # 检查是否是连接错误
            if "EndOfStream" in error_msg or "Connection" in error_msg:
                self.logger.warning("检测到连接错误，尝试继续运行...")
                # 不抛出异常，让程序继续运行
                return

            await error_handler.handle_telegram_error(context.error, "全局错误处理")
        except Exception as e:
            self.logger.error(f"错误处理器异常: {e}")

    async def _handle_all_messages(self, update, context):
        """统一消息处理器"""
        try:
            message = update.message
            if not message:
                return

            # 检查是否为私聊消息
            if message.chat.type == 'private':
                # 首先检查是否在等待用户输入
                if await self._handle_user_input(update, context):
                    return

                # 如果转发模式激活，处理转发消息
                if forward_mode.is_active:
                    await forward_mode.handle_forwarded_message(update, context)
            elif message.chat.type in ['channel', 'supergroup'] and not forward_mode.is_active:
                # 监听模式：只处理频道/超级群组消息
                await message_processor.handle_channel_message(update, context)
            else:
                # 其他情况不处理
                self.logger.debug(f"跳过处理消息 - 聊天类型: {message.chat.type}, 转发模式: {forward_mode.is_active}")
        except Exception as e:
            self.logger.error(f"消息处理失败: {e}")

    async def _handle_user_input(self, update, context):
        """处理用户输入"""
        try:
            # 检查是否在等待用户输入
            waiting_for = context.user_data.get('waiting_for')
            if not waiting_for:
                return False

            # 检查是否为管理员
            if not config.is_admin(update.effective_user.id):
                return False

            message_text = update.message.text
            if not message_text:
                await update.message.reply_text("❌ 请发送文本消息")
                return True

            # 处理不同类型的输入
            if waiting_for == 'detection_text':
                await self._handle_detection_text_input(update, context, message_text)
            elif waiting_for == 'link_text':
                await self._handle_link_text_input(update, context, message_text)
            elif waiting_for == 'add_channel':
                await self._handle_add_channel_input(update, context, message_text)
            elif waiting_for == 'set_schedule':
                await self._handle_schedule_input(update, context, message_text)
            else:
                await update.message.reply_text("❌ 未知的输入类型")

            # 清除等待状态
            context.user_data.pop('waiting_for', None)
            return True

        except Exception as e:
            self.logger.error(f"处理用户输入失败: {e}")
            context.user_data.pop('waiting_for', None)
            return True

    async def _handle_detection_text_input(self, update, context, text):
        """处理检测文本输入"""
        try:
            if config.set_detection_text(text):
                await update.message.reply_text(f"✅ 检测文本已设置为: {text}")
            else:
                await update.message.reply_text("❌ 设置检测文本失败")
        except Exception as e:
            self.logger.error(f"设置检测文本时发生错误: {e}")
            await update.message.reply_text("❌ 设置检测文本时发生错误，请重试")

        # 返回主菜单
        await asyncio.sleep(1.5)
        await inline_keyboard_manager.send_main_menu(update, context)

    async def _handle_link_text_input(self, update, context, text):
        """处理链接文本输入"""
        try:
            if config.set_link_text(text):
                await update.message.reply_text(f"✅ 链接文本已设置为: {text}")
            else:
                await update.message.reply_text("❌ 设置链接文本失败")
        except Exception as e:
            self.logger.error(f"设置链接文本时发生错误: {e}")
            await update.message.reply_text("❌ 设置链接文本时发生错误，请重试")

        # 返回主菜单
        await asyncio.sleep(1.5)
        await inline_keyboard_manager.send_main_menu(update, context)

    async def _handle_add_channel_input(self, update, context, channel):
        """处理添加频道输入"""
        try:
            # 验证频道格式
            if not self._validate_channel_format(channel):
                await update.message.reply_text("❌ 频道格式无效\n\n正确格式:\n• @channel_username\n• -1001234567890")
                await asyncio.sleep(1.5)
                await inline_keyboard_manager.send_main_menu(update, context)
                return

            # 添加频道
            if config.add_channel(channel):
                await update.message.reply_text(f"✅ 频道已添加: {channel}")
            else:
                await update.message.reply_text(f"❌ 频道已存在或添加失败: {channel}")
        except Exception as e:
            self.logger.error(f"添加频道时发生错误: {e}")
            await update.message.reply_text("❌ 添加频道时发生错误，请重试")

        # 返回主菜单
        await asyncio.sleep(1.5)
        await inline_keyboard_manager.send_main_menu(update, context)

    async def _handle_schedule_input(self, update, context, time_str):
        """处理定时设置输入"""
        try:
            from datetime import datetime
            # 解析时间格式
            scheduled_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M')

            # 检查时间是否在未来
            if scheduled_time <= datetime.now():
                await update.message.reply_text("❌ 定时时间必须是未来时间")
                await asyncio.sleep(1.5)
                await inline_keyboard_manager.send_main_menu(update, context)
                return

            forward_mode.scheduled_time = scheduled_time
            await update.message.reply_text(f"✅ 定时发送已设置为: {scheduled_time.strftime('%Y-%m-%d %H:%M')}")

        except ValueError:
            await update.message.reply_text("❌ 时间格式错误\n\n正确格式: YYYY-MM-DD HH:MM\n示例: 2024-12-25 15:30")
            await asyncio.sleep(1.5)
            await inline_keyboard_manager.send_main_menu(update, context)
            return
        except Exception as e:
            self.logger.error(f"处理定时设置时发生错误: {e}")
            await update.message.reply_text("❌ 设置定时时发生错误，请重试")
            await asyncio.sleep(1.5)
            await inline_keyboard_manager.send_main_menu(update, context)
            return

        # 返回主菜单
        await asyncio.sleep(1.5)
        await inline_keyboard_manager.send_main_menu(update, context)

    def _validate_channel_format(self, channel):
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
    

    
def main():
    """主函数"""
    bot = TelegramBot()

    try:
        bot.initialize()

        # 显示启动信息
        channels = config.get_channels()
        settings = config.get_settings()

        print("🤖 Telegram频道消息处理机器人已启动")
        print(f"📋 监听频道数量: {len(channels)}")
        print(f"🔍 检测文本: {settings.get('detection_text')}")
        print(f"👥 管理员数量: {len(config.admin_ids)}")
        print("✅ 机器人正在运行中...")
        print("按 Ctrl+C 停止机器人")

        # 启动机器人（带重连机制）
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                bot.application.run_polling(
                    poll_interval=1.0,
                    timeout=10,
                    bootstrap_retries=3,
                    read_timeout=30,
                    write_timeout=30,
                    connect_timeout=30,
                    pool_timeout=30
                )
                break  # 如果成功运行，跳出循环

            except Exception as e:
                retry_count += 1
                error_msg = str(e)
                print(f"❌ 连接失败 (尝试 {retry_count}/{max_retries}): {error_msg}")

                if "EndOfStream" in error_msg or "Connection" in error_msg:
                    if retry_count < max_retries:
                        print("🔄 检测到网络问题，5秒后重试...")
                        import time
                        time.sleep(5)
                        continue

                if retry_count >= max_retries:
                    print(f"❌ 程序运行失败，已重试 {max_retries} 次: {e}")
                    sys.exit(1)

    except KeyboardInterrupt:
        print("\n👋 机器人已停止")
    except Exception as e:
        print(f"❌ 程序运行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 再见！")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)
