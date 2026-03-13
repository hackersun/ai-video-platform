"""
角色一致性服务 - 特征提取与向量存储
"""

import os
import uuid
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import numpy as np
from PIL import Image
import httpx

from app.core.config import settings


class CharacterConsistencyService:
    """角色一致性管理服务"""

    def __init__(self):
        self.milvus_host = os.getenv("MILVUS_HOST", "localhost")
        self.milvus_port = os.getenv("MILVUS_PORT", "19530")
        self.collection_name = "character_features"
        self.dimension = 512  # CLIP embedding dimension
        
        # 特征提取提示词模板
        self.feature_prompt_template = """
分析以下角色描述，提取关键特征用于AI图像生成的一致性控制：

角色描述：{description}

请提取以下特征：
1. 外貌特征：发型、发色、眼睛颜色、面部特征
2. 服装风格：服装类型、颜色、配饰
3. 整体风格：写实/卡通/动漫、色调
4. 标志性元素：独特识别特征

输出格式（JSON）：
{{
    "appearance": "详细外貌描述",
    "clothing": "服装描述",
    "style": "整体风格",
    "signature_elements": ["特征1", "特征2"],
    "prompt_keywords": "用于图像生成的关键词"
}}
"""

    async def extract_features(self, character_data: Dict) -> Dict:
        """
        从角色数据中提取特征
        
        Args:
            character_data: 角色数据，包含 name, description, avatar 等
            
        Returns:
            特征数据字典
        """
        features = {
            "character_id": character_data.get("id"),
            "name": character_data.get("name"),
            "extracted_at": datetime.utcnow().isoformat(),
        }

        # 1. 从描述中提取文本特征
        description = character_data.get("description", "")
        if description:
            text_features = await self._extract_text_features(description)
            features.update(text_features)

        # 2. 从头像中提取图像特征（如果有）
        avatar_url = character_data.get("avatar")
        if avatar_url:
            image_features = await self._extract_image_features(avatar_url)
            features["image_embedding"] = image_features

        # 3. 生成一致性控制提示词
        features["consistency_prompt"] = self._generate_consistency_prompt(features)

        return features

    async def _extract_text_features(self, description: str) -> Dict:
        """从文本描述中提取特征"""
        # TODO: 调用 LLM 提取特征
        # 这里使用简单的规则提取作为示例
        
        features = {
            "appearance_keywords": [],
            "clothing_keywords": [],
            "style_keywords": [],
        }

        # 简单的关键词匹配
        appearance_keywords = ["长发", "短发", "黑发", "金发", "红发", "蓝眼睛", "黑眼睛"]
        clothing_keywords = ["校服", "西装", "连衣裙", "T恤", "牛仔裤"]
        style_keywords = ["写实", "卡通", "动漫", "二次元", "Q版"]

        for keyword in appearance_keywords:
            if keyword in description:
                features["appearance_keywords"].append(keyword)

        for keyword in clothing_keywords:
            if keyword in description:
                features["clothing_keywords"].append(keyword)

        for keyword in style_keywords:
            if keyword in description:
                features["style_keywords"].append(keyword)

        return features

    async def _extract_image_features(self, image_url: str) -> List[float]:
        """从图像中提取特征向量（使用 CLIP）"""
        # TODO: 集成 CLIP 模型提取图像特征
        # 这里返回模拟的 embedding
        return np.random.randn(self.dimension).tolist()

    def _generate_consistency_prompt(self, features: Dict) -> str:
        """生成一致性控制提示词"""
        prompt_parts = []

        if "appearance_keywords" in features:
            prompt_parts.append(
                "外貌: " + ", ".join(features["appearance_keywords"])
            )

        if "clothing_keywords" in features:
            prompt_parts.append(
                "服装: " + ", ".join(features["clothing_keywords"])
            )

        if "style_keywords" in features:
            prompt_parts.append(
                "风格: " + ", ".join(features["style_keywords"])
            )

        # 添加一致性控制指令
        consistency_instructions = [
            "保持角色外观一致性",
            "相同的发型、发色和面部特征",
            "保持服装风格统一",
        ]

        prompt = "; ".join(prompt_parts)
        prompt += "; " + "; ".join(consistency_instructions)

        return prompt

    async def store_character_features(self, character_id: str, features: Dict) -> bool:
        """
        存储角色特征到向量数据库
        
        Args:
            character_id: 角色ID
            features: 特征数据
            
        Returns:
            是否成功
        """
        # TODO: 实现 Milvus 向量存储
        # from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType
        
        # 目前使用内存存储作为示例
        return True

    async def search_similar_characters(
        self,
        query_features: List[float],
        top_k: int = 5
    ) -> List[Dict]:
        """
        搜索相似角色
        
        Args:
            query_features: 查询特征向量
            top_k: 返回数量
            
        Returns:
            相似角色列表
        """
        # TODO: 实现 Milvus 向量搜索
        return []

    async def check_consistency(
        self,
        character_id: str,
        generated_image_url: str
    ) -> Dict:
        """
        检查生成图像与角色特征的一致性
        
        Args:
            character_id: 角色ID
            generated_image_url: 生成的图像URL
            
        Returns:
            一致性检查结果
        """
        # 1. 提取生成图像的特征
        image_features = await self._extract_image_features(generated_image_url)
        
        # 2. 获取角色特征
        # TODO: 从 Milvus 查询角色特征
        
        # 3. 计算相似度
        similarity = self._calculate_similarity(image_features, [])
        
        return {
            "character_id": character_id,
            "similarity_score": similarity,
            "is_consistent": similarity > 0.8,
            "suggestions": self._generate_suggestions(similarity),
        }

    def _calculate_similarity(
        self,
        features1: List[float],
        features2: List[float]
    ) -> float:
        """计算特征相似度（余弦相似度）"""
        if not features1 or not features2:
            return 0.0
        
        vec1 = np.array(features1)
        vec2 = np.array(features2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))

    def _generate_suggestions(self, similarity: float) -> List[str]:
        """根据相似度生成建议"""
        suggestions = []
        
        if similarity < 0.6:
            suggestions.append("角色特征差异较大，建议重新生成")
            suggestions.append("检查角色描述是否足够详细")
        elif similarity < 0.8:
            suggestions.append("角色特征部分匹配，可微调后使用")
            suggestions.append("建议调整发型或服装细节")
        else:
            suggestions.append("角色特征高度一致，可以使用")
        
        return suggestions

    def get_consistency_prompt(self, character_id: str) -> str:
        """
        获取角色一致性控制提示词
        
        Args:
            character_id: 角色ID
            
        Returns:
            一致性控制提示词
        """
        # TODO: 从数据库获取并返回
        return "保持角色外观一致性，相同的发型、发色和面部特征"


# 服务实例
character_consistency_service = CharacterConsistencyService()