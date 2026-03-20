"""
火山引擎视频生成SDK测试
"""
import os
import time

from volcenginesdkarkruntime import Ark

# 初始化客户端
client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key="be8feb9d-6b08-406e-8447-b22b87cd907a",
)

def test_video_generation():
    print("=== 创建视频生成任务 ===")
    
    # 使用用户提供的模型ID
    create_result = client.content_generation.tasks.create(
        model="ep-20260320184133-9ncm4",
        content=[
            {
                "type": "text",
                "text": "无人机以极快速度穿越复杂障碍或自然奇观，带来沉浸式飞行体验 --duration 5 --camerafixed false --watermark true"
            },
        ]
    )
    
    task_id = create_result.id
    print(f"任务ID: {task_id}")
    
    # 轮询查询状态
    print("\n=== 轮询任务状态 ===")
    
    while True:
        get_result = client.content_generation.tasks.get(task_id=task_id)
        status = get_result.status
        
        print(f"当前状态: {status}")
        
        if status == "succeeded":
            print("=== 任务成功 ===")
            output = getattr(get_result, 'output', None)
            if output:
                video_url = getattr(output, 'video_url', 'N/A')
                cover_url = getattr(output, 'cover_url', 'N/A')
                print(f"视频URL: {video_url}")
                print(f"封面URL: {cover_url}")
            print(f"完整结果: {get_result}")
            break
        elif status == "failed":
            print("=== 任务失败 ===")
            error = getattr(get_result, 'error', 'Unknown')
            print(f"错误: {error}")
            break
        else:
            print("3秒后重试...")
            time.sleep(3)

if __name__ == "__main__":
    test_video_generation()
