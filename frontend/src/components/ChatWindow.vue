<template>
  <Transition name="chat-fade">
    <div v-if="isOpen" class="chat-window-container">
      <div class="chat-window">
        <!-- 左侧聊天室列表 -->
        <div class="chat-rooms-sidebar">
          <!-- 搜索栏 -->
          <div class="rooms-search-bar">
            <div class="search-input-wrapper">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" class="search-icon">
                <path fill="none" d="M0 0h24v24H0z"/>
                <path d="M18.031 16.617l4.283 4.282-1.415 1.415-4.282-4.283A8.96 8.96 0 0 1 11 20c-4.968 0-9-4.032-9-9s4.032-9 9-9 9 4.032 9 9a8.96 8.96 0 0 1-1.969 5.617zm-2.006-.742A6.977 6.977 0 0 0 18 11c0-3.868-3.133-7-7-7-3.868 0-7 3.132-7 7 0 3.867 3.132 7 7 7a6.977 6.977 0 0 0 4.875-1.975l.15-.15z" fill="currentColor"/>
              </svg>
              <input type="text" placeholder="Search Room" v-model="searchQuery" class="search-input">
            </div>
          </div>
          
          <!-- 聊天室列表 -->
          <div class="rooms-list" @contextmenu.prevent="openEmptyContextMenu($event)">
            <div 
              v-for="room in filteredRooms" 
              :key="room.id" 
              class="room-item" 
              :class="{ 'active': room.id === currentRoomId, 'member': room.is_member }"
              @click="selectRoom(room.id)"
              @contextmenu.stop.prevent="openContextMenu($event, room)"
            >
              <div class="room-info">
                <div class="room-badges">
                  <div class="room-badge official" v-if="room.isOfficial">官方</div>
                  <div class="room-badge public" v-if="room.isPublic">公开</div>
                </div>
                <div class="room-name">{{ room.name }}</div>
                <div class="room-time">{{ formatTime(room.lastActivity || new Date()) }}</div>
              </div>
              <div class="room-status">
                <div class="notification-dot" v-if="room.hasNewMessages"></div>
                <div v-if="room.unreadCount > 0" class="room-unread-badge">{{ room.unreadCount > 99 ? '99+' : room.unreadCount }}</div>
                <div class="member-badge" v-if="room.is_member">已加入</div>
              </div>
            </div>
            
            <!-- 没有聊天室时显示提示 -->
            <div v-if="filteredRooms.length === 0" class="no-rooms-message">
              <p>暂无聊天室</p>
              <p class="no-rooms-hint">右击此区域创建新聊天室</p>
            </div>
          </div>
        </div>

        <!-- 右侧聊天内容区域 -->
        <div class="chat-content">
        <!-- 聊天窗口标题栏 -->
        <div class="chat-header">
          <div class="chat-title">
              <h3>{{ getCurrentRoomName() }}</h3>
              <!-- 删除管理员操作按钮 -->
          </div>
          <div class="chat-actions">
            <button @click="$emit('minimize')" class="action-button minimize" aria-label="最小化">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18">
                <path fill="none" d="M0 0h24v24H0z"/>
                <path d="M5 11h14v2H5z" fill="currentColor"/>
              </svg>
            </button>
            <button @click="$emit('close')" class="action-button close" aria-label="關閉">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18">
                <path fill="none" d="M0 0h24v24H0z"/>
                <path d="M12 10.586l4.95-4.95 1.414 1.414-4.95 4.95 4.95 4.95-1.414 1.414-4.95-4.95-4.95 4.95-1.414-1.414 4.95-4.95-4.95-4.95L7.05 5.636z" fill="currentColor"/>
              </svg>
            </button>
          </div>
        </div>
          
          <!-- 顶部通知横幅 -->
          <div class="announcement-banner" v-if="currentRoomAnnouncement">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" class="announcement-icon">
              <path fill="none" d="M0 0h24v24H0z"/>
              <path d="M12 22a2 2 0 0 0 2-2h-4a2 2 0 0 0 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z" fill="currentColor"/>
            </svg>
            <span>{{ currentRoomAnnouncement }}</span>
        </div>
        
          <!-- 非聊天室成员提示 -->
          <div v-if="currentRoom && !currentRoom.is_member" class="not-member-container">
            <div class="not-member-message">
              <p>您尚未加入此聊天室，无法查看消息</p>
              <button @click="handleJoinRoom(currentRoomId)" class="join-room-now-button" :disabled="isLoadingInitialMessages">
                <span v-if="isLoadingInitialMessages">
                  <div class="button-loader"></div>
                  正在加入...
                </span>
                <span v-else>加入此聊天室</span>
              </button>
            </div>
          </div>
          
          <!-- 聊天消息区域 - 仅成员可见 -->
          <div v-else class="chat-messages" ref="messagesContainer">
            <!-- 加載動畫 - 初始載入消息時顯示 -->
            <div v-if="isLoadingInitialMessages" class="messages-loading-overlay">
              <div class="loader"></div>
            </div>

            <!-- 加載更多消息提示 - 滾動載入更多時顯示 -->
            <div v-if="isLoadingMore && !isLoadingInitialMessages" class="loading-more-messages">
              <div class="loading-spinner"></div>
              <span>載入更多訊息...</span>
            </div>
            
            <!-- 欢迎消息 -->
            <div class="message system" v-if="currentRoomMessages.length === 0 && !isLoadingInitialMessages">
              <div class="message-content">
                <p>👋 歡迎來到 {{ getCurrentRoomName() }}！</p>
                <span class="message-time">{{ formatTime(new Date()) }}</span>
              </div>
            </div>
            
            <!-- 消息列表 - 修改後的渲染邏輯，處理連續消息 -->
            <template v-for="(message, index) in groupedMessages" :key="message.id || index">
              <!-- 系统消息 -->
              <div v-if="message.type === 'system'" class="message system">
                <div class="message-content system-content">
                  <p>{{ message.text }}</p>
                  <span class="message-time">{{ formatTime(message.time) }}</span>
                </div>
              </div>
              
              <!-- 用户自己的消息 -->
              <div v-else-if="message.type === 'user'" class="message user">
                <div class="message-wrapper">
                  <div class="message-content">
                    <p>{{ message.text }}</p>
                    <span class="message-time">{{ formatTime(message.time) }}</span>
                  </div>
                </div>
              </div>
              
              <!-- 他人消息 - 带分组逻辑 -->
              <div v-else class="message other" :class="{'consecutive': message.isConsecutive}">
                <!-- 只有不是连续消息时才显示头像和用户名 -->
                <template v-if="!message.isConsecutive">
                  <div class="message-avatar">
                    <UserAvatar 
                      :username="message.username"
                      :avatar-url="message.avatar" 
                      size="medium"
                      :no-cache="false"
                    />
                  </div>
                  <div class="message-wrapper">
                    <div class="message-header">
                      <span class="message-username">{{ message.username }}</span>
                      <span class="message-time">{{ formatTime(message.time) }}</span>
                    </div>
                    <div class="message-content">
                      <p>{{ message.text }}</p>
                    </div>
                  </div>
                </template>
                
                <!-- 连续消息只显示内容 -->
                <template v-else>
                  <div class="message-avatar invisible"></div>
                  <div class="message-wrapper consecutive-wrapper">
                    <div class="message-content consecutive-content">
                      <p>{{ message.text }}</p>
                    </div>
                  </div>
                </template>
              </div>
            </template>
          </div>
        
          <!-- 聊天输入区域 - 仅成员可见 -->
          <div v-if="currentRoom && currentRoom.is_member" class="chat-input-area">
          <input
            v-model="inputMessage"
            @keyup.enter="sendMessage"
            class="chat-input"
              placeholder="在這裡輸入..."
            :disabled="!isOnline"
          />
            <div class="input-actions">
              <button class="emoji-button">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20">
                  <path fill="none" d="M0 0h24v24H0z"/>
                  <path d="M12 22C6.477 22 2 17.523 2 12S6.477 2 12 2s10 4.477 10 10-4.477 10-10 10zm0-2a8 8 0 1 0 0-16 8 8 0 0 0 0 16zm-5-7h2a3 3 0 0 0 6 0h2a5 5 0 0 1-10 0zm1-2a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm8 0a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z" fill="currentColor"/>
                </svg>
              </button>
          <button 
            @click="sendMessage" 
            class="send-button" 
            :disabled="!inputMessage.trim() || !isOnline"
          >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20">
            <path fill="none" d="M0 0h24v24H0z"/>
            <path d="M3 13h6v-2H3V1.846a.5.5 0 0 1 .741-.438l18.462 10.154a.5.5 0 0 1 0 .876L3.741 22.592A.5.5 0 0 1 3 22.154V13z" fill="currentColor"/>
          </svg>
        </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>

  <!-- 创建新聊天室模态框 -->
  <div v-if="showNewRoomModal" class="modal-overlay">
    <div class="modal-content">
      <h3>創建新聊天室</h3>
      <!-- 聊天室名称输入 -->
      <input 
        v-model="newRoomName" 
        class="new-room-input" 
        placeholder="請輸入聊天室名稱" 
        @keyup.enter="createNewRoom"
        ref="roomNameInput"
      />
      
      <!-- 聊天室设置选项 -->
      <div class="room-options">
        <!-- 是否公开 -->
        <label class="checkbox-label">
          <input
            type="checkbox"
            v-model="newRoomOptions.isPublic"
          />
          <span>公开聊天室（允许所有用户加入）</span>
        </label>
        
        <!-- 是否官方 -->
        <label class="checkbox-label">
          <input
            type="checkbox"
            v-model="newRoomOptions.isOfficial"
          />
          <span>官方聊天室（添加官方标记）</span>
        </label>
      </div>
      
      <div class="modal-actions">
        <button @click="showNewRoomModal = false" class="cancel-button">取消</button>
        <button @click="createNewRoom" class="confirm-button" :disabled="!newRoomName.trim()">創建</button>
      </div>
    </div>
  </div>

  <!-- 确认删除聊天室模态框 -->
  <div v-if="showDeleteConfirmModal" class="modal-overlay">
    <div class="modal-content">
      <h3>删除聊天室</h3>
      <p class="confirm-message">确定要删除"{{ getCurrentRoomName() }}"聊天室吗？此操作不可逆。</p>
      <div class="modal-actions">
        <button @click="showDeleteConfirmModal = false" class="cancel-button" :disabled="isDeletingRoom">取消</button>
        <button @click="deleteCurrentRoom" class="delete-button" :disabled="isDeletingRoom">
          <span v-if="isDeletingRoom">正在删除...</span>
          <span v-else>确认删除</span>
        </button>
      </div>
    </div>
  </div>

  <!-- 加入聊天室模态框 -->
  <div v-if="showJoinRoomModal" class="modal-overlay">
    <div class="modal-content">
      <h3>加入聊天室</h3>
      <div v-if="isLoadingPublicRooms" class="loading-indicator">正在加载聊天室列表...</div>
      <div v-else-if="publicRooms.length === 0" class="no-rooms-message">
        暂无可加入的公共聊天室
      </div>
      <div v-else class="public-rooms-list">
        <div 
          v-for="room in publicRooms" 
          :key="room.id" 
          class="public-room-item"
          @click="handleJoinRoom(room.id)"
          :class="{ 'already-joined': room.is_member }"
        >
          <div class="public-room-info">
            <div class="public-room-name">{{ room.name }}</div>
            <div class="public-room-status">
              {{ room.is_member ? '已加入' : '未加入' }} 
              ({{ room.member_count || 0 }}人)
            </div>
          </div>
          <button 
            v-if="!room.is_member" 
            class="join-button"
            @click.stop="handleJoinRoom(room.id)"
            :disabled="isLoadingInitialMessages"
          >
            <span v-if="isLoadingInitialMessages && currentRoomId === room.id">
              <div class="small-loader"></div>
            </span>
            <span v-else>加入</span>
          </button>
          <div v-else class="joined-indicator">已加入</div>
        </div>
      </div>
      <div class="modal-actions">
        <button @click="refreshPublicRooms" class="refresh-button">
          刷新列表
        </button>
        <button @click="showJoinRoomModal = false" class="cancel-button">关闭</button>
      </div>
    </div>
  </div>

  <!-- 添加聊天室右键菜单 -->
  <div v-if="showContextMenu" class="context-menu" :style="contextMenuStyle">
    <!-- 管理员专用选项 - 新建聊天室 -->
    <div v-if="isUserAdmin" class="context-menu-item context-menu-admin" @click="openNewRoomModal">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16">
        <path fill="none" d="M0 0h24v24H0z"/>
        <path d="M11 11V5h2v6h6v2h-6v6h-2v-6H5v-2z" fill="currentColor"/>
      </svg>
      <span>新建聊天室</span>
    </div>
    
    <!-- 查看成员选项 - 所有用户可见，仅在有聊天室时显示 -->
    <div class="context-menu-item" @click="viewRoomMembers" v-if="contextMenuRoom">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16">
        <path fill="none" d="M0 0h24v24H0z"/>
        <path d="M12 11a5 5 0 0 1 5 5v6H7v-6a5 5 0 0 1 5-5zm0-2a3 3 0 1 1 0-6 3 3 0 0 1 0 6zm10 11v-3a3 3 0 0 0-6 0v3h6zm-2-7c1.64 0 3 1.36 3 3v2h2v-2c0-2.34-2.01-4.21-4.39-3.98C18.4 10.12 16.21 8 13.5 8H12v2h1.5c1.99 0 3.5 1.51 3.5 3.5 0 1.56-.51 2.75-1.42 3.5h2.38zM6 13c-1.64 0-3 1.36-3 3v2H1v-2c0-2.34 2.01-4.21 4.39-3.98C7.6 10.12 9.79 8 12.5 8H14v2h-1.5c-1.99 0-3.5 1.51-3.5 3.5 0 1.56.51 2.75 1.42 3.5H8.62c-1.5-.75-2.62-3-2.62-4z" fill="currentColor"/>
      </svg>
      <span>查看成员</span>
    </div>
    
    <!-- 管理员专用选项 - 管理聊天室设置 -->
    <div v-if="isUserAdmin && contextMenuRoom" class="context-menu-item context-menu-admin" @click="openRoomManagementModal">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16">
        <path fill="none" d="M0 0h24v24H0z"/>
        <path d="M12 1l9.5 5.5v11L12 23l-9.5-5.5v-11L12 1zm0 2.311L4.5 7.653v8.694l7.5 4.342 7.5-4.342V7.653L12 3.311zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm0-2a2 2 0 1 0 0-4 2 2 0 0 0 0 4z" fill="currentColor"/>
      </svg>
      <span>管理聊天室设置</span>
    </div>
    
    <!-- 退出聊天室选项 - 仅成员可见 -->
    <div class="context-menu-item" v-if="contextMenuRoom && contextMenuRoom.is_member" @click="leaveRoom">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16">
        <path fill="none" d="M0 0h24v24H0z"/>
        <path d="M5 22a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H5zm10-6l5-4-5-4v3H9v2h6v3z" fill="currentColor"/>
      </svg>
      <span>退出聊天室</span>
    </div>
    
    <!-- 管理员专用选项 - 删除聊天室 -->
    <div v-if="isUserAdmin && contextMenuRoom" class="context-menu-item context-menu-admin context-menu-danger" @click="confirmDeleteCurrentRoom">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16">
        <path fill="none" d="M0 0h24v24H0z"/>
        <path d="M17 6h5v2h-2v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V8H2V6h5V3a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v3zm1 2H6v12h12V8zm-9 3h2v6H9v-6zm4 0h2v6h-2v-6zM9 4v2h6V4H9z" fill="currentColor"/>
      </svg>
      <span>删除聊天室</span>
    </div>
    
    <!-- 加入公共聊天室选项 -->
    <div v-if="isUserAdmin && !contextMenuRoom" class="context-menu-item" @click="openJoinRoomModal">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16">
        <path fill="none" d="M0 0h24v24H0z"/>
        <path d="M12 22C6.477 22 2 17.523 2 12S6.477 2 12 2s10 4.477 10 10-4.477 10-10 10zm-4-9h8v2H8v-2z" fill="currentColor"/>
      </svg>
      <span>加入聊天室</span>
    </div>
  </div>

  <!-- 查看聊天室成员模态框 -->
  <div v-if="showMembersModal" class="modal-overlay" @click="showMembersModal = false">
    <div class="modal-content" style="max-width: 550px; width: 90%;" @click.stop>
      <h3>{{ contextMenuRoom ? contextMenuRoom.name : '' }} - 聊天室成员</h3>
      <div v-if="isLoadingMembers" class="loading-indicator">正在加载成员列表...</div>
      <div v-else-if="!roomMembers || roomMembers.length === 0" class="no-members-message">
        暂无成员信息
      </div>
      <div v-else class="room-members-list">
        <div v-for="member in roomMembers" :key="member.user.id" class="room-member-item">
          <div class="member-avatar">
            <img :src="member.user.avatar_url || 'https://via.placeholder.com/40'" alt="avatar">
          </div>
          <div class="member-info">
            <div class="member-name">{{ member.user.username }}</div>
            <div class="member-role">{{ member.is_admin ? '管理员' : '成员' }}</div>
          </div>
          <div class="member-joined-time">
            加入于: {{ formatDate(member.joined_at) }}
          </div>
        </div>
      </div>
      <div class="modal-actions">
        <button @click="showMembersModal = false" class="cancel-button">关闭</button>
      </div>
    </div>
  </div>

  <!-- 确认离开聊天室模态框 -->
  <div v-if="showLeaveConfirmModal" class="modal-overlay">
    <div class="modal-content">
      <h3>离开聊天室</h3>
      <p class="confirm-message">确定要离开"{{ contextMenuRoom ? contextMenuRoom.name : '' }}"聊天室吗？</p>
      <div class="modal-actions">
        <button @click="showLeaveConfirmModal = false" class="cancel-button" :disabled="isLeavingRoom">取消</button>
        <button @click="confirmLeaveRoom" class="delete-button" :disabled="isLeavingRoom">
          <span v-if="isLeavingRoom">正在处理...</span>
          <span v-else>确认离开</span>
        </button>
      </div>
    </div>
  </div>

  <!-- 聊天室管理设置模态框 -->
  <div v-if="showRoomManagementModal" class="modal-overlay">
    <div class="modal-content room-management-modal">
      <h3>聊天室管理设置</h3>
      
      <div class="room-management-form">
        <!-- 聊天室名称 -->
        <div class="form-group">
          <label for="room-name">聊天室名称</label>
          <input
            type="text"
            id="room-name"
            v-model="roomManagement.name"
            class="form-input"
            placeholder="输入聊天室名称"
          />
        </div>
        
        <!-- 删除聊天室描述字段 -->
        
        <!-- 人数上限 -->
        <div class="form-group">
          <label for="room-max-members">人数上限</label>
          <div class="input-with-info">
            <input
              type="number"
              id="room-max-members"
              v-model="roomManagement.maxMembers"
              class="form-input"
              min="2"
              placeholder="设置聊天室最大人数"
            />
            <div class="input-info">
              设置为0表示不限制人数
            </div>
          </div>
        </div>
        
        <!-- 是否公开 -->
        <div class="form-group">
          <label class="checkbox-label">
            <input
              type="checkbox"
              v-model="roomManagement.isPublic"
            />
            <span>公开聊天室（允许所有用户加入）</span>
          </label>
        </div>
        
        <!-- 是否官方 -->
        <div class="form-group">
          <label class="checkbox-label">
            <input
              type="checkbox"
              v-model="roomManagement.isOfficial"
            />
            <span>官方聊天室（添加官方标记）</span>
          </label>
        </div>
        
        <!-- 公告设置 -->
        <div class="form-group">
          <label for="room-announcement">聊天室公告</label>
          <textarea
            id="room-announcement"
            v-model="roomManagement.announcement"
            class="form-textarea"
            placeholder="设置聊天室公告"
            rows="3"
          ></textarea>
        </div>
      </div>
      
      <div class="modal-actions">
        <button @click="showRoomManagementModal = false" class="cancel-button">取消</button>
        <button @click="saveRoomSettings" class="confirm-button">保存设置</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, reactive, onMounted, onUnmounted, nextTick } from 'vue'
