# 聊天室功能使用指南

## 概述

聊天室功能允许用户创建和加入实时聊天室，与其他用户进行即时通信。系统支持公开聊天室和私人聊天室两种类型，并提供丰富的API接口和WebSocket实时通信能力。

## 1. API 接口

### 1.1 创建聊天室

- 路径: `/api/v1/chatroom/rooms`
- 方法: `POST`
- 请求体:
  ```json
  {
    "name": "我的聊天室",
    "description": "这是一个聊天室描述",
    "is_public": true,
    "is_official": false
  }
  ```
- 参数说明:
  - `name`: 聊天室名称 (必填，1-100字符)
  - `description`: 聊天室描述 (可选，最多500字符)
  - `is_public`: 是否公开聊天室 (默认为 true)
  - `is_official`: 是否为官方聊天室 (仅管理员可设置为 true)
- 权限: 任何认证用户
- 返回示例:
  ```json
  {
    "id": 1,
    "name": "我的聊天室",
    "description": "这是一个聊天室描述",
    "is_public": true,
    "is_official": false,
    "created_by": 123,
    "created_at": "2023-09-10T12:34:56",
    "updated_at": "2023-09-10T12:34:56",
    "creator": {
      "id": 123,
      "username": "user123",
      "avatar_url": "https://example.com/avatar.jpg"
    },
    "member_count": 1,
    "is_member": true,
    "is_admin": true
  }
  ```

### 1.2 获取聊天室列表

- 路径: `/api/v1/chatroom/rooms`
- 方法: `GET`
- 查询参数:
  - `skip`: 跳过的记录数 (默认为 0)
  - `limit`: 返回的最大记录数 (默认为 100)
- 权限: 任何认证用户
- 返回: 聊天室列表，包括用户可见的公开聊天室和用户已加入的私有聊天室
- 返回示例:
  ```json
  [
    {
      "id": 1,
      "name": "聊天室1",
      "description": "描述1",
      "is_public": true,
      "is_official": false,
      "created_by": 123,
      "created_at": "2023-09-10T12:34:56",
      "updated_at": "2023-09-10T12:34:56",
      "creator": {
        "id": 123,
        "username": "user123",
        "avatar_url": "https://example.com/avatar.jpg"
      },
      "member_count": 5,
      "is_member": true,
      "is_admin": false
    },
    {
      "id": 2,
      "name": "聊天室2",
      "description": "描述2",
      "is_public": true,
      "is_official": true,
      "created_by": 456,
      "created_at": "2023-09-09T10:20:30",
      "updated_at": "2023-09-09T10:20:30",
      "creator": {
        "id": 456,
        "username": "admin",
        "avatar_url": null
      },
      "member_count": 20,
      "is_member": false,
      "is_admin": false
    }
  ]
  ```

### 1.3 获取聊天室详情

- 路径: `/api/v1/chatroom/rooms/{room_id}`
- 方法: `GET`
- 路径参数:
  - `room_id`: 聊天室ID
- 权限: 聊天室成员或公开聊天室的任何认证用户
- 返回: 聊天室详情，包括成员列表和最近的聊天消息
- 返回示例:
  ```json
  {
    "id": 1,
    "name": "我的聊天室",
    "description": "这是一个聊天室描述",
    "is_public": true,
    "is_official": false,
    "created_by": 123,
    "created_at": "2023-09-10T12:34:56",
    "updated_at": "2023-09-10T12:34:56",
    "creator": {
      "id": 123,
      "username": "user123",
      "avatar_url": "https://example.com/avatar.jpg"
    },
    "member_count": 3,
    "is_member": true,
    "is_admin": true,
    "members": [
      {
        "id": 1,
        "room_id": 1,
        "user_id": 123,
        "is_admin": true,
        "joined_at": "2023-09-10T12:34:56",
        "last_read_at": "2023-09-10T14:30:00",
        "user": {
          "id": 123,
          "username": "user123",
          "avatar_url": "https://example.com/avatar.jpg"
        }
      },
      {
        "id": 2,
        "room_id": 1,
        "user_id": 456,
        "is_admin": false,
        "joined_at": "2023-09-10T13:00:00",
        "last_read_at": "2023-09-10T14:15:00",
        "user": {
          "id": 456,
          "username": "user456",
          "avatar_url": null
        }
      }
    ],
    "latest_messages": [
      {
        "id": 101,
        "room_id": 1,
        "user_id": 123,
        "content": "大家好!",
        "is_system": false,
        "created_at": "2023-09-10T13:00:10",
        "user": {
          "id": 123,
          "username": "user123",
          "avatar_url": "https://example.com/avatar.jpg"
        }
      },
      {
        "id": 102,
        "room_id": 1,
        "user_id": 456,
        "content": "你好!",
        "is_system": false,
        "created_at": "2023-09-10T13:01:15",
        "user": {
          "id": 456,
          "username": "user456",
          "avatar_url": null
        }
      }
    ]
  }
  ```

