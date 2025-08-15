"""
Telegram频道消息处理机器人主程序
"""

import sys
from telegram.ext import Application, MessageHandler, filters
from config import config
from message_handler import message_processor
from admin_commands import admin_handler
from forward_mode import forward_mode
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

            # 添加错误处理器
            self.application.add_error_handler(self.error_callback)

            self.logger.info("机器人初始化完成")

        except Exception as e:
            self.logger.error(f"机器人初始化失败: {e}")
            raise
    
    async def error_callback(self, _, context):
        """错误回调处理器"""
        try:
            await error_handler.handle_telegram_error(context.error, "全局错误处理")
        except Exception as e:
            self.logger.error(f"错误处理器异常: {e}")

    async def _handle_all_messages(self, update, context):
        """统一消息处理器"""
        try:
            message = update.message
            if not message:
                return

            # 检查是否为私聊消息且转发模式激活
            if message.chat.type == 'private' and forward_mode.is_active:
                # 转发模式：处理私聊中的消息
                await forward_mode.handle_forwarded_message(update, context)
            elif message.chat.type in ['channel', 'supergroup'] and not forward_mode.is_active:
                # 监听模式：只处理频道/超级群组消息
                await message_processor.handle_channel_message(update, context)
            else:
                # 其他情况不处理
                self.logger.debug(f"跳过处理消息 - 聊天类型: {message.chat.type}, 转发模式: {forward_mode.is_active}")
        except Exception as e:
            self.logger.error(f"消息处理失败: {e}")
    

    
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

        # 启动机器人
        bot.application.run_polling()

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