import { useUserStore } from '@/stores/user'
import { useChatroomStore } from '@/stores/chatroom'
import { useAuthStore } from '@/stores/auth' // 添加引入auth store
import axios from 'axios'
import UserAvatar from '@/components/UserAvatar.vue' // 確保正確導入頭像組件

// 获取用户store和聊天store
const userStore = useUserStore()
const chatroomStore = useChatroomStore()
const authStore = useAuthStore() // 初始化auth store

// 控制聊天窗口状态的props和emits
const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close', 'minimize'])

// 聊天窗口状态
const messagesContainer = ref(null) // 消息容器引用
const inputMessage = ref('') // 输入框内容
const searchQuery = ref('') // 搜索查询
const newRoomName = ref('') // 新聊天室名称
const newRoomOptions = ref({ // 新聊天室选项
  isPublic: true,
  isOfficial: false
})
const showNewRoomModal = ref(false) // 是否显示创建聊天室模态框
const showDeleteConfirmModal = ref(false) // 是否显示删除确认模态框
const showJoinRoomModal = ref(false) // 是否显示加入聊天室模态框
const isLoadingPublicRooms = ref(false) // 是否正在加载公共聊天室
const publicRooms = ref([]) // 公共聊天室列表
const roomNameInput = ref(null) // 聊天室名称输入框引用
const currentRoomAnnouncement = ref('') // 当前聊天室公告

