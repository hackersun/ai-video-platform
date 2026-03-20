"""
Coding Plan API 端点
支持代码规划、技术方案设计、AI生成调用
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.services.dashscope_service import DashScopeService, create_dashscope_service

router = APIRouter(tags=["Coding Plan"])


# ============== 请求/响应模型 ==============

class CodingPlanRequest(BaseModel):
    """代码规划请求"""
    requirement: str = Field(..., description="需求描述")
    model: str = Field("qwen-coder-plus", description="模型ID")
    context: Optional[str] = Field(None, description="额外上下文")
    language: Optional[str] = Field(None, description="目标编程语言")
    api_key: str = Field(..., description="DashScope API Key")


class CodingPlanResponse(BaseModel):
    """代码规划响应"""
    plan: str
    model: str
    usage: dict
    cost: float


class NovelWithPlanRequest(BaseModel):
    """带规划的小说生成请求"""
    prompt: str = Field(..., description="小说主题")
    model: str = Field("qwen-long", description="生成模型，默认使用qwen-long支持长文本")
    api_key: str = Field(..., description="DashScope API Key")


class NovelWithPlanResponse(BaseModel):
    """带规划的小说响应"""
    plan: str
    content: str
    usage: dict
    cost: float


class TechnicalStoryboardRequest(BaseModel):
    """技术分镜请求"""
    scene_description: str = Field(..., description="场景描述")
    technical_requirements: Optional[str] = Field(None, description="技术要求")
    model: str = Field("qwen-coder-plus", description="模型ID")
    api_key: str = Field(..., description="DashScope API Key")


class TechnicalStoryboardResponse(BaseModel):
    """技术分镜响应"""
    storyboard: str
    model: str
    usage: dict
    cost: float


class AutoGenerateRequest(BaseModel):
    """自动生成请求（对话理解 + 规划 + 生成）"""
    user_input: str = Field(..., description="用户输入")
    generate_type: str = Field(..., description="生成类型：novel/storyboard/code")
    context: Optional[List[dict]] = Field(None, description="对话上下文")
    api_key: str = Field(..., description="DashScope API Key")


class AutoGenerateResponse(BaseModel):
    """自动生成响应"""
    understanding: str  # 对话理解结果
    plan: Optional[str]  # 规划（如有）
    result: str  # 最终生成结果
    model_used: str
    total_cost: float


# ============== API端点 ==============

@router.post("/generate", response_model=CodingPlanResponse)
async def generate_coding_plan(request: CodingPlanRequest):
    """
    生成 Coding Plan（代码规划）
    
    使用 qwen-coder-plus 进行技术方案设计
    """
    try:
        service = await create_dashscope_service(request.api_key)
        
        response = await service.generate_coding_plan(
            requirement=request.requirement,
            model=request.model,
            context=request.context,
            language=request.language
        )
        
        plan = response["choices"][0]["message"]["content"]
        usage = response.get("usage", {})
        
        cost = service.calculate_request_cost(
            request.model,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0)
        )
        
        return CodingPlanResponse(
            plan=plan,
            model=request.model,
            usage=usage,
            cost=cost
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Coding Plan生成失败: {str(e)}"
        )


@router.post("/novel", response_model=NovelWithPlanResponse)
async def generate_novel_with_plan(request: NovelWithPlanRequest):
    """
    使用 Coding Plan 方式生成小说
    
    先规划情节架构，再生成具体内容
    默认使用 qwen-long 模型支持长文本输出
    """
    try:
        service = await create_dashscope_service(request.api_key)
        
        response = await service.generate_novel_with_plan(
            prompt=request.prompt,
            model=request.model  # 默认 qwen-long
        )
        
        plan = response["plan"]
        content = response["content"]
        usage = response.get("usage", {})
        
        # 计算总成本
        cost = service.calculate_request_cost(
            request.model,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0)
        )
        
        return NovelWithPlanResponse(
            plan=plan,
            content=content,
            usage=usage,
            cost=cost
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"小说生成失败: {str(e)}"
        )


@router.post("/storyboard", response_model=TechnicalStoryboardResponse)
async def generate_technical_storyboard(request: TechnicalStoryboardRequest):
    """
    生成技术分镜方案
    
    结合代码规划能力，生成技术实现导向的分镜
    """
    try:
        service = await create_dashscope_service(request.api_key)
        
        response = await service.generate_technical_storyboard(
            scene_description=request.scene_description,
            technical_requirements=request.technical_requirements,
            model=request.model
        )
        
        storyboard = response["choices"][0]["message"]["content"]
        usage = response.get("usage", {})
        
        cost = service.calculate_request_cost(
            request.model,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0)
        )
        
        return TechnicalStoryboardResponse(
            storyboard=storyboard,
            model=request.model,
            usage=usage,
            cost=cost
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"技术分镜生成失败: {str(e)}"
        )


@router.post("/auto-generate", response_model=AutoGenerateResponse)
async def auto_generate(request: AutoGenerateRequest):
    """
    自动生成（对话理解 + 规划 + 生成）
    
    一站式AI生成调用：
    1. 理解用户需求
    2. 生成规划（Coding Plan）
    3. 执行生成
    """
    try:
        service = await create_dashscope_service(request.api_key)
        
        # 第一步：对话理解
        understanding_response = await service.understand_dialogue(
            user_input=request.user_input,
            context=request.context,
            model="qwen-plus"
        )
        
        understanding = understanding_response["choices"][0]["message"]["content"]
        
        # 第二步：根据类型执行生成
        plan = None
        result = None
        total_cost = 0
        
        if request.generate_type == "novel":
            # 小说生成 - 默认使用 qwen-long 支持长文本
            novel_response = await service.generate_novel_with_plan(
                prompt=request.user_input,
                model="qwen-long"
            )
            plan = novel_response.get("plan", "")
            result = novel_response.get("content", "")
            
        elif request.generate_type == "storyboard":
            # 分镜生成
            storyboard_response = await service.generate_technical_storyboard(
                scene_description=request.user_input,
                model="qwen-coder-plus"
            )
            result = storyboard_response["choices"][0]["message"]["content"]
            
        elif request.generate_type == "code":
            # 代码生成
            code_response = await service.generate_coding_plan(
                requirement=request.user_input,
                model="qwen-coder-plus"
            )
            result = code_response["choices"][0]["message"]["content"]
        else:
            result = "未知的生成类型"
        
        # 计算总成本
        total_cost = 0.1  # 简化计算
        
        return AutoGenerateResponse(
            understanding=understanding,
            plan=plan,
            result=result,
            model_used=request.generate_type,
            total_cost=total_cost
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"自动生成失败: {str(e)}"
        )