### 1.4 加入聊天室

- 路径: `/api/v1/chatroom/rooms/{room_id}/join`
- 方法: `POST`
- 路径参数:
  - `room_id`: 聊天室ID
- 权限: 任何认证用户可加入公开聊天室；私有聊天室需要邀请（当前版本不支持）
- 返回示例:
  ```json
  {
    "message": "已成功加入聊天室"
  }
  ```

### 1.5 离开聊天室

- 路径: `/api/v1/chatroom/rooms/{room_id}/leave`
- 方法: `POST`
- 路径参数:
  - `room_id`: 聊天室ID
- 权限: 聊天室成员
- 返回示例:
  ```json
  {
    "message": "已成功离开聊天室"
  }
  ```

### 1.6 删除聊天室

- 路径: `/api/v1/chatroom/rooms/{room_id}`
- 方法: `DELETE`
- 路径参数:
  - `room_id`: 聊天室ID
- 权限: 聊天室创建者或管理员
- 返回示例:
  ```json
  {
    "message": "聊天室已成功删除"
  }
  ```

## 2. WebSocket 连接

为了实现实时聊天功能，您需要建立 WebSocket 连接。WebSocket 端点格式如下：

```
ws://your-server/api/v1/chatroom/ws/{room_id}/{token}
```

- `room_id`: 聊天室ID
- `token`: 用户的JWT身份验证令牌

示例：
```javascript
// 建立WebSocket连接
const token = "your_jwt_token";
const roomId = 1;
const socket = new WebSocket(`ws://localhost:8000/api/v1/chatroom/ws/${roomId}/${token}`);

// 处理连接事件
socket.onopen = function(e) {
  console.log("WebSocket 连接已建立");
};

// 接收消息
socket.onmessage = function(event) {
  const message = JSON.parse(event.data);
  console.log("收到消息:", message);
};

// 处理错误
socket.onerror = function(error) {
  console.error("WebSocket 错误:", error);
};

