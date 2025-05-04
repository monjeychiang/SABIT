# WebSocket连接池配置说明

本文档详细说明了聊天系统WebSocket连接池的配置参数和使用方法。

## 配置参数

WebSocket连接池相关的配置参数主要通过环境变量进行设置，在`.env`文件中添加以下配置：

```bash
# WebSocket连接池配置
WS_MAX_GLOBAL_CONNECTIONS=1000    # 系统支持的全局最大WebSocket连接数
WS_MAX_CONNECTIONS_PER_USER=5     # 每个用户允许的最大连接数
WS_MAX_CONNECTIONS_PER_ROOM=100   # 每个聊天室允许的最大连接数
WS_MESSAGE_RATE_LIMIT=10          # 消息速率限制（每个时间窗口的最大消息数）
WS_RATE_LIMIT_WINDOW=60           # 速率限制时间窗口（秒）
```

## 参数说明

### 1. 连接数限制

- `WS_MAX_GLOBAL_CONNECTIONS`：整个系统支持的WebSocket连接总数上限。当达到此限制时，新的连接请求将被拒绝。设置过高可能导致服务器资源耗尽，设置过低则会限制系统的并发用户数。
  - 默认值：1000
  - 推荐范围：500-5000（根据服务器资源调整）

- `WS_MAX_CONNECTIONS_PER_USER`：每个用户允许同时建立的WebSocket连接数上限。这限制了单个用户可以打开的聊天室窗口数量。
  - 默认值：5
  - 推荐范围：3-10

- `WS_MAX_CONNECTIONS_PER_ROOM`：每个聊天室允许的最大连接数。这限制了一个聊天室中的最大用户数。
  - 默认值：100
  - 推荐范围：50-500（根据预期的聊天室规模调整）

### 2. 消息速率限制

- `WS_MESSAGE_RATE_LIMIT`：在指定时间窗口内，用户允许发送的最大消息数。用于防止消息洪水和滥用。
  - 默认值：10
  - 推荐范围：5-30（根据应用场景调整）

- `WS_RATE_LIMIT_WINDOW`：速率限制的时间窗口，以秒为单位。
  - 默认值：60
  - 推荐范围：30-120

## 配置示例

### 小型部署（资源受限）

```bash
WS_MAX_GLOBAL_CONNECTIONS=500
WS_MAX_CONNECTIONS_PER_USER=3
WS_MAX_CONNECTIONS_PER_ROOM=50
WS_MESSAGE_RATE_LIMIT=5
WS_RATE_LIMIT_WINDOW=60
```

### 中型部署（标准配置）

```bash
WS_MAX_GLOBAL_CONNECTIONS=1000
WS_MAX_CONNECTIONS_PER_USER=5
WS_MAX_CONNECTIONS_PER_ROOM=100
WS_MESSAGE_RATE_LIMIT=10
WS_RATE_LIMIT_WINDOW=60
```

### 大型部署（高并发）

```bash
WS_MAX_GLOBAL_CONNECTIONS=5000
WS_MAX_CONNECTIONS_PER_USER=10
WS_MAX_CONNECTIONS_PER_ROOM=500
WS_MESSAGE_RATE_LIMIT=20
WS_RATE_LIMIT_WINDOW=60
```

## 监控与调优

WebSocket连接池的状态可以通过API端点查看：

```
GET /api/v1/chatroom/stats
```

此端点返回当前WebSocket连接的统计信息，包括活跃连接数、消息速率等指标，可用于监控系统负载并调整配置参数。

## 注意事项

1. 修改配置参数后需要重启应用才能生效
2. 在高负载情况下，建议降低单用户和单聊天室的连接数限制
3. 如果使用多节点部署，请确保所有节点使用相同的配置参数
4. 消息速率限制太严格可能影响用户体验，太宽松则可能被滥用 