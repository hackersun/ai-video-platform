"""
更新火山引擎视频模型ID
"""
import sys
sys.path.insert(0, '.')

from app.core.database import sync_engine
from sqlalchemy.orm import Session
from app.models.llm_config import LLMModel


def update_video_model():
    """更新视频模型ID"""
    
    with Session(sync_engine) as session:
        # 查找火山引擎的视频模型
        model = session.query(LLMModel).filter_by(
            provider_id="volcano",
            model_type="video"
        ).first()
        
        if model:
            print(f"当前模型ID: {model.model_id}")
            print(f"当前模型名称: {model.model_name}")
            
            # 更新为正确的模型ID
            model.model_id = "doubao-seedance-1-5-pro-251215"
            model.model_name = "Doubao-Seedance-1.5-pro"
            model.description = "Doubao Seedance 1.5 Pro 视频生成模型，支持4-10秒视频生成"
            
            session.commit()
            print(f"\n✅ 已更新为: {model.model_id}")
        else:
            print("未找到火山引擎视频模型")


if __name__ == "__main__":
    print("=" * 50)
    print("更新视频模型ID")
    print("=" * 50)
    update_video_model()
