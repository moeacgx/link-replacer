"""
转发模式处理模块
实现管理员转发消息到多个频道的功能
"""

import logging
import asyncio
import re
from datetime import datetime

from telegram import Update, Message, MessageEntity
from telegram.ext import ContextTypes
from telegram.error import TimedOut, NetworkError, RetryAfter
from config import config

logger = logging.getLogger(__name__)


class ForwardMode:
    """转发模式处理器"""
    
    def __init__(self):
        self.is_active = False  # 是否处于转发模式
        self.is_batch_mode = False  # 是否处于批量模式
        self.scheduled_time = None  # 定时发送时间
        self.pending_messages = []  # 待处理的消息队列
        self.processed_count = 0
        self.error_count = 0
        self.media_group_buffer = {}  # 存储媒体组消息
        self.media_group_timers = {}  # 媒体组处理定时器

        # 频道队列系统
        self.channel_queues = {}  # 每个频道的任务队列 {channel_id: [tasks]}
        self.current_channel = None  # 当前处理的频道
        self.queue_worker_task = None  # 队列工作任务
        self.is_queue_running = False  # 队列是否运行中

        # 任务完成通知
        self.pending_notifications = {}  # 待发送的通知 {task_group_id: {message, total_channels, completed_channels}}


    
    def activate(self):
        """激活转发模式"""
        self.is_active = True
        self._start_queue_worker()
        logger.info("转发模式已激活")

    def deactivate(self):
        """停用转发模式"""
        self.is_active = False
        self.is_batch_mode = False
        self.scheduled_time = None
        self.pending_messages.clear()
        self._stop_queue_worker()
        self._clear_all_queues()
        logger.info("转发模式已停用")

    def _start_queue_worker(self):
        """启动队列工作器"""
        if not self.is_queue_running:
            self.is_queue_running = True
            self.queue_worker_task = asyncio.create_task(self._queue_worker())
            logger.info("频道队列工作器已启动")

    def _stop_queue_worker(self):
        """停止队列工作器"""
        self.is_queue_running = False
        if self.queue_worker_task and not self.queue_worker_task.done():
            self.queue_worker_task.cancel()
            logger.info("频道队列工作器已停止")

    def _clear_all_queues(self):
        """清空所有频道队列"""
        self.channel_queues.clear()
        self.current_channel = None
        logger.info("所有频道队列已清空")

    async def _queue_worker(self):
        """队列工作器 - 按频道顺序处理任务"""
        logger.info("频道队列工作器开始运行")
        try:
            while self.is_queue_running:
                try:
                    # 检查是否有任务需要处理
                    if not self.channel_queues:
                        await asyncio.sleep(1)  # 没有任务时等待1秒
                        continue

                    # 选择下一个要处理的频道
                    if self.current_channel is None or self.current_channel not in self.channel_queues:
                        # 选择第一个有任务的频道
                        self.current_channel = next(iter(self.channel_queues.keys()))
                        logger.info(f"开始处理频道: {self.current_channel}")

                    # 处理当前频道的一个任务
                    if self.current_channel in self.channel_queues and self.channel_queues[self.current_channel]:
                        task = self.channel_queues[self.current_channel].pop(0)
                        await self._execute_task(task)

                        # 任务间延迟
                        await asyncio.sleep(1)
                    else:
                        # 当前频道没有任务了，切换到下一个频道
                        if self.current_channel in self.channel_queues:
                            del self.channel_queues[self.current_channel]

                        if self.channel_queues:
                            # 还有其他频道有任务
                            self.current_channel = next(iter(self.channel_queues.keys()))
                            logger.info(f"切换到下一个频道: {self.current_channel}")
                            await asyncio.sleep(3)  # 频道间延迟3秒
                        else:
                            # 所有频道都处理完了
                            self.current_channel = None
                            logger.info("所有频道任务处理完成")

                except Exception as e:
                    logger.error(f"队列工作器处理任务失败: {e}")
                    await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("队列工作器被取消")
        except Exception as e:
            logger.error(f"队列工作器异常退出: {e}")
        finally:
            logger.info("队列工作器已停止")

    async def _execute_task(self, task):
        """执行单个任务"""
        try:
            task_type = task['type']
            channel = task['channel']
            context = task['context']
            task_group_id = task.get('task_group_id')

            logger.info(f"执行任务: {task_type} -> {channel}")

            success = False
            if task_type == 'media_group':
                messages = task['messages']
                await self._send_media_group_to_channel_direct(messages, channel, context)
                success = True

            elif task_type == 'single_message':
                message = task['message']
                await self._send_to_channel_direct(message, channel, context)
                success = True

            else:
                logger.error(f"未知的任务类型: {task_type}")

            # 如果任务成功且有任务组ID，更新完成状态
            if success and task_group_id and task_group_id in self.pending_notifications:
                await self._update_task_completion(task_group_id)

        except Exception as e:
            logger.error(f"执行任务失败: {e}")
            self.error_count += 1

    async def _update_task_completion(self, task_group_id):
        """更新任务完成状态并发送通知"""
        try:
            notification = self.pending_notifications[task_group_id]
            notification['completed_channels'] += 1

            logger.info(f"任务组 {task_group_id}: {notification['completed_channels']}/{notification['total_channels']} 完成")

            # 如果所有频道都完成了，发送成功通知
            if notification['completed_channels'] >= notification['total_channels']:
                message = notification['message']
                total_channels = notification['total_channels']
                message_type = notification['message_type']

                if message_type == 'single':
                    await message.reply_text(f"✅ 消息已成功发送到 {total_channels} 个频道")
                else:
                    await message.reply_text(f"✅ 媒体组已成功发送到 {total_channels} 个频道")

                # 清理通知记录
                del self.pending_notifications[task_group_id]
                logger.info(f"任务组 {task_group_id} 全部完成，已发送成功通知")

        except Exception as e:
            logger.error(f"更新任务完成状态失败: {e}")
    
    def start_batch(self):
        """开始批量模式"""
        self.is_batch_mode = True
        self.pending_messages.clear()
        logger.info("批量模式已开始")
    
    def end_batch(self):
        """结束批量模式"""
        self.is_batch_mode = False
        message_count = len(self.pending_messages)
        self.pending_messages.clear()
        logger.info(f"批量模式已结束，共处理 {message_count} 条消息")
        return message_count
    
    def set_scheduled_time(self, scheduled_time: datetime):
        """设置定时发送时间"""
        self.scheduled_time = scheduled_time
        logger.info(f"定时发送时间已设置: {scheduled_time}")
    
    def clear_scheduled_time(self):
        """清除定时发送时间"""
        self.scheduled_time = None
        logger.info("定时发送时间已清除")
    
    async def handle_forwarded_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理私聊中的消息（转发模式）"""
        try:
            if not self.is_active:
                return

            message = update.message
            if not message:
                return

            logger.info(f"收到私聊消息，消息ID: {message.message_id}")

            # 检查是否为媒体组
            if message.media_group_id:
                logger.info(f"检测到媒体组消息，组ID: {message.media_group_id}")
                await self._handle_media_group(message, context)
                return

            # 检查是否包含目标文本
            if not self._contains_target_text(message):
                logger.info("消息不包含目标文本，跳过处理")
                return

            logger.info("✅ 消息包含目标文本，开始转发处理")

            if self.is_batch_mode:
                # 批量模式：添加到队列
                self.pending_messages.append(message)
                logger.info(f"消息已添加到批量队列，当前队列长度: {len(self.pending_messages)}")
                # 发送确认消息
                await message.reply_text(f"✅ 消息已加入批量队列 ({len(self.pending_messages)})")
            else:
                # 立即处理模式
                await self._process_single_message(message, context)
                # 不在这里发送通知，等实际发送完成后再通知

        except Exception as e:
            logger.error(f"处理转发消息失败: {e}")
            self.error_count += 1

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

    async def _handle_media_group(self, message: Message, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理媒体组消息"""
        group_id = message.media_group_id

        # 将消息添加到缓冲区
        if group_id not in self.media_group_buffer:
            self.media_group_buffer[group_id] = []

        self.media_group_buffer[group_id].append(message)
        logger.info(f"媒体组 {group_id} 当前有 {len(self.media_group_buffer[group_id])} 个消息")

        # 只有第一个消息才设置定时器
        if len(self.media_group_buffer[group_id]) == 1:
            logger.info(f"为媒体组 {group_id} 设置2秒延迟处理")
            self.media_group_timers[group_id] = asyncio.create_task(
                self._process_media_group_delayed(group_id, context)
            )
        else:
            logger.info(f"媒体组 {group_id} 已有定时器，跳过设置")

    async def _process_media_group_delayed(self, group_id: str, context: ContextTypes.DEFAULT_TYPE) -> None:
        """延迟处理媒体组"""
        try:
            logger.info(f"媒体组 {group_id} 延迟处理开始，等待2秒...")
            await asyncio.sleep(2)  # 等待2秒确保所有媒体都收到

            if group_id not in self.media_group_buffer:
                logger.info(f"媒体组 {group_id} 已被处理或清理，跳过")
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

                # 检查消息是否包含目标文本
                if not self._contains_target_text(text_message):
                    logger.info("媒体组消息不包含目标文本，跳过处理")
                    return

                logger.info("✅ 媒体组消息包含目标文本，开始转发处理")

                if self.is_batch_mode:
                    # 批量模式：添加整个媒体组到队列
                    self.pending_messages.extend(messages)
                    logger.info(f"媒体组已添加到批量队列，当前队列长度: {len(self.pending_messages)}")
                    # 发送确认消息
                    await text_message.reply_text(f"✅ 媒体组已加入批量队列 ({len(messages)} 个媒体)")
                else:
                    # 立即处理模式
                    await self._process_media_group_messages(messages, context)
            else:
                logger.info("媒体组中没有找到包含文本的消息")

        except Exception as e:
            logger.error(f"处理媒体组时发生错误: {e}")
        finally:
            # 清理缓冲区、定时器和处理标记
            if group_id in self.media_group_buffer:
                del self.media_group_buffer[group_id]
                logger.info(f"清理媒体组 {group_id} 缓冲区")
            if group_id in self.media_group_timers:
                del self.media_group_timers[group_id]
                logger.info(f"清理媒体组 {group_id} 定时器")

    async def _process_media_group_delayed(self, group_id: str, context: ContextTypes.DEFAULT_TYPE) -> None:
        """延迟处理媒体组"""
        try:
            logger.info(f"媒体组 {group_id} 延迟处理开始，等待2秒...")
            await asyncio.sleep(2)  # 等待2秒确保所有媒体都收到

            if group_id not in self.media_group_buffer:
                logger.info(f"媒体组 {group_id} 已被处理或清理，跳过")
                return

            # 检查是否已经在处理中（防止重复处理）
            if hasattr(self, '_processing_groups') and group_id in self._processing_groups:
                logger.info(f"媒体组 {group_id} 正在处理中，跳过重复处理")
                return

            # 标记为正在处理
            if not hasattr(self, '_processing_groups'):
                self._processing_groups = set()
            self._processing_groups.add(group_id)

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

                # 检查消息是否包含目标文本
                if not self._contains_target_text(text_message):
                    logger.info("媒体组消息不包含目标文本，跳过处理")
                    return

                logger.info("✅ 媒体组消息包含目标文本，开始转发处理")

                if self.is_batch_mode:
                    # 批量模式：添加整个媒体组到队列
                    self.pending_messages.extend(messages)
                    logger.info(f"媒体组已添加到批量队列，当前队列长度: {len(self.pending_messages)}")
                    # 发送确认消息
                    await text_message.reply_text(f"✅ 媒体组已加入批量队列 ({len(messages)} 个媒体)")
                else:
                    # 立即处理模式
                    await self._process_media_group_messages(messages, context)
                    # 不在这里发送通知，等实际发送完成后再通知
            else:
                logger.info("媒体组中没有找到包含文本的消息")

        except Exception as e:
            logger.error(f"处理媒体组时发生错误: {e}")
        finally:
            # 清理缓冲区、定时器和处理标记
            if group_id in self.media_group_buffer:
                del self.media_group_buffer[group_id]
                logger.info(f"清理媒体组 {group_id} 缓冲区")
            if group_id in self.media_group_timers:
                del self.media_group_timers[group_id]
                logger.info(f"清理媒体组 {group_id} 定时器")
            if hasattr(self, '_processing_groups') and group_id in self._processing_groups:
                self._processing_groups.remove(group_id)
                logger.info(f"清理媒体组 {group_id} 处理标记")
    
    async def process_batch_messages(self, context: ContextTypes.DEFAULT_TYPE) -> int:
        """处理批量消息"""
        try:
            if not self.pending_messages:
                logger.info("没有待处理的消息")
                return 0

            logger.info(f"开始处理批量消息，共 {len(self.pending_messages)} 条")

            processed = 0
            for message in self.pending_messages:
                try:
                    await self._process_single_message(message, context)
                    processed += 1
                except Exception as e:
                    logger.error(f"处理消息 {message.message_id} 失败: {e}")
                    self.error_count += 1

            self.pending_messages.clear()
            logger.info(f"批量处理完成，成功处理 {processed} 条消息")
            return processed

        except Exception as e:
            logger.error(f"批量处理失败: {e}")
            return 0

    async def _process_media_group_messages(self, messages, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理媒体组消息 - 添加到频道队列"""
        try:
            logger.info(f"开始处理媒体组，共 {len(messages)} 个消息")

            # 获取目标频道列表
            target_channels = config.get_channels()
            if not target_channels:
                logger.warning("没有配置目标频道")
                return

            # 找到包含文本的消息用于通知
            text_message = None
            for msg in messages:
                if msg.text or msg.caption:
                    text_message = msg
                    break

            # 创建任务组ID用于跟踪完成状态
            task_group_id = f"mediagroup_{messages[0].message_id}"

            # 设置通知跟踪
            if text_message:
                self.pending_notifications[task_group_id] = {
                    'message': text_message,
                    'total_channels': len(target_channels),
                    'completed_channels': 0,
                    'message_type': 'media_group'
                }

            # 为每个频道创建任务并添加到对应的队列
            for channel in target_channels:
                task = {
                    'type': 'media_group',
                    'messages': messages,
                    'channel': channel,
                    'context': context,
                    'task_group_id': task_group_id
                }
                self._add_task_to_channel_queue(channel, task)

            logger.info(f"媒体组任务已添加到 {len(target_channels)} 个频道队列")

        except Exception as e:
            logger.error(f"处理媒体组消息失败: {e}")
            self.error_count += 1

    async def _send_media_group_to_channel(self, messages, channel: str, context: ContextTypes.DEFAULT_TYPE) -> None:
        """发送媒体组到指定频道"""
        try:
            from telegram import InputMediaPhoto, InputMediaVideo, InputMediaDocument

            logger.info(f"准备发送媒体组到频道: {channel}")

            # 解析频道ID
            if channel.startswith('@'):
                chat_id = channel
            else:
                chat_id = int(channel)

            media_list = []

            # 找到包含文本的消息
            text_message = None
            for msg in messages:
                if msg.text or msg.caption:
                    text_message = msg
                    break

            # 处理文本中的链接
            if text_message:
                processed_text, processed_entities = self._process_message_links(text_message, chat_id)
            else:
                processed_text = ""
                processed_entities = []

            # 构建媒体列表
            for i, message in enumerate(messages):
                logger.info(f"处理媒体组中的第 {i+1} 个消息")

                if message.photo:
                    # 获取最大尺寸的照片
                    photo = message.photo[-1]
                    if i == 0:
                        # 第一个媒体包含处理后的caption
                        media = InputMediaPhoto(
                            media=photo.file_id,
                            caption=processed_text,
                            caption_entities=processed_entities
                        )
                    else:
                        media = InputMediaPhoto(media=photo.file_id)
                    media_list.append(media)

                elif message.video:
                    if i == 0:
                        media = InputMediaVideo(
                            media=message.video.file_id,
                            caption=processed_text,
                            caption_entities=processed_entities
                        )
                    else:
                        media = InputMediaVideo(media=message.video.file_id)
                    media_list.append(media)

                elif message.document:
                    if i == 0:
                        media = InputMediaDocument(
                            media=message.document.file_id,
                            caption=processed_text,
                            caption_entities=processed_entities
                        )
                    else:
                        media = InputMediaDocument(media=message.document.file_id)
                    media_list.append(media)

            if media_list:
                logger.info(f"准备发送包含 {len(media_list)} 个媒体的媒体组")

                # 构建发送参数
                send_params = {
                    'chat_id': chat_id,
                    'media': media_list
                }

                # 添加定时发送参数
                if self.scheduled_time:
                    send_params['schedule_date'] = int(self.scheduled_time.timestamp())
                    logger.info(f"设置定时发送: {self.scheduled_time}")

                await self._send_with_retry(context.bot.send_media_group, **send_params)
                logger.info(f"✅ 媒体组发送成功到 {chat_id}")
            else:
                logger.warning("没有找到可发送的媒体")

        except Exception as e:
            logger.error(f"发送媒体组到频道 {channel} 失败: {e}")
            raise
    
    async def _process_single_message(self, message: Message, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理单条消息 - 添加到频道队列"""
        try:
            logger.info(f"开始处理消息 {message.message_id}")

            # 获取目标频道列表
            target_channels = config.get_channels()
            if not target_channels:
                logger.warning("没有配置目标频道")
                return

            logger.info(f"目标频道列表: {target_channels}")

            # 创建任务组ID用于跟踪完成状态
            task_group_id = f"msg_{message.message_id}"

            # 设置通知跟踪
            self.pending_notifications[task_group_id] = {
                'message': message,
                'total_channels': len(target_channels),
                'completed_channels': 0,
                'message_type': 'single'
            }

            # 为每个频道创建任务并添加到对应的队列
            for channel in target_channels:
                task = {
                    'type': 'single_message',
                    'message': message,
                    'channel': channel,
                    'context': context,
                    'task_group_id': task_group_id
                }
                self._add_task_to_channel_queue(channel, task)

            logger.info(f"单条消息任务已添加到 {len(target_channels)} 个频道队列")

        except Exception as e:
            logger.error(f"处理单条消息失败: {e}")
            self.error_count += 1

    def _add_task_to_channel_queue(self, channel: str, task):
        """添加任务到指定频道的队列"""
        if channel not in self.channel_queues:
            self.channel_queues[channel] = []

        self.channel_queues[channel].append(task)
        queue_length = len(self.channel_queues[channel])
        logger.info(f"任务已添加到频道 {channel} 队列，当前队列长度: {queue_length}")

    async def _send_media_group_to_channel_direct(self, messages, channel: str, context: ContextTypes.DEFAULT_TYPE) -> None:
        """直接发送媒体组到指定频道（队列工作器使用）"""
        try:
            from telegram import InputMediaPhoto, InputMediaVideo, InputMediaDocument

            logger.info(f"队列处理：发送媒体组到频道 {channel}")

            # 解析频道ID
            if channel.startswith('@'):
                chat_id = channel
            else:
                chat_id = int(channel)

            media_list = []

            # 找到包含文本的消息
            text_message = None
            for msg in messages:
                if msg.text or msg.caption:
                    text_message = msg
                    break

            # 处理文本中的链接
            if text_message:
                processed_text, processed_entities = self._process_message_links(text_message, chat_id)
            else:
                processed_text = ""
                processed_entities = []

            # 构建媒体列表
            for i, message in enumerate(messages):
                if message.photo:
                    photo = message.photo[-1]
                    if i == 0:
                        media = InputMediaPhoto(
                            media=photo.file_id,
                            caption=processed_text,
                            caption_entities=processed_entities
                        )
                    else:
                        media = InputMediaPhoto(media=photo.file_id)
                    media_list.append(media)

                elif message.video:
                    if i == 0:
                        media = InputMediaVideo(
                            media=message.video.file_id,
                            caption=processed_text,
                            caption_entities=processed_entities
                        )
                    else:
                        media = InputMediaVideo(media=message.video.file_id)
                    media_list.append(media)

                elif message.document:
                    if i == 0:
                        media = InputMediaDocument(
                            media=message.document.file_id,
                            caption=processed_text,
                            caption_entities=processed_entities
                        )
                    else:
                        media = InputMediaDocument(media=message.document.file_id)
                    media_list.append(media)

            if media_list:
                # 构建发送参数
                send_params = {
                    'chat_id': chat_id,
                    'media': media_list
                }

                # 添加定时发送参数
                if self.scheduled_time:
                    send_params['schedule_date'] = int(self.scheduled_time.timestamp())

                await self._send_with_retry(context.bot.send_media_group, **send_params)
                logger.info(f"✅ 队列处理：媒体组发送成功到 {chat_id}")
                self.processed_count += 1
            else:
                logger.warning("没有找到可发送的媒体")

        except Exception as e:
            logger.error(f"队列处理：发送媒体组到频道 {channel} 失败: {e}")
            self.error_count += 1
            raise

    async def _send_to_channel_direct(self, message: Message, channel: str, context: ContextTypes.DEFAULT_TYPE) -> None:
        """直接发送消息到指定频道（队列工作器使用）"""
        try:
            logger.info(f"队列处理：发送消息到频道 {channel}")

            # 解析频道ID
            if channel.startswith('@'):
                chat_id = channel
            else:
                chat_id = int(channel)

            # 处理不同类型的消息
            if message.text:
                await self._send_text_message_direct(message, chat_id, context)
            elif message.photo or message.video or message.document:
                await self._send_media_message_direct(message, chat_id, context)
            else:
                logger.info("不支持的消息类型")

            self.processed_count += 1

        except Exception as e:
            logger.error(f"队列处理：发送到频道 {channel} 失败: {e}")
            self.error_count += 1
            raise

    async def _send_text_message_direct(self, message: Message, chat_id, context: ContextTypes.DEFAULT_TYPE) -> None:
        """直接发送文本消息"""
        # 处理链接替换
        processed_text, processed_entities = self._process_message_links(message, chat_id)

        # 构建发送参数
        send_params = {
            'chat_id': chat_id,
            'text': processed_text,
            'entities': processed_entities,
            'disable_web_page_preview': False
        }

        # 添加定时发送参数
        if self.scheduled_time:
            send_params['schedule_date'] = int(self.scheduled_time.timestamp())

        await self._send_with_retry(context.bot.send_message, **send_params)
        logger.info(f"✅ 队列处理：文本消息发送成功到 {chat_id}")

    async def _send_media_message_direct(self, message: Message, chat_id, context: ContextTypes.DEFAULT_TYPE) -> None:
        """直接发送媒体消息"""
        # 处理caption中的链接
        processed_caption, processed_entities = self._process_message_links(message, chat_id)

        # 构建基础参数
        base_params = {
            'chat_id': chat_id,
            'caption': processed_caption,
            'caption_entities': processed_entities
        }

        # 添加定时发送参数
        if self.scheduled_time:
            base_params['schedule_date'] = int(self.scheduled_time.timestamp())

        # 根据媒体类型发送
        if message.photo:
            photo = message.photo[-1]  # 获取最大尺寸
            await self._send_with_retry(context.bot.send_photo, photo=photo.file_id, **base_params)
        elif message.video:
            await self._send_with_retry(context.bot.send_video, video=message.video.file_id, **base_params)
        elif message.document:
            await self._send_with_retry(context.bot.send_document, document=message.document.file_id, **base_params)

        logger.info(f"✅ 队列处理：媒体消息发送成功到 {chat_id}")
    
    async def _send_to_channel(self, message: Message, channel: str, context: ContextTypes.DEFAULT_TYPE) -> None:
        """发送消息到指定频道"""
        try:
            logger.info(f"准备发送消息到频道: {channel}")
            
            # 解析频道ID
            if channel.startswith('@'):
                chat_id = channel
            else:
                chat_id = int(channel)
            
            # 处理不同类型的消息
            if message.media_group_id:
                logger.info("处理媒体组消息")
                # 媒体组消息需要特殊处理
                # 这里简化处理，实际需要收集完整的媒体组
                await self._send_media_message(message, chat_id, context)
            elif message.text:
                logger.info("处理文本消息")
                await self._send_text_message(message, chat_id, context)
            elif message.photo or message.video or message.document:
                logger.info("处理媒体消息")
                await self._send_media_message(message, chat_id, context)
            else:
                logger.info("不支持的消息类型")
        
        except Exception as e:
            logger.error(f"发送到频道 {channel} 失败: {e}")
            raise
    
    async def _send_text_message(self, message: Message, chat_id, context: ContextTypes.DEFAULT_TYPE) -> None:
        """发送文本消息"""
        try:
            # 处理链接替换
            processed_text, processed_entities = self._process_message_links(message, chat_id)
            
            # 构建发送参数
            send_params = {
                'chat_id': chat_id,
                'text': processed_text,
                'entities': processed_entities,
                'disable_web_page_preview': False
            }
            
            # 添加定时发送参数
            if self.scheduled_time:
                send_params['schedule_date'] = int(self.scheduled_time.timestamp())
                logger.info(f"设置定时发送: {self.scheduled_time}")
            
            await self._send_with_retry(context.bot.send_message, **send_params)
            logger.info(f"✅ 文本消息发送成功到 {chat_id}")

        except Exception as e:
            logger.error(f"发送文本消息失败: {e}")
            raise
    
    async def _send_media_message(self, message: Message, chat_id, context: ContextTypes.DEFAULT_TYPE) -> None:
        """发送媒体消息"""
        try:
            # 处理caption中的链接
            processed_caption, processed_entities = self._process_message_links(message, chat_id)
            
            # 构建基础参数
            base_params = {
                'chat_id': chat_id,
                'caption': processed_caption,
                'caption_entities': processed_entities
            }
            
            # 添加定时发送参数
            if self.scheduled_time:
                base_params['schedule_date'] = int(self.scheduled_time.timestamp())
            
            # 根据媒体类型发送
            if message.photo:
                photo = message.photo[-1]  # 获取最大尺寸
                await self._send_with_retry(context.bot.send_photo, photo=photo.file_id, **base_params)
            elif message.video:
                await self._send_with_retry(context.bot.send_video, video=message.video.file_id, **base_params)
            elif message.document:
                await self._send_with_retry(context.bot.send_document, document=message.document.file_id, **base_params)

            logger.info(f"✅ 媒体消息发送成功到 {chat_id}")

        except Exception as e:
            logger.error(f"发送媒体消息失败: {e}")
            raise
    
    def _process_message_links(self, message: Message, target_chat_id) -> tuple:
        """处理消息中的链接，替换频道ID"""
        text = message.text or message.caption or ""
        original_entities = message.entities or message.caption_entities or []
        
        # 获取目标频道ID（处理-100前缀）
        if isinstance(target_chat_id, str) and target_chat_id.startswith('@'):
            # 用户名格式，无需处理
            return text, list(original_entities)
        
        target_id_str = str(target_chat_id)
        if target_id_str.startswith('-100'):
            new_channel_id = target_id_str[4:]
        else:
            new_channel_id = target_id_str
        
        # 处理实体中的链接
        pattern = r'https://t\.me/c/(\d+)/(\d+)'
        new_entities = []
        
        for entity in original_entities:
            if entity.type == "text_link" and entity.url:
                match = re.match(pattern, entity.url)
                if match:
                    message_id = match.group(2)
                    new_link = f"https://t.me/c/{new_channel_id}/{message_id}"
                    
                    new_entity = MessageEntity(
                        type=entity.type,
                        offset=entity.offset,
                        length=entity.length,
                        url=new_link
                    )
                    new_entities.append(new_entity)
                else:
                    new_entities.append(entity)
            else:
                new_entities.append(entity)
        
        return text, new_entities

    async def _send_with_retry(self, send_func, max_retries=10, base_delay=2, **kwargs):
        """带重试机制的发送方法 - 针对Telegram速率限制优化"""
        attempt = 0
        while attempt < max_retries:
            try:
                logger.info(f"发送尝试 {attempt + 1}/{max_retries}")
                result = await send_func(**kwargs)
                # 发送成功，重置重试计数并返回结果
                logger.info("✅ 发送成功")
                return result

            except TimedOut as e:
                attempt += 1
                logger.warning(f"发送超时 (尝试 {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    # 超时使用较长的延迟
                    delay = base_delay * (2 ** min(attempt - 1, 4))  # 最大32秒
                    logger.info(f"超时重试，等待 {delay} 秒...")
                    await asyncio.sleep(delay)
                else:
                    logger.error("所有重试都失败了")
                    raise

            except RetryAfter as e:
                logger.warning(f"触发速率限制，需要等待 {e.retry_after} 秒")
                # 速率限制必须等待指定时间，不计入重试次数
                await asyncio.sleep(e.retry_after + 1)  # 额外等待1秒确保安全
                logger.info("速率限制等待完成，继续重试...")
                # 不增加attempt计数，继续下一次尝试

            except NetworkError as e:
                attempt += 1
                logger.warning(f"网络错误 (尝试 {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    delay = base_delay * (1.5 ** (attempt - 1))  # 较温和的指数退避
                    logger.info(f"网络错误重试，等待 {delay:.1f} 秒...")
                    await asyncio.sleep(delay)
                else:
                    logger.error("所有重试都失败了")
                    raise

            except Exception as e:
                attempt += 1
                logger.error(f"发送失败，未知错误 (尝试 {attempt}/{max_retries}): {e}")
                # 对于未知错误，也尝试重试几次
                if attempt < max_retries:
                    delay = base_delay * 2
                    logger.info(f"未知错误重试，等待 {delay} 秒...")
                    await asyncio.sleep(delay)
                else:
                    logger.error("所有重试都失败了")
                    raise

    def get_status(self) -> dict:
        """获取转发模式状态"""
        return {
            'is_active': self.is_active,
            'is_batch_mode': self.is_batch_mode,
            'scheduled_time': self.scheduled_time.isoformat() if self.scheduled_time else None,
            'pending_messages_count': len(self.pending_messages),
            'processed_count': self.processed_count,
            'error_count': self.error_count
        }


# 全局转发模式实例
forward_mode = ForwardMode()
