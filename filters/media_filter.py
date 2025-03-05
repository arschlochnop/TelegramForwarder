import logging
import os
import asyncio
from utils.media import get_media_size
from utils.constants import TEMP_DIR
from filters.base_filter import BaseFilter
from utils.media import get_max_media_size
from enums.enums import PreviewMode
from models.models import MediaTypes
from models.models import get_session

logger = logging.getLogger(__name__)

class MediaFilter(BaseFilter):
    """
    媒体过滤器，处理消息中的媒体内容
    """
    
    async def _process(self, context):
        """
        处理媒体内容
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否继续处理
        """
        # 确保临时目录存在
        os.makedirs(TEMP_DIR, exist_ok=True)
        
        rule = context.rule
        event = context.event
        client = context.client
        
        
        # 如果是媒体组消息
        if event.message.grouped_id:
            await self._process_media_group(context)
        else:
            await self._process_single_media(context)
        
        return True
    
    async def _process_media_group(self, context):
        """处理媒体组消息"""
        event = context.event
        rule = context.rule
        client = context.client
        
        logger.info(f'处理媒体组消息 组ID: {event.message.grouped_id}')
        
        # 等待更长时间让所有媒体消息到达
        await asyncio.sleep(1)
        
        # 获取媒体类型设置
        media_types = None
        if rule.enable_media_type_filter:
            session = get_session()
            try:
                media_types = session.query(MediaTypes).filter_by(rule_id=rule.id).first()
            finally:
                session.close()
        
        # 收集媒体组的所有消息
        try:
            async for message in event.client.iter_messages(
                event.chat_id,
                limit=20,
                min_id=event.message.id - 10,
                max_id=event.message.id + 10
            ):
                if message.grouped_id == event.message.grouped_id:
                    # # 保存第一条消息的文本和按钮
                    # if not context.message_text:
                    #     context.message_text = message.text or ''
                    #     context.buttons = message.buttons if hasattr(message, 'buttons') else None
                    #     logger.info(f'获取到媒体组文本: {context.message_text}')
                    
                    # 检查媒体类型
                    if rule.enable_media_type_filter and media_types and message.media:
                        if await self._is_media_type_blocked(message.media, media_types):
                            logger.info(f'媒体类型被屏蔽，跳过消息 ID={message.id}')
                            continue
                    
                    # 检查媒体大小
                    if message.media:
                        file_size = await get_media_size(message.media)
                        logger.info(f'是否启用媒体大小过滤: {rule.enable_media_size_filter}')
                        if rule.enable_media_size_filter:
                            if rule.max_media_size and file_size > rule.max_media_size:
                                if rule.is_send_over_media_size_message:
                                    logger.info(f'是否发送媒体大小超限提醒: {rule.is_send_over_media_size_message}')
                                    context.should_forward = False
                                context.skipped_media.append((message, file_size))
                                continue
                    context.media_group_messages.append(message)
                    logger.info(f'找到媒体组消息: ID={message.id}, 类型={type(message.media).__name__ if message.media else "无媒体"}')
        except Exception as e:
            logger.error(f'收集媒体组消息时出错: {str(e)}')
            context.errors.append(f"收集媒体组消息错误: {str(e)}")
        
        logger.info(f'共找到 {len(context.media_group_messages)} 条媒体组消息，{len(context.skipped_media)} 条超限')
    
    async def _process_single_media(self, context):
        """处理单条媒体消息"""
        event = context.event
        rule = context.rule
        # logger.info(f'context属性: {context.rule.__dict__}')
        # 检查是否是纯链接预览消息
        is_pure_link_preview = (
            event.message.media and
            hasattr(event.message.media, 'webpage') and
            not any([
                getattr(event.message.media, 'photo', None),
                getattr(event.message.media, 'document', None),
                getattr(event.message.media, 'video', None),
                getattr(event.message.media, 'audio', None),
                getattr(event.message.media, 'voice', None)
            ])
        )
        
        # 检查是否有实际媒体
        has_media = (
            event.message.media and
            any([
                getattr(event.message.media, 'photo', None),
                getattr(event.message.media, 'document', None),
                getattr(event.message.media, 'video', None),
                getattr(event.message.media, 'audio', None),
                getattr(event.message.media, 'voice', None)
            ])
        )
        
        # 处理实际媒体
        if has_media:
            # 检查媒体类型是否被屏蔽
            if rule.enable_media_type_filter:
                session = get_session()
                try:
                    media_types = session.query(MediaTypes).filter_by(rule_id=rule.id).first()
                    if media_types and await self._is_media_type_blocked(event.message.media, media_types):
                        logger.info(f'媒体类型被屏蔽，跳过消息 ID={event.message.id}')
                        context.should_forward = False
                        return True
                finally:
                    session.close()
            
            # 检查媒体大小
            file_size = await get_media_size(event.message.media)
            file_size = round(file_size/1024/1024, 2)
            logger.info(f'event.message.document: {event.message.document}')
            
            logger.info(f'媒体文件大小: {file_size}MB')
            logger.info(f'规则最大媒体大小: {rule.max_media_size}MB')
            
            logger.info(f'是否启用媒体大小过滤: {rule.enable_media_size_filter}')
            if rule.max_media_size and (file_size > rule.max_media_size) and rule.enable_media_size_filter:
                file_name =''
                if event.message.document:
                    file_name = event.message.document.attributes[0].file_name
                logger.info(f'媒体文件超过大小限制 ({rule.max_media_size}MB)')
                if rule.is_send_over_media_size_message:
                    logger.info(f'是否发送媒体大小超限提醒: {rule.is_send_over_media_size_message}')
                    context.should_forward = False
                context.skipped_media.append((event.message, file_size, file_name))
            else:
                try:
                    # 下载媒体文件
                    file_path = await event.message.download_media(TEMP_DIR)
                    if file_path:
                        context.media_files.append(file_path)
                        logger.info(f'媒体文件已下载到: {file_path}')
                except Exception as e:
                    logger.error(f'下载媒体文件时出错: {str(e)}')
                    context.errors.append(f"下载媒体文件错误: {str(e)}")
        elif is_pure_link_preview:
            # 记录这是纯链接预览消息
            context.is_pure_link_preview = True
            logger.info('这是一条纯链接预览消息')
            
    async def _is_media_type_blocked(self, media, media_types):
        """
        检查媒体类型是否被屏蔽
        
        Args:
            media: 媒体对象
            media_types: MediaTypes对象
            
        Returns:
            bool: 如果媒体类型被屏蔽返回True，否则返回False
        """
        # 检查各种媒体类型
        if getattr(media, 'photo', None) and media_types.photo:
            logger.info('媒体类型为图片，已被屏蔽')
            return True
        
        if getattr(media, 'document', None) and media_types.document:
            logger.info('媒体类型为文档，已被屏蔽')
            return True
        
        if getattr(media, 'video', None) and media_types.video:
            logger.info('媒体类型为视频，已被屏蔽')
            return True
        
        if getattr(media, 'audio', None) and media_types.audio:
            logger.info('媒体类型为音频，已被屏蔽')
            return True
        
        if getattr(media, 'voice', None) and media_types.voice:
            logger.info('媒体类型为语音，已被屏蔽')
            return True
        
        return False 