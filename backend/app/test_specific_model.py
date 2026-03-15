"""
测试指定模型: doubao-pro-4k-240515
"""
import asyncio
import time
import json

API_KEY = "be8feb9d-6b08-406e-8447-b22b87cd907a"
MODEL_ID = "doubao-pro-4k-240515"


async def test_specific_model():
    """测试指定模型"""
    print("=" * 60)
    print(f"🤖 测试模型: {MODEL_ID}")
    print("=" * 60)
    
    url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": "你是一个 helpful assistant."},
            {"role": "user", "content": "你好，请简短介绍一下你自己"}
        ],
        "temperature": 0.7,
        "max_tokens": 500
    }
    
    print(f"📡 URL: {url}")
    print(f"📡 Model: {MODEL_ID}")
    print(f"📡 API Key: {API_KEY[:8]}...{API_KEY[-8:]}")
    
    import aiohttp
    start_time = time.time()
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                elapsed_time = time.time() - start_time
                response_text = await response.text()
                
                print(f"\n⏱️  响应时间: {elapsed_time:.2f}s")
                print(f"📊 HTTP状态码: {response.status}")
                
                if response.status == 200:
                    data = json.loads(response_text)
                    content = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})
                    
                    print("\n" + "=" * 60)
                    print("✅ API调用成功!")
                    print("=" * 60)
                    print(f"\n📝 模型回复:\n{content}")
                    print(f"\n📈 Token消耗:")
                    print(f"   - Prompt Tokens: {usage.get('prompt_tokens', 0)}")
                    print(f"   - Completion Tokens: {usage.get('completion_tokens', 0)}")
                    print(f"   - Total Tokens: {usage.get('total_tokens', 0)}")
                    print(f"\n⏱️  响应时间: {elapsed_time:.2f}s")
                    
                    return {
                        "success": True,
                        "model": MODEL_ID,
                        "status": response.status,
                        "response_time": elapsed_time,
                        "tokens": usage,
                        "content": content
                    }
                else:
                    print(f"\n❌ API调用失败!")
                    print(f"   状态码: {response.status}")
                    try:
                        error_data = json.loads(response_text)
                        print(f"   错误码: {error_data.get('error', {}).get('code', 'Unknown')}")
                        print(f"   错误信息: {error_data.get('error', {}).get('message', 'No message')}")
                    except:
                        print(f"   响应: {response_text[:500]}")
                    
                    return {
                        "success": False,
                        "model": MODEL_ID,
                        "status": response.status,
                        "error": response_text[:500]
                    }
                    
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"\n❌ 请求异常!")
        print(f"   耗时: {elapsed_time:.2f}s")
        print(f"   错误: {str(e)}")
        
        return {
            "success": False,
            "model": MODEL_ID,
            "error": str(e)
        }


if __name__ == "__main__":
    result = asyncio.run(test_specific_model())
    
    # 保存结果
    with open("/Users/admin/workspace/ai-video-platform/backend/test_specific_model.json", "w") as f:
        json.dump(result, f, indent=2, default=str)
    
    print("\n💾 结果已保存到 test_specific_model.json")