from fastapi import APIRouter, Depends, HTTPException, Query, status, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Dict, Any, Optional
import datetime
from ...db.database import get_db
from ...core.security import get_current_user, get_current_active_user
from ...db.models.user import User
from ...db.models.chat import ChatSession, ChatMessage, ChatMessageUsage
from ...services.gemini_service import GeminiService
from ...schemas.chat import (
    ChatSessionCreate, ChatSessionResponse, ChatMessageCreate, 
    ChatMessageResponse, ChatRequest, ChatHistoryResponse,
    ChatSessionWithMessages, PaginatedChatSessions
)
from ...core.config import settings
import logging

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter()

# 初始化Gemini服务
gemini_service = GeminiService()

# 获取每个会话的最大消息数量
MAX_MESSAGES_PER_SESSION = settings.GEMINI_MAX_MESSAGES_PER_SESSION

# 每日消息限制
DAILY_MESSAGE_LIMITS = settings.DAILY_MESSAGE_LIMITS

# 获取中国时间
def get_china_time():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

# 检查并更新用户消息使用量
def check_and_update_message_usage(db: Session, user_id: int) -> bool:
    """
    检查用户当天的消息使用量是否超过限制，并更新计数
    
    Args:
        db: 数据库会话
        user_id: 用户ID
    
    Returns:
        bool: 如果未超过限制返回True，否则返回False
    """
    # 获取当前北京时间
    now = get_china_time()
    today = now.date()
    
    # 获取或创建用户的消息使用统计记录
    usage = db.query(ChatMessageUsage).filter(ChatMessageUsage.user_id == user_id).first()
    
    # 如果没有记录，创建一条新记录
    if not usage:
        usage = ChatMessageUsage(user_id=user_id, message_count=0, last_reset_at=now)
        db.add(usage)
        db.commit()
        db.refresh(usage)
    
    # 检查上次重置时间是否是今天，如果不是则重置计数
    last_reset_date = usage.last_reset_at.date()
    if last_reset_date != today:
        usage.message_count = 0
        usage.last_reset_at = now
        db.commit()
    
    # 获取用户对象以确定用户等级
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    
    # 获取用户等级对应的每日消息限制
    user_tag = user.user_tag.value
    daily_limit = DAILY_MESSAGE_LIMITS.get(user_tag, DAILY_MESSAGE_LIMITS["regular"])
    
    # 检查是否是管理员且无限制
    if user_tag == "admin" and daily_limit == -1:
        return True
    
    # 检查消息数量是否超过每日限制
    if usage.message_count >= daily_limit:
        return False
    
    # 更新消息计数
    usage.message_count += 1
    db.commit()
    
    return True