// 消息加載相關狀態
const isLoadingInitialMessages = ref(false); // 添加新狀態：初始加載消息狀態
const isLoadingMore = ref(false);
const scrollPosition = ref(null);
const hasMoreMessagesToLoad = ref(true);

// 聊天室管理相关状态
const showRoomManagementModal = ref(false) // 是否显示聊天室管理模态框
const roomManagement = ref({
  name: '',
  description: '',
  maxMembers: 0,
  isPublic: true,
  isOfficial: false,
  announcement: ''
})

// 计算属性：是否在线
const isOnline = computed(() => chatroomStore.isConnected)

// 计算属性：当前聊天室ID
const currentRoomId = computed({
  get: () => chatroomStore.currentRoomId,
  set: (value) => {
    chatroomStore.currentRoomId = value
  }
})

// 计算属性：当前聊天室消息
const currentRoomMessages = computed(() => {
  // 从chatroomStore获取当前聊天室的消息
  const messages = chatroomStore.currentRoomMessages || []
  const currentUserId = userStore.user?.id
  
  // 转换数据格式以适应模板
  return messages.map(msg => {
    // 判断消息类型：
    // 1. 系统消息 - system
    // 2. 自己发送的消息 - user
    // 3. 其他人发送的消息 - other
    let type = 'other';
    if (msg.isSystem) {
      type = 'system';
    } else if (msg.userId === currentUserId) {
      type = 'user';
    }
    
    return {
      id: msg.id,
      text: msg.content,
      username: msg.username,
      avatar: msg.avatar,
      time: msg.timestamp,
      type: type,
      userId: msg.userId
    }
  })
})

// 计算属性：当前聊天室
const currentRoom = computed(() => {
  if (!currentRoomId.value) return null
  const room = chatroomStore.rooms.find(r => r.id === currentRoomId.value)
  return room || null
})

// 计算属性：聊天室列表
const filteredRooms = computed(() => {
  const rooms = chatroomStore.roomsWithUnread || []
  if (!searchQuery.value.trim()) return rooms
  
  const query = searchQuery.value.toLowerCase()
  return rooms.filter(room => room.name.toLowerCase().includes(query))
})

// 获取当前聊天室名称
const getCurrentRoomName = () => {
  if (!currentRoom.value) return '聊天窗口'
  return currentRoom.value.name
}

// 选择聊天室
const selectRoom = async (roomId) => {
  if (currentRoomId.value === roomId) return
  
  // 设置当前聊天室ID
  currentRoomId.value = roomId
  
  // 設置加載狀態
  isLoadingInitialMessages.value = true;
  
  try {
    // 加載聊天室消息
    await chatroomStore.loadRoomMessages(roomId)
    
    // 标记该聊天室所有消息为已读
    chatroomStore.markRoomAsRead(roomId)
    
    // 获取当前聊天室信息，包括公告
    try {
      const response = await axios.get(`/api/v1/chatroom/rooms/${roomId}`)
      if (response.data && response.data.announcement) {
        currentRoomAnnouncement.value = response.data.announcement
      } else {
        currentRoomAnnouncement.value = ''
      }
    } catch (error) {
      console.error('获取聊天室详情失败:', error)
      currentRoomAnnouncement.value = ''
    }
  } catch (error) {
    console.error('載入聊天室訊息失敗:', error)
  } finally {
    // 重置加載狀態
    isLoadingInitialMessages.value = false;
    
    // 滚动到底部
    await nextTick()
    scrollToBottom()
  }
}

// 發送消息
const sendMessage = () => {
  const content = inputMessage.value.trim()
  if (!content || !currentRoomId.value) return
  
  // 使用chatroomStore發送消息
  console.log(`[UI] 發送消息到聊天室 ${currentRoomId.value}:`, content);
  
  const result = chatroomStore.sendChatMessage(content)
  console.log(`[UI] 消息發送結果:`, result);
  
  // 清空輸入框
  inputMessage.value = ''
}

// 创建新聊天室
const createNewRoom = async () => {
  const name = newRoomName.value.trim()
  if (!name) return
  
  try {
    const response = await axios.post('/api/v1/chatroom/rooms', {
      name,
      description: '',
      is_public: newRoomOptions.value.isPublic,
      is_official: newRoomOptions.value.isOfficial
    })
    
    // 关闭模态框
    showNewRoomModal.value = false
    newRoomName.value = ''
    // 重置选项为默认值
    newRoomOptions.value = {
      isPublic: true,
      isOfficial: false
    }
    
    // 重新加载聊天室列表并选择新创建的聊天室
    await chatroomStore.fetchUserRooms()
    if (response.data && response.data.id) {
      selectRoom(response.data.id)
    }
  } catch (error) {
    console.error('创建聊天室失败:', error)
  }
}

// 删除当前聊天室
const deleteCurrentRoom = async () => {
  if (!currentRoomId.value) return
  
  // 设置加载状态
  isDeletingRoom.value = true
  
  try {
    // 保存当前聊天室ID，因为在删除成功后我们会将currentRoomId.value设为null
    const roomIdToDelete = currentRoomId.value
    
    // 调用API删除聊天室
    await axios.delete(`/api/v1/chatroom/rooms/${roomIdToDelete}`)
    
    // 关闭模态框并重置当前聊天室
    showDeleteConfirmModal.value = false
    currentRoomId.value = null
    
    // 重要：清除聊天室的消息记录
    chatroomStore.clearRoomMessages(roomIdToDelete)
    
    // 重新加载聊天室列表
    await chatroomStore.fetchUserRooms()
  } catch (error) {
    console.error('删除聊天室失败:', error)
    // 显示错误提示
    alert(`删除聊天室失败: ${error.response?.data?.detail || '服务器错误'}`)
  } finally {
    // 重置加载状态
    isDeletingRoom.value = false
  }
}

// 确认删除聊天室
const confirmDeleteRoom = () => {
  showDeleteConfirmModal.value = true
}

// 処理加入聊天室
const handleJoinRoom = async (roomId) => {
  try {
    // 設置加載狀態
    isLoadingInitialMessages.value = true;
    
    const success = await chatroomStore.joinRoom(roomId)
    if (success) {
      // 如果模態框是打開的，關閉它
      showJoinRoomModal.value = false;
      
      // 刷新房间列表
      await chatroomStore.fetchUserRooms();
      
      // 選擇剛加入的房間 - 不需要再設置加載狀態，因為 selectRoom 已有處理
      await selectRoom(roomId);
    }
  } catch (error) {
    console.error('加入聊天室失敗:', error);
  } finally {
    isLoadingInitialMessages.value = false;
  }
}

// 打开加入聊天室模态框
const openJoinRoomModal = async () => {
  showJoinRoomModal.value = true
  
  // 加载公共聊天室列表
  await refreshPublicRooms()
}

// 加载公共聊天室列表
const refreshPublicRooms = async () => {
  isLoadingPublicRooms.value = true
  try {
    const response = await axios.get('/api/v1/chatroom/rooms')
    publicRooms.value = response.data.filter(r => r.is_public && !r.is_member)
  } catch (error) {
    console.error('加载公共聊天室失败:', error)
  } finally {
    isLoadingPublicRooms.value = false
  }
}

// 打开创建聊天室模态框
const openNewRoomModal = () => {
  showNewRoomModal.value = true
  // 重置表单
  newRoomName.value = ''
  newRoomOptions.value = {
    isPublic: true,
    isOfficial: false
  }
  // 在下一个 DOM 更新周期后，聚焦到输入框
  nextTick(() => {
    roomNameInput.value?.focus()
  })
}

// 打开聊天室管理模态框
const openRoomManagementModal = async () => {
  // 如果是从右键菜单点击，使用contextMenuRoom
  const roomToManage = contextMenuRoom.value || currentRoom.value
  
  if (!roomToManage) return
  
  try {
    // 获取最新的聊天室详情
    const response = await axios.get(`/api/v1/chatroom/rooms/${roomToManage.id}`)
    const roomData = response.data
    
    // 初始化表单数据
    roomManagement.value = {
      name: roomData.name || '',
      maxMembers: roomData.max_members || 0,
      isPublic: roomData.is_public || false,
      isOfficial: roomData.is_official || false,
      announcement: roomData.announcement || ''
    }
    
    // 显示模态框
    showRoomManagementModal.value = true
    
    // 如果是从右键菜单打开的，关闭上下文菜单
    if (contextMenuRoom.value) {
      closeContextMenu()
    }
  } catch (error) {
    console.error('获取聊天室详情失败:', error)
    alert(`获取聊天室详情失败: ${error.response?.data?.detail || '服务器错误'}`)
  }
}

