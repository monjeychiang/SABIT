import asyncio
import json
import websockets
import requests
from datetime import datetime
import logging
import sys
import os
import argparse
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# 配置
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"
TEST_USER = {
    "username": "testuser6666",
    "password": "Test123456",
    "email": "testuser6666@example.com",
    "full_name": "Test User 6666"
}
TEST_USER2 = {
    "username": "testuser7777",
    "password": "Test123456",
    "email": "testuser7777@example.com",
    "full_name": "Test User 7777"
}

# 辅助函数
async def check_user_exists(username):
    """检查用户是否已存在"""
    try:
        # 直接尝试用户登录，如果登录成功说明用户存在
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login/simple", 
            data={
                "username": username,
                "password": "wrongpassword123"  # 使用错误密码，我们只是想检查用户名是否存在
            }
        )
        
        # 分析响应内容判断用户是否存在
        if response.status_code == 401 and "用戶名或密碼錯誤" in response.text:
            logger.info(f"用户 {username} 已存在")
            return True
        elif response.status_code == 404 or "找不到用户" in response.text or "用户不存在" in response.text:
            logger.info(f"用户 {username} 不存在")
            return False
        else:
            logger.warning(f"检查用户存在状态未知: {response.status_code}, {response.text}")
            # 默认假设用户不存在，以便尝试注册
            return False
    except Exception as e:
        logger.error(f"检查用户存在时发生错误: {str(e)}")
        return False

async def ensure_user_deleted(username):
    """确保用户被删除（用于重新创建）"""
    try:
        # 注意：这需要管理员权限，通常测试环境才能使用
        # 为简化测试，我们先尝试使用超级用户登录
        admin_token = await get_admin_token()
        if not admin_token:
            logger.warning("无法获取管理员令牌，跳过用户删除")
            return False
        
        # 查找用户ID
        headers = {"Authorization": f"Bearer {admin_token}"}
        user_response = requests.get(f"{BASE_URL}/api/v1/admin/users?username={username}", headers=headers)
        
        if user_response.status_code != 200:
            logger.warning(f"查询用户失败: {user_response.text}")
            return False
        
        users = user_response.json()
        if not users or len(users) == 0:
            logger.info(f"用户 {username} 不存在，无需删除")
            return True
        
        user_id = users[0]["id"]
        
        # 删除用户
        delete_response = requests.delete(f"{BASE_URL}/api/v1/admin/users/{user_id}", headers=headers)
        
        if delete_response.status_code == 200 or delete_response.status_code == 204:
            logger.info(f"用户 {username} 已成功删除")
            return True
        else:
            logger.warning(f"删除用户失败: {delete_response.text}")
            return False
    except Exception as e:
        logger.error(f"删除用户时发生错误: {str(e)}")
        return False

async def get_admin_token():
    """获取管理员令牌"""
    try:
        # 尝试使用标准管理员账号登录
        admin_data = {
            "username": "admin",
            "password": "adminpassword"  # 替换为实际的管理员密码
        }
        
        response = requests.post(f"{BASE_URL}/api/v1/auth/login/simple", data=admin_data)
        if response.status_code == 200:
            return response.json()["access_token"]
        
        # 如果没有标准管理员，可以尝试其他已知管理员
        return None
    except Exception as e:
        logger.error(f"获取管理员令牌失败: {str(e)}")
        return None