# 获取用户今日剩余的消息发送次数，为/remaining_messages接口使用
def get_remaining_daily_messages(db: Session, user: User) -> int:
    """
    获取用户今日剩余的消息发送次数
    
    Args:
        db: 数据库会话
        user: 当前用户
        
    Returns:
        int: 剩余消息次数，-1表示无限制
    """
    # 管理员无限制
    if user.user_tag.value == "admin" and DAILY_MESSAGE_LIMITS["admin"] == -1:
        return -1
    
    # 获取用户对应等级的每日限制
    user_limit = DAILY_MESSAGE_LIMITS.get(user.user_tag.value, DAILY_MESSAGE_LIMITS["regular"])
    
    # 获取当前北京时间
    now = get_china_time()
    today = now.date()
    
    # 查询用户的使用记录
    usage = db.query(ChatMessageUsage).filter(ChatMessageUsage.user_id == user.id).first()
    
    # 如果没有记录，剩余次数就是限制值
    if not usage:
        return user_limit
    
    # 检查上次重置时间是否是今天，如果不是则重置计数
    last_reset_date = usage.last_reset_at.date()
    if last_reset_date != today:
        # 如果不是今天的记录，直接返回限制值
        return user_limit
    
    # 计算剩余次数
    remaining = user_limit - usage.message_count
    return max(0, remaining)


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    session_data: ChatSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    创建新的聊天会话
    
    Args:
        session_data: 会话创建数据
        db: 数据库会话
        current_user: 当前认证用户
        
    Returns:
        ChatSessionResponse: 创建的会话信息
    """
    new_session = ChatSession(
        user_id=current_user.id,
        title=session_data.title
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    logger.info(f"用户 {current_user.username} 创建了新的聊天会话: {new_session.id}")
    return new_session


@router.get("/sessions", response_model=PaginatedChatSessions)
async def get_chat_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    """
    获取用户的聊天会话列表
    
    Args:
        db: 数据库会话
        current_user: 当前认证用户
        skip: 跳过的记录数
        limit: 返回的最大记录数
        
    Returns:
        PaginatedChatSessions: 分页的会话列表
    """
    # 获取总记录数
    total = db.query(func.count(ChatSession.id)).filter(
        ChatSession.user_id == current_user.id
    ).scalar()
    
    # 获取分页数据
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id
    ).order_by(ChatSession.updated_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "items": sessions,
        "total": total,
        "page": skip // limit + 1 if limit > 0 else 1,
        "per_page": limit
    }


@router.get("/sessions/{session_id}", response_model=ChatSessionWithMessages)
async def get_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    获取特定聊天会话及其消息
    
    Args:
        session_id: 会话ID
        db: 数据库会话
        current_user: 当前认证用户
        
    Returns:
        ChatSessionWithMessages: 会话信息及消息列表
        
    Raises:
        HTTPException: 会话不存在或无权访问时
    """
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天会话不存在或无权访问"
        )
    
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at).all()
    
    return {
        **session.__dict__,
        "messages": messages
    }


@router.get("/messages", response_model=List[ChatMessageResponse])
async def get_chat_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500)
):
    """
    获取特定会话的消息列表
    
    Args:
        session_id: 会话ID
        db: 数据库会话
        current_user: 当前认证用户
        skip: 跳过的记录数
        limit: 返回的最大记录数
        
    Returns:
        List[ChatMessageResponse]: 消息列表
        
    Raises:
        HTTPException: 会话不存在或无权访问时
    """
    # 验证会话所有权
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天会话不存在或无权访问"
        )
    
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at).offset(skip).limit(limit).all()
    
    return messages


@router.get("/remaining_messages", response_model=Dict[str, Any])
async def get_remaining_messages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    获取用户今日剩余的消息发送次数
    
    Args:
        db: 数据库会话
        current_user: 当前认证用户
        
    Returns:
        Dict[str, Any]: 包含用户等级、每日限制和剩余次数的信息
    """
    # 获取用户等级的每日限制
    user_tag = current_user.user_tag.value
    user_limit = DAILY_MESSAGE_LIMITS.get(user_tag, DAILY_MESSAGE_LIMITS["regular"])
    
    # 获取剩余次数
    remaining = get_remaining_daily_messages(db, current_user)
    
    # 无限制的情况
    if remaining == -1 or user_limit == -1:
        unlimited = True
        remaining_percent = 100
    else:
        unlimited = False
        remaining_percent = (remaining / user_limit) * 100 if user_limit > 0 else 0
    
    return {
        "user_tag": user_tag,
        "daily_limit": "无限制" if unlimited else user_limit,
        "remaining": "无限制" if unlimited else remaining,
        "remaining_percent": remaining_percent,
        "unlimited": unlimited
    }


@router.post("/send", response_model=ChatMessageResponse)
async def send_message(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    发送消息并获取AI回复
    
    处理用户发送的消息，将其保存到数据库，然后将会话历史发送给Gemini模型，
    获取AI回复并保存到数据库中。支持消息数量限制，超过限制将删除最旧的消息。
    同时实现基于用户等级的每日消息使用次数限制。
    
    Args:
        request: 发送消息请求
        db: 数据库会话
        current_user: 当前认证用户
        
    Returns:
        ChatMessageResponse: AI的回复消息
        
    Raises:
        HTTPException: 会话不存在、无权访问、超过每日限制或API调用失败时
    """
    # 验证会话所有权
    session = db.query(ChatSession).filter(
        ChatSession.id == request.session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天会话不存在或无权访问"
        )
    
    # 检查用户当日消息使用是否超出限制
    if not check_and_update_message_usage(db, current_user.id):
        # 获取用户等级
        user_tag = current_user.user_tag.value
        # 获取对应等级的每日限制
        limit = DAILY_MESSAGE_LIMITS.get(user_tag, DAILY_MESSAGE_LIMITS["regular"])
        
        # 构建升级建议消息
        upgrade_msg = ""
        if user_tag == "regular":
            upgrade_msg = "请考虑升级到高级会员以获得更多每日使用次数。"
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"您今日发送消息数量已达上限（{limit}条）。{upgrade_msg}"
        )
    
    try:
        # 开始事务
        # 保存用户消息
        user_message = ChatMessage(
            session_id=request.session_id,
            role="user",
            content=request.message
        )
        db.add(user_message)
        db.flush()  # 刷新但不提交，以便获取ID
        
        # 获取会话中的消息数量
        message_count = db.query(func.count(ChatMessage.id)).filter(
            ChatMessage.session_id == request.session_id
        ).scalar()
        
        # 检查是否超过最大消息数量限制
        if message_count >= MAX_MESSAGES_PER_SESSION:
            # 计算需要删除的消息数量
            messages_to_remove = message_count - MAX_MESSAGES_PER_SESSION + 2  # +2 为即将添加的两条消息腾出空间
            
            # 获取最旧的消息
            oldest_messages = db.query(ChatMessage).filter(
                ChatMessage.session_id == request.session_id
            ).order_by(ChatMessage.created_at).limit(messages_to_remove).all()
            
            # 删除最旧的消息
            for msg in oldest_messages:
                db.delete(msg)
                
            logger.info(f"会话 {request.session_id} 消息数量超过限制，已删除 {len(oldest_messages)} 条最旧消息")
        
        # 获取会话历史（包括刚添加的用户消息）
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == request.session_id
        ).order_by(ChatMessage.created_at).all()
        
        # 格式化消息为Gemini API所需格式
        formatted_messages = await gemini_service.format_messages_for_gemini(messages)
        
        # 调用Gemini API获取回复
        response_text = await gemini_service.get_chat_response(formatted_messages)
        
        # 保存AI回复
        ai_message = ChatMessage(
            session_id=request.session_id,
            role="assistant",
            content=response_text
        )
        db.add(ai_message)
        
        # 更新会话时间
        session.updated_at = func.now()
        
        # 提交所有更改
        db.commit()
        db.refresh(ai_message)
        
        logger.info(f"成功处理用户 {current_user.username} 在会话 {session.id} 中的消息")
        
        return ai_message
        
    except Exception as e:
        # 回滚事务
        db.rollback()
        logger.error(f"处理聊天消息时出错: {str(e)}")
        logger.exception("详细错误信息:")  # 输出详细的堆栈跟踪
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发送消息失败: {str(e)}"
        )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    删除特定的聊天会话
    
    Args:
        session_id: 会话ID
        db: 数据库会话
        current_user: 当前认证用户
        
    Raises:
        HTTPException: 会话不存在或无权访问时
    """
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天会话不存在或无权访问"
        )
    
    db.delete(session)
    db.commit()
    
    logger.info(f"用户 {current_user.username} 删除了聊天会话 {session_id}")


@router.put("/sessions/{session_id}", response_model=ChatSessionResponse)
async def update_chat_session(
    session_id: int,
    session_data: ChatSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    更新聊天会话标题
    
    Args:
        session_id: 会话ID
        session_data: 更新数据
        db: 数据库会话
        current_user: 当前认证用户
        
    Returns:
        ChatSessionResponse: 更新后的会话信息
        
    Raises:
        HTTPException: 会话不存在或无权访问时
    """
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天会话不存在或无权访问"
        )
    
    session.title = session_data.title
    session.updated_at = func.now()
    db.commit()
    db.refresh(session)
    
    logger.info(f"用户 {current_user.username} 更新了聊天会话 {session_id} 的标题")
    return session 