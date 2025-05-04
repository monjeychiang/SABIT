import requests
import json

# 测试登录
def test_login():
    """测试各种用户登录接口"""
    # 基本登录URL
    base_url = "http://localhost:8000/api/v1/auth"
    
    # 登录数据
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    print("=" * 50)
    print("测试标准OAuth2登录端点")
    print("=" * 50)
    
    # 发送标准OAuth2登录请求
    try:
        # 使用表单格式
        print("\n尝试使用表单格式 - 标准OAuth2登录:")
        response_form = requests.post(
            f"{base_url}/login", 
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        # 打印请求信息
        print(f"请求方法: {response_form.request.method}")
        print(f"请求URL: {response_form.request.url}")
        print(f"请求头: {response_form.request.headers}")
        print(f"请求体: {response_form.request.body}")
        
        # 打印响应信息
        print(f"响应状态码: {response_form.status_code}")
        print(f"响应头: {response_form.headers}")
        print(f"响应内容: {response_form.text}")
    except Exception as e:
        print(f"请求发生错误: {e}")
    
    print("\n" + "=" * 50)
    print("测试简化登录端点")
    print("=" * 50)
    
    # 发送简化登录请求
    try:
        # 使用表单格式
        print("\n尝试使用表单格式 - 简化登录:")
        response_simple = requests.post(
            f"{base_url}/login/simple", 
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        # 打印请求信息
        print(f"请求方法: {response_simple.request.method}")
        print(f"请求URL: {response_simple.request.url}")
        print(f"请求头: {response_simple.request.headers}")
        print(f"请求体: {response_simple.request.body}")
        
        # 打印响应信息
        print(f"响应状态码: {response_simple.status_code}")
        print(f"响应头: {response_simple.headers}")
        print(f"响应内容: {response_simple.text}")
        
        # 如果登录成功，打印token
        if response_simple.status_code == 200:
            data = response_simple.json()
            print(f"\n登录成功! Token: {data.get('access_token')}")
            return True
        else:
            print("\n登录失败")
            return False
    except Exception as e:
        print(f"请求发生错误: {e}")
        return False

if __name__ == "__main__":
    # 运行测试
    test_login() 