// 保存聊天室设置
const saveRoomSettings = async () => {
  if (!currentRoom.value) return
  
  try {
    const response = await axios.patch(`/api/v1/chatroom/rooms/${currentRoom.value.id}`, {
      name: roomManagement.value.name,
      max_members: roomManagement.value.maxMembers,
      is_public: roomManagement.value.isPublic,
      is_official: roomManagement.value.isOfficial,
      announcement: roomManagement.value.announcement
    })
    
    // 更新本地聊天室信息
    if (response.data) {
      // 更新聊天室列表
      await chatroomStore.fetchUserRooms()
      
      // 更新当前聊天室公告
      if (roomManagement.value.announcement) {
        currentRoomAnnouncement.value = roomManagement.value.announcement
      } else {
        currentRoomAnnouncement.value = ''
      }
    }
    
    // 关闭模态框
    showRoomManagementModal.value = false
  } catch (error) {
    console.error('保存聊天室设置失败:', error)
  }
}

// 格式化时间
const formatTime = (timestamp) => {
  if (!timestamp) return '';
  
  const date = new Date(timestamp);
  if (isNaN(date.getTime())) {
    return '';
  }
  
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  
  // 刚刚 - 1分钟内
  if (diffMins < 1) {
    return '剛剛';
  }
  
  // xx分钟前 - 1小时内
  if (diffMins < 60) {
    return `${diffMins}分鐘前`;
  }
  
  // 今天 HH:MM - 24小时内
  if (diffDays < 1) {
    return `今天 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
  }
  
  // 昨天 HH:MM - 48小时内
  if (diffDays === 1) {
    return `昨天 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
  }
  
  // YYYY-MM-DD HH:MM - 其他时间
  return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
};

// 上下文菜单
const contextMenu = reactive({
  show: false,
  x: 0,
  y: 0,
  roomId: null
})

// 打开上下文菜单
const openContextMenu = (event, room) => {
  contextMenu.show = true
  contextMenu.x = event.clientX
  contextMenu.y = event.clientY
  contextMenu.roomId = room.id
  
  // 点击其他区域关闭菜单
  document.addEventListener('click', closeContextMenu, { once: true })
}

// 关闭上下文菜单
const closeContextMenu = () => {
  contextMenu.show = false
}
  
  // 滚动到底部
const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 监听当前聊天室变化，滚动到底部
watch(currentRoomMessages, () => {
  nextTick(() => {
    scrollToBottom()
  })
})

// 定義處理新消息事件的函數
const handleNewMessage = (event) => {
  console.log('[ChatWindow] 收到新消息事件，更新UI', event.detail || {});
  // 強制下一個tick更新UI
  nextTick(() => {
    scrollToBottom();
    // 可以嘗試額外的強制更新方法
    forceUpdate();
  });
};

// 組件掛載時執行
onMounted(async () => {
  // 初始化聊天室列表
  if (userStore.isAuthenticated) {
    // 只在用戶首次打開聊天窗口且尚未加載聊天室列表時加載
    if (chatroomStore.rooms.length === 0) {
      await chatroomStore.fetchUserRooms()
      
      // 如果有聊天室，選擇第一個
      if (chatroomStore.rooms.length > 0) {
        isLoadingInitialMessages.value = true;
        try {
          await selectRoom(chatroomStore.rooms[0].id)
        } finally {
          isLoadingInitialMessages.value = false;
        }
      }
    } else if (currentRoomId.value) {
      // 如果已有當前聊天室，加載其消息和公告
      isLoadingInitialMessages.value = true;
      try {
        await chatroomStore.loadRoomMessages(currentRoomId.value)
        try {
          const response = await axios.get(`/api/v1/chatroom/rooms/${currentRoomId.value}`)
          if (response.data && response.data.announcement) {
            currentRoomAnnouncement.value = response.data.announcement
          }
        } catch (error) {
          console.error('初始化時獲取聊天室詳情失敗:', error)
        }
      } finally {
        isLoadingInitialMessages.value = false;
      }
    }
  }
  
  // 註冊事件監聽器
  window.addEventListener('chat:message-received', handleNewMessage);
  
  // 處理點擊外部關閉上下文菜單
  document.addEventListener('click', (event) => {
    if (contextMenu.show) {
      // 修正選擇器，使用正確的類名
      const isClickInside = event.target.closest('.context-menu')
      if (!isClickInside) {
        closeContextMenu()
      }
    }
  })
})

// 強制更新函數
const forceUpdate = () => {
  if (messagesContainer.value) {
    // 嘗試觸發DOM重繪
    const currentScrollTop = messagesContainer.value.scrollTop;
    const currentScrollHeight = messagesContainer.value.scrollHeight;
    
    // 設置滾動位置，確保內容可見
    setTimeout(() => {
      messagesContainer.value.scrollTop = currentScrollHeight;
    }, 10);
  }
};

// 组件卸载时执行
onUnmounted(() => {
  // 移除事件监听器
  document.removeEventListener('click', closeContextMenu);
  
  // 確保移除正確的消息事件處理函數
  // window.removeEventListener('chat:message-received', () => {}); // 這是錯誤的寫法
  window.removeEventListener('chat:message-received', handleNewMessage);
})

// 计算属性：判断当前用户是否为管理员
const isUserAdmin = computed(() => {
  // 使用 userStore 的 isAdmin 計算屬性
  return userStore.isAdmin
})

// 修复 showContextMenu 计算属性
const showContextMenu = computed(() => contextMenu.show)

// 添加 contextMenuStyle 计算属性
const contextMenuStyle = computed(() => {
  return {
    top: `${contextMenu.y}px`,
    left: `${contextMenu.x}px`
  }
})

// 添加 contextMenuRoom 计算属性
const contextMenuRoom = computed(() => {
  if (!contextMenu.roomId) return null
  return chatroomStore.rooms.find(r => r.id === contextMenu.roomId) || null
})

// 添加 showMembersModal 和 showLeaveConfirmModal 状态
const showMembersModal = ref(false)
const showLeaveConfirmModal = ref(false)
const roomMembers = ref([])
const isLoadingMembers = ref(false)

// 查看聊天室成员
const viewRoomMembers = async () => {
  if (!contextMenuRoom.value) return
  
  showMembersModal.value = true
  isLoadingMembers.value = true
  
  try {
    // 获取聊天室成员列表
    const response = await axios.get(`/api/v1/chatroom/rooms/${contextMenuRoom.value.id}/members`)
    roomMembers.value = response.data || []
  } catch (error) {
    console.error('获取聊天室成员失败:', error)
    // 显示错误提示
    roomMembers.value = []
    alert(`获取成员列表失败: ${error.response?.data?.detail || '服务器错误'}`)
  } finally {
    isLoadingMembers.value = false
  }
  
  // 关闭上下文菜单
  closeContextMenu()
}

// 退出聊天室确认
const leaveRoom = () => {
  if (!contextMenuRoom.value) return
  
  showLeaveConfirmModal.value = true
  closeContextMenu()
}

// 添加是否正在退出聊天室的状态
const isLeavingRoom = ref(false)

// 确认退出聊天室
const confirmLeaveRoom = async () => {
  if (!contextMenuRoom.value) return
  
  // 设置加载状态
  isLeavingRoom.value = true
  
  try {
    // 调用API退出聊天室 - 修改为使用POST请求和正确的路径
    await axios.post(`/api/v1/chatroom/rooms/${contextMenuRoom.value.id}/leave`)
    
    // 关闭模态框
    showLeaveConfirmModal.value = false
    
    // 如果当前选中的就是要退出的聊天室，清除选择
    if (currentRoomId.value === contextMenuRoom.value.id) {
      currentRoomId.value = null
    }
    
    // 重新加载聊天室列表
    await chatroomStore.fetchUserRooms()
    
    // 如果还有其他聊天室，选择第一个
    if (chatroomStore.rooms.length > 0 && !currentRoomId.value) {
      selectRoom(chatroomStore.rooms[0].id)
    }
  } catch (error) {
    console.error('退出聊天室失败:', error)
    // 显示错误提示
    alert(`退出聊天室失败: ${error.response?.data?.detail || '服务器错误'}`)
  } finally {
    // 重置加载状态
    isLeavingRoom.value = false
  }
}

