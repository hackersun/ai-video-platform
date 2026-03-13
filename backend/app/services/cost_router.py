"""
智能成本路由服务
"""

from typing import List, Dict, Optional, Tuple
from enum import Enum
import os


class RoutingStrategy(str, Enum):
    """路由策略"""
    BALANCED = "balanced"         # 平衡模式
    QUALITY_FIRST = "quality_first"  # 质量优先
    COST_FIRST = "cost_first"    # 成本优先
    SPEED_FIRST = "speed_first"  # 速度优先


class TaskPriority(int, Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class CostRouter:
    """智能成本路由器"""

    # 模型能力配置
    MODEL_CAPABILITIES = {
        # 文本生成
        "gpt-4o": {"cost": 0.015, "quality": 10, "speed": 8, "provider": "openai"},
        "gpt-4o-mini": {"cost": 0.002, "quality": 8, "speed": 10, "provider": "openai"},
        "claude-3-5-sonnet": {"cost": 0.015, "quality": 10, "speed": 7, "provider": "anthropic"},
        "claude-3-haiku": {"cost": 0.001, "quality": 7, "speed": 10, "provider": "anthropic"},
        "qwen-plus": {"cost": 0.004, "quality": 8, "speed": 9, "provider": "volcengine"},
        
        # 图像生成
        "cve-v1": {"cost": 0.02, "quality": 8, "speed": 8, "provider": "volcengine"},
        "midjourney": {"cost": 0.04, "quality": 10, "speed": 5, "provider": "midjourney"},
        "dalle-3": {"cost": 0.08, "quality": 9, "speed": 7, "provider": "openai"},
        "stable-diffusion": {"cost": 0, "quality": 7, "speed": 6, "provider": "local"},
        
        # 视频生成
        "kling-v1": {"cost": 0.5, "quality": 9, "speed": 5, "provider": "volcengine"},
        "runway-gen3": {"cost": 0.5, "quality": 10, "speed": 4, "provider": "runway"},
        "pika-2": {"cost": 0.3, "quality": 8, "speed": 7, "provider": "pika"},
        "svd": {"cost": 0, "quality": 7, "speed": 3, "provider": "local"},
        
        # 语音合成
        "elevenlabs-v2": {"cost": 0.3, "quality": 10, "speed": 9, "provider": "elevenlabs"},
        "edge-tts": {"cost": 0, "quality": 8, "speed": 10, "provider": "volcengine"},
        "azure-tts": {"cost": 0.1, "quality": 9, "speed": 8, "provider": "azure"},
        
        # 音乐生成
        "suno-v3": {"cost": 0.1, "quality": 9, "speed": 6, "provider": "suno"},
        "udio": {"cost": 0.1, "quality": 9, "speed": 5, "provider": "udio"},
        "musicgen": {"cost": 0, "quality": 7, "speed": 4, "provider": "local"},
    }

    # 免费模型
    FREE_MODELS = {
        "text_generation": ["qwen-plus", "claude-3-haiku"],
        "image_generation": ["stable-diffusion"],
        "video_generation": ["svd"],
        "voice_synthesis": ["edge-tts"],
        "music_generation": ["musicgen"],
    }

    def __init__(
        self,
        strategy: RoutingStrategy = RoutingStrategy.BALANCED,
        daily_budget: float = 0,
        monthly_budget: float = 0,
    ):
        self.strategy = strategy
        self.daily_budget = daily_budget
        self.monthly_budget = monthly_budget
        self.daily_spent = 0.0
        self.monthly_spent = 0.0

    def select_model(
        self,
        task_type: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        quality_requirement: int = 5,  # 1-10
        **kwargs
    ) -> Tuple[str, Dict]:
        """
        智能选择最优模型
        
        Args:
            task_type: 任务类型 (text_generation, image_generation等)
            priority: 任务优先级
            quality_requirement: 质量要求 (1-10)
            
        Returns:
            (model_name, config)
        """
        # 1. 获取该类型的可用模型
        available_models = self._get_available_models(task_type)
        
        if not available_models:
            raise ValueError(f"No available models for task type: {task_type}")
        
        # 2. 根据策略筛选
        candidates = self._filter_by_strategy(
            available_models, 
            task_type, 
            priority,
            quality_requirement
        )
        
        if not candidates:
            # 如果没有合适的候选，回退到免费的
            free_models = self.FREE_MODELS.get(task_type, [])
            if free_models:
                return free_models[0], {"fallback": True, "reason": "no_candidates"}
            raise ValueError(f"No suitable models found for: {task_type}")
        
        # 3. 选择最优模型
        selected = self._select_optimal(candidates, priority)
        
        return selected, self.MODEL_CAPABILITIES.get(selected, {})

    def _get_available_models(self, task_type: str) -> List[str]:
        """获取任务类型可用的模型"""
        model_map = {
            "text_generation": ["gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet", "claude-3-haiku", "qwen-plus"],
            "image_generation": ["cve-v1", "midjourney", "dalle-3", "stable-diffusion"],
            "video_generation": ["kling-v1", "runway-gen3", "pika-2", "svd"],
            "voice_synthesis": ["elevenlabs-v2", "edge-tts", "azure-tts"],
            "music_generation": ["suno-v3", "udio", "musicgen"],
        }
        return model_map.get(task_type, [])

    def _filter_by_strategy(
        self,
        models: List[str],
        task_type: str,
        priority: TaskPriority,
        quality_requirement: int
    ) -> List[str]:
        """根据策略筛选模型"""
        candidates = []
        
        for model in models:
            config = self.MODEL_CAPABILITIES.get(model, {})
            if not config:
                continue
            
            # 预算检查
            if self.daily_budget > 0 and self.daily_spent >= self.daily_budget:
                # 预算用完，检查是否是免费模型
                if config.get("cost", 0) > 0:
                    continue
            
            # 质量检查 - 确保模型质量满足要求
            if config.get("quality", 0) < quality_requirement - 2:
                continue
            
            # 高优先级任务检查
            if priority >= TaskPriority.HIGH:
                # 高优先级任务优先选择高质量模型
                if config.get("quality", 0) >= 8:
                    candidates.append(model)
            else:
                candidates.append(model)
        
        return candidates

    def _select_optimal(
        self,
        candidates: List[str],
        priority: TaskPriority
    ) -> str:
        """选择最优模型"""
        if not candidates:
            return candidates[0]
        
        if self.strategy == RoutingStrategy.COST_FIRST:
            # 成本优先：选择最便宜的
            return min(candidates, key=lambda m: self.MODEL_CAPABILITIES.get(m, {}).get("cost", 999))
        
        elif self.strategy == RoutingStrategy.QUALITY_FIRST:
            # 质量优先：选择质量最高的
            return max(candidates, key=lambda m: self.MODEL_CAPABILITIES.get(m, {}).get("quality", 0))
        
        elif self.strategy == RoutingStrategy.SPEED_FIRST:
            # 速度优先：选择速度最快的
            return max(candidates, key=lambda m: self.MODEL_CAPABILITIES.get(m, {}).get("speed", 0))
        
        else:
            # 平衡模式：性价比计算
            def calculate_score(model: str) -> float:
                config = self.MODEL_CAPABILITIES.get(model, {})
                quality = config.get("quality", 5)
                cost = config.get("cost", 0.1)
                speed = config.get("speed", 5)
                # 性价比 = 质量 * 速度 / (成本 + 0.01)
                return (quality * speed) / (cost + 0.01)
            
            return max(candidates, key=calculate_score)

    def should_use_free_model(self) -> bool:
        """判断是否应该使用免费模型"""
        if self.daily_budget > 0 and self.daily_spent >= self.daily_budget * 0.9:
            return True
        if self.monthly_budget > 0 and self.monthly_spent >= self.monthly_budget * 0.9:
            return True
        return False

    def record_usage(self, model: str, cost: float):
        """记录使用情况"""
        self.daily_spent += cost
        self.monthly_spent += cost

    def get_cost_estimate(self, task_type: str, **params) -> float:
        """获取成本估算"""
        model, config = self.select_model(task_type)
        return config.get("cost", 0)

    def get_savings_report(self) -> Dict:
        """获取节省报告"""
        # 计算如果全部使用付费模型的花费
        paid_total = sum(
            config.get("cost", 0) 
            for config in self.MODEL_CAPABILITIES.values()
        )
        
        # 当前实际花费
        actual = self.daily_spent
        
        # 免费模型节省
        free_savings = paid_total - actual if actual > 0 else paid_total
        
        return {
            "daily_spent": self.daily_spent,
            "monthly_spent": self.monthly_spent,
            "daily_budget": self.daily_budget,
            "monthly_budget": self.monthly_budget,
            "free_savings": free_savings,
            "budget_remaining": max(0, self.daily_budget - self.daily_spent) if self.daily_budget > 0 else None,
        }


# 全局路由器实例
cost_router = CostRouter()