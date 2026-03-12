"""
API功能测试脚本
测试后端API各个端点
"""

import requests
import json
from datetime import datetime

# API基础URL
BASE_URL = "http://localhost:8000/api/v1"

# 测试数据
TEST_USER = {
    "email": f"test_{datetime.now().timestamp()}@example.com",
    "username": f"testuser_{int(datetime.now().timestamp())}",
    "password": "TestPassword123!",
    "nickname": "测试用户"
}

class APITester:
    def __init__(self):
        self.token = None
        self.user_id = None
        self.novel_id = None
        self.script_id = None
        self.results = []
    
    def log(self, message, status="INFO"):
        """记录测试结果"""
        emoji = {"SUCCESS": "✅", "ERROR": "❌", "INFO": "ℹ️", "WARNING": "⚠️"}
        result = f"{emoji.get(status, 'ℹ️')} [{status}] {message}"
        self.results.append(result)
        print(result)
    
    def test_health_check(self):
        """测试健康检查"""
        try:
            response = requests.get(f"{BASE_URL.replace('/api/v1', '')}/health", timeout=5)
            if response.status_code == 200:
                self.log("健康检查通过", "SUCCESS")
                return True
            else:
                self.log(f"健康检查失败: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"健康检查异常: {str(e)}", "ERROR")
            return False
    
    def test_register(self):
        """测试用户注册"""
        try:
            response = requests.post(
                f"{BASE_URL}/auth/register",
                json=TEST_USER,
                timeout=10
            )
            if response.status_code == 201:
                data = response.json()
                self.user_id = data.get("id")
                self.log(f"用户注册成功: {data.get('username')}", "SUCCESS")
                return True
            else:
                self.log(f"注册失败: {response.status_code} - {response.text}", "ERROR")
                return False
        except Exception as e:
            self.log(f"注册异常: {str(e)}", "ERROR")
            return False
    
    def test_login(self):
        """测试用户登录"""
        try:
            response = requests.post(
                f"{BASE_URL}/auth/login",
                json={
                    "username": TEST_USER["username"],
                    "password": TEST_USER["password"]
                },
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                self.log("登录成功，获取到JWT令牌", "SUCCESS")
                return True
            else:
                self.log(f"登录失败: {response.status_code} - {response.text}", "ERROR")
                return False
        except Exception as e:
            self.log(f"登录异常: {str(e)}", "ERROR")
            return False
    
    def test_get_current_user(self):
        """测试获取当前用户信息"""
        if not self.token:
            self.log("未登录，跳过测试", "WARNING")
            return False
        
        try:
            response = requests.get(
                f"{BASE_URL}/auth/me",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.log(f"获取用户信息成功: {data.get('username')}", "SUCCESS")
                return True
            else:
                self.log(f"获取用户信息失败: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"获取用户信息异常: {str(e)}", "ERROR")
            return False
    
    def test_create_novel(self):
        """测试创建小说"""
        if not self.token:
            self.log("未登录，跳过测试", "WARNING")
            return False
        
        try:
            response = requests.post(
                f"{BASE_URL}/novels",
                headers={"Authorization": f"Bearer {self.token}"},
                json={
                    "title": "测试小说",
                    "description": "这是一个测试小说",
                    "genre": "玄幻"
                },
                timeout=10
            )
            if response.status_code == 201:
                data = response.json()
                self.novel_id = data.get("id")
                self.log(f"创建小说成功: {data.get('title')}", "SUCCESS")
                return True
            else:
                self.log(f"创建小说失败: {response.status_code} - {response.text}", "ERROR")
                return False
        except Exception as e:
            self.log(f"创建小说异常: {str(e)}", "ERROR")
            return False
    
    def test_get_novels(self):
        """测试获取小说列表"""
        if not self.token:
            self.log("未登录，跳过测试", "WARNING")
            return False
        
        try:
            response = requests.get(
                f"{BASE_URL}/novels/my",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.log(f"获取小说列表成功: {len(data.get('items', []))} 本", "SUCCESS")
                return True
            else:
                self.log(f"获取小说列表失败: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"获取小说列表异常: {str(e)}", "ERROR")
            return False
    
    def test_create_script(self):
        """测试创建剧本"""
        if not self.token or not self.novel_id:
            self.log("未登录或无小说，跳过测试", "WARNING")
            return False
        
        try:
            response = requests.post(
                f"{BASE_URL}/scripts",
                headers={"Authorization": f"Bearer {self.token}"},
                json={
                    "title": "测试剧本",
                    "novel_id": self.novel_id
                },
                timeout=10
            )
            if response.status_code == 201:
                data = response.json()
                self.script_id = data.get("id")
                self.log(f"创建剧本成功: {data.get('title')}", "SUCCESS")
                return True
            else:
                self.log(f"创建剧本失败: {response.status_code} - {response.text}", "ERROR")
                return False
        except Exception as e:
            self.log(f"创建剧本异常: {str(e)}", "ERROR")
            return False
    
    def test_get_scripts(self):
        """测试获取剧本列表"""
        if not self.token:
            self.log("未登录，跳过测试", "WARNING")
            return False
        
        try:
            response = requests.get(
                f"{BASE_URL}/scripts",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.log(f"获取剧本列表成功: {len(data.get('items', []))} 个", "SUCCESS")
                return True
            else:
                self.log(f"获取剧本列表失败: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"获取剧本列表异常: {str(e)}", "ERROR")
            return False
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("🧪 AI视频平台API功能测试")
        print("=" * 60)
        print()
        
        # 基础测试
        self.test_health_check()
        print()
        
        # 认证测试
        self.test_register()
        self.test_login()
        self.test_get_current_user()
        print()
        
        # 小说测试
        self.test_create_novel()
        self.test_get_novels()
        print()
        
        # 剧本测试
        self.test_create_script()
        self.test_get_scripts()
        print()
        
        # 输出总结
        print("=" * 60)
        print("📊 测试总结")
        print("=" * 60)
        success = len([r for r in self.results if "SUCCESS" in r])
        error = len([r for r in self.results if "ERROR" in r])
        warning = len([r for r in self.results if "WARNING" in r])
        print(f"✅ 成功: {success}")
        print(f"❌ 失败: {error}")
        print(f"⚠️  跳过: {warning}")
        print(f"📋 总计: {len(self.results)}")
        print()
        
        return self.results


if __name__ == "__main__":
    tester = APITester()
    results = tester.run_all_tests()
    
    # 保存测试结果
    with open("/tmp/api_test_results.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(results))
    
    print("💾 测试结果已保存到: /tmp/api_test_results.txt")