// 格式化日期
const formatDate = (dateString) => {
  if (!dateString) return ''
  
  const date = new Date(dateString)
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

// 添加是否正在删除聊天室的状态
const isDeletingRoom = ref(false)

// 处理通过右键菜单删除聊天室
const confirmDeleteCurrentRoom = () => {
  if (!contextMenuRoom.value) return
  
  // 将当前房间ID设置为右键点击的房间ID
  currentRoomId.value = contextMenuRoom.value.id
  
  // 打开删除确认对话框
  showDeleteConfirmModal.value = true
  
  // 关闭上下文菜单
  closeContextMenu()
}

// 打开空列表右键菜单
const openEmptyContextMenu = (event) => {
  // 只有当没有聊天室时才打开菜单
  if (filteredRooms.value.length === 0) {
    contextMenu.show = true
    contextMenu.x = event.clientX
    contextMenu.y = event.clientY
    contextMenu.roomId = null
    
    // 点击其他区域关闭菜单
    document.addEventListener('click', closeContextMenu, { once: true })
  }
}

// 计算属性：分组后的消息
const groupedMessages = computed(() => {
  // 将消息分组，处理连续消息
  const messages = currentRoomMessages.value || [];
  const grouped = [];
  
  // 设置连续消息的最大时间间隔(毫秒)
  const MAX_TIME_DIFF = 5 * 60 * 1000; // 5分钟
  
  messages.forEach((message, index) => {
    // 克隆消息对象，避免修改原始数据
    const clonedMessage = { ...message };
    
    // 判断是否为连续消息
    if (index > 0) {
      const prevMessage = messages[index - 1];
      const isSameUser = prevMessage.userId === message.userId && prevMessage.type === message.type;
      let prevTime = new Date(prevMessage.time).getTime();
      let currTime = new Date(message.time).getTime();
      
      // 如果时间解析失败，使用当前时间
      if (isNaN(prevTime) || isNaN(currTime)) {
        console.warn('消息时间格式解析错误，使用默认值', prevMessage.time, message.time);
        prevTime = Date.now() - 1000;
        currTime = Date.now();
      }
      
      const isCloseInTime = (currTime - prevTime) < MAX_TIME_DIFF;
      
      // 如果是同一用户在短时间内的连续消息，标记为连续消息
      clonedMessage.isConsecutive = isSameUser && isCloseInTime && message.type === 'other';
    } else {
      clonedMessage.isConsecutive = false;
    }
    
    grouped.push(clonedMessage);
  });
  
  return grouped;
});

// 處理消息容器滾動事件，用於檢測是否需要加載更多歷史消息
const handleMessagesScroll = async () => {
  if (!messagesContainer.value) return;
  
  // 當滾動到頂部時加載更多消息
  // 滾動位置小於50px時觸發加載
  if (messagesContainer.value.scrollTop < 50 && !isLoadingMore.value && hasMoreMessagesToLoad.value && currentRoomId.value) {
    // 保存當前捲動位置和高度
    const oldScrollHeight = messagesContainer.value.scrollHeight;
    
    // 設置加載狀態
    isLoadingMore.value = true;
    
    try {
      // 調用store方法加載更多消息
      const hasMore = await chatroomStore.loadMoreMessages(currentRoomId.value);
      
      // 更新是否還有更多消息可加載
      hasMoreMessagesToLoad.value = hasMore;
      
      // 加載完成後恢復滾動位置
      await nextTick();
      if (messagesContainer.value) {
        // 計算新增內容的高度差
        const newScrollHeight = messagesContainer.value.scrollHeight;
        const heightDiff = newScrollHeight - oldScrollHeight;
        
        // 設置滾動位置，保持用戶查看的位置不變
        messagesContainer.value.scrollTop = heightDiff + 50;
      }
    } catch (error) {
      console.error('加載更多消息失敗:', error);
    } finally {
      // 重置加載狀態
      isLoadingMore.value = false;
    }
  }
};
</script>

<style scoped>
.chat-window-container {
  position: fixed;
  bottom: 30px;
  right: 30px;
  z-index: 998;
  width: 850px;
  max-width: calc(100vw - 40px);
}

.chat-window {
  display: flex;
  height: 550px;
  max-height: calc(100vh - 100px);
  background-color: var(--background-color, #ffffff);
  border-radius: 8px;
  box-shadow: 0 5px 20px rgba(0, 0, 0, 0.2);
  overflow: hidden;
  border: 1px solid var(--border-color, #e0e0e0);
  color: var(--text-color, #333333);
}

/* 左侧聊天室列表样式 */
.chat-rooms-sidebar {
  width: 240px; /* 缩小聊天室列表宽度，原来是280px */
  border-right: 1px solid var(--border-color, #e0e0e0);
  display: flex;
  flex-direction: column;
  background-color: var(--sidebar-bg, #f8f9fa);
}

.rooms-search-bar {
  padding: 15px;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
}

.search-input-wrapper {
  display: flex;
  align-items: center;
  background-color: var(--input-bg, #f0f0f0);
  border-radius: 20px;
  padding: 8px 12px;
}

.search-icon {
  color: var(--text-secondary, #666666);
  margin-right: 8px;
}

.search-input {
  background: none;
  border: none;
  outline: none;
  color: var(--text-color, #333333);
  width: 100%;
  font-size: 14px;
}

.search-input::placeholder {
  color: var(--text-secondary, #666666);
}

.rooms-list {
  flex: 1;
  overflow-y: auto;
}

.room-item {
  padding: 12px 15px;
  cursor: pointer;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: background-color 0.2s;
}

.room-item:hover {
  background-color: var(--hover-color, #f0f0f0);
}

.room-item.active {
  background-color: var(--active-color, #e6f7ff);
}

/* 删除背景颜色设置 */

.room-info {
  flex: 1;
}

.room-badges {
  display: flex;
  gap: 5px;
  margin-bottom: 5px;
}

.room-badge {
  display: inline-block;
  font-size: 10px;
  padding: 2px 5px;
  border-radius: 3px;
  font-weight: bold;
}

.room-badge.official {
  background-color: var(--badge-color, #f0b90b);
  color: var(--badge-text, #000000);
}

.room-badge.public {
  background-color: #52c41a;
  color: white;
}

.room-name {
  font-weight: 500;
  margin-bottom: 4px;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.room-time {
  font-size: 12px;
  color: var(--text-secondary, #666666);
}

.room-status {
  display: flex;
  align-items: center;
}

.notification-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--notification-color, #f44336);
}

.room-unread-badge {
  background-color: var(--error-color, #ff4d4f);
  color: white;
  font-size: 10px;
  font-weight: bold;
  border-radius: 10px;
  padding: 1px 6px;
  margin-right: 5px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  min-width: 16px;
  text-align: center;
}

.member-badge {
  font-size: 10px;
  color: var(--success-color, #4caf50);
  background-color: rgba(76, 175, 80, 0.1);
  padding: 2px 6px;
  border-radius: 10px;
  border: 1px solid var(--success-color, #4caf50);
}

/* 右侧聊天内容区域样式 */
.chat-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: var(--chat-bg, #ffffff);
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  background-color: var(--header-bg, #ffffff);
  color: var(--text-color, #333333);
  border-bottom: 1px solid var(--border-color, #e0e0e0);
}

.chat-title h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
}

.chat-actions {
  display: flex;
  gap: 10px;
}

.action-button {
  background: none;
  border: none;
  color: var(--text-color, #333333);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  transition: background-color 0.2s;
}

.action-button:hover {
  background-color: var(--button-hover, rgba(0, 0, 0, 0.1));
}

.announcement-banner {
  display: flex;
  align-items: center;
  padding: 10px 15px;
  background-color: var(--announcement-bg, rgba(240, 185, 11, 0.15));
  color: var(--announcement-text, #b87c00);
  font-size: 13px;
  font-weight: 500;
  border-bottom: 1px solid rgba(186, 132, 0, 0.3);
  line-height: 1.4;
  overflow-wrap: break-word;
}

.announcement-icon {
  flex-shrink: 0;
  margin-right: 10px;
  color: var(--announcement-text, #b87c00);
}

.chat-messages {
  flex: 1;
  padding: 15px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 15px;
  background-color: var(--chat-bg, #ffffff);
}

.loading-more-messages {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px;
  margin-bottom: 10px;
  color: var(--text-secondary, #666666);
  font-size: 12px;
}

.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(0, 0, 0, 0.1);
  border-top-color: var(--primary-color, #f0b90b);
  border-radius: 50%;
  margin-right: 8px;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.message {
  display: flex;
  margin-bottom: 5px;
}

.message-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  overflow: hidden;
  margin-right: 10px;
  flex-shrink: 0;
}

.message-avatar :deep(.user-avatar-component) {
  width: 30px;
  height: 30px;
  min-width: 30px;
  min-height: 30px;
  aspect-ratio: 1/1;
}

.message-wrapper {
  flex: 1;
}

.message-header {
  display: flex;
  align-items: center;
  margin-bottom: 3px;
}

.message-username {
  font-weight: 500;
  font-size: 14px;
  margin-right: 8px;
  color: var(--username-color, #f0b90b);
}

.message-content {
  font-size: 14px;
  line-height: 1.4;
  word-break: break-word;
}

.message-content p {
  margin: 0;
  white-space: pre-line;
}

.message-time {
  font-size: 10px;
  color: var(--text-secondary, #666666);
  margin-top: 2px;
  display: inline-block;
}

.message.user {
  justify-content: flex-end;
}

.message.user .message-content {
  background-color: var(--user-msg-bg, #e6f7ff);
  color: var(--text-color, #333333);
  padding: 8px 12px;
  border-radius: 12px;
  border-bottom-right-radius: 4px;
  max-width: 80%;
}

.message.system .message-content {
  color: var(--text-color, #333333);
}

.message.other .message-content {
  background-color: var(--other-msg-bg, #f5f5f5);
  color: var(--text-color, #333333);
  padding: 8px 12px;
  border-radius: 12px;
  border-bottom-left-radius: 4px;
  max-width: 80%;
}

.message.other .message-username {
  color: var(--username-color, #f0b90b);
  font-weight: 500;
}

.typing-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
}

.typing-indicator span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: var(--text-secondary, #666666);
  animation: typing 1s infinite alternate;
}

.typing-indicator span:nth-child(1) {
  animation-delay: 0s;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.3s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.6s;
}

@keyframes typing {
  0% {
    transform: translateY(0px);
  }
  100% {
    transform: translateY(-5px);
  }
}

.chat-input-area {
  display: flex;
  padding: 12px 15px;
  background-color: var(--input-area-bg, #f8f9fa);
  border-top: 1px solid var(--border-color, #e0e0e0);
}

.chat-input {
  flex: 1;
  padding: 10px 15px;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 20px;
  font-size: 14px;
  outline: none;
  background-color: var(--input-bg, #f0f0f0);
  color: var(--text-color, #333333);
}

.chat-input:focus {
  border-color: var(--focus-color, #f0b90b);
}

.chat-input:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.input-actions {
  display: flex;
  margin-left: 10px;
  gap: 5px;
}

.emoji-button {
  background: none;
  border: none;
  color: var(--text-secondary, #666666);
  cursor: pointer;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s;
}

.emoji-button:hover {
  color: var(--text-color, #333333);
}

.send-button {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background-color: var(--primary-color, #f0b90b);
  color: var(--button-text, #000000);
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.2s;
}

.send-button:hover {
  background-color: var(--primary-hover, #e0aa0a);
}

.send-button:disabled {
  background-color: var(--disabled-color, #cccccc);
  color: var(--text-secondary, #666666);
  cursor: not-allowed;
}

/* 模态框样式 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background-color: var(--modal-bg, #ffffff);
  border-radius: 8px;
  padding: 20px;
  width: 80%;
  max-width: 300px;
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
}

.modal-content h3 {
  margin-top: 0;
  margin-bottom: 15px;
  font-size: 18px;
  color: var(--text-color, #333333);
}

.new-room-input {
  width: 100%;
  padding: 10px;
  border-radius: 6px;
  border: 1px solid var(--border-color, #e0e0e0);
  margin-bottom: 15px;
  box-sizing: border-box;
  font-size: 14px;
  background-color: var(--input-bg, #f0f0f0);
  color: var(--text-color, #333333);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.cancel-button, .confirm-button {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
}

.cancel-button {
  background-color: var(--button-secondary, #f5f5f5);
  border: 1px solid var(--border-color, #e0e0e0);
  color: var(--text-color, #333333);
}

.confirm-button {
  background-color: var(--primary-color, #f0b90b);
  border: none;
  color: var(--button-text, #000000);
}

.confirm-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 过渡动画 */
.chat-fade-enter-active,
.chat-fade-leave-active {
  transition: transform 0.3s, opacity 0.3s;
}

.chat-fade-enter-from,
.chat-fade-leave-to {
  transform: translateY(20px);
  opacity: 0;
}

/* 响应式设计 */
@media (max-width: 900px) {
  .chat-window-container {
    width: 90vw;
    height: 80vh;
    position: fixed;
    top: 10vh;
    right: 5vw;
    bottom: auto;
  }
  
  .chat-window {
    height: 100%;
    max-height: none;
  }
}

@media (max-width: 700px) {
  .chat-window {
    flex-direction: column;
  }
  
  .chat-rooms-sidebar {
    width: 100%;
    height: 35%; /* 略微减少高度比例，原来是40% */
    min-height: 180px; /* 减少最小高度，原来是200px */
    border-right: none;
    border-bottom: 1px solid var(--border-color, #e0e0e0);
  }
  
  .chat-content {
    height: 65%; /* 增加内容区域比例 */
  }
}

@media (max-width: 480px) {
  .chat-window-container {
    width: 100vw;
    height: 100vh;
    right: 0;
    top: 0;
    bottom: 0;
  }
  
  .room-item {
    padding: 10px;
  }
  
  .chat-header, .chat-input-area {
    padding: 10px;
  }
  
  .chat-messages {
    padding: 10px;
  }
}

/* 深色模式样式 */
:root.dark .chat-window,
:root[data-theme='dark'] .chat-window {
  background-color: var(--dark-background-color, #1a1a1a);
  border-color: var(--dark-border-color, #333333);
  color: var(--dark-text-color, #e0e0e0);
}

:root.dark .chat-rooms-sidebar,
:root[data-theme='dark'] .chat-rooms-sidebar {
  background-color: var(--dark-sidebar-bg, #1a1a1a);
  border-right-color: var(--dark-border-color, #333333);
}

:root.dark .rooms-search-bar,
:root[data-theme='dark'] .rooms-search-bar {
  border-bottom-color: var(--dark-border-color, #333333);
}

:root.dark .search-input-wrapper,
:root[data-theme='dark'] .search-input-wrapper {
  background-color: var(--dark-input-bg, #333333);
}

:root.dark .search-input,
:root[data-theme='dark'] .search-input {
  color: var(--dark-text-color, #e0e0e0);
}

:root.dark .search-icon,
:root.dark .search-input::placeholder,
:root[data-theme='dark'] .search-icon,
:root[data-theme='dark'] .search-input::placeholder {
  color: var(--dark-text-secondary, #808080);
}

:root.dark .room-item,
:root[data-theme='dark'] .room-item {
  border-bottom-color: var(--dark-border-color, #333333);
}

:root.dark .room-item:hover,
:root[data-theme='dark'] .room-item:hover {
  background-color: var(--dark-hover-color, #2a2a2a);
}

:root.dark .room-item.active,
:root[data-theme='dark'] .room-item.active {
  background-color: var(--dark-active-color, #2c2c2c);
}

/* 删除深色模式下的特殊背景颜色设置 */

:root.dark .room-time,
:root[data-theme='dark'] .room-time {
  color: var(--dark-text-secondary, #808080);
}

:root.dark .chat-content,
:root[data-theme='dark'] .chat-content {
  background-color: var(--dark-chat-bg, #1a1a1a);
}

:root.dark .chat-header,
:root[data-theme='dark'] .chat-header {
  background-color: var(--dark-header-bg, #1a1a1a);
  color: var(--dark-text-color, #e0e0e0);
  border-bottom-color: var(--dark-border-color, #333333);
}

:root.dark .action-button,
:root[data-theme='dark'] .action-button {
  color: var(--dark-text-color, #e0e0e0);
}

:root.dark .action-button:hover,
:root[data-theme='dark'] .action-button:hover {
  background-color: var(--dark-button-hover, rgba(255, 255, 255, 0.1));
}

:root.dark .announcement-banner,
:root[data-theme='dark'] .announcement-banner {
  background-color: var(--dark-announcement-bg, rgba(240, 185, 11, 0.15));
  color: var(--dark-announcement-text, #f0b90b);
}

:root.dark .chat-messages,
:root[data-theme='dark'] .chat-messages {
  background-color: var(--dark-chat-bg, #1a1a1a);
}

:root.dark .message-time,
:root[data-theme='dark'] .message-time {
  color: var(--dark-text-secondary, #808080);
}

:root.dark .message.user .message-content,
:root[data-theme='dark'] .message.user .message-content {
  background-color: var(--dark-user-msg-bg, rgba(79, 190, 250, 0.15));
  color: var(--dark-text-color, #e0e0e0);
}

:root.dark .message.system .message-content,
:root[data-theme='dark'] .message.system .message-content {
  color: var(--dark-text-color, #e0e0e0);
}

:root.dark .message.other .message-content,
:root[data-theme='dark'] .message.other .message-content {
  background-color: var(--dark-other-msg-bg, #333333);
  color: var(--dark-text-color, #e0e0e0);
}

:root.dark .message.other .message-username,
:root[data-theme='dark'] .message.other .message-username {
  color: var(--dark-username-color, #f0b90b);
  font-weight: 500;
}

:root.dark .typing-indicator span,
:root[data-theme='dark'] .typing-indicator span {
  background-color: var(--dark-text-secondary, #808080);
}

:root.dark .chat-input-area,
:root[data-theme='dark'] .chat-input-area {
  background-color: var(--dark-input-area-bg, #212121);
  border-top-color: var(--dark-border-color, #333333);
}

:root.dark .chat-input,
:root[data-theme='dark'] .chat-input {
  border-color: var(--dark-border-color, #333333);
  background-color: var(--dark-input-bg, #2c2c2c);
  color: var(--dark-text-color, #e0e0e0);
}

:root.dark .emoji-button,
:root[data-theme='dark'] .emoji-button {
  color: var(--dark-text-secondary, #808080);
}

:root.dark .emoji-button:hover,
:root[data-theme='dark'] .emoji-button:hover {
  color: var(--dark-text-color, #e0e0e0);
}

:root.dark .send-button:disabled,
:root[data-theme='dark'] .send-button:disabled {
  background-color: var(--dark-disabled-color, #3a3a3a);
  color: var(--dark-text-secondary, #808080);
}

:root.dark .modal-overlay,
:root[data-theme='dark'] .modal-overlay {
  background-color: rgba(0, 0, 0, 0.8);
}

:root.dark .modal-content,
:root[data-theme='dark'] .modal-content {
  background-color: var(--dark-modal-bg, #212121);
  color: var(--dark-text-color, #e0e0e0);
}

:root.dark .new-room-input,
:root[data-theme='dark'] .new-room-input {
  background-color: var(--dark-input-bg, #2c2c2c);
  color: var(--dark-text-color, #e0e0e0);
  border-color: var(--dark-border-color, #444444);
}

:root.dark .cancel-button,
:root[data-theme='dark'] .cancel-button {
  background-color: var(--dark-button-secondary, #333333);
  border-color: var(--dark-border-color, #444444);
  color: var(--dark-text-color, #e0e0e0);
}

/* 新建聊天室按鈕樣式 */
.create-room-button-container {
  padding: 0 15px 10px;
  display: flex;
  justify-content: center;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
}

.create-room-button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  background-color: var(--primary-color, #f0b90b);
  color: var(--button-text, #000000);
  border: none;
  border-radius: 20px;
  padding: 8px 12px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
}

.create-room-button:hover {
  background-color: var(--primary-hover, #e0aa0a);
}

.create-icon {
  margin-right: 6px;
}

/* 加入聊天室按钮样式 */
.join-room-button-container {
  padding: 10px 15px;
  display: flex;
  justify-content: center;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
}

.join-room-button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  background-color: var(--secondary-color, #4caf50);
  color: white;
  border: none;
  border-radius: 20px;
  padding: 8px 12px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
}

.join-room-button:hover {
  background-color: var(--secondary-hover, #3d8b40);
}

.join-icon {
  margin-right: 6px;
}

/* 公共聊天室列表样式 */
.public-rooms-list {
  max-height: 250px;
  overflow-y: auto;
  margin-bottom: 15px;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 6px;
}

.public-room-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  cursor: pointer;
  transition: background-color 0.2s;
}

.public-room-item:last-child {
  border-bottom: none;
}

.public-room-item:hover {
  background-color: var(--hover-color, #f0f0f0);
}

.public-room-item.already-joined {
  background-color: var(--joined-bg, #f5f9ff);
  cursor: default;
}

.public-room-info {
  flex: 1;
}

.public-room-name {
  font-weight: 500;
  font-size: 14px;
  margin-bottom: 3px;
}

.public-room-status {
  font-size: 12px;
  color: var(--text-secondary, #666666);
}

.join-button {
  background-color: var(--secondary-color, #4caf50);
  color: white;
  border: none;
  border-radius: 4px;
  padding: 5px 10px;
  font-size: 12px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.join-button:hover {
  background-color: var(--secondary-hover, #3d8b40);
}

.joined-indicator {
  font-size: 12px;
  color: var(--success-color, #4caf50);
  font-weight: 500;
}

.loading-indicator,
.no-rooms-message {
  text-align: center;
  padding: 15px;
  color: var(--text-secondary, #666666);
  font-style: italic;
}

.refresh-button {
  background-color: var(--refresh-color, #2196f3);
  color: white;
  border: none;
  border-radius: 4px;
  padding: 5px 10px;
  font-size: 12px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.refresh-button:hover {
  background-color: var(--refresh-hover, #0d8bf0);
}

/* 深色模式样式 */
:root.dark .join-room-button,
:root[data-theme='dark'] .join-room-button {
  background-color: var(--dark-secondary-color, #388e3c);
}

:root.dark .join-room-button:hover,
:root[data-theme='dark'] .join-room-button:hover {
  background-color: var(--dark-secondary-hover, #2e7d32);
}

:root.dark .join-room-button-container,
:root[data-theme='dark'] .join-room-button-container {
  border-bottom-color: var(--dark-border-color, #333333);
}

:root.dark .public-rooms-list,
:root[data-theme='dark'] .public-rooms-list {
  border-color: var(--dark-border-color, #333333);
}

:root.dark .public-room-item,
:root[data-theme='dark'] .public-room-item {
  border-bottom-color: var(--dark-border-color, #333333);
}

:root.dark .public-room-item:hover,
:root[data-theme='dark'] .public-room-item:hover {
  background-color: var(--dark-hover-color, #2a2a2a);
}

:root.dark .public-room-item.already-joined,
:root[data-theme='dark'] .public-room-item.already-joined {
  background-color: var(--dark-joined-bg, #1e2a3a);
}

:root.dark .public-room-status,
:root[data-theme='dark'] .public-room-status {
  color: var(--dark-text-secondary, #808080);
}

:root.dark .joined-indicator,
:root[data-theme='dark'] .joined-indicator {
  color: var(--dark-success-color, #4caf50);
}

/* 非成员聊天室界面 */
.not-member-container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--chat-bg, #ffffff);
  transition: background-color 0.3s ease;
}

.not-member-message {
  text-align: center;
  padding: 30px;
  background-color: var(--input-bg, #f0f0f0);
  border-radius: 15px;
  max-width: 80%;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transition: all 0.3s ease;
  border: 1px solid var(--border-color, #e0e0e0);
}

.not-member-message p {
  margin-bottom: 20px;
  font-size: 16px;
  color: var(--text-color, #333333);
  line-height: 1.5;
}

.join-room-now-button {
  background-color: var(--secondary-color, #4caf50);
  color: white;
  border: none;
  border-radius: 20px;
  padding: 10px 24px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 2px 6px rgba(76, 175, 80, 0.3);
}

.join-room-now-button:hover {
  background-color: var(--secondary-hover, #3d8b40);
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(76, 175, 80, 0.4);
}

.join-room-now-button:active {
  transform: translateY(0);
  box-shadow: 0 2px 4px rgba(76, 175, 80, 0.2);
}

/* 删除按钮 */
.delete-room-button {
  background-color: var(--error-color, #f44336);
  color: white;
  border: none;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 12px;
  margin-left: 10px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.delete-room-button:hover {
  background-color: var(--error-hover, #d32f2f);
}

/* 确认删除模态框 */
.confirm-message {
  margin-bottom: 20px;
  color: var(--text-color, #333333);
}

.delete-button {
  background-color: var(--error-color, #f44336);
  color: white;
  border: none;
  border-radius: 6px;
  padding: 8px 16px;
  font-size: 14px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.delete-button:hover {
  background-color: var(--error-hover, #d32f2f);
}

/* 深色模式样式 */
:root.dark .not-member-container,
:root[data-theme='dark'] .not-member-container {
  background-color: var(--dark-chat-bg, #1a1a1a);
}

:root.dark .not-member-message,
:root[data-theme='dark'] .not-member-message {
  background-color: var(--dark-input-bg, #2c2c2c);
  border-color: var(--dark-border-color, #444444);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

:root.dark .not-member-message p,
:root[data-theme='dark'] .not-member-message p {
  color: var(--dark-text-color, #e0e0e0);
}

:root.dark .join-room-now-button,
:root[data-theme='dark'] .join-room-now-button {
  background-color: var(--dark-secondary-color, #388e3c);
  box-shadow: 0 2px 6px rgba(56, 142, 60, 0.3);
}

:root.dark .join-room-now-button:hover,
:root[data-theme='dark'] .join-room-now-button:hover {
  background-color: var(--dark-secondary-hover, #2e7d32);
  box-shadow: 0 4px 8px rgba(56, 142, 60, 0.4);
}

:root.dark .member-badge,
:root[data-theme='dark'] .member-badge {
  background-color: rgba(76, 175, 80, 0.2);
}

:root.dark .confirm-message,
:root[data-theme='dark'] .confirm-message {
  color: var(--dark-text-color, #e0e0e0);
}

.no-members-message {
  text-align: center;
  padding: 15px;
  color: var(--text-secondary, #666666);
  font-style: italic;
}

/* 添加聊天室成员列表样式 */
.room-members-list {
  max-height: 300px;
  overflow-y: auto;
  margin-bottom: 15px;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 6px;
}

.room-member-item {
  display: flex;
  align-items: center;
  padding: 12px;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
}

.room-member-item:last-child {
  border-bottom: none;
}

.member-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  overflow: hidden;
  margin-right: 16px;
  flex-shrink: 0;
}

.member-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.member-info {
  flex: 1;
  min-width: 0;
}

.member-name {
  font-weight: 500;
  font-size: 15px;
  margin-bottom: 4px;
  color: var(--text-color, #333333);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.member-role {
  font-size: 12px;
  color: var(--primary-color, #f0b90b);
  background-color: rgba(240, 185, 11, 0.1);
  display: inline-block;
  padding: 3px 8px;
  border-radius: 10px;
}

.member-joined-time {
  font-size: 13px;
  color: var(--text-secondary, #666666);
  margin-left: auto;
  white-space: nowrap;
  padding-left: 16px;
}

/* 深色模式样式 */
:root.dark .context-menu,
:root[data-theme='dark'] .context-menu {
  background-color: var(--dark-background-color, #1a1a1a);
  border-color: var(--dark-border-color, #333333);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
}

:root.dark .context-menu-item,
:root[data-theme='dark'] .context-menu-item {
  color: var(--dark-text-color, #e0e0e0);
}

:root.dark .context-menu-item:hover,
:root[data-theme='dark'] .context-menu-item:hover {
  background-color: var(--dark-hover-color, #2a2a2a);
}

:root.dark .context-menu-admin,
:root[data-theme='dark'] .context-menu-admin {
  border-top-color: var(--dark-border-color, #333333);
  background-color: rgba(240, 185, 11, 0.1);
}

/* 管理员操作按钮样式 */
.admin-actions {
  display: flex;
  align-items: center;
  margin-left: 10px;
  gap: 10px;
}

.admin-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 5px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
}

.manage-room-button {
  background-color: var(--primary-color, #f0b90b);
  color: var(--button-text, #000000);
  border: none;
}

.manage-room-button:hover {
  background-color: var(--primary-hover, #e0aa0a);
}

.delete-room-button {
  background-color: var(--error-color, #f44336);
  color: white;
  border: none;
}

.delete-room-button:hover {
  background-color: var(--error-hover, #d32f2f);
}

/* 聊天室管理模态框样式 */
.room-management-modal {
  max-width: 500px;
  width: 90%;
}

.room-management-form {
  display: flex;
  flex-direction: column;
  gap: 15px;
  margin-bottom: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.form-group label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-color, #333333);
}

.form-input, .form-textarea {
  padding: 8px 12px;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 4px;
  font-size: 14px;
  background-color: var(--input-bg, #f0f0f0);
  color: var(--text-color, #333333);
}

.form-textarea {
  resize: vertical;
  min-height: 60px;
}

.input-with-info {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.input-info {
  font-size: 12px;
  color: var(--text-secondary, #666666);
  font-style: italic;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.checkbox-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

/* 深色模式样式 */
:root.dark .admin-button.manage-room-button,
:root[data-theme='dark'] .admin-button.manage-room-button {
  background-color: var(--dark-primary-color, #f0b90b);
  color: var(--dark-button-text, #000000);
}

:root.dark .form-group label,
:root[data-theme='dark'] .form-group label {
  color: var(--dark-text-color, #e0e0e0);
}

:root.dark .form-input, 
:root.dark .form-textarea,
:root[data-theme='dark'] .form-input, 
:root[data-theme='dark'] .form-textarea {
  background-color: var(--dark-input-bg, #333333);
  color: var(--dark-text-color, #e0e0e0);
  border-color: var(--dark-border-color, #444444);
}

:root.dark .input-info,
:root[data-theme='dark'] .input-info {
  color: var(--dark-text-secondary, #aaaaaa);
}

/* 右键菜单样式 */
.system-username {
  color: #ff4d4f !important; /* 系统消息用户名使用红色 */
  font-weight: 600;
}

.system-content {
  color: #ff4d4f !important; /* 系统消息内容使用红色 */
}

.message.system {
  padding-left: 10px; /* 由于系统消息没有头像，增加左侧内边距保持对齐 */
}

/* 深色模式样式 - 标签和公告 */
:root.dark .room-badge.official,
:root[data-theme='dark'] .room-badge.official {
  background-color: #8c6b00;
  color: #ffffff;
}

:root.dark .room-badge.public,
:root[data-theme='dark'] .room-badge.public {
  background-color: #389e0d;
  color: #ffffff;
}

:root.dark .announcement-banner,
:root[data-theme='dark'] .announcement-banner {
  background-color: rgba(240, 185, 11, 0.1);
  color: #f0b90b;
  border-bottom-color: rgba(240, 185, 11, 0.2);
}

:root.dark .announcement-icon,
:root[data-theme='dark'] .announcement-icon {
  color: #f0b90b;
}

/* 新聊天室选项样式 */
.room-options {
  margin-bottom: 15px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  font-size: 14px;
  color: var(--text-color, #333333);
}

.checkbox-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

:root.dark .checkbox-label,
:root[data-theme='dark'] .checkbox-label {
  color: var(--dark-text-color, #e0e0e0);
}

:root.dark .context-menu-item svg,
:root[data-theme='dark'] .context-menu-item svg {
  color: var(--dark-text-secondary, #808080);
}

/* 深色模式下的管理员菜单项 */
:root.dark .context-menu-admin,
:root[data-theme='dark'] .context-menu-admin {
  border-top-color: var(--dark-border-color, #333333);
  background-color: rgba(240, 185, 11, 0.1);
}

:root.dark .context-menu-admin:hover,
:root[data-theme='dark'] .context-menu-admin:hover {
  background-color: rgba(240, 185, 11, 0.15);
}

:root.dark .context-menu-admin svg,
:root[data-theme='dark'] .context-menu-admin svg {
  color: var(--dark-primary-color, #f0b90b);
}

/* 深色模式下的危险操作菜单项 */
:root.dark .context-menu-danger,
:root[data-theme='dark'] .context-menu-danger {
  background-color: rgba(244, 67, 54, 0.1);
}

:root.dark .context-menu-danger:hover,
:root[data-theme='dark'] .context-menu-danger:hover {
  background-color: rgba(244, 67, 54, 0.15);
}

:root.dark .context-menu-danger svg,
:root.dark .context-menu-danger span,
:root[data-theme='dark'] .context-menu-danger svg,
:root[data-theme='dark'] .context-menu-danger span {
  color: var(--dark-error-color, #f44336);
}

/* 空聊天室列表样式 */
.no-rooms-message {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 20px;
  color: var(--text-secondary, #666666);
  text-align: center;
}

.no-rooms-message p {
  margin: 5px 0;
}

.no-rooms-hint {
  font-size: 12px;
  font-style: italic;
  margin-top: 8px;
  color: var(--text-tertiary, #999999);
}

/* 深色模式样式 */
:root.dark .no-rooms-message,
:root[data-theme='dark'] .no-rooms-message {
  color: var(--dark-text-secondary, #808080);
}

:root.dark .no-rooms-hint,
:root[data-theme='dark'] .no-rooms-hint {
  color: var(--dark-text-tertiary, #666666);
}

/* 添加缺失的右键菜单基本样式 */
.context-menu {
  position: fixed;
  background-color: var(--surface-color, #ffffff);
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: var(--border-radius-md, 8px);
  padding: 5px 0;
  min-width: 180px;
  z-index: 1100;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.context-menu-item {
  padding: 10px 15px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  transition: background-color 0.2s;
  color: var(--text-color, #333333);
  font-size: 14px;
}

.context-menu-item:hover {
  background-color: var(--hover-color, #f0f0f0);
}

.context-menu-admin {
  border-top: 1px solid var(--border-color, #e0e0e0);
  background-color: rgba(240, 185, 11, 0.05);
}

.context-menu-danger {
  color: var(--error-color, #ff4d4f);
}

.context-menu-item svg {
  color: var(--text-secondary, #666666);
}

/* 深色模式样式 */
:root.dark .context-menu,
:root[data-theme='dark'] .context-menu {
  background-color: var(--dark-background-color, #1a1a1a);
  border-color: var(--dark-border-color, #333333);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
}

:root.dark .context-menu-item,
:root[data-theme='dark'] .context-menu-item {
  color: var(--dark-text-color, #e0e0e0);
}

:root.dark .context-menu-item:hover,
:root[data-theme='dark'] .context-menu-item:hover {
  background-color: var(--dark-hover-color, #2a2a2a);
}

:root.dark .context-menu-admin,
:root[data-theme='dark'] .context-menu-admin {
  border-top-color: var(--dark-border-color, #333333);
  background-color: rgba(240, 185, 11, 0.1);
}

/* 恢复被误删的深色模式样式 */
:root.dark .context-menu-item svg,
:root[data-theme='dark'] .context-menu-item svg {
  color: var(--dark-text-secondary, #808080);
}

:root.dark .room-members-list,
:root[data-theme='dark'] .room-members-list {
  border-color: var(--dark-border-color, #333333);
}

:root.dark .room-member-item,
:root[data-theme='dark'] .room-member-item {
  border-bottom-color: var(--dark-border-color, #333333);
}

:root.dark .member-role,
:root[data-theme='dark'] .member-role {
  color: var(--dark-primary-color, #f0b90b);
}

:root.dark .member-joined-time,
:root.dark .no-members-message,
:root[data-theme='dark'] .member-joined-time,
:root[data-theme='dark'] .no-members-message {
  color: var(--dark-text-secondary, #808080);
}

/* 模态框样式 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background-color: var(--modal-bg, #ffffff);
  border-radius: 8px;
  padding: 20px;
  width: 80%;
  max-width: 300px;
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
}

/* 添加成员模态框专用样式 */
.members-modal {
  max-width: 550px;
  width: 90%;
}

.modal-content {
  background-color: var(--modal-bg, #ffffff);
  border-radius: 8px;
  padding: 20px;
  width: 80%;
  max-width: 300px;
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
}

/* 成员模态框专用样式 - 使其更宽 */
.members-modal {
  max-width: 550px !important;
  width: 90%;
}

.modal-content h3 {
  margin-top: 0;
  margin-bottom: 15px;
  font-size: 18px;
  color: var(--text-color, #333333);
}

.room-unread-badge {
  background-color: #ff4d4f;
  color: white;
  border-radius: 10px;
  padding: 2px 6px;
  font-size: 10px;
  margin-left: 5px;
}

:root.dark .member-badge,
:root[data-theme='dark'] .member-badge {
  background-color: rgba(76, 175, 80, 0.2);
}

:root.dark .room-unread-badge,
:root[data-theme='dark'] .room-unread-badge {
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

:root.dark .confirm-message,
:root[data-theme='dark'] .confirm-message {
  color: var(--dark-text-color, #e0e0e0);
}

/* 添加連續消息相關樣式 */
.message.other.consecutive {
  margin-top: 2px;
}

.message-avatar.invisible {
  visibility: hidden;
  width: 30px;
  height: 30px;
  margin-right: 10px;
  flex-shrink: 0;
}

.consecutive-wrapper {
  margin-top: 2px;
}

.consecutive-content {
  margin-top: 0;
  border-top-left-radius: 6px;
}

/* 修改聊天訊息感知間距，使連續消息看起來更加緊湊 */
.message {
  display: flex;
  margin-bottom: 5px;
}

.message.system {
  margin-bottom: 10px;
  padding-left: 40px; /* 為系統消息添加左側間距，與有頭像的消息對齊 */
}

/* 優化GIF頭像顯示 */
.message-avatar img,
.message-avatar :deep(.avatar-image) {
  width: 100%;
  height: 100%;
  object-fit: cover;
  image-rendering: auto;
  transform: translateZ(0); /* 開啟GPU加速 */
}

/* 確保頭像組件正確顯示 */
.message-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  overflow: hidden;
  margin-right: 10px;
  flex-shrink: 0;
}

.message-avatar :deep(.user-avatar-component) {
  width: 30px !important;
  height: 30px !important;
  min-width: 30px !important;
  min-height: 30px !important;
  max-width: 30px !important;
  max-height: 30px !important;
  aspect-ratio: 1/1;
}

/* 訊息加載動畫容器 */
.messages-loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: rgba(255, 255, 255, 0.8);
  z-index: 10;
  backdrop-filter: blur(2px);
}

/* 深色模式樣式 */
:root.dark .messages-loading-overlay,
:root[data-theme='dark'] .messages-loading-overlay {
  background-color: rgba(26, 26, 26, 0.8);
}

:root.dark .loading-text,
:root[data-theme='dark'] .loading-text {
  color: #aaaaaa;
}

/* 加載動畫 - 使用與登入頁面相同的三點加載動畫 */
.loader {
  width: 45px;
  aspect-ratio: .75;
  --c: no-repeat linear-gradient(var(--primary-color, #f0b90b) 0 0);
  background: 
    var(--c) 0%   50%,
    var(--c) 50%  50%,
    var(--c) 100% 50%;
  animation: l7 1s infinite linear alternate;
}

@keyframes l7 {
  0%  {background-size: 20% 50% ,20% 50% ,20% 50% }
  20% {background-size: 20% 20% ,20% 50% ,20% 50% }
  40% {background-size: 20% 100%,20% 20% ,20% 50% }
  60% {background-size: 20% 50% ,20% 100%,20% 20% }
  80% {background-size: 20% 50% ,20% 50% ,20% 100%}
  100%{background-size: 20% 50% ,20% 50% ,20% 50% }
}

/* 加載文字樣式 */
.loading-text {
  margin-top: 20px;
  font-size: 14px;
  color: var(--text-secondary, #666666);
}

/* 改進加載更多消息的樣式 */
.loading-more-messages {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px;
  margin-bottom: 10px;
  color: var(--text-secondary, #666666);
  font-size: 12px;
}

.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(0, 0, 0, 0.1);
  border-top-color: var(--primary-color, #f0b90b);
  border-radius: 50%;
  margin-right: 8px;
  animation: spin 0.8s linear infinite;
}

/* 添加按鈕加載動畫樣式 */
.button-loader {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: white;
  border-radius: 50%;
  margin-right: 8px;
  animation: spin 0.8s linear infinite;
  vertical-align: middle;
}

/* 添加小型加載器樣式 */
.small-loader {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  vertical-align: middle;
}
</style> 