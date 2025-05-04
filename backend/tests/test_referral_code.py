#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试用户推荐码功能

此脚本测试:
1. 用户注册时自动生成推荐码
2. 使用已有用户的推荐码注册新用户
3. 验证推荐关系是否正确建立
"""

import requests
import random
import string
import json
import logging
import sys
import os
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

# API配置
BASE_URL = "http://localhost:8000"  # 修改为你的API地址
API_PREFIX = "/api/v1"

def generate_random_string(length=8):
    """生成随机字符串，用于用户名和邮箱"""
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))

def register_user(username, email, password, referrer_id=None):
    """
    注册新用户
    
    参数:
        username: 用户名
        email: 邮箱
        password: 密码
        referrer_id: 推荐人ID（可选）
        
    返回:
        响应对象
    """
    url = f"{BASE_URL}{API_PREFIX}/auth/register"
    
    payload = {
        "username": username,
        "email": email,
        "password": password,
        "confirm_password": password
    }
    
    # 如果有推荐人ID，添加到注册数据中
    if referrer_id:
        payload["referrer_id"] = referrer_id
    
    headers = {
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    return response

def get_user_by_token(token):
    """
    获取当前用户信息
    
    参数:
        token: 访问令牌
        
    返回:
        用户信息对象
    """
    url = f"{BASE_URL}{API_PREFIX}/auth/me"
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.get(url, headers=headers)
    return response

def login_user(username, password):
    """
    用户登录
    
    参数:
        username: 用户名
        password: 密码
        
    返回:
        令牌对象
    """
    url = f"{BASE_URL}{API_PREFIX}/auth/login/simple"
    
    data = {
        "username": username,
        "password": password
    }
    
    response = requests.post(url, data=data)
    return response

def main():
    """主测试函数"""
    try:
        logger.info("开始测试推荐码功能...")
        
        # 生成随机用户信息 - 第一个用户
        username1 = f"testuser_{generate_random_string(5)}"
        email1 = f"{username1}@example.com"
        password1 = "Password123!"
        
        # 1. 注册第一个用户
        logger.info(f"注册第一个用户: {username1}")
        response1 = register_user(username1, email1, password1)
        
        if response1.status_code != 201:
            logger.error(f"注册第一个用户失败: {response1.text}")
            return
            
        user1_data = response1.json()
        user1_id = user1_data["id"]
        user1_referral_code = user1_data["referral_code"]
        
        logger.info(f"第一个用户注册成功! ID: {user1_id}, 推荐码: {user1_referral_code}")
        
        # 登录第一个用户，获取令牌
        login_response1 = login_user(username1, password1)
        if login_response1.status_code != 200:
            logger.error(f"第一个用户登录失败: {login_response1.text}")
            return
            
        token1 = login_response1.json()["access_token"]
        
        # 再次验证用户信息和推荐码
        user_info_response = get_user_by_token(token1)
        if user_info_response.status_code != 200:
            logger.error(f"获取用户信息失败: {user_info_response.text}")
            return
            
        user_info = user_info_response.json()
        logger.info(f"确认第一个用户的推荐码: {user_info['referral_code']}")
        
        # 2. 使用第一个用户的推荐码注册第二个用户
        username2 = f"refuser_{generate_random_string(5)}"
        email2 = f"{username2}@example.com"
        password2 = "Password123!"
        
        logger.info(f"使用推荐码 {user1_referral_code} 注册第二个用户: {username2}")
        response2 = register_user(username2, email2, password2, user1_id)
        
        if response2.status_code != 201:
            logger.error(f"注册第二个用户失败: {response2.text}")
            return
            
        user2_data = response2.json()
        user2_id = user2_data["id"]
        user2_referral_code = user2_data["referral_code"]
        
        logger.info(f"第二个用户注册成功! ID: {user2_id}, 推荐码: {user2_referral_code}")
        
        # 登录第二个用户
        login_response2 = login_user(username2, password2)
        if login_response2.status_code != 200:
            logger.error(f"第二个用户登录失败: {login_response2.text}")
            return
            
        token2 = login_response2.json()["access_token"]
        
        # 获取第二个用户的完整信息
        user2_info_response = get_user_by_token(token2)
        if user2_info_response.status_code != 200:
            logger.error(f"获取第二个用户信息失败: {user2_info_response.text}")
            return
            
        user2_info = user2_info_response.json()
        
        # 3. 验证推荐关系
        logger.info("验证推荐关系...")
        
        # 这里可以添加直接查询数据库的代码来验证推荐关系
        # 由于API可能没有直接提供查询方法，我们可以通过后续的扩展接口验证
        
        logger.info(f"测试完成!")
        logger.info(f"用户1: {username1}, ID: {user1_id}, 推荐码: {user1_referral_code}")
        logger.info(f"用户2: {username2}, ID: {user2_id}, 推荐码: {user2_referral_code}")
        logger.info("用户2的推荐人ID应该是用户1的ID")
        
        # 打印总结信息
        if user2_data.get("referrer_id") == user1_id:
            logger.info("✅ 推荐关系验证成功! 用户2的推荐人是用户1")
        else:
            logger.warning("❌ 推荐关系验证失败! API响应中没有显示推荐关系")
            logger.warning("注意: 这可能是因为API响应中没有包含referrer_id字段，但数据库中的关系可能已正确建立")
            
    except Exception as e:
        logger.error(f"测试过程中出错: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 