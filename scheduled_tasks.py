"""
定时任务管理模块
实现本地定时发送功能
"""

import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class ScheduledTaskManager:
    """定时任务管理器"""
    
    def __init__(self, db_file: str = "scheduled_tasks.json"):
        self.db_file = Path(db_file)
        self.tasks = []  # 内存中的任务列表
        self.scheduler_task = None  # 调度器任务
        self.is_running = False
        self.load_tasks()
    
    def load_tasks(self):
        """从文件加载任务"""
        try:
            if self.db_file.exists():
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.tasks = data.get('tasks', [])
                    logger.info(f"已加载 {len(self.tasks)} 个定时任务")
            else:
                self.tasks = []
                logger.info("定时任务文件不存在，创建新的任务列表")
        except Exception as e:
            logger.error(f"加载定时任务失败: {e}")
            self.tasks = []
    
    def save_tasks(self):
        """保存任务到文件"""
        try:
            data = {
                'tasks': self.tasks,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"已保存 {len(self.tasks)} 个定时任务")
        except Exception as e:
            logger.error(f"保存定时任务失败: {e}")
    
    def add_task(self, scheduled_time: datetime, task_type: str, task_data: Dict[str, Any]) -> str:
        """添加定时任务"""
        task_id = f"task_{datetime.now().timestamp()}_{len(self.tasks)}"
        
        task = {
            'id': task_id,
            'scheduled_time': scheduled_time.isoformat(),
            'task_type': task_type,  # 'media_group', 'single_message', 'batch_messages'
            'task_data': task_data,
            'status': 'pending',  # 'pending', 'completed', 'failed'
            'created_at': datetime.now().isoformat(),
            'attempts': 0,
            'max_attempts': 3
        }
        
        self.tasks.append(task)
        self.save_tasks()
        logger.info(f"已添加定时任务: {task_id}, 执行时间: {scheduled_time}")
        return task_id
    
    def remove_task(self, task_id: str) -> bool:
        """移除定时任务"""
        for i, task in enumerate(self.tasks):
            if task['id'] == task_id:
                del self.tasks[i]
                self.save_tasks()
                logger.info(f"已移除定时任务: {task_id}")
                return True
        return False
    
    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """获取待执行的任务"""
        now = datetime.now()
        pending_tasks = []
        
        for task in self.tasks:
            if task['status'] == 'pending':
                scheduled_time = datetime.fromisoformat(task['scheduled_time'])
                if scheduled_time <= now:
                    pending_tasks.append(task)
        
        return pending_tasks
    
    def update_task_status(self, task_id: str, status: str, error_msg: str = None):
        """更新任务状态"""
        for task in self.tasks:
            if task['id'] == task_id:
                task['status'] = status
                task['attempts'] += 1
                task['last_attempt'] = datetime.now().isoformat()
                if error_msg:
                    task['error_message'] = error_msg
                self.save_tasks()
                logger.info(f"任务 {task_id} 状态更新为: {status}")
                break
    
    def cleanup_old_tasks(self, days: int = 7):
        """清理旧任务"""
        cutoff_date = datetime.now() - timedelta(days=days)
        original_count = len(self.tasks)
        
        self.tasks = [
            task for task in self.tasks
            if datetime.fromisoformat(task['created_at']) > cutoff_date
            or task['status'] == 'pending'
        ]
        
        cleaned_count = original_count - len(self.tasks)
        if cleaned_count > 0:
            self.save_tasks()
            logger.info(f"已清理 {cleaned_count} 个旧任务")
    
    def start_scheduler(self):
        """启动定时调度器"""
        if not self.is_running:
            self.is_running = True
            self.scheduler_task = asyncio.create_task(self._scheduler_loop())
            logger.info("定时任务调度器已启动")
    
    def stop_scheduler(self):
        """停止定时调度器"""
        self.is_running = False
        if self.scheduler_task and not self.scheduler_task.done():
            self.scheduler_task.cancel()
            logger.info("定时任务调度器已停止")
    
    async def _scheduler_loop(self):
        """调度器主循环"""
        logger.info("定时任务调度器开始运行")
        try:
            while self.is_running:
                try:
                    # 检查待执行的任务
                    pending_tasks = self.get_pending_tasks()
                    
                    for task in pending_tasks:
                        try:
                            await self._execute_task(task)
                        except Exception as e:
                            logger.error(f"执行定时任务失败: {e}")
                            self.update_task_status(task['id'], 'failed', str(e))
                    
                    # 每分钟检查一次
                    await asyncio.sleep(60)
                    
                    # 每小时清理一次旧任务
                    if datetime.now().minute == 0:
                        self.cleanup_old_tasks()
                        
                except Exception as e:
                    logger.error(f"调度器循环异常: {e}")
                    await asyncio.sleep(60)
                    
        except asyncio.CancelledError:
            logger.info("定时任务调度器被取消")
        except Exception as e:
            logger.error(f"调度器异常退出: {e}")
        finally:
            logger.info("定时任务调度器已停止")
    
    async def _execute_task(self, task: Dict[str, Any]):
        """执行定时任务"""
        task_id = task['id']
        task_type = task['task_type']
        task_data = task['task_data']
        
        logger.info(f"开始执行定时任务: {task_id}, 类型: {task_type}")
        
        try:
            if task_type == 'media_group':
                await self._execute_media_group_task(task_data)
            elif task_type == 'single_message':
                await self._execute_single_message_task(task_data)
            elif task_type == 'batch_messages':
                await self._execute_batch_messages_task(task_data)
            else:
                raise ValueError(f"未知的任务类型: {task_type}")
            
            self.update_task_status(task_id, 'completed')
            logger.info(f"定时任务执行成功: {task_id}")
            
        except Exception as e:
            logger.error(f"定时任务执行失败: {task_id}, 错误: {e}")
            
            # 检查是否需要重试
            if task['attempts'] < task['max_attempts']:
                logger.info(f"任务 {task_id} 将在5分钟后重试")
                # 延迟5分钟重试
                new_time = datetime.now() + timedelta(minutes=5)
                task['scheduled_time'] = new_time.isoformat()
                self.save_tasks()
            else:
                self.update_task_status(task_id, 'failed', str(e))
    
    async def _execute_media_group_task(self, task_data: Dict[str, Any]):
        """执行媒体组任务"""
        from telegram import Bot, InputMediaPhoto, InputMediaVideo, InputMediaDocument
        from config import config

        channels = task_data['channels']
        media_info = task_data['media_info']

        logger.info(f"执行定时媒体组发送，目标频道: {channels}")

        # 创建Bot实例
        bot = Bot(token=config.bot_token)

        # 构建媒体列表
        media_list = []
        text_content = ""

        for i, media_item in enumerate(media_info):
            if media_item['type'] == 'photo':
                if i == 0 and media_item['caption']:
                    media = InputMediaPhoto(
                        media=media_item['file_id'],
                        caption=media_item['caption']
                    )
                else:
                    media = InputMediaPhoto(media=media_item['file_id'])
                media_list.append(media)

            elif media_item['type'] == 'video':
                if i == 0 and media_item['caption']:
                    media = InputMediaVideo(
                        media=media_item['file_id'],
                        caption=media_item['caption']
                    )
                else:
                    media = InputMediaVideo(media=media_item['file_id'])
                media_list.append(media)

            elif media_item['type'] == 'document':
                if i == 0 and media_item['caption']:
                    media = InputMediaDocument(
                        media=media_item['file_id'],
                        caption=media_item['caption']
                    )
                else:
                    media = InputMediaDocument(media=media_item['file_id'])
                media_list.append(media)

            elif media_item['type'] == 'text':
                text_content = media_item['text']

        # 发送到每个频道
        for channel in channels:
            try:
                logger.info(f"定时发送媒体组到频道: {channel}")

                # 解析频道ID
                if channel.startswith('@'):
                    chat_id = channel
                else:
                    chat_id = int(channel)

                # 如果有媒体，发送媒体组
                if media_list:
                    await bot.send_media_group(chat_id=chat_id, media=media_list)
                    logger.info(f"✅ 定时媒体组发送成功到 {chat_id}")

                # 如果有纯文本，单独发送
                if text_content and not media_list:
                    await bot.send_message(chat_id=chat_id, text=text_content)
                    logger.info(f"✅ 定时文本消息发送成功到 {chat_id}")

                # 频道间延迟
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"定时发送到频道 {channel} 失败: {e}")
                raise
    
    async def _execute_single_message_task(self, task_data: Dict[str, Any]):
        """执行单条消息任务"""
        from telegram import Bot
        from config import config

        channels = task_data['channels']
        message_info = task_data['message_info']

        logger.info(f"执行定时单条消息发送，目标频道: {channels}")

        # 创建Bot实例
        bot = Bot(token=config.bot_token)

        # 发送到每个频道
        for channel in channels:
            try:
                logger.info(f"定时发送消息到频道: {channel}")

                # 解析频道ID
                if channel.startswith('@'):
                    chat_id = channel
                else:
                    chat_id = int(channel)

                # 根据消息类型发送
                if message_info['type'] == 'text':
                    await bot.send_message(
                        chat_id=chat_id,
                        text=message_info['text']
                    )
                elif message_info['type'] == 'photo':
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=message_info['file_id'],
                        caption=message_info['caption'] or None
                    )
                elif message_info['type'] == 'video':
                    await bot.send_video(
                        chat_id=chat_id,
                        video=message_info['file_id'],
                        caption=message_info['caption'] or None
                    )
                elif message_info['type'] == 'document':
                    await bot.send_document(
                        chat_id=chat_id,
                        document=message_info['file_id'],
                        caption=message_info['caption'] or None
                    )

                logger.info(f"✅ 定时消息发送成功到 {chat_id}")

                # 频道间延迟
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"定时发送到频道 {channel} 失败: {e}")
                raise
    
    async def _execute_batch_messages_task(self, task_data: Dict[str, Any]):
        """执行批量消息任务"""
        from telegram import Bot, InputMediaPhoto, InputMediaVideo, InputMediaDocument, MessageEntity
        from config import config

        channels = task_data['channels']
        items_info = task_data['items_info']

        logger.info(f"执行定时批量消息发送，共 {len(items_info)} 项，目标频道: {channels}")

        # 创建Bot实例
        bot = Bot(token=config.bot_token)

        # 为每个频道发送所有项目
        for channel in channels:
            try:
                logger.info(f"定时发送批量消息到频道: {channel}")

                # 解析频道ID
                if channel.startswith('@'):
                    chat_id = channel
                else:
                    chat_id = int(channel)

                # 发送每个项目
                for item_info in items_info:
                    try:
                        if item_info['type'] == 'media_group':
                            # 发送媒体组 - 使用正确的媒体组发送方式
                            await self._send_media_group_properly(bot, chat_id, item_info)
                        elif item_info['type'] == 'single_message':
                            # 发送单条消息
                            await self._send_single_message_from_info(bot, chat_id, item_info)

                        # 项目间延迟
                        await asyncio.sleep(2)

                    except Exception as e:
                        logger.error(f"定时发送项目失败: {e}")
                        # 继续发送其他项目

                logger.info(f"✅ 定时批量消息发送成功到 {chat_id}")

                # 频道间延迟
                await asyncio.sleep(3)

            except Exception as e:
                logger.error(f"定时发送批量消息到频道 {channel} 失败: {e}")
                raise

    async def _send_media_group_properly(self, bot, chat_id, media_group_info):
        """正确发送媒体组 - 参考forward_mode的逻辑"""
        from telegram import InputMediaPhoto, InputMediaVideo, InputMediaDocument, MessageEntity

        messages_data = media_group_info['messages_data']
        media_list = []

        logger.info(f"准备发送媒体组到 {chat_id}，共 {len(messages_data)} 个媒体")

        # 找到包含文本的消息
        text_message_data = None
        for msg_data in messages_data:
            if msg_data['text'] or msg_data['caption']:
                text_message_data = msg_data
                break

        # 处理文本和链接
        processed_text = ""
        processed_entities = []
        if text_message_data:
            processed_text = text_message_data['text'] or text_message_data['caption']

            # 重建entities
            for entity_info in text_message_data.get('entities', []):
                entity = MessageEntity(
                    type=entity_info['type'],
                    offset=entity_info['offset'],
                    length=entity_info['length'],
                    url=entity_info.get('url')
                )
                processed_entities.append(entity)

        # 构建媒体列表 - 完全参考forward_mode的逻辑
        for i, msg_data in enumerate(messages_data):
            if msg_data['media_type'] == 'photo':
                if i == 0:
                    # 第一个媒体包含处理后的caption
                    media = InputMediaPhoto(
                        media=msg_data['file_id'],
                        caption=processed_text,
                        caption_entities=processed_entities
                    )
                else:
                    media = InputMediaPhoto(media=msg_data['file_id'])
                media_list.append(media)

            elif msg_data['media_type'] == 'video':
                if i == 0:
                    media = InputMediaVideo(
                        media=msg_data['file_id'],
                        caption=processed_text,
                        caption_entities=processed_entities
                    )
                else:
                    media = InputMediaVideo(media=msg_data['file_id'])
                media_list.append(media)

            elif msg_data['media_type'] == 'document':
                if i == 0:
                    media = InputMediaDocument(
                        media=msg_data['file_id'],
                        caption=processed_text,
                        caption_entities=processed_entities
                    )
                else:
                    media = InputMediaDocument(media=msg_data['file_id'])
                media_list.append(media)

        if media_list:
            logger.info(f"发送包含 {len(media_list)} 个媒体的媒体组")
            await bot.send_media_group(chat_id=chat_id, media=media_list)
            logger.info(f"✅ 定时媒体组发送成功到 {chat_id}")
        else:
            logger.warning("没有找到可发送的媒体")

    async def _send_media_group_from_info(self, bot, chat_id, media_group_info):
        """从信息重建并发送媒体组"""
        from telegram import InputMediaPhoto, InputMediaVideo, InputMediaDocument, MessageEntity

        messages_info = media_group_info['messages']
        media_list = []

        # 找到包含文本的消息
        text_message_info = None
        for msg_info in messages_info:
            if msg_info['text'] or msg_info['caption']:
                text_message_info = msg_info
                break

        # 处理文本和链接
        processed_text = ""
        processed_entities = []
        if text_message_info:
            processed_text = text_message_info['text'] or text_message_info['caption']
            # 重建entities
            for entity_info in text_message_info.get('entities', []):
                entity = MessageEntity(
                    type=entity_info['type'],
                    offset=entity_info['offset'],
                    length=entity_info['length'],
                    url=entity_info.get('url')
                )
                processed_entities.append(entity)

        # 构建媒体列表
        for i, msg_info in enumerate(messages_info):
            if msg_info['type'] == 'photo':
                if i == 0:
                    media = InputMediaPhoto(
                        media=msg_info['file_id'],
                        caption=processed_text,
                        caption_entities=processed_entities
                    )
                else:
                    media = InputMediaPhoto(media=msg_info['file_id'])
                media_list.append(media)

            elif msg_info['type'] == 'video':
                if i == 0:
                    media = InputMediaVideo(
                        media=msg_info['file_id'],
                        caption=processed_text,
                        caption_entities=processed_entities
                    )
                else:
                    media = InputMediaVideo(media=msg_info['file_id'])
                media_list.append(media)

            elif msg_info['type'] == 'document':
                if i == 0:
                    media = InputMediaDocument(
                        media=msg_info['file_id'],
                        caption=processed_text,
                        caption_entities=processed_entities
                    )
                else:
                    media = InputMediaDocument(media=msg_info['file_id'])
                media_list.append(media)

        if media_list:
            await bot.send_media_group(chat_id=chat_id, media=media_list)
            logger.info(f"✅ 定时媒体组发送成功到 {chat_id}")

    async def _send_single_message_from_info(self, bot, chat_id, message_info):
        """从信息重建并发送单条消息"""
        from telegram import MessageEntity

        # 重建entities
        entities = []
        for entity_info in message_info.get('entities', []):
            entity = MessageEntity(
                type=entity_info['type'],
                offset=entity_info['offset'],
                length=entity_info['length'],
                url=entity_info.get('url')
            )
            entities.append(entity)

        # 根据消息类型发送
        if message_info['media_type'] == 'text':
            await bot.send_message(
                chat_id=chat_id,
                text=message_info['text'],
                entities=entities
            )
        elif message_info['media_type'] == 'photo':
            await bot.send_photo(
                chat_id=chat_id,
                photo=message_info['file_id'],
                caption=message_info['caption'] or None,
                caption_entities=entities if message_info['caption'] else None
            )
        elif message_info['media_type'] == 'video':
            await bot.send_video(
                chat_id=chat_id,
                video=message_info['file_id'],
                caption=message_info['caption'] or None,
                caption_entities=entities if message_info['caption'] else None
            )
        elif message_info['media_type'] == 'document':
            await bot.send_document(
                chat_id=chat_id,
                document=message_info['file_id'],
                caption=message_info['caption'] or None,
                caption_entities=entities if message_info['caption'] else None
            )

        logger.info(f"✅ 定时单条消息发送成功到 {chat_id}")
    
    def get_task_stats(self) -> Dict[str, int]:
        """获取任务统计信息"""
        stats = {
            'total': len(self.tasks),
            'pending': 0,
            'completed': 0,
            'failed': 0
        }
        
        for task in self.tasks:
            stats[task['status']] += 1
        
        return stats


# 全局定时任务管理器实例
scheduled_task_manager = ScheduledTaskManager()
