"""
消息处理模块
负责处理Telegram消息的核心业务逻辑
"""

import logging
import asyncio
import re
from typing import Optional, Dict
from telegram import Update, Message, MessageEntity
from telegram.ext import ContextTypes
from config import config

logger = logging.getLogger(__name__)


class MessageProcessor:
    """消息处理器类"""
    
    def __init__(self):
        self.processed_count = 0
        self.error_count = 0
        self.media_group_buffer: Dict[str, list] = {}  # 存储媒体组消息
        self.media_group_timers: Dict[str, asyncio.Task] = {}  # 媒体组处理定时器
    
    async def handle_channel_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理频道消息"""
        try:
            logger.info("收到更新，开始处理...")

            # 详细记录更新类型
            if update.channel_post:
                logger.info("检测到频道消息")
                message = update.channel_post
            elif update.message:
                logger.info("检测到普通消息")
                message = update.message
            elif update.edited_channel_post:
                logger.info("检测到编辑的频道消息")
                message = update.edited_channel_post
            elif update.edited_message:
                logger.info("检测到编辑的消息")
                message = update.edited_message
            else:
                logger.info("未检测到相关消息类型，跳过处理")
                return

            # 记录消息基本信息
            chat_info = f"频道ID: {message.chat.id}"
            if message.chat.username:
                chat_info += f", 用户名: @{message.chat.username}"
            if message.chat.title:
                chat_info += f", 标题: {message.chat.title}"

            logger.info(f"消息来源 - {chat_info}")
            logger.info(f"消息ID: {message.message_id}")

            # 检查消息内容（文本或caption）
            message_text = message.text or message.caption
            if message_text:
                logger.info(f"消息文本: {message_text[:100]}...")  # 只显示前100个字符
            else:
                logger.info("消息无文本内容")

            # 检查是否为媒体组
            if message.media_group_id:
                logger.info(f"检测到媒体组消息，组ID: {message.media_group_id}")
                await self._handle_media_group(message, context)
                return

            # 检查消息是否来自监听的频道
            if not self._is_monitored_channel(message):
                logger.info("消息不来自监听的频道，跳过处理")
                return

            logger.info("✅ 消息来自监听的频道")

            # 检查消息是否包含目标文本
            if not self._contains_target_text(message):
                logger.info("消息不包含目标文本，跳过处理")
                return

            logger.info("✅ 消息包含目标文本，开始处理")

            # 处理消息
            await self._process_message(message, context)

        except Exception as e:
            logger.error(f"处理消息时发生错误: {e}")
            self.error_count += 1

    async def _handle_media_group(self, message: Message, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理媒体组消息"""
        group_id = message.media_group_id

        # 将消息添加到缓冲区
        if group_id not in self.media_group_buffer:
            self.media_group_buffer[group_id] = []

        self.media_group_buffer[group_id].append(message)
        logger.info(f"媒体组 {group_id} 当前有 {len(self.media_group_buffer[group_id])} 个消息")

        # 取消之前的定时器
        if group_id in self.media_group_timers:
            self.media_group_timers[group_id].cancel()

        # 设置新的定时器，等待2秒后处理媒体组
        self.media_group_timers[group_id] = asyncio.create_task(
            self._process_media_group_delayed(group_id, context)
        )

    async def _process_media_group_delayed(self, group_id: str, context: ContextTypes.DEFAULT_TYPE) -> None:
        """延迟处理媒体组"""
        try:
            await asyncio.sleep(2)  # 等待2秒确保所有媒体都收到

            if group_id not in self.media_group_buffer:
                return

            messages = self.media_group_buffer[group_id]
            logger.info(f"开始处理媒体组 {group_id}，共 {len(messages)} 个消息")

            # 查找包含文本的消息（通常是第一个）
            text_message = None
            for msg in messages:
                if msg.text or msg.caption:
                    text_message = msg
                    break

            if text_message:
                logger.info(f"找到包含文本的消息: {text_message.text or text_message.caption}")

                # 检查消息是否来自监听的频道
                if not self._is_monitored_channel(text_message):
                    logger.info("媒体组消息不来自监听的频道，跳过处理")
                    return

                logger.info("✅ 媒体组消息来自监听的频道")

                # 检查消息是否包含目标文本
                if not self._contains_target_text(text_message):
                    logger.info("媒体组消息不包含目标文本，跳过处理")
                    return

                logger.info("✅ 媒体组消息包含目标文本，开始处理")

                # 处理媒体组消息
                await self._process_media_group_message(messages, text_message, context)
            else:
                logger.info("媒体组中没有找到包含文本的消息")

        except Exception as e:
            logger.error(f"处理媒体组时发生错误: {e}")
        finally:
            # 清理缓冲区和定时器
            if group_id in self.media_group_buffer:
                del self.media_group_buffer[group_id]
            if group_id in self.media_group_timers:
                del self.media_group_timers[group_id]

    async def _process_media_group_message(self, messages: list, text_message: Message, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理媒体组消息 - 保持媒体组结构"""
        try:
            logger.info("开始处理媒体组消息，保持媒体组结构")

            # 处理文本消息的链接
            original_text = text_message.text or text_message.caption or ""
            logger.info(f"原始文本: {original_text}")

            # 处理链接
            processed_text, processed_entities = self._process_links(text_message, text_message.chat.id)

            # 检查是否有变化
            original_entities = text_message.entities or text_message.caption_entities or []
            has_entity_changes = any(
                orig.url != proc.url if hasattr(orig, 'url') and hasattr(proc, 'url') else False
                for orig, proc in zip(original_entities, processed_entities)
            )

            if processed_text != original_text or has_entity_changes:
                logger.info("检测到链接变化，需要重新发送媒体组")

                # 删除整个媒体组
                for msg in messages:
                    await self._delete_message_safely(context, msg.chat.id, msg.message_id)

                # 重新发送媒体组，但只更新第一个媒体的caption
                await self._resend_media_group(messages, processed_text, processed_entities, context)

                self.processed_count += 1
                logger.info("✅ 成功处理媒体组消息")
            else:
                logger.info("媒体组消息无需处理")

        except Exception as e:
            logger.error(f"处理媒体组消息失败: {e}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            self.error_count += 1

    async def _resend_media_group(self, messages: list, new_caption: str, new_entities: list, context: ContextTypes.DEFAULT_TYPE) -> None:
        """重新发送媒体组"""
        try:
            from telegram import InputMediaPhoto, InputMediaVideo, InputMediaDocument

            media_list = []
            chat_id = messages[0].chat.id

            for i, message in enumerate(messages):
                logger.info(f"处理媒体组中的第 {i+1} 个消息")

                # 确定媒体类型和文件ID
                if message.photo:
                    # 获取最大尺寸的照片
                    photo = message.photo[-1]
                    if i == 0:
                        # 第一个媒体包含处理后的caption
                        media = InputMediaPhoto(
                            media=photo.file_id,
                            caption=new_caption,
                            caption_entities=new_entities
                        )
                    else:
                        media = InputMediaPhoto(media=photo.file_id)
                    media_list.append(media)

                elif message.video:
                    if i == 0:
                        media = InputMediaVideo(
                            media=message.video.file_id,
                            caption=new_caption,
                            caption_entities=new_entities
                        )
                    else:
                        media = InputMediaVideo(media=message.video.file_id)
                    media_list.append(media)

                elif message.document:
                    if i == 0:
                        media = InputMediaDocument(
                            media=message.document.file_id,
                            caption=new_caption,
                            caption_entities=new_entities
                        )
                    else:
                        media = InputMediaDocument(media=message.document.file_id)
                    media_list.append(media)

            if media_list:
                logger.info(f"准备发送包含 {len(media_list)} 个媒体的媒体组")
                await context.bot.send_media_group(chat_id=chat_id, media=media_list)
                logger.info("✅ 成功重新发送媒体组")
            else:
                logger.warning("没有找到可发送的媒体")

        except Exception as e:
            logger.error(f"重新发送媒体组失败: {e}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            raise
    
    def _is_monitored_channel(self, message: Message) -> bool:
        """检查消息是否来自监听的频道"""
        if not message.chat:
            logger.warning("消息没有聊天信息")
            return False

        monitored_channels = config.get_channels()
        logger.info(f"当前监听的频道列表: {monitored_channels}")

        if not monitored_channels:
            logger.warning("没有配置监听频道")
            return False

        chat_id = str(message.chat.id)
        chat_username = f"@{message.chat.username}" if message.chat.username else None

        logger.info(f"检查频道匹配 - 消息频道ID: {chat_id}, 用户名: {chat_username}")

        # 检查频道ID或用户名是否在监听列表中
        for channel in monitored_channels:
            logger.info(f"对比配置频道: {channel}")
            if channel == chat_id or channel == chat_username:
                logger.info(f"✅ 找到匹配的频道: {channel}")
                return True

        logger.info("❌ 未找到匹配的频道")
        return False
    
    def _contains_target_text(self, message: Message) -> bool:
        """检查消息是否包含目标文本"""
        message_text = message.text or message.caption
        if not message_text:
            logger.info("消息没有文本内容")
            return False

        settings = config.get_settings()
        target_text = settings.get('detection_text', '▶️加入会员观看完整版')

        logger.info(f"检查目标文本 - 目标: '{target_text}'")
        logger.info(f"消息文本: '{message_text}'")

        contains_target = target_text in message_text
        if contains_target:
            logger.info("✅ 消息包含目标文本")
        else:
            logger.info("❌ 消息不包含目标文本")

        return contains_target
    
    async def _process_message(self, message: Message, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理包含目标文本的消息"""
        try:
            logger.info("开始处理消息...")

            # 获取原始消息文本
            original_text = message.text or message.caption
            if not original_text:
                logger.warning("消息没有文本内容，无法处理")
                return

            logger.info(f"原始消息文本: {original_text}")

            # 处理链接替换
            logger.info("开始处理链接替换...")
            processed_text, processed_entities = self._process_links(message, message.chat.id)
            logger.info(f"处理后文本: {processed_text}")

            # 检查实体是否有变化
            original_entities = message.entities or message.caption_entities or []
            has_entity_changes = any(
                orig.url != proc.url if hasattr(orig, 'url') and hasattr(proc, 'url') else False
                for orig, proc in zip(original_entities, processed_entities)
            )

            if processed_text != original_text or has_entity_changes:
                logger.info("检测到文本变化，需要替换消息")

                # 保存原始消息的格式信息，使用处理后的实体
                logger.info("提取消息格式信息...")
                message_data = self._extract_message_data(message)
                # 更新实体信息
                message_data['entities'] = processed_entities
                logger.info(f"消息格式信息: {message_data}")

                # 删除原始消息
                logger.info(f"准备删除原始消息 ID: {message.message_id}")
                delete_success = await self._delete_message_safely(context, message.chat.id, message.message_id)

                if delete_success:
                    logger.info("原始消息删除成功，准备发送新消息")
                    # 发送处理后的消息，保持原有格式
                    await self._send_processed_message(context, message.chat.id, processed_text, message_data)

                    self.processed_count += 1
                    logger.info(f"✅ 成功处理消息，频道: {message.chat.id}")
                else:
                    logger.error("删除原始消息失败，跳过发送新消息")
            else:
                logger.info("文本没有变化，无需处理")

        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            self.error_count += 1

    def _extract_message_data(self, message: Message) -> dict:
        """提取消息的格式和元数据"""
        return {
            'parse_mode': getattr(message, 'parse_mode', None),
            'entities': message.entities,
            'caption_entities': message.caption_entities,
            'has_media': bool(message.photo or message.video or message.document or message.audio),
            'media_type': self._get_media_type(message),
            'reply_markup': message.reply_markup,
            'disable_web_page_preview': True  # 默认禁用预览，避免重复显示
        }

    def _get_media_type(self, message: Message) -> Optional[str]:
        """获取消息的媒体类型"""
        if message.photo:
            return 'photo'
        elif message.video:
            return 'video'
        elif message.document:
            return 'document'
        elif message.audio:
            return 'audio'
        elif message.voice:
            return 'voice'
        elif message.video_note:
            return 'video_note'
        return None

    async def _delete_message_safely(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int) -> bool:
        """安全地删除消息"""
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.debug(f"成功删除消息 {message_id}")
            return True
        except Exception as e:
            logger.error(f"删除消息失败 {message_id}: {e}")
            return False

    async def _send_processed_message(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int,
                                    text: str, message_data: dict) -> None:
        """发送处理后的消息，保持原有格式"""
        try:
            logger.info(f"准备发送消息到频道 {chat_id}")
            logger.info(f"消息内容: {text}")

            # 构建发送参数 - 使用实体信息而不是Markdown
            send_params = {
                'chat_id': chat_id,
                'text': text,
                'entities': message_data.get('entities'),  # 使用处理后的实体
                'disable_web_page_preview': False,  # 允许链接预览
                'reply_markup': message_data.get('reply_markup')
            }

            # 移除None值
            send_params = {k: v for k, v in send_params.items() if v is not None}

            logger.info(f"发送参数: {send_params}")
            await context.bot.send_message(**send_params)
            logger.info(f"✅ 成功发送处理后的消息到频道 {chat_id}")

        except Exception as e:
            logger.error(f"发送处理后的消息失败: {e}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            raise
    
    def _process_links(self, message: Message, current_chat_id: int) -> tuple:
        """处理消息中的链接 - 返回新文本和实体"""
        logger.info(f"开始处理链接，当前频道ID: {current_chat_id}")

        text = message.text or message.caption or ""
        logger.info(f"原始文本内容: '{text}'")

        # 检查消息实体中的链接
        original_entities = message.entities or message.caption_entities or []
        logger.info(f"消息实体数量: {len(original_entities)}")

        # 获取当前频道ID（处理-100前缀）
        current_id = str(current_chat_id)
        if current_id.startswith('-100'):
            new_channel_id = current_id[4:]
            logger.info(f"移除-100前缀: {current_id} -> {new_channel_id}")
        else:
            new_channel_id = current_id
            logger.info(f"频道ID无需处理: {new_channel_id}")

        has_changes = False
        pattern = r'https://t\.me/c/(\d+)/(\d+)'
        new_entities = []

        # 处理消息实体中的链接
        for entity in original_entities:
            logger.info(f"实体类型: {entity.type}, 偏移: {entity.offset}, 长度: {entity.length}")

            if entity.type == "text_link" and entity.url:
                logger.info(f"找到text_link实体，URL: {entity.url}")

                match = re.match(pattern, entity.url)
                if match:
                    original_channel_id = match.group(1)
                    message_id = match.group(2)

                    logger.info(f"处理链接 - 原频道ID: {original_channel_id}, 消息ID: {message_id}")

                    # 构建新链接
                    new_link = f"https://t.me/c/{new_channel_id}/{message_id}"
                    logger.info(f"链接替换: {entity.url} -> {new_link}")

                    # 创建新的MessageEntity对象
                    new_entity = MessageEntity(
                        type=entity.type,
                        offset=entity.offset,
                        length=entity.length,
                        url=new_link
                    )
                    new_entities.append(new_entity)
                    has_changes = True
                else:
                    # 保持原实体不变
                    new_entities.append(entity)
            else:
                # 保持原实体不变
                new_entities.append(entity)

        if has_changes:
            logger.info("找到并更新了链接实体")
            return text, new_entities
        else:
            logger.info("没有找到需要处理的链接实体")
            return text, list(original_entities)
    
    def get_stats(self) -> dict:
        """获取处理统计信息"""
        return {
            'processed_count': self.processed_count,
            'error_count': self.error_count
        }


# 全局消息处理器实例
message_processor = MessageProcessor()
