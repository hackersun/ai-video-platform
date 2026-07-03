"""
成本计算器服务
支持按任务估算token/图片/视频/TTS成本
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from app.models.shot import Shot
from app.models.storyboard import Storyboard


# ============== 价格表（单位：元） ==============

PRICING = {
    "text": {
        "input_tokens": 0.001,   # 每1K tokens (豆包Seed-1.8)
        "output_tokens": 0.002,
    },
    "image": {
        "low": 0.05,    # 低分辨率 (1K)
        "medium": 0.10, # 中分辨率 (2K)
        "high": 0.20,   # 高分辨率 (4K)
    },
    "video": {
        "short": 0.50,   # 4秒
        "medium": 1.00, # 8秒
        "long": 1.50,    # 10秒
        "per_second": 0.125,  # 每秒单价（用于计算其他时长）
    },
    "tts": {
        "per_char": 0.001,  # 每字符
    },
    "synthesis": {
        "flat": 0.10,    # 音视频合成固定费用
    },
}


VIDEO_RESOLUTION_DIMENSIONS = {
    "480p": (854, 480),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
}


# ============== 数据模型 ==============

@dataclass
class CostEstimate:
    """成本估算结果"""
    total_cost: float = 0.0
    breakdown: Dict[str, float] = None
    details: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.breakdown is None:
            self.breakdown = {}
        if self.details is None:
            self.details = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_cost": round(self.total_cost, 4),
            "breakdown": {k: round(v, 4) for k, v in self.breakdown.items()},
            "details": self.details,
        }


@dataclass
class ResourceCostEstimate:
    """单资源成本估算"""
    resource_type: str
    resource_id: str
    cost: float
    parameters: Dict[str, Any]


# ============== 成本计算器 ==============

class CostCalculator:
    """成本计算器"""

    def __init__(self):
        self.pricing = PRICING

    # ============== 文本成本 ==============

    def estimate_text_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        input_cost_per_1k: Optional[float] = None,
        output_cost_per_1k: Optional[float] = None,
    ) -> float:
        """
        估算文本生成成本

        Args:
            input_tokens: 输入token数
            output_tokens: 输出token数
            input_cost_per_1k: 自定义输入单价（每1K tokens），默认使用豆包Seed
            output_cost_per_1k: 自定义输出单价（每1K tokens）

        Returns:
            成本（元）
        """
        ic = input_cost_per_1k if input_cost_per_1k is not None else self.pricing["text"]["input_tokens"]
        oc = output_cost_per_1k if output_cost_per_1k is not None else self.pricing["text"]["output_tokens"]
        cost = (input_tokens / 1000) * ic + (output_tokens / 1000) * oc
        return round(cost, 4)

    # ============== 图像成本 ==============

    def estimate_image_cost(
        self,
        count: int = 1,
        resolution: str = "medium",
        custom_price: Optional[float] = None,
    ) -> float:
        """
        估算图像生成成本

        Args:
            count: 生成数量
            resolution: 分辨率等级 (low/medium/high)
            custom_price: 自定义单价

        Returns:
            成本（元）
        """
        if custom_price is not None:
            return round(custom_price * count, 4)

        price = self.pricing["image"].get(resolution, self.pricing["image"]["medium"])
        return round(price * count, 4)

    # ============== 视频成本 ==============

    def estimate_video_cost(
        self,
        count: int = 1,
        duration: int = 4,
        resolution: str = "720p",
        model_id: Optional[str] = None,
        frame_rate: int = 24,
        input_video_duration: float = 0,
        price_per_million_tokens: Optional[float] = None,
        custom_price: Optional[float] = None,
    ) -> float:
        """
        估算视频生成成本

        Args:
            count: 生成数量
            duration: 时长（秒），支持 4/5/8/10
            resolution: 分辨率 (480p/720p/1080p)
            model_id: 模型ID；Seedance 2.x 可生成计费 token 明细
            frame_rate: 帧率，用于 Seedance 2.x token 公式
            input_video_duration: 输入视频时长，用于视频到视频计费估算
            price_per_million_tokens: 可选每百万 token 单价；不配置则保留旧估算
            custom_price: 自定义单价

        Returns:
            成本（元）
        """
        if custom_price is not None:
            return round(custom_price * count, 4)

        billing_units = self.estimate_video_billing_units(
            model_id=model_id,
            count=count,
            duration=duration,
            resolution=resolution,
            frame_rate=frame_rate,
            input_video_duration=input_video_duration,
        )
        if billing_units and price_per_million_tokens is not None:
            cost = (billing_units["estimated_tokens"] / 1_000_000) * price_per_million_tokens
            return round(cost, 4)

        # 根据时长确定基础价格
        if duration == 4:
            base_price = self.pricing["video"]["short"]
        elif duration == 8:
            base_price = self.pricing["video"]["medium"]
        elif duration == 10:
            base_price = self.pricing["video"]["long"]
        else:
            # 其他时长按每秒计算
            base_price = duration * self.pricing["video"]["per_second"]

        # 高分辨率加价
        resolution_multiplier = {"480p": 1.0, "720p": 1.2, "1080p": 1.5}.get(resolution, 1.0)

        cost = base_price * resolution_multiplier * count
        return round(cost, 4)

    def estimate_video_billing_units(
        self,
        *,
        model_id: Optional[str] = None,
        count: int = 1,
        duration: int = 4,
        resolution: str = "720p",
        frame_rate: int = 24,
        input_video_duration: float = 0,
    ) -> Optional[Dict[str, Any]]:
        """估算 Seedance 2.x 的视频计费 token 数，不内置供应商单价。"""
        if not _is_seedance_2_model(model_id):
            return None

        width, height = VIDEO_RESOLUTION_DIMENSIONS.get(resolution, VIDEO_RESOLUTION_DIMENSIONS["720p"])
        output_duration = duration or 0
        input_duration = input_video_duration or 0
        total_duration = input_duration + output_duration
        tokens_per_video = int(round(total_duration * width * height * frame_rate / 1024))
        estimated_tokens = tokens_per_video * count

        return {
            "formula": "seedance_2_token_formula",
            "model_id": model_id,
            "count": count,
            "duration_seconds": duration,
            "input_duration_seconds": _compact_number(input_duration),
            "output_duration_seconds": duration,
            "resolution": resolution,
            "width": width,
            "height": height,
            "frame_rate": frame_rate,
            "tokens_per_video": tokens_per_video,
            "estimated_tokens": estimated_tokens,
        }

    # ============== TTS成本 ==============

    def estimate_tts_cost(
        self,
        char_count: int,
        custom_price: Optional[float] = None,
    ) -> float:
        """
        估算TTS成本

        Args:
            char_count: 字符数
            custom_price: 自定义每字符单价

        Returns:
            成本（元）
        """
        if custom_price is not None:
            return round(custom_price * char_count, 4)

        price = self.pricing["tts"]["per_char"]
        return round(price * char_count, 4)

    # ============== 合成成本 ==============

    def estimate_synthesis_cost(
        self,
        duration: Optional[float] = None,
        custom_price: Optional[float] = None,
    ) -> float:
        """
        估算音视频合成成本

        Args:
            duration: 时长（秒），可选
            custom_price: 自定义单价

        Returns:
            成本（元）
        """
        if custom_price is not None:
            return round(custom_price, 4)

        # 固定费用
        return self.pricing["synthesis"]["flat"]

    # ============== 镜头成本 ==============

    def estimate_shot_cost(self, shot: Shot) -> CostEstimate:
        """
        估算单个镜头成本（图像+视频+TTS）

        Args:
            shot: 镜头对象

        Returns:
            CostEstimate 包含总成本和明细
        """
        estimate = CostEstimate()
        details = []

        # 图像成本
        if shot.image_url or shot.visual_description:
            image_cost = self.estimate_image_cost(count=1)
            estimate.total_cost += image_cost
            estimate.breakdown["image"] = estimate.breakdown.get("image", 0) + image_cost
            details.append({
                "type": "image",
                "description": "参考图生成",
                "cost": image_cost,
            })

        # 视频成本
        if shot.prompt:
            video_cost = self.estimate_video_cost(
                count=1,
                duration=shot.duration or 4,
            )
            estimate.total_cost += video_cost
            estimate.breakdown["video"] = estimate.breakdown.get("video", 0) + video_cost
            details.append({
                "type": "video",
                "description": f"视频生成 ({shot.duration or 4}s)",
                "cost": video_cost,
            })

        # TTS成本
        if shot.dialogue:
            char_count = len(shot.dialogue)
            tts_cost = self.estimate_tts_cost(char_count)
            estimate.total_cost += tts_cost
            estimate.breakdown["tts"] = estimate.breakdown.get("tts", 0) + tts_cost
            details.append({
                "type": "tts",
                "description": f"语音合成 ({char_count}字符)",
                "cost": tts_cost,
            })

        estimate.details = details
        return estimate

    # ============== 分镜成本 ==============

    async def estimate_storyboard_cost(
        self,
        storyboard: Storyboard,
        shots: List[Shot],
    ) -> CostEstimate:
        """
        估算整个分镜成本

        Args:
            storyboard: 分镜对象
            shots: 分镜下的镜头列表

        Returns:
            CostEstimate 包含总成本和明细
        """
        estimate = CostEstimate()
        details = []

        # 累加每个镜头的成本
        for shot in shots:
            shot_estimate = self.estimate_shot_cost(shot)

            for key, value in shot_estimate.breakdown.items():
                estimate.breakdown[key] = estimate.breakdown.get(key, 0) + value

            estimate.total_cost += shot_estimate.total_cost
            details.extend(shot_estimate.details)

        estimate.details = details
        return estimate

    # ============== 资源成本 ==============

    def estimate_resource_cost(
        self,
        resource_type: str,
        parameters: Dict[str, Any],
    ) -> float:
        """
        根据资源类型估算成本

        Args:
            resource_type: 资源类型 (text/image/video/tts/synthesis)
            parameters: 参数字典

        Returns:
            成本（元）
        """
        estimators = {
            "text": lambda p: self.estimate_text_cost(
                input_tokens=p.get("input_tokens", 0),
                output_tokens=p.get("output_tokens", 0),
                input_cost_per_1k=p.get("input_cost_per_1k"),
                output_cost_per_1k=p.get("output_cost_per_1k"),
            ),
            "image": lambda p: self.estimate_image_cost(
                count=p.get("count", 1),
                resolution=p.get("resolution", "medium"),
                custom_price=p.get("custom_price"),
            ),
            "video": lambda p: self.estimate_video_cost(
                count=p.get("count", 1),
                duration=p.get("duration", 4),
                resolution=p.get("resolution", "720p"),
                model_id=p.get("model_id"),
                frame_rate=p.get("frame_rate", 24),
                input_video_duration=p.get("input_video_duration", 0),
                price_per_million_tokens=p.get("price_per_million_tokens"),
                custom_price=p.get("custom_price"),
            ),
            "tts": lambda p: self.estimate_tts_cost(
                char_count=p.get("char_count", 0),
                custom_price=p.get("custom_price"),
            ),
            "synthesis": lambda p: self.estimate_synthesis_cost(
                duration=p.get("duration"),
                custom_price=p.get("custom_price"),
            ),
        }

        estimator = estimators.get(resource_type)
        if not estimator:
            return 0.0

        return estimator(parameters)


# ============== 单例 ==============

_cost_calculator: Optional[CostCalculator] = None


def get_cost_calculator() -> CostCalculator:
    """获取成本计算器单例"""
    global _cost_calculator
    if _cost_calculator is None:
        _cost_calculator = CostCalculator()
    return _cost_calculator


def _is_seedance_2_model(model_id: Optional[str]) -> bool:
    normalized = str(model_id or "").lower().replace("_", "-")
    return "seedance-2-0" in normalized or "seedance-2.0" in normalized


def _compact_number(value: float) -> float | int:
    return int(value) if float(value).is_integer() else value