// 处理连接关闭
socket.onclose = function(event) {
  console.log("WebSocket 连接已关闭");
};
```

### 2.1 消息格式

#### 发送消息

当发送消息到服务器时，应使用以下格式：

```json
{
  "type": "message",
  "content": "消息内容"
}
```

#### 发送正在输入状态

当用户正在输入时，可以发送以下消息通知其他用户：

```json
{
  "type": "typing"
}
```

#### 接收消息

从服务器接收的消息可能有多种类型，包括：

- 聊天消息：
  ```json
  {
    "type": "message",
    "message_id": 103,
    "room_id": 1,
    "user_id": 123,
    "username": "user123",
    "avatar_url": "https://example.com/avatar.jpg",
    "content": "消息内容",
    "timestamp": "2023-09-10T14:30:45"
  }
  ```

- 用户上线通知：
  ```json
  {
    "type": "user_online",
    "room_id": 1,
    "user_id": 123,
    "username": "user123",
    "avatar_url": "https://example.com/avatar.jpg",
    "timestamp": "2023-09-10T14:30:00"
  }
  ```

- 用户下线通知：
  ```json
  {
    "type": "user_offline",
    "room_id": 1,
    "user_id": 123,
    "username": "user123",
    "timestamp": "2023-09-10T15:00:00"
  }
  ```

- 用户正在输入状态：
  ```json
  {
    "type": "typing",
    "room_id": 1,
    "user_id": 123,
    "username": "user123",
    "timestamp": "2023-09-10T14:35:10"
  }
  ```

- 系统通知（如用户加入/离开聊天室）：
  ```json
  {
    "type": "join",
    "room_id": 1,
    "user_id": 789,
    "username": "newuser",
    "avatar_url": null,
    "content": "newuser 加入了聊天室",
    "timestamp": "2023-09-10T14:40:00"
  }
  ```

## 3. 前端集成示例

### 3.1 获取聊天室列表

```javascript
// 获取聊天室列表
async function getChatRoomList() {
  try {
    const response = await fetch('http://localhost:8000/api/v1/chatroom/rooms', {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${yourJwtToken}`,
        'Content-Type': 'application/json'
      }
    });
    
    if (!response.ok) {
      throw new Error('获取聊天室列表失败');
    }
    
    const chatRooms = await response.json();
    console.log('聊天室列表:', chatRooms);
    
    // 渲染聊天室列表
    renderChatRoomList(chatRooms);
    
  } catch (error) {
    console.error('获取聊天室列表出错:', error);
  }
}
```

### 3.2 创建聊天室

```javascript
// 创建新聊天室
async function createChatRoom(name, description, isPublic = true) {
  try {
    const response = await fetch('http://localhost:8000/api/v1/chatroom/rooms', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${yourJwtToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        name,
        description,
        is_public: isPublic,
        is_official: false
      })
    });
    
    if (!response.ok) {
      throw new Error('创建聊天室失败');
    }
    
    const newRoom = await response.json();
    console.log('创建的聊天室:', newRoom);
    
    // 更新聊天室列表或导航到新聊天室
    navigateToChatRoom(newRoom.id);
    
  } catch (error) {
    console.error('创建聊天室出错:', error);
  }
}
```

### 3.3 建立WebSocket连接

```javascript
class ChatRoomManager {
  constructor(roomId, token) {
    this.roomId = roomId;
    this.token = token;
    this.socket = null;
    this.isConnected = false;
    this.messageCallbacks = [];
  }
  
  // 连接到聊天室
  connect() {
    const wsUrl = `ws://localhost:8000/api/v1/chatroom/ws/${this.roomId}/${this.token}`;
    this.socket = new WebSocket(wsUrl);
    
    this.socket.onopen = (event) => {
      console.log('WebSocket连接已建立');
      this.isConnected = true;
      this._notifyCallbacks({ type: 'connection', status: 'connected' });
    };
    
    this.socket.onmessage = (event) => {
      const message = JSON.parse(event.data);
      console.log('收到消息:', message);
      this._notifyCallbacks(message);
    };
    
    this.socket.onerror = (error) => {
      console.error('WebSocket错误:', error);
      this._notifyCallbacks({ type: 'error', error });
    };
    
    this.socket.onclose = (event) => {
      console.log('WebSocket连接已关闭');
      this.isConnected = false;
      this._notifyCallbacks({ type: 'connection', status: 'disconnected' });
    };
  }
  
  // 发送消息
  sendMessage(content) {
    if (!this.isConnected) {
      console.error('WebSocket未连接，无法发送消息');
      return false;
    }
    
    const message = {
      type: 'message',
      content
    };
    
    this.socket.send(JSON.stringify(message));
    return true;
  }
  
  // 发送正在输入状态
  sendTyping() {
    if (!this.isConnected) {
      return false;
    }
    
    const message = {
      type: 'typing'
    };
    
    this.socket.send(JSON.stringify(message));
    return true;
  }
  
  // 关闭连接
  disconnect() {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
      this.isConnected = false;
    }
  }
  
  // 添加消息回调
  onMessage(callback) {
    this.messageCallbacks.push(callback);
  }
  
  // 通知所有回调
  _notifyCallbacks(message) {
    this.messageCallbacks.forEach(callback => {
      try {
        callback(message);
      } catch (e) {
        console.error('消息回调执行出错:', e);
      }
    });
  }
}

// 使用示例
const chatManager = new ChatRoomManager(1, 'your_jwt_token');

// 添加消息处理回调
chatManager.onMessage(message => {
  if (message.type === 'message') {
    // 显示聊天消息
    displayChatMessage(message);
  } else if (message.type === 'typing') {
    // 显示用户正在输入指示器
    showTypingIndicator(message.username);
  } else if (message.type === 'user_online' || message.type === 'user_offline') {
    // 更新在線用戶列表
    updateOnlineUsersList();
  }
});

// 连接到聊天室
chatManager.connect();

// 当用户输入消息时发送
document.getElementById('send-button').addEventListener('click', () => {
  const messageInput = document.getElementById('message-input');
  const content = messageInput.value.trim();
  
  if (content) {
    chatManager.sendMessage(content);
    messageInput.value = '';
  }
});

// 当用户开始输入时发送输入状态
let typingTimeout = null;
document.getElementById('message-input').addEventListener('input', () => {
  if (typingTimeout) {
    clearTimeout(typingTimeout);
  } else {
    chatManager.sendTyping();
  }
  
  typingTimeout = setTimeout(() => {
    typingTimeout = null;
  }, 2000);
});
```

## 4. 测试聊天室功能

您可以使用我们提供的测试脚本来验证WebSocket连接和消息功能。测试脚本位于 `backend/tests/test_chatroom_websocket.py`。

使用方法：

```bash
python test_chatroom_websocket.py --room-id 1 --token1 "用户1的JWT令牌" --token2 "用户2的JWT令牌" --duration 30
```

参数说明：
- `--room-id`: 要测试的聊天室ID
- `--token1`: 第一个用户的JWT令牌
- `--token2`: 第二个用户的JWT令牌
- `--duration`: 测试持续时间（秒，默认60秒）
- `--base-url`: WebSocket服务器基础URL（默认为ws://localhost:8000）

## 5. 常见问题与解决方案

### 5.1 连接问题

**问题：WebSocket连接失败**

可能的原因：
- 服务器未运行或无法访问
- JWT令牌无效或已过期
- 聊天室ID不存在
- 用户没有访问私有聊天室的权限

解决方案：
- 检查服务器是否正常运行
- 检查JWT令牌是否有效，必要时刷新令牌
- 验证聊天室ID是否正确
- 确认用户有权访问该聊天室

### 5.2 消息发送问题

**问题：无法发送消息**

可能的原因：
- WebSocket连接已断开
- 消息格式不正确

解决方案：
- 检查WebSocket连接状态，如果已断开则重新连接
- 确保消息格式符合要求（有type字段和正确的内容）
- 在发送消息前检查连接状态

### 5.3 性能优化

**问题：高流量聊天室性能下降**

解决方案：
- 为大型聊天室实现消息分页加载
- 优化前端渲染，避免一次显示太多消息
- 使用虚拟滚动技术显示大量消息
- 实现自动重连机制以提高稳定性

### 5.4 断线重连

实现简单的断线重连功能：

```javascript
class ChatRoomManager {
  // 已有代码...
  
  // 添加自动重连功能
  setupAutoReconnect(maxRetries = 5, initialDelay = 1000) {
    this.reconnectAttempts = 0;
    this.maxRetries = maxRetries;
    this.reconnectDelay = initialDelay;
    
    // 监听连接关闭
    this.socket.onclose = (event) => {
      console.log('WebSocket连接已关闭');
      this.isConnected = false;
      this._notifyCallbacks({ type: 'connection', status: 'disconnected' });
      
      // 尝试重连
      this.tryReconnect();
    };
  }
  
  tryReconnect() {
    if (this.reconnectAttempts >= this.maxRetries) {
      console.log('达到最大重试次数，停止重连');
      this._notifyCallbacks({ type: 'connection', status: 'failed' });
      return;
    }
    
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1);
    
    console.log(`尝试在 ${delay}ms 后重新连接... (尝试 ${this.reconnectAttempts}/${this.maxRetries})`);
    
    setTimeout(() => {
      console.log('正在重新连接...');
      this.connect();
    }, delay);
  }
}
```

## 6. 最佳实践

1. **错误处理**：始终实现适当的错误处理，特别是对WebSocket连接失败的情况。

2. **令牌刷新**：实现令牌刷新机制，确保长时间保持连接时不会因令牌过期而断开。

3. **消息去重**：在前端实现消息去重逻辑，处理可能的消息重复问题。

4. **优雅降级**：如果WebSocket不可用，可以回退到轮询机制获取新消息。

5. **离线消息**：实现离线消息存储，用户重新上线时可以接收离线期间的消息。

6. **消息发送确认**：实现消息发送确认机制，确保消息被成功处理。

7. **数据加载优化**：对于频繁访问的数据（如聊天室列表）实现缓存策略。 