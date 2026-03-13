"""
API自动化测试脚本
测试所有后端API端点
"""

import requests
import json
from datetime import datetime

# 配置
BASE_URL = "http://localhost:8000"
TEST_USER = {
    "username": f"testuser_{int(datetime.now().timestamp())}",
    "email": f"test_{int(datetime.now().timestamp())}@example.com",
    "password": "Test123!"
}

# 全局变量
token = None
novel_id = None
script_id = None
character_id = None

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'

def print_success(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.RESET}")

def print_error(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.RESET}")

def print_info(msg):
    print(f"{Colors.YELLOW}ℹ️ {msg}{Colors.RESET}")

def test_register():
    """测试用户注册"""
    print_info("测试: 用户注册")
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/register",
            json=TEST_USER
        )
        if response.status_code in [200, 201]:
            print_success("用户注册成功")
            return True
        else:
            print_error(f"注册失败: {response.text}")
            return False
    except Exception as e:
        print_error(f"注册异常: {e}")
        return False

def test_login():
    """测试用户登录"""
    global token
    print_info("测试: 用户登录")
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={
                "username": TEST_USER["username"],
                "password": TEST_USER["password"]
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            print_success("用户登录成功")
            return True
        else:
            print_error(f"登录失败: {response.text}")
            return False
    except Exception as e:
        print_error(f"登录异常: {e}")
        return False

def test_get_profile():
    """测试获取用户信息"""
    print_info("测试: 获取用户信息")
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        if response.status_code == 200:
            print_success("获取用户信息成功")
            return True
        else:
            print_error(f"获取用户信息失败: {response.text}")
            return False
    except Exception as e:
        print_error(f"获取用户信息异常: {e}")
        return False

def test_create_novel():
    """测试创建小说"""
    global novel_id
    print_info("测试: 创建小说")
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/novels/",
            json={
                "title": f"测试小说_{int(datetime.now().timestamp())}",
                "description": "这是一个测试小说",
                "genre": "科幻"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        if response.status_code in [200, 201]:
            data = response.json()
            novel_id = data.get("id")
            print_success(f"创建小说成功, ID: {novel_id}")
            return True
        else:
            print_error(f"创建小说失败: {response.text}")
            return False
    except Exception as e:
        print_error(f"创建小说异常: {e}")
        return False

def test_get_novels():
    """测试获取小说列表"""
    print_info("测试: 获取小说列表")
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/novels/",
            headers={"Authorization": f"Bearer {token}"}
        )
        if response.status_code == 200:
            print_success("获取小说列表成功")
            return True
        else:
            print_error(f"获取小说列表失败: {response.text}")
            return False
    except Exception as e:
        print_error(f"获取小说列表异常: {e}")
        return False

def test_create_script():
    """测试创建剧本"""
    global script_id
    print_info("测试: 创建剧本")
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/scripts/",
            json={
                "title": f"测试剧本_{int(datetime.now().timestamp())}",
                "novel_id": novel_id,
                "content": "这是一个测试剧本"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        if response.status_code in [200, 201]:
            data = response.json()
            script_id = data.get("id")
            print_success(f"创建剧本成功, ID: {script_id}")
            return True
        else:
            print_error(f"创建剧本失败: {response.text}")
            return False
    except Exception as e:
        print_error(f"创建剧本异常: {e}")
        return False

def test_get_scripts():
    """测试获取剧本列表"""
    print_info("测试: 获取剧本列表")
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/scripts/",
            headers={"Authorization": f"Bearer {token}"}
        )
        if response.status_code == 200:
            print_success("获取剧本列表成功")
            return True
        else:
            print_error(f"获取剧本列表失败: {response.text}")
            return False
    except Exception as e:
        print_error(f"获取剧本列表异常: {e}")
        return False

def test_create_character():
    """测试创建角色"""
    global character_id
    print_info("测试: 创建角色")
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/characters/",
            json={
                "name": f"测试角色_{int(datetime.now().timestamp())}",
                "novel_id": novel_id,
                "description": "这是一个测试角色"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        if response.status_code in [200, 201]:
            data = response.json()
            character_id = data.get("id")
            print_success(f"创建角色成功, ID: {character_id}")
            return True
        else:
            print_error(f"创建角色失败: {response.text}")
            return False
    except Exception as e:
        print_error(f"创建角色异常: {e}")
        return False

def test_get_characters():
    """测试获取角色列表"""
    print_info("测试: 获取角色列表")
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/characters/",
            headers={"Authorization": f"Bearer {token}"}
        )
        if response.status_code == 200:
            print_success("获取角色列表成功")
            return True
        else:
            print_error(f"获取角色列表失败: {response.text}")
            return False
    except Exception as e:
        print_error(f"获取角色列表异常: {e}")
        return False

def test_health():
    """测试健康检查"""
    print_info("测试: 健康检查")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/health")
        if response.status_code == 200:
            print_success("健康检查通过")
            return True
        else:
            print_error(f"健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"健康检查异常: {e}")
        return False

def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*50)
    print("AI视频平台 - API自动化测试")
    print("="*50 + "\n")
    
    results = []
    
    # 基础测试
    results.append(("健康检查", test_health()))
    
    # 认证测试
    results.append(("用户注册", test_register()))
    results.append(("用户登录", test_login()))
    results.append(("获取用户信息", test_get_profile()))
    
    # 小说测试
    results.append(("创建小说", test_create_novel()))
    results.append(("获取小说列表", test_get_novels()))
    
    # 剧本测试
    results.append(("创建剧本", test_create_script()))
    results.append(("获取剧本列表", test_get_scripts()))
    
    # 角色测试
    results.append(("创建角色", test_create_character()))
    results.append(("获取角色列表", test