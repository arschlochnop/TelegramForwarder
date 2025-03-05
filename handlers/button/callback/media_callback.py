import traceback

from handlers.button.button_helpers import create_media_size_buttons,create_media_settings_buttons,create_media_types_buttons
from models.models import ForwardRule, MediaTypes
import logging
from utils.common import get_media_settings_text, get_db_ops
from models.models import get_session

logger = logging.getLogger(__name__)



async def callback_media_settings(event, rule_id, session, message, data):
    # 显示媒体设置页面
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            await event.edit(await get_media_settings_text(), buttons=await create_media_settings_buttons(rule))
    finally:
        session.close()
    return



async def callback_toggle_enable_media_size_filter(event, rule_id, session, message, data):
        rule_id = data.split(':')[1]
        try:
            rule = session.query(ForwardRule).get(int(rule_id))
            if rule:
                rule.enable_media_size_filter = not rule.enable_media_size_filter
                session.commit()
                await event.edit("媒体设置：", buttons=await create_media_settings_buttons(rule))
        finally:
            session.close()
        return


async def callback_set_max_media_size(event, rule_id, session, message, data):
        await event.edit("请选择最大媒体大小(MB)：", buttons=await create_media_size_buttons(rule_id, page=0))
        return



async def callback_select_max_media_size(event, rule_id, session, message, data):
        parts = data.split(':', 2)  # 最多分割2次
        if len(parts) == 3:
            _, rule_id, size = parts
            logger.info(f"设置规则 {rule_id} 的最大媒体大小为: {size}")
            try:
                rule = session.query(ForwardRule).get(int(rule_id))
                if rule:
                    # 记录旧大小
                    old_size = rule.max_media_size

                    # 更新最大媒体大小
                    rule.max_media_size = int(size)
                    session.commit()
                    logger.info(f"数据库更新成功: {old_size} -> {size}")

                    # 获取消息对象
                    message = await event.get_message()

                    await event.edit("媒体设置：",buttons=await create_media_settings_buttons(rule))
                    await event.answer(f"已设置最大媒体大小为: {size}MB")
                    logger.info("界面更新完成")
            except Exception as e:
                logger.error(f"设置最大媒体大小时出错: {str(e)}")
                logger.error(f"错误详情: {traceback.format_exc()}")
            finally:
                session.close()
        return


async def callback_toggle_send_over_media_size_message(event, rule_id, session, message, data):
    rule_id = data.split(':')[1]
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            rule.is_send_over_media_size_message = not rule.is_send_over_media_size_message
            session.commit()
            await event.edit("媒体设置：", buttons=await create_media_settings_buttons(rule))
    finally:
        session.close()
    return


async def callback_toggle_enable_media_type_filter(event, rule_id, session, message, data):
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            rule.enable_media_type_filter = not rule.enable_media_type_filter
            session.commit()
            await event.edit("媒体设置：", buttons=await create_media_settings_buttons(rule))
    finally:
        session.close()
    return

async def callback_set_media_types(event, rule_id, session, message, data):
    """处理查看并设置媒体类型的回调"""
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if not rule:
            await event.answer("规则不存在")
            return
            
        # 获取或创建媒体类型设置
        db_ops = await get_db_ops()
        success, msg, media_types = await db_ops.get_media_types(session, rule.id)
        
        if not success:
            await event.answer(f"获取媒体类型设置失败: {msg}")
            return
            
        # 显示媒体类型选择界面
        await event.edit("请选择要屏蔽的媒体类型", buttons=await create_media_types_buttons(rule.id, media_types))
        
    except Exception as e:
        logger.error(f"设置媒体类型时出错: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        await event.answer(f"设置媒体类型时出错: {str(e)}")
    finally:
        session.close()
    return
    
async def callback_toggle_media_type(event, rule_id, session, message, data):
    """处理切换媒体类型的回调"""
    try:
        # 正确解析数据获取rule_id和媒体类型
        parts = data.split(':')
        if len(parts) < 3:
            await event.answer("数据格式错误")
            return
            
        # toggle_media_type:31:voice
        action = parts[0]  
        rule_id = parts[1]  
        media_type = parts[2]  
        # 检查媒体类型是否有效
        if media_type not in ['photo', 'document', 'video', 'audio', 'voice']:
            await event.answer(f"无效的媒体类型: {media_type}")
            return
            
        # 获取规则
        rule = session.query(ForwardRule).get(int(rule_id))
        if not rule:
            await event.answer("规则不存在")
            return
            
        # 切换媒体类型状态
        db_ops = await get_db_ops()
        success, msg = await db_ops.toggle_media_type(session, rule.id, media_type)
        
        if not success:
            await event.answer(f"切换媒体类型失败: {msg}")
            return
            
        # 重新获取媒体类型设置
        success, _, media_types = await db_ops.get_media_types(session, rule.id)
        
        if not success:
            await event.answer("获取媒体类型设置失败")
            return
            
        # 更新界面
        await event.edit("请选择要屏蔽的媒体类型", buttons=await create_media_types_buttons(rule.id, media_types))
        await event.answer(msg)
        
    except Exception as e:
        logger.error(f"切换媒体类型时出错: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        await event.answer(f"切换媒体类型时出错: {str(e)}")
    finally:
        session.close()
    return