async def register_user(user_data):
    """注册测试用户，如果存在则尝试验证登录，失败则重新创建"""
    # 先检查用户是否已存在
    exists = await check_user_exists(user_data["username"])
    
    if exists:
        logger.info(f"用户 {user_data['username']} 已存在，尝试登录验证")
        try:
            # 尝试登录验证密码是否正确
            token = await get_auth_token(user_data["username"], user_data["password"])
            if token:
                logger.info(f"用户 {user_data['username']} 登录成功，无需重新创建")
                return True
            else:
                logger.warning(f"用户 {user_data['username']} 登录失败，尝试重新创建")
        except Exception as e:
            logger.warning(f"用户 {user_data['username']} 登录验证失败: {str(e)}")
            
        # 登录失败，尝试删除后重新创建
        logger.info(f"尝试删除现有用户 {user_data['username']} 并重新创建")
        await ensure_user_deleted(user_data["username"])
        # 等待一段时间确保删除操作完成
        await asyncio.sleep(1)
    
    # 创建新用户
    logger.info(f"开始创建用户 {user_data['username']}")
    register_data = {
        "username": user_data["username"],
        "password": user_data["password"],
        "confirm_password": user_data["password"],
        "email": user_data["email"],
        "full_name": user_data["full_name"]
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/v1/auth/register", json=register_data)
        logger.info(f"注册响应状态码: {response.status_code}, 响应内容: {response.text[:200]}")
        
        if response.status_code == 201:
            logger.info(f"用户 {user_data['username']} 注册成功")
            # 等待账户信息完全写入数据库
            await asyncio.sleep(2)
            return True
        else:
            # 如果注册失败，可能是因为用户已存在但我们的检测未能发现
            if "already exists" in response.text or "已存在" in response.text:
                logger.warning(f"用户 {user_data['username']} 已存在，但我们无法正确登录")
                # 尝试使用直接数据库操作更新密码（仅测试环境）
                # 此处省略具体实现，实际项目中需根据数据库访问方式实现
                return False
            else:
                logger.error(f"注册用户 {user_data['username']} 失败: {response.text}")
                return False
                
    except Exception as e:
        logger.error(f"注册过程中发生错误: {str(e)}")
        return False

async def get_auth_token(username, password):
    """获取用户的认证令牌"""
    try:
        # 使用简化版登录接口
        logger.info(f"尝试使用简化登录接口登录用户: {username}")
        login_data = {
            "username": username,
            "password": password
        }
        response = requests.post(f"{BASE_URL}/api/v1/auth/login/simple", data=login_data)
        if response.status_code == 200:
            token = response.json()["access_token"]
            logger.info(f"用户 {username} 登录成功，获取到令牌")
            return token
        else:
            logger.warning(f"简化登录失败: {response.text}")
            
            # 尝试使用标准OAuth2登录
            logger.info(f"尝试使用标准OAuth2登录用户: {username}")
            form_data = {
                "username": username,
                "password": password,
                "grant_type": "password",
                "scope": ""
            }
            oauth_response = requests.post(
                f"{BASE_URL}/api/v1/auth/login", 
                data=form_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if oauth_response.status_code == 200:
                token = oauth_response.json()["access_token"]
                logger.info(f"用户 {username} OAuth2登录成功，获取到令牌")
                return token
            else:
                error_msg = f"所有登录尝试均失败: {oauth_response.text}"
                logger.error(error_msg)
                return None
    except Exception as e:
        logger.error(f"登录过程中发生错误: {str(e)}")
        return None

async def create_chat_room(token):
    """创建测试聊天室"""
    room_data = {
        "name": f"测试聊天室 {datetime.now().isoformat()}",
        "description": "这是一个测试聊天室",
        "is_public": True,
        "is_official": False
    }
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(f"{BASE_URL}/api/v1/chatroom/rooms", json=room_data, headers=headers)
    if response.status_code != 201:
        raise Exception(f"创建聊天室失败: {response.text}")
    return response.json()

async def join_chat_room(token, room_id):
    """加入聊天室"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(f"{BASE_URL}/api/v1/chatroom/rooms/{room_id}/join", headers=headers)
    if response.status_code != 200:
        raise Exception(f"加入聊天室失败: {response.text}")
    return response.json()

# WebSocket聊天室客户端类 - 更新为用户级别连接
class ChatRoomClient:
    def __init__(self, base_url, token, client_name):
        self.base_url = base_url
        self.token = token
        self.client_name = client_name
        self.websocket = None
        self.is_connected = False
        self.active_room_id = None  # 当前活跃的聊天室ID
        self.joined_rooms = set()   # 已加入的聊天室ID集合
    
    async def connect(self):
        """连接到用户WebSocket"""
        # 更新URL模式，不再包含room_id
        ws_url = f"{self.base_url}/api/v1/chatroom/ws/user/{self.token}"
        logger.info(f"客户端 {self.client_name} 正在连接到: {ws_url}")
        
        try:
            self.websocket = await websockets.connect(ws_url)
            self.is_connected = True
            logger.info(f"客户端 {self.client_name} 已连接")
            
            # 等待连接确认消息
            connected_msg = await self.websocket.recv()
            conn_data = json.loads(connected_msg)
            
            if conn_data.get("type") == "connected":
                logger.info(f"客户端 {self.client_name} 连接确认: {conn_data}")
                # 保存已加入的聊天室
                if "room_ids" in conn_data:
                    self.joined_rooms = set(conn_data["room_ids"])
                    logger.info(f"客户端 {self.client_name} 已加入的聊天室: {self.joined_rooms}")
            else:
                logger.warning(f"客户端 {self.client_name} 收到非连接确认消息: {conn_data}")
                
            return True
        except Exception as e:
            logger.error(f"连接失败: {str(e)}")
            return False
    
    async def listen(self):
        """监听接收的消息"""
        if not self.is_connected:
            logger.error("未连接，无法监听消息")
            return
        
        try:
            while True:
                message = await self.websocket.recv()
                data = json.loads(message)
                # 添加聊天室信息到日志
                room_id = data.get("room_id", "全局")
                logger.info(f"客户端 {self.client_name} 收到消息 (聊天室 {room_id}): {data}")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"客户端 {self.client_name} 的连接已关闭")
            self.is_connected = False
        except Exception as e:
            logger.error(f"监听消息时出错: {str(e)}")
            self.is_connected = False
    
    def set_active_room(self, room_id):
        """设置当前活跃的聊天室"""
        self.active_room_id = room_id
        logger.info(f"客户端 {self.client_name} 当前活跃聊天室设置为: {room_id}")
    
    async def join_room(self, room_id):
        """通过WebSocket请求加入聊天室"""
        if not self.is_connected:
            logger.error("未连接，无法加入聊天室")
            return False
        
        if room_id in self.joined_rooms:
            logger.info(f"客户端 {self.client_name} 已经在聊天室 {room_id} 中")
            self.set_active_room(room_id)
            return True
        
        try:
            join_message = {
                "type": "join_room",
                "room_id": room_id,
                "timestamp": datetime.now().isoformat()
            }
            
            await self.websocket.send(json.dumps(join_message))
            logger.info(f"客户端 {self.client_name} 请求加入聊天室 {room_id}")
            
            # 添加到已加入聊天室集合
            self.joined_rooms.add(room_id)
            self.set_active_room(room_id)
            return True
        except Exception as e:
            logger.error(f"加入聊天室失败: {str(e)}")
            return False
    
    async def leave_room(self, room_id):
        """通过WebSocket请求离开聊天室"""
        if not self.is_connected:
            logger.error("未连接，无法离开聊天室")
            return False
        
        if room_id not in self.joined_rooms:
            logger.info(f"客户端 {self.client_name} 未在聊天室 {room_id} 中")
            return True
        
        try:
            leave_message = {
                "type": "leave_room",
                "room_id": room_id,
                "timestamp": datetime.now().isoformat()
            }
            
            await self.websocket.send(json.dumps(leave_message))
            logger.info(f"客户端 {self.client_name} 请求离开聊天室 {room_id}")
            
            # 从已加入聊天室集合中移除
            self.joined_rooms.remove(room_id)
            
            # 如果当前活跃聊天室是要离开的聊天室，则清除活跃聊天室
            if self.active_room_id == room_id:
                self.active_room_id = None
                
            return True
        except Exception as e:
            logger.error(f"离开聊天室失败: {str(e)}")
            return False
    
    async def send_message(self, content, room_id=None):
        """发送聊天消息"""
        if not self.is_connected:
            logger.error("未连接，无法发送消息")
            return False
        
        # 确定目标聊天室
        target_room_id = room_id if room_id is not None else self.active_room_id
        
        if target_room_id is None:
            logger.error("未指定聊天室，无法发送消息")
            return False
        
        if target_room_id not in self.joined_rooms:
            logger.error(f"未加入聊天室 {target_room_id}，无法发送消息")
            return False
        
        try:
            message = {
                "type": "message",
                "room_id": target_room_id,
                "content": content,
                "timestamp": datetime.now().isoformat()
            }
            
            await self.websocket.send(json.dumps(message))
            logger.info(f"客户端 {self.client_name} 向聊天室 {target_room_id} 发送消息: {content}")
            return True
        except Exception as e:
            logger.error(f"发送消息失败: {str(e)}")
            return False
    
    async def send_typing(self, room_id=None):
        """发送正在输入状态"""
        if not self.is_connected:
            logger.error("未连接，无法发送输入状态")
            return False
        
        # 确定目标聊天室
        target_room_id = room_id if room_id is not None else self.active_room_id
        
        if target_room_id is None:
            logger.error("未指定聊天室，无法发送输入状态")
            return False
        
        if target_room_id not in self.joined_rooms:
            logger.error(f"未加入聊天室 {target_room_id}，无法发送输入状态")
            return False
        
        try:
            message = {
                "type": "typing",
                "room_id": target_room_id,
                "timestamp": datetime.now().isoformat()
            }
            
            await self.websocket.send(json.dumps(message))
            logger.info(f"客户端 {self.client_name} 向聊天室 {target_room_id} 发送输入状态")
            return True
        except Exception as e:
            logger.error(f"发送输入状态失败: {str(e)}")
            return False
    
    async def close(self):
        """关闭WebSocket连接"""
        if not self.is_connected:
            return
        
        try:
            await self.websocket.close()
            logger.info(f"客户端 {self.client_name} 已断开连接")
            self.is_connected = False
        except Exception as e:
            logger.error(f"关闭连接失败: {str(e)}")

# 主测试函数
async def run_test(base_url, room_id, token1, token2, duration=60):
    """
    运行聊天室WebSocket测试 - 更新以支持用户级别的WebSocket
    
    Args:
        base_url: WebSocket服务器基础URL
        room_id: 测试用的聊天室ID
        token1: 第一个用户的认证令牌
        token2: 第二个用户的认证令牌
        duration: 测试持续时间（秒）
    """
    # 创建两个客户端 - 不再传入room_id
    client1 = ChatRoomClient(base_url, token1, "用户1")
    client2 = ChatRoomClient(base_url, token2, "用户2")
    
    logger.info(f"==== 测试开始：在两个聊天室中测试单一WebSocket连接 ====")
    
    # 连接到用户的WebSocket
    if not await client1.connect():
        logger.error("客户端1连接失败，测试终止")
        return
    
    if not await client2.connect():
        logger.error("客户端2连接失败，测试终止")
        await client1.close()
        return
    
    # 请求加入聊天室
    await client1.join_room(room_id)
    await client2.join_room(room_id)
    
    # 创建监听任务
    listen_task1 = asyncio.create_task(client1.listen())
    listen_task2 = asyncio.create_task(client2.listen())
    
    # 测试消息交换
    try:
        # 发送一些测试消息
        logger.info(f"==== 第一阶段：在第一个聊天室 (ID: {room_id}) 中测试消息交换 ====")
        
        await client1.send_message("大家好！这是来自用户1的消息 (聊天室1)")
        await asyncio.sleep(1)
        
        await client2.send_typing()
        await asyncio.sleep(1)
        
        await client2.send_message("你好用户1，这是来自用户2的回复 (聊天室1)")
        await asyncio.sleep(1)
        
        # 模拟聊天对话
        for i in range(2):
            await client1.send_typing()
            await asyncio.sleep(0.5)
            await client1.send_message(f"聊天室1 - 测试消息 {i+1} 从用户1")
            await asyncio.sleep(1)
            
            await client2.send_typing()
            await asyncio.sleep(0.5)
            await client2.send_message(f"聊天室1 - 回复测试消息 {i+1} 从用户2")
            await asyncio.sleep(1)
        
        # 开启多聊天室测试
        # 创建第二个聊天室并测试
        is_multi_room_test = True
        second_room_id = None
        
        if is_multi_room_test:
            logger.info(f"==== 第二阶段：创建第二个聊天室并在两个聊天室之间切换 ====")
            # 创建第二个聊天室并让两个用户加入
            try:
                # 这部分使用HTTP API创建和加入
                new_room = await create_chat_room(token1)
                second_room_id = new_room["id"]
                logger.info(f"已创建第二个聊天室: {new_room['name']} (ID: {second_room_id})")
                
                await join_chat_room(token2, second_room_id)
                logger.info(f"用户2已加入第二个聊天室")
                
                # 通过WebSocket加入聊天室
                await client1.join_room(second_room_id)
                await client2.join_room(second_room_id)
                
                # 在第二个聊天室测试消息
                client1.set_active_room(second_room_id)
                client2.set_active_room(second_room_id)
                
                logger.info(f"==== 第三阶段：在第二个聊天室 (ID: {second_room_id}) 中测试消息交换 ====")
                
                await client1.send_message("大家好！这是来自用户1在第二个聊天室的消息")
                await asyncio.sleep(1)
                
                await client2.send_message("你好用户1，这是在第二个聊天室的回复")
                await asyncio.sleep(1)
                
                # 多个消息测试
                for i in range(2):
                    await client1.send_typing()
                    await asyncio.sleep(0.5)
                    await client1.send_message(f"聊天室2 - 测试消息 {i+1} 从用户1")
                    await asyncio.sleep(1)
                    
                    await client2.send_typing()
                    await asyncio.sleep(0.5)
                    await client2.send_message(f"聊天室2 - 回复测试消息 {i+1} 从用户2")
                    await asyncio.sleep(1)
                
                # 切换回第一个聊天室
                logger.info(f"==== 第四阶段：在两个聊天室之间快速切换 ====")
                
                client1.set_active_room(room_id)
                await client1.send_message("我们回到了第一个聊天室")
                await asyncio.sleep(1)
                
                client2.set_active_room(room_id)
                await client2.send_message("用户2也回到了第一个聊天室")
                await asyncio.sleep(1)
                
                # 快速切换聊天室测试
                for i in range(2):
                    # 用户1在聊天室1发送消息
                    client1.set_active_room(room_id)
                    await client1.send_message(f"切换测试 - 用户1在聊天室1的消息 {i+1}")
                    await asyncio.sleep(0.5)
                    
                    # 用户1在聊天室2发送消息
                    client1.set_active_room(second_room_id)
                    await client1.send_message(f"切换测试 - 用户1在聊天室2的消息 {i+1}")
                    await asyncio.sleep(0.5)
                    
                    # 用户2在聊天室2回复
                    client2.set_active_room(second_room_id)
                    await client2.send_message(f"切换测试 - 用户2在聊天室2的回复 {i+1}")
                    await asyncio.sleep(0.5)
                    
                    # 用户2在聊天室1回复
                    client2.set_active_room(room_id)
                    await client2.send_message(f"切换测试 - 用户2在聊天室1的回复 {i+1}")
                    await asyncio.sleep(0.5)
                
                logger.info(f"==== 多聊天室测试完成 ====")
                
            except Exception as e:
                logger.error(f"多聊天室测试失败: {str(e)}")
        
        # 等待指定时间
        logger.info(f"测试将持续运行 {duration} 秒以检测长连接稳定性...")
        await asyncio.sleep(duration)
        
        # 测试离开聊天室
        logger.info(f"==== 最后阶段：测试离开聊天室 ====")
        
        if second_room_id:
            logger.info(f"用户离开第二个聊天室...")
            await client1.leave_room(second_room_id)
            await client2.leave_room(second_room_id)
            await asyncio.sleep(1)
        
        logger.info(f"用户离开第一个聊天室...")
        await client1.leave_room(room_id)
        await client2.leave_room(room_id)
        
    except Exception as e:
        logger.error(f"测试过程中出错: {str(e)}")
    finally:
        # 关闭连接和任务
        listen_task1.cancel()
        listen_task2.cancel()
        
        await client1.close()
        await client2.close()
        
        logger.info("==== 测试完成 ====")

# 自动化测试流程 - 减少默认持续时间为更快地完成测试
async def auto_setup_and_test(duration=15, ws_base_url="ws://localhost:8000", http_base_url="http://localhost:8000"):
    """
    自动设置并运行测试 - 包括注册用户、登录获取令牌和创建聊天室
    
    Args:
        duration: 测试持续时间（秒）
        ws_base_url: WebSocket服务器基础URL
        http_base_url: HTTP服务器基础URL
    """
    # 临时替换全局BASE_URL，仅在此函数作用域内有效
    global BASE_URL
    original_base_url = BASE_URL
    BASE_URL = http_base_url
    
    logger.info(f"使用HTTP基础URL: {BASE_URL}")
    logger.info(f"使用WebSocket基础URL: {ws_base_url}")
    logger.info("=== 开始自动测试流程 ===")
    
    # 设置最大重试次数
    max_retries = 3
    current_retry = 0
    
    try:
        while current_retry < max_retries:
            try:
                current_retry += 1
                logger.info(f"尝试运行测试 (尝试 {current_retry}/{max_retries})")
                
                # 步骤1: 注册两个测试用户
                logger.info("步骤1: 注册/准备测试用户")
                user1_registered = await register_user(TEST_USER)
                
                if not user1_registered:
                    logger.error(f"无法注册或验证用户1 ({TEST_USER['username']})")
                    if current_retry < max_retries:
                        logger.info("等待5秒后重试...")
                        await asyncio.sleep(5)
                        continue
                    else:
                        return
                
                user2_registered = await register_user(TEST_USER2)
                
                if not user2_registered:
                    logger.error(f"无法注册或验证用户2 ({TEST_USER2['username']})")
                    if current_retry < max_retries:
                        logger.info("等待5秒后重试...")
                        await asyncio.sleep(5)
                        continue
                    else:
                        return
                
                # 步骤2: 获取用户令牌
                logger.info("步骤2: 获取用户令牌")
                token1 = await get_auth_token(TEST_USER["username"], TEST_USER["password"])
                
                if not token1:
                    logger.error(f"无法获取用户1 ({TEST_USER['username']}) 的令牌")
                    if current_retry < max_retries:
                        logger.info("等待5秒后重试...")
                        await asyncio.sleep(5)
                        continue
                    else:
                        return
                
                token2 = await get_auth_token(TEST_USER2["username"], TEST_USER2["password"])
                
                if not token2:
                    logger.error(f"无法获取用户2 ({TEST_USER2['username']}) 的令牌")
                    if current_retry < max_retries:
                        logger.info("等待5秒后重试...")
                        await asyncio.sleep(5)
                        continue
                    else:
                        return
                
                logger.info(f"用户1令牌: {token1[:20]}...")
                logger.info(f"用户2令牌: {token2[:20]}...")
                
                # 验证令牌是否可用
                logger.info("步骤2.1: 验证令牌有效性")
                headers1 = {"Authorization": f"Bearer {token1}"}
                validate_response = requests.get(f"{BASE_URL}/api/v1/auth/me", headers=headers1)
                
                if validate_response.status_code != 200:
                    logger.error(f"用户1令牌无效: {validate_response.text}")
                    if current_retry < max_retries:
                        logger.info("等待5秒后重试...")
                        await asyncio.sleep(5)
                        continue
                    else:
                        return
                
                # 步骤3: 创建测试聊天室
                logger.info("步骤3: 创建测试聊天室")
                try:
                    room = await create_chat_room(token1)
                    room_id = room["id"]
                    logger.info(f"已创建聊天室: {room['name']} (ID: {room_id})")
                except Exception as e:
                    logger.error(f"创建聊天室失败: {str(e)}")
                    if current_retry < max_retries:
                        logger.info("等待5秒后重试...")
                        await asyncio.sleep(5)
                        continue
                    else:
                        return
                
                # 步骤4: 第二个用户加入聊天室
                logger.info("步骤4: 第二个用户加入聊天室")
                try:
                    await join_chat_room(token2, room_id)
                    logger.info(f"用户 {TEST_USER2['username']} 已加入聊天室")
                except Exception as e:
                    logger.error(f"加入聊天室失败: {str(e)}")
                    if current_retry < max_retries:
                        logger.info("等待5秒后重试...")
                        await asyncio.sleep(5)
                        continue
                    else:
                        return
                
                # 步骤5: 运行WebSocket测试
                logger.info("步骤5: 开始WebSocket测试")
                await run_test(ws_base_url, room_id, token1, token2, duration)
                
                logger.info("=== 自动测试流程完成 ===")
                # 测试成功，退出重试循环
                break
                
            except Exception as e:
                logger.error(f"自动测试过程中出错: {str(e)}")
                if current_retry < max_retries:
                    logger.info(f"等待5秒后进行第 {current_retry+1} 次重试...")
                    await asyncio.sleep(5)
                else:
                    logger.error(f"达到最大重试次数 ({max_retries})，测试失败")
                    import traceback
                    traceback.print_exc()
    finally:
        # 确保恢复原始BASE_URL
        BASE_URL = original_base_url

# 命令行入口
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="聊天室WebSocket测试工具")
    parser.add_argument("--manual", action="store_true", help="启用手动测试模式（需要提供room_id和token）")
    parser.add_argument("--ws-url", default="ws://localhost:8000", help="WebSocket服务器基础URL")
    parser.add_argument("--http-url", default="http://localhost:8000", help="HTTP服务器基础URL")
    parser.add_argument("--room-id", type=int, help="聊天室ID（手动模式必填）")
    parser.add_argument("--token1", help="第一个用户的认证令牌（手动模式必填）")
    parser.add_argument("--token2", help="第二个用户的认证令牌（手动模式必填）")
    parser.add_argument("--duration", type=int, default=15, help="测试持续时间（秒），默认15秒")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="日志级别")
    
    args = parser.parse_args()
    
    # 设置日志级别
    log_level = getattr(logging, args.log_level)
    logger.setLevel(log_level)
    
    if args.manual:
        # 手动模式 - 需要提供room_id和token
        if not all([args.room_id, args.token1, args.token2]):
            parser.error("手动模式需要指定 --room-id, --token1 和 --token2 参数")
        
        logger.info("=== 开始手动测试模式 ===")
        # 运行手动测试
        asyncio.run(run_test(args.ws_url, args.room_id, args.token1, args.token2, args.duration))
    else:
        # 默认执行自动化测试
        logger.info("=== 开始自动测试模式 ===")
        asyncio.run(auto_setup_and_test(args.duration, args.ws_url, args.http_url)) 