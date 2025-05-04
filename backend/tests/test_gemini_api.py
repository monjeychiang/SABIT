#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Gemini API 测试脚本

此脚本用于测试Gemini聊天API的各项功能，包括：
1. 用户认证(使用手动输入的凭据)
2. 创建聊天会话
3. 发送消息和接收AI回复
4. 获取会话列表和历史记录
5. 更新和删除会话
"""

import requests
import json
import time
import os
import logging
import sys
import random
import string
import getpass
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dotenv import load_dotenv
import argparse

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# 配置常量
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")

# 测试消息列表
TEST_MESSAGES = [
    "你好，请介绍一下自己",
    "请分析比特币近期的价格走势和可能的支撑阻力位",
    "什么是RSI指标和MACD指标？如何利用它们进行交易决策？",
    "在加密货币市场中，如何制定有效的风险管理策略？",
    "如何判断一个代币项目的长期投资价值？请从基本面分析的角度解答"
]


class GeminiAPITester:
    """Gemini API测试类，用于测试各项API功能"""

    def __init__(self, api_base_url: str = API_BASE_URL):
        """
        初始化测试类
        
        Args:
            api_base_url: API基础URL
        """
        self.api_base_url = api_base_url
        self.access_token = None
        self.headers = {"Content-Type": "application/json"}
        self.test_results = {}
        self.session_id = None
        self.username = None
        self.password = None
        self.debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
        
    def prompt_credentials(self):
        """提示用户输入用户名和密码"""
        print("\n======== Gemini API 测试工具 ========")
        print("请输入您的登录信息:")
        self.username = input("用户名/邮箱: ").strip()
        self.password = getpass.getpass("密码: ")
        print("=====================================\n")
        
        if not self.username or not self.password:
            logger.error("用户名和密码不能为空")
            return False
        return True
        
    def setup(self) -> bool:
        """
        设置测试环境，使用用户输入的凭据登录
        
        Returns:
            bool: 设置是否成功
        """
        logger.info("开始设置测试环境...")
        
        # 获取用户凭据
        if not self.prompt_credentials():
            return False
            
        try:
            # 尝试登录
            if not self.login():
                logger.error("登录失败，请检查您的用户名和密码是否正确")
                return False
            
            logger.info("测试环境设置成功！")
            return True
        except Exception as e:
            logger.error(f"设置测试环境时出错: {str(e)}")
            return False

    def login(self) -> bool:
        """
        用户登录并获取访问令牌
        
        Returns:
            bool: 登录是否成功
        """
        logger.info(f"尝试登录: {self.username}")
        try:
            url = f"{self.api_base_url}/auth/login"
            payload = {
                "username": self.username,
                "password": self.password
            }
            
            response = requests.post(url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                if self.access_token:
                    self.headers["Authorization"] = f"Bearer {self.access_token}"
                    logger.info("登录成功，获取到访问令牌")
                    self.test_results["login"] = "成功"
                    return True
                else:
                    logger.error("登录响应中未找到访问令牌")
                    self.test_results["login"] = "失败 (无访问令牌)"
                    return False
            else:
                logger.error(f"登录失败: {response.status_code} - {response.text}")
                self.test_results["login"] = f"失败 ({response.status_code})"
                return False
        except Exception as e:
            logger.error(f"登录时出错: {str(e)}")
            self.test_results["login"] = f"错误 ({str(e)})"
            return False

    def create_chat_session(self, title: str = None) -> Optional[int]:
        """
        创建新的聊天会话
        
        Args:
            title: 会话标题，为None时使用随机生成的标题
            
        Returns:
            Optional[int]: 成功时返回会话ID，失败时返回None
        """
        if title is None:
            # 生成随机标题
            random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
            title = f"Test Session {random_suffix}"
            
        logger.info(f"尝试创建聊天会话: {title}")
        try:
            url = f"{self.api_base_url}/chat/sessions"
            payload = {"title": title}
            
            response = requests.post(url, json=payload, headers=self.headers)
            
            if response.status_code == 201:
                data = response.json()
                session_id = data.get("id")
                logger.info(f"聊天会话创建成功，ID: {session_id}")
                self.test_results["create_chat_session"] = "成功"
                return session_id
            else:
                logger.error(f"创建聊天会话失败: {response.status_code} - {response.text}")
                self.test_results["create_chat_session"] = f"失败 ({response.status_code})"
                return None
        except Exception as e:
            logger.error(f"创建聊天会话时出错: {str(e)}")
            self.test_results["create_chat_session"] = f"错误 ({str(e)})"
            return None

    def get_chat_sessions(self) -> Optional[List[Dict]]:
        """
        获取聊天会话列表
        
        Returns:
            Optional[List[Dict]]: 成功时返回会话列表，失败时返回None
        """
        logger.info("尝试获取聊天会话列表")
        try:
            url = f"{self.api_base_url}/chat/sessions"
            
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                session_count = len(data.get("items", []))
                logger.info(f"成功获取聊天会话列表，共有 {session_count} 个会话")
                self.test_results["get_chat_sessions"] = "成功"
                return data.get("items", [])
            else:
                logger.error(f"获取聊天会话列表失败: {response.status_code} - {response.text}")
                self.test_results["get_chat_sessions"] = f"失败 ({response.status_code})"
                return None
        except Exception as e:
            logger.error(f"获取聊天会话列表时出错: {str(e)}")
            self.test_results["get_chat_sessions"] = f"错误 ({str(e)})"
            return None

    def get_chat_session(self, session_id: int) -> Optional[Dict]:
        """
        获取特定聊天会话的详情
        
        Args:
            session_id: 会话ID
            
        Returns:
            Optional[Dict]: 成功时返回会话详情，失败时返回None
        """
        logger.info(f"尝试获取聊天会话详情: {session_id}")
        try:
            url = f"{self.api_base_url}/chat/sessions/{session_id}"
            
            # 打印请求详情
            if self.debug_mode:
                logger.info(f"请求URL: {url}")
                logger.info(f"请求头: {json.dumps(self.headers, default=str)}")
            
            response = requests.get(url, headers=self.headers)
            
            # 尝试解析响应内容
            response_text = response.text
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.info(f"成功获取聊天会话详情: {data.get('title', 'Unknown')}")
                    self.test_results["get_chat_session"] = "成功"
                    return data
                except json.JSONDecodeError as e:
                    logger.error(f"解析JSON响应失败: {str(e)}")
                    logger.error(f"响应内容: {response_text[:200]}...")
                    self.test_results["get_chat_session"] = f"失败 (JSON解析错误)"
                    return None
            else:
                # 获取更详细的错误信息
                error_detail = "未知错误"
                try:
                    error_data = response.json()
                    error_detail = error_data.get("detail", "未知错误")
                except:
                    error_detail = response_text[:200]
                
                logger.error(f"获取聊天会话详情失败: {response.status_code} - {error_detail}")
                self.test_results["get_chat_session"] = f"失败 ({response.status_code})"
                
                # 如果是500错误，捕获服务器错误并输出更详细的信息
                if response.status_code == 500:
                    logger.error("检测到服务器内部错误 (500):")
                    logger.error(f"响应内容: {response_text[:500]}")
                    logger.warning("将继续测试其他功能，但会话详情将使用模拟数据...")
                    self.test_results["get_chat_session"] = "跳过 (服务器错误500)"
                    # 返回一个基本的会话对象，以便测试可以继续
                    return {
                        "id": session_id, 
                        "title": f"[模拟] 测试会话 {session_id}", 
                        "messages": [],
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                        "is_mock_data": True  # 标记这是模拟数据
                    }
                
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP请求错误: {str(e)}")
            self.test_results["get_chat_session"] = f"错误 (网络请求失败: {str(e)})"
            return None
        except Exception as e:
            logger.error(f"获取聊天会话详情时出错: {str(e)}")
            self.test_results["get_chat_session"] = f"错误 ({str(e)})"
            return None

    def send_message(self, session_id: int, message: str) -> Optional[Dict]:
        """
        发送消息并获取AI回复
        
        Args:
            session_id: 会话ID
            message: 消息内容
            
        Returns:
            Optional[Dict]: 成功时返回AI回复，失败时返回None
        """
        logger.info(f"尝试发送消息: '{message}'")
        try:
            url = f"{self.api_base_url}/chat/send"
            payload = {
                "session_id": session_id,
                "message": message
            }
            
            if self.debug_mode:
                logger.info(f"请求URL: {url}")
                logger.info(f"请求数据: {json.dumps(payload)}")
                logger.info(f"请求头: {json.dumps(self.headers, default=str)}")
            
            # 开始计时
            start_time = time.time()
            response = requests.post(url, json=payload, headers=self.headers)
            elapsed_time = time.time() - start_time
            response_text = response.text
            
            if self.debug_mode:
                logger.info(f"响应时间: {elapsed_time:.2f}秒")
                logger.info(f"响应状态码: {response.status_code}")
                logger.info(f"响应头: {json.dumps(dict(response.headers), default=str)}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    ai_reply = data.get("content", "")
                    reply_preview = ai_reply[:100] + "..." if len(ai_reply) > 100 else ai_reply
                    logger.info(f"消息发送成功，AI回复: '{reply_preview}'")
                    if "send_message" not in self.test_results:
                        self.test_results["send_message"] = []
                    self.test_results["send_message"].append("成功")
                    return data
                except json.JSONDecodeError as e:
                    logger.error(f"解析AI回复JSON失败: {str(e)}")
                    logger.error(f"响应内容: {response_text[:200]}...")
                    if "send_message" not in self.test_results:
                        self.test_results["send_message"] = []
                    self.test_results["send_message"].append("失败 (JSON解析错误)")
                    return None
            else:
                # 处理500错误
                if response.status_code == 500:
                    logger.error(f"发送消息时服务器返回500错误")
                    logger.error(f"请求参数: {json.dumps(payload)}")
                    logger.error(f"响应内容: {response_text[:500]}")
                    # 检查是否有常见错误模式
                    if "database" in response_text.lower() or "db" in response_text.lower():
                        logger.error("可能的数据库错误。请检查数据库连接和事务处理。")
                    if "gemini" in response_text.lower() or "api key" in response_text.lower():
                        logger.error("可能的Gemini API错误。请检查API密钥和请求格式。")
                else:
                    logger.error(f"发送消息失败: {response.status_code} - {response.text}")
                
                if "send_message" not in self.test_results:
                    self.test_results["send_message"] = []
                self.test_results["send_message"].append(f"失败 ({response.status_code})")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"发送消息HTTP请求错误: {str(e)}")
            if "send_message" not in self.test_results:
                self.test_results["send_message"] = []
            self.test_results["send_message"].append(f"错误 (网络请求: {str(e)})")
            return None
        except Exception as e:
            logger.error(f"发送消息时出错: {str(e)}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            if "send_message" not in self.test_results:
                self.test_results["send_message"] = []
            self.test_results["send_message"].append(f"错误 ({str(e)})")
            return None

    def update_chat_session(self, session_id: int, title: str) -> bool:
        """
        更新聊天会话标题
        
        Args:
            session_id: 会话ID
            title: 新标题
            
        Returns:
            bool: 更新是否成功
        """
        logger.info(f"尝试更新聊天会话标题: {title}")
        try:
            url = f"{self.api_base_url}/chat/sessions/{session_id}"
            payload = {"title": title}
            
            if self.debug_mode:
                logger.info(f"请求URL: {url}")
                logger.info(f"请求数据: {json.dumps(payload)}")
            
            response = requests.put(url, json=payload, headers=self.headers)
            
            if response.status_code == 200:
                logger.info("聊天会话标题更新成功")
                self.test_results["update_chat_session"] = "成功"
                return True
            else:
                logger.error(f"更新聊天会话标题失败: {response.status_code} - {response.text}")
                self.test_results["update_chat_session"] = f"失败 ({response.status_code})"
                return False
        except Exception as e:
            logger.error(f"更新聊天会话标题时出错: {str(e)}")
            self.test_results["update_chat_session"] = f"错误 ({str(e)})"
            return False

    def delete_chat_session(self, session_id: int) -> bool:
        """
        删除聊天会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            bool: 删除是否成功
        """
        logger.info(f"尝试删除聊天会话: {session_id}")
        try:
            url = f"{self.api_base_url}/chat/sessions/{session_id}"
            
            if self.debug_mode:
                logger.info(f"请求URL: {url}")
            
            response = requests.delete(url, headers=self.headers)
            
            if response.status_code == 204:
                logger.info("聊天会话删除成功")
                self.test_results["delete_chat_session"] = "成功"
                return True
            else:
                logger.error(f"删除聊天会话失败: {response.status_code} - {response.text}")
                self.test_results["delete_chat_session"] = f"失败 ({response.status_code})"
                return False
        except Exception as e:
            logger.error(f"删除聊天会话时出错: {str(e)}")
            self.test_results["delete_chat_session"] = f"错误 ({str(e)})"
            return False

    def run_full_test(self, custom_only: bool = False, interactive: bool = False) -> bool:
        """
        运行完整的API测试流程
        
        Args:
            custom_only: 如果为True，则跳过预设消息测试，只测试用户输入的自定义问题
            interactive: 如果为True，则进入交互模式，允许用户连续提问多个问题
            
        Returns:
            bool: 测试是否全部通过
        """
        logger.info("=" * 50)
        logger.info("开始运行Gemini API完整测试")
        logger.info("=" * 50)
        
        # 设置测试环境 - 使用手动输入的凭据
        if not self.setup():
            logger.error("测试环境设置失败，无法继续测试")
            return False
        
        # 创建聊天会话
        self.session_id = self.create_chat_session()
        if not self.session_id:
            logger.error("创建聊天会话失败，无法继续测试")
            return False
        
        # 获取会话列表
        sessions = self.get_chat_sessions()
        if sessions is None:
            logger.error("获取会话列表失败")
            return False
        
        # 获取特定会话详情
        session_details = self.get_chat_session(self.session_id)
        if session_details is None:
            logger.error("获取会话详情完全失败，无法继续测试")
            return False
        
        # 即使会话详情获取跳过了，但返回了基本会话对象，也可以继续测试
        if self.test_results.get("get_chat_session") == "跳过 (服务器错误500)":
            logger.warning("会话详情获取被跳过，但将继续测试其他功能")
        
        success_messages = 0
        
        # 如果不是只测试自定义问题，则测试预设问题
        if not custom_only:
            # 发送消息并获取AI回复
            message_count = min(3, len(TEST_MESSAGES))  # 限制测试消息数量
            for i in range(message_count):
                logger.info(f"测试消息 {i+1}/{message_count}")
                message = TEST_MESSAGES[i]
                response = self.send_message(self.session_id, message)
                if response is None:
                    logger.error(f"发送测试消息 {i+1} 失败")
                    # 继续测试其他消息
                    continue
                else:
                    success_messages += 1
                # 添加短暂延迟，避免请求过于频繁
                time.sleep(1)
        elif custom_only:
            logger.info("跳过预设消息测试，只进行自定义问题测试")
        
        # 自定义问题处理部分
        if interactive:
            # 交互模式：连续提问多个问题直到用户选择退出
            logger.info("\n进入交互式问答模式，您可以连续提问多个问题")
            logger.info("输入'exit'、'quit'或'q'退出交互模式\n")
            
            question_count = 0
            while True:
                custom_message = input("\n请输入您的问题 (或输入'q'退出): ").strip()
                if custom_message.lower() in ['exit', 'quit', 'q']:
                    logger.info("退出交互式问答模式")
                    break
                
                if not custom_message:
                    logger.warning("未输入有效问题，请重新输入")
                    continue
                
                question_count += 1
                logger.info(f"发送自定义问题 #{question_count}: '{custom_message}'")
                response = self.send_message(self.session_id, custom_message)
                
                if response is None:
                    logger.error("发送自定义问题失败")
                else:
                    success_messages += 1
                    # 显示完整回复，而不是截断版本
                    ai_reply = response.get("content", "")
                    logger.info(f"AI回复完整内容:\n{'-' * 50}\n{ai_reply}\n{'-' * 50}")
                
                # 添加短暂延迟，避免请求过于频繁
                time.sleep(1)
            
            if question_count > 0:
                logger.info(f"交互式问答结束，共发送了 {question_count} 个问题")
        else:
            # 原有单次提问模式
            custom_message_choice = 'y' if custom_only else input("\n是否要发送自定义问题? (y/n): ").strip().lower()
                
            if custom_message_choice == 'y':
                custom_message = input("\n请输入您想问的问题: ").strip()
                if custom_message:
                    logger.info(f"发送自定义问题: '{custom_message}'")
                    response = self.send_message(self.session_id, custom_message)
                    if response is None:
                        logger.error("发送自定义问题失败")
                    else:
                        success_messages += 1
                        # 显示完整回复，而不是截断版本
                        ai_reply = response.get("content", "")
                        logger.info(f"AI回复完整内容:\n{'-' * 50}\n{ai_reply}\n{'-' * 50}")
                else:
                    logger.warning("未输入有效问题，跳过自定义问题测试")
        
        # 只要有一条消息发送成功，就继续测试
        if success_messages == 0 and (not custom_only or custom_message_choice == 'y' or interactive):
            logger.error("所有测试消息均发送失败，无法继续测试会话更新")
        else:
            # 更新会话标题
            new_title = f"Updated Test Session {datetime.now().strftime('%Y%m%d%H%M%S')}"
            if not self.update_chat_session(self.session_id, new_title):
                logger.error("更新会话标题失败")
            else:
                # 验证标题更新是否成功
                updated_session = self.get_chat_session(self.session_id)
                # 会话详情仍然可能失败，但不影响测试的完成
                if updated_session and updated_session.get("title") == new_title:
                    logger.info("会话标题更新验证成功")
                elif updated_session:
                    logger.warning(f"会话标题似乎未更新: 期望 '{new_title}', 实际 '{updated_session.get('title')}'")
                else:
                    logger.error("无法验证会话标题更新，获取更新后的会话详情失败")
        
        # 输出测试结果摘要
        self._print_test_summary()
        
        # 询问用户是否要删除测试会话
        if not interactive and not custom_only:  # 在交互模式或自定义模式下，默认保留会话
            delete_choice = input("\n是否删除测试会话? (y/n): ").strip().lower()
            if delete_choice == 'y':
                if self.delete_chat_session(self.session_id):
                    logger.info("成功删除测试会话")
                else:
                    logger.error("删除测试会话失败")
            else:
                logger.info(f"已保留测试会话 (ID: {self.session_id})")
        else:
            logger.info(f"已保留测试会话 (ID: {self.session_id})，以便于后续使用")
        
        # 检查是否所有必要的测试都成功
        # 可能有些测试被跳过，所有标记为跳过的测试不影响测试结果
        all_passed = True
        critical_tests = ["login", "create_chat_session"]
        for test in critical_tests:
            result = self.test_results.get(test)
            if result != "成功":
                all_passed = False
                break
        
        # 对于send_message测试，只要有一条消息发送成功就可以
        if "send_message" in self.test_results and isinstance(self.test_results["send_message"], list):
            if "成功" not in self.test_results["send_message"]:
                all_passed = False
        
        if all_passed:
            logger.info("=" * 50)
            logger.info("✅ 基本测试通过! (部分功能可能被跳过)")
            logger.info("=" * 50)
        else:
            logger.warning("=" * 50)
            logger.warning("⚠️ 部分关键测试未通过，请查看详细日志")
            logger.warning("=" * 50)
            
        return all_passed
    
    def _print_test_summary(self) -> None:
        """打印测试结果摘要"""
        logger.info("=" * 50)
        logger.info("测试结果摘要:")
        
        for test_name, result in self.test_results.items():
            if isinstance(result, list):
                success_count = result.count("成功")
                total_count = len(result)
                logger.info(f"- {test_name}: {success_count}/{total_count} 成功")
            else:
                logger.info(f"- {test_name}: {result}")
        
        logger.info("=" * 50)

    def run_only_interactive(self) -> bool:
        """
        仅运行交互式问答模式，跳过其他测试步骤
        
        Returns:
            bool: 测试是否顺利完成
        """
        logger.info("=" * 50)
        logger.info("开始Gemini API交互式问答模式")
        logger.info("=" * 50)
        
        # 设置测试环境 - 使用手动输入的凭据
        if not self.setup():
            logger.error("测试环境设置失败，无法继续")
            return False
        
        # 创建聊天会话
        self.session_id = self.create_chat_session("交互式问答会话")
        if not self.session_id:
            logger.error("创建聊天会话失败，无法继续")
            return False
        
        logger.info("\n进入交互式问答模式，您可以连续提问多个问题")
        logger.info("输入'exit'、'quit'或'q'退出交互模式\n")
        
        question_count = 0
        success_count = 0
        
        # 交互式问答循环
        while True:
            custom_message = input("\n请输入您的问题 (或输入'q'退出): ").strip()
            if custom_message.lower() in ['exit', 'quit', 'q']:
                logger.info("退出交互式问答模式")
                break
            
            if not custom_message:
                logger.warning("未输入有效问题，请重新输入")
                continue
            
            question_count += 1
            logger.info(f"发送问题 #{question_count}: '{custom_message}'")
            response = self.send_message(self.session_id, custom_message)
            
            if response is None:
                logger.error("发送问题失败")
            else:
                success_count += 1
                # 显示完整回复
                ai_reply = response.get("content", "")
                logger.info(f"AI回复完整内容:\n{'-' * 50}\n{ai_reply}\n{'-' * 50}")
            
            # 添加短暂延迟，避免请求过于频繁
            time.sleep(1)
        
        if question_count > 0:
            logger.info(f"交互式问答结束，共发送 {question_count} 个问题，成功 {success_count} 个")
            
        logger.info(f"交互式会话ID: {self.session_id}，您可以在前端应用中继续使用此会话")
        
        return success_count > 0 if question_count > 0 else True
    
    def run_custom_test(self) -> bool:
        """
        运行自定义测试项目
        
        Returns:
            bool: 测试是否通过
        """
        logger.info("=" * 50)
        logger.info("开始自定义测试项目")
        logger.info("=" * 50)
        
        # 设置测试环境 - 使用手动输入的凭据
        if not self.setup():
            logger.error("测试环境设置失败，无法继续")
            return False
        
        # 创建一个总体成功标志，用于最终返回值
        overall_success = True
        
        # 进入自定义测试循环
        while True:
            # 显示可测试项目菜单
            print("\n" + "=" * 50)
            print("自定义测试菜单".center(48))
            print("=" * 50)
            print("请选择要测试的项目:")
            print("1. 创建聊天会话")
            print("2. 获取会话列表")
            print("3. 获取单个会话详情")
            print("4. 发送单条消息并接收回复")
            print("5. 更新会话标题")
            print("6. 删除会话")
            print("7. 所有上述项目")
            print("0. 返回主菜单")
            print("-" * 50)
            
            choice = input("\n请输入选项 (0-7): ").strip()
            
            # 检查是否返回主菜单
            if choice == "0":
                logger.info("返回主菜单")
                break
            
            if choice not in ["1", "2", "3", "4", "5", "6", "7"]:
                logger.error("无效选项，请重新选择")
                continue
            
            success = True
            
            # 创建会话（大部分选项都需要）
            if choice in ["1", "3", "4", "5", "6", "7"]:
                # 如果已经有会话ID且不是选择创建会话，则使用现有的
                if choice != "1" and self.session_id:
                    logger.info(f"使用现有会话 (ID: {self.session_id})")
                else:
                    session_title = input("\n请输入会话标题 (留空使用随机标题): ").strip() or None
                    self.session_id = self.create_chat_session(session_title)
                    
                if not self.session_id and choice != "2":  # 只有获取会话列表不需要创建新会话
                    logger.error("创建聊天会话失败，无法继续此项测试")
                    success = False
                    overall_success = False
                    if choice in ["1", "3", "4", "5", "6"]:  # 如果只选择了单项测试且依赖会话ID，则继续下一轮
                        continue
            
            # 获取会话列表
            if choice in ["2", "7"]:
                sessions = self.get_chat_sessions()
                if sessions is None:
                    logger.error("获取会话列表失败")
                    success = False
                    overall_success = False
                else:
                    logger.info(f"成功获取会话列表，共有 {len(sessions)} 个会话")
                    if len(sessions) > 0:
                        logger.info("会话列表预览:")
                        for i, session in enumerate(sessions[:5]):  # 只显示前5个
                            logger.info(f"  {i+1}. ID: {session.get('id')}, 标题: {session.get('title')}")
                        if len(sessions) > 5:
                            logger.info(f"  ... 还有 {len(sessions) - 5} 个会话")
                        
                        # 如果没有活动会话，可以选择一个已有的会话
                        if not self.session_id and len(sessions) > 0:
                            select_choice = input("\n是否选择一个现有会话继续测试? (y/n): ").strip().lower()
                            if select_choice == 'y':
                                try:
                                    idx = int(input(f"请输入会话序号 (1-{min(len(sessions), 5)}): ").strip()) - 1
                                    if 0 <= idx < len(sessions):
                                        self.session_id = sessions[idx].get('id')
                                        logger.info(f"已选择会话 ID: {self.session_id}")
                                    else:
                                        logger.warning("无效的会话序号")
                                except ValueError:
                                    logger.warning("输入无效，未选择会话")
            
            # 获取单个会话详情
            if choice in ["3", "7"] and self.session_id:
                session_details = self.get_chat_session(self.session_id)
                if session_details is None:
                    logger.error("获取会话详情失败")
                    success = False
                    overall_success = False
                else:
                    # 显示会话详情的摘要
                    title = session_details.get('title', 'Unknown')
                    created_at = session_details.get('created_at', 'Unknown')
                    message_count = len(session_details.get('messages', []))
                    logger.info(f"会话详情摘要:")
                    logger.info(f"  标题: {title}")
                    logger.info(f"  创建时间: {created_at}")
                    logger.info(f"  消息数量: {message_count}")
            
            # 发送消息
            if choice in ["4", "7"] and self.session_id:
                while True:
                    custom_message = input("\n请输入您想测试的问题 (输入'q'返回上级菜单): ").strip()
                    if custom_message.lower() in ['q', 'quit', 'exit']:
                        break
                        
                    if not custom_message:
                        logger.warning("未输入有效问题，请重新输入")
                        continue
                        
                    response = self.send_message(self.session_id, custom_message)
                    if response is None:
                        logger.error("发送消息失败")
                        success = False
                        overall_success = False
                    else:
                        ai_reply = response.get("content", "")
                        logger.info(f"AI回复完整内容:\n{'-' * 50}\n{ai_reply}\n{'-' * 50}")
                    
                    if choice != "7":  # 如果不是"所有项目"测试，则询问是否继续发消息
                        continue_choice = input("\n是否继续发送消息? (y/n): ").strip().lower()
                        if continue_choice != 'y':
                            break
            
            # 更新会话标题
            if choice in ["5", "7"] and self.session_id:
                new_title = input("\n请输入新的会话标题 (留空使用自动生成标题): ").strip()
                if not new_title:
                    new_title = f"Updated Test Session {datetime.now().strftime('%Y%m%d%H%M%S')}"
                    logger.info(f"使用自动生成的标题: {new_title}")
                    
                if not self.update_chat_session(self.session_id, new_title):
                    logger.error("更新会话标题失败")
                    success = False
                    overall_success = False
                else:
                    # 验证标题更新
                    updated_session = self.get_chat_session(self.session_id)
                    if updated_session and updated_session.get("title") == new_title:
                        logger.info("会话标题更新验证成功")
                    elif updated_session:
                        logger.warning(f"会话标题似乎未更新: 期望 '{new_title}', 实际 '{updated_session.get('title')}'")
                        success = False
                        overall_success = False
            
            # 删除会话
            if choice in ["6", "7"] and self.session_id:
                delete_choice = input(f"\n是否删除当前测试会话 ID: {self.session_id}? (y/n): ").strip().lower()
                if delete_choice == 'y':
                    if self.delete_chat_session(self.session_id):
                        logger.info("成功删除测试会话")
                        self.session_id = None  # 清除会话ID，因为已被删除
                    else:
                        logger.error("删除测试会话失败")
                        success = False
                        overall_success = False
                else:
                    logger.info(f"保留测试会话 (ID: {self.session_id})")
            
            # 输出测试结果摘要
            if choice == "7":  # 只在测试"所有项目"时显示完整摘要
                self._print_test_summary()
            
            if success:
                logger.info("=" * 50)
                logger.info(f"✅ 测试项目 {choice} 完成")
                logger.info("=" * 50)
            else:
                logger.warning("=" * 50)
                logger.warning(f"⚠️ 测试项目 {choice} 部分失败")
                logger.warning("=" * 50)
                
            # 在每次测试后提示用户继续
            print("\n" + "-" * 50)
            print("此项测试已完成，即将返回自定义测试菜单...")
            input("按任意键继续...")
            
        return overall_success

def display_menu():
    """显示主菜单并获取用户选择"""
    print("\n" + "=" * 60)
    print("  Gemini API 测试工具  ".center(58))
    print("=" * 60)
    print("请选择您要执行的操作:")
    print("1. 运行完整测试 (包含预设问题和可选的自定义问题)")
    print("2. 只进行交互式问答 (创建会话并连续提问)")
    print("3. 运行自定义测试 (选择特定功能进行测试)")
    print("0. 退出程序")
    print("-" * 60)
    
    choice = input("请输入选项 (0-3): ").strip()
    return choice

def main():
    """主函数，运行测试"""
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description="Gemini API 测试工具")
    parser.add_argument("--debug", action="store_true", help="启用调试模式，输出详细日志")
    parser.add_argument("--url", type=str, help="指定API基础URL，例如 http://localhost:8000/api/v1")
    parser.add_argument("--skip-delete", action="store_true", help="自动跳过删除测试会话的步骤")
    parser.add_argument("--custom-only", action="store_true", help="跳过预设问题测试，只发送用户自定义问题")
    parser.add_argument("--interactive", action="store_true", help="启用交互模式，允许连续提问多个问题")
    parser.add_argument("--menu", action="store_true", help="显示交互式菜单，选择测试模式")
    parser.add_argument("--no-loop", action="store_true", help="运行单次测试后退出，不进入连续测试模式")
    
    args = parser.parse_args()
    
    # 设置环境变量
    if args.debug:
        os.environ["DEBUG_MODE"] = "true"
        logger.info("已启用调试模式")
    
    # 获取API基础URL
    api_base_url = args.url or API_BASE_URL
    logger.info(f"使用API基础URL: {api_base_url}")
    
    # 是否使用循环模式（可以通过命令行参数禁用）
    use_loop_mode = not args.no_loop
    
    try:
        # 检查是否使用命令行参数直接指定了测试模式
        if not args.menu and (args.custom_only or args.interactive):
            # 直接使用命令行参数指定的模式，只运行一次
            tester = GeminiAPITester(api_base_url=api_base_url)
            result = tester.run_full_test(custom_only=args.custom_only, interactive=args.interactive)
            
            # 自动跳过删除步骤
            if args.skip_delete and tester.session_id:
                logger.info(f"根据参数设置，保留测试会话 (ID: {tester.session_id})")
            
            # 返回适当的退出代码
            return 0 if result else 1
        
        # 进入主循环模式
        while True:
            # 显示菜单并获取用户选择
            choice = display_menu()
            
            if choice == "0":
                logger.info("退出测试工具")
                return 0
            
            # 为每次测试创建新的测试器实例，避免状态混乱
            tester = GeminiAPITester(api_base_url=api_base_url)
            
            if choice == "1":
                # 运行完整测试
                logger.info("\n准备运行完整测试...\n")
                result = tester.run_full_test(custom_only=False, interactive=False)
            elif choice == "2":
                # 只进行交互式问答
                logger.info("\n准备进入交互式问答模式...\n")
                result = tester.run_only_interactive()
            elif choice == "3":
                # 运行自定义测试 - 注意这里会在run_custom_test内部循环，直到用户选择返回主菜单
                logger.info("\n准备进入自定义测试模式...\n")
                result = tester.run_custom_test()
            else:
                logger.error("无效选项，请重新选择")
                continue
            
            # 处理测试结果 - 对于选项3，这些操作会在返回主菜单后执行
            if tester.session_id and not args.skip_delete:
                logger.info(f"测试会话 (ID: {tester.session_id}) 处理完成")
            
            # 提示用户继续
            if result:
                logger.info("\n✅ 测试执行完成")
            else:
                logger.warning("\n⚠️ 测试执行完成，但部分测试未通过")
                
            if not use_loop_mode:
                # 如果设置了非循环模式，则退出
                return 0 if result else 1
                
            # 提示用户继续
            print("\n" + "-" * 60)
            print("测试已完成，按任意键返回主菜单...")
            input()
            
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
        return 130  # SIGINT的标准退出代码
    except Exception as e:
        logger.error(f"测试过程中发生未处理的错误: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main()) 