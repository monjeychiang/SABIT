import google.generativeai as genai
from typing import List, Dict, Any, Optional
import logging
import os
from tenacity import retry, stop_after_attempt, wait_exponential
from ..core.config import settings

# 配置日志
logger = logging.getLogger(__name__)

class GeminiService:
    """
    Gemini AI聊天服务
    
    提供与Google Gemini大语言模型交互的功能，包括发送消息、获取回复等。
    使用tenacity库实现自动重试机制，提高API调用的稳定性。
    """
    
    def __init__(self):
        """
        初始化Gemini服务
        
        从环境变量中获取API密钥，配置Google Generative AI客户端，
        并选择默认使用的模型（gemini-1.5-pro）。
        """
        # 从环境变量获取API密钥
        self.api_key = settings.GEMINI_API_KEY
        if not self.api_key:
            logger.warning("未设置GEMINI_API_KEY环境变量，Gemini服务将无法正常工作")
            
        # 配置API客户端
        genai.configure(api_key=self.api_key)
        
        # 选择默认模型
        self.model_name = "gemini-1.5-pro"
        self.model = genai.GenerativeModel(self.model_name)
        
        # 默认的系统提示（角色设置）
        self.system_prompt = settings.GEMINI_SYSTEM_PROMPT
        
        # 响应长度限制
        self.max_response_tokens = settings.GEMINI_MAX_RESPONSE_TOKENS
        self.max_response_chars = settings.GEMINI_MAX_RESPONSE_CHARS
        
        logger.info(f"Gemini服务初始化完成，使用模型: {self.model_name}")
    
    def set_system_prompt(self, role_prompt: str) -> None:
        """
        设置系统提示（角色扮演）
        
        Args:
            role_prompt: 角色提示内容，例如"你是一位经验丰富的数学老师，擅长用简单易懂的方式讲解复杂概念。"
        """
        self.system_prompt = role_prompt
        logger.info(f"已设置系统提示: {role_prompt[:50]}...")
    
    @retry(
        stop=stop_after_attempt(3),  # 最多重试3次
        wait=wait_exponential(multiplier=1, min=2, max=10),  # 指数退避重试
        reraise=True  # 重试失败后抛出原始异常
    )
    async def get_completion(self, prompt: str) -> str:
        """
        获取单条提示的完成结果
        
        Args:
            prompt: 用户提问或指令
            
        Returns:
            str: AI生成的回复内容
            
        Raises:
            Exception: API调用失败时抛出异常
        """
        try:
            # 添加系统提示
            full_prompt = f"{self.system_prompt}\n\n用户问题: {prompt}"
            
            # 配置生成参数，限制回复长度
            generation_config = {
                "max_output_tokens": self.max_response_tokens,
                "temperature": 0.7
            }
            
            response = self.model.generate_content(
                full_prompt,
                generation_config=generation_config
            )
            
            # 进一步限制返回字符数
            response_text = response.text
            if len(response_text) > self.max_response_chars:
                response_text = response_text[:self.max_response_chars] + "...(回复已截断)"
                logger.info(f"回复长度超过限制，已截断至{self.max_response_chars}个字符")
                
            return response_text
        except Exception as e:
            logger.error(f"Gemini API调用失败: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def get_chat_response(self, messages: List[Dict[str, Any]]) -> str:
        """
        发送聊天历史记录并获取响应
        
        处理多轮对话，将之前的对话历史和新消息一起发送给模型，
        以保持对话的连贯性和上下文理解。
        
        Args:
            messages: 聊天历史记录，格式为[{"role": "user"/"assistant", "content": "消息内容"}, ...]
            
        Returns:
            str: AI生成的回复内容
            
        Raises:
            Exception: API调用失败时抛出异常
        """
        try:
            # 创建聊天会话
            chat = self.model.start_chat(history=[])
            
            # 配置生成参数，限制回复长度
            generation_config = {
                "max_output_tokens": self.max_response_tokens,
                "temperature": 0.7
            }
            
            # 首先发送系统提示作为上下文设置
            if self.system_prompt:
                # Gemini API不直接支持系统提示，但我们可以将其作为第一条消息
                system_message = f"[系统指令]：{self.system_prompt}[/系统指令]\n\n请在接下来的对话中遵循上述指令。"
                chat.send_message(system_message)
            
            # 加载聊天历史
            for msg in messages[:-1]:  # 不包括最后一条消息
                if msg["role"] == "user":
                    chat.send_message(msg["content"])
                # 如果是助手的消息，我们需要模拟接收
                # 由于Gemini API不直接支持设置助手消息，我们只能记录历史用于上下文
            
            # 发送最后一条消息并获取回复
            last_message = messages[-1]
            response = chat.send_message(
                last_message["content"],
                generation_config=generation_config
            )
            
            # 进一步限制返回字符数
            response_text = response.text
            if len(response_text) > self.max_response_chars:
                response_text = response_text[:self.max_response_chars] + "...(回复已截断)"
                logger.info(f"回复长度超过限制，已截断至{self.max_response_chars}个字符")
                
            return response_text
        except Exception as e:
            logger.error(f"Gemini聊天API调用失败: {str(e)}")
            raise
    
    async def format_messages_for_gemini(self, db_messages: List[Any]) -> List[Dict[str, Any]]:
        """
        将数据库消息记录转换为Gemini API所需的格式
        
        Args:
            db_messages: 数据库中的消息记录列表
            
        Returns:
            List[Dict[str, Any]]: 符合Gemini API格式的消息列表
        """
        formatted_messages = []
        for msg in db_messages:
            formatted_messages.append({
                "role": msg.role,
                "content": msg.content
            })
        return formatted_messages 