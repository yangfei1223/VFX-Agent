"""Session Logger：保存 Agent 每次调用的完整 session

保存内容包括：
- System prompt + User prompt
- 输入图片路径
- LLM 原始响应
- 解析后的结果
- Usage 统计
- 时间戳和耗时

用途：
- 调试分析 Agent 行为
- 复现问题场景
- Prompt 优化参考
"""

import json
import time
import uuid
from pathlib import Path
from datetime import datetime


class SessionLogger:
    """保存 Agent session 到 JSON 文件"""
    
    # Session 存储根目录
    SESSION_DIR = Path("app/sessions")
    
    @classmethod
    def save_session(
        cls,
        pipeline_id: str,
        agent_name: str,
        iteration: int,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[str] | None = None,
        raw_response: str = "",
        parsed_result: dict | str | None = None,
        usage: dict | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        model: str = "",
        duration_ms: int = 0,
        human_feedback: str | None = None,
    ) -> str:
        """
        保存 Agent session 到 JSON 文件。
        
        Args:
            pipeline_id: Pipeline ID（用于创建目录）
            agent_name: Agent 名称（decompose/generate/inspect）
            iteration: 当前迭代轮次
            system_prompt: System prompt 内容
            user_prompt: User prompt 内容
            image_paths: 输入图片路径列表
            raw_response: LLM 原始响应
            parsed_result: 解析后的结果（dict 或 str）
            usage: Token 使用统计
            temperature: Temperature 设置
            max_tokens: Max tokens 设置
            model: 使用的模型名称
            duration_ms: 调用耗时（毫秒）
            human_feedback: 用户人工反馈（可选）
        
        Returns:
            session_file_path: Session 文件路径
        """
        # 创建 session 目录
        session_dir = cls.SESSION_DIR / pipeline_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成 session ID 和文件名
        session_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{agent_name}_iter{iteration}_{timestamp}_{session_id}.json"
        session_path = session_dir / filename
        
        # 构建 session 结构
        session_data = {
            "session_id": session_id,
            "pipeline_id": pipeline_id,
            "agent_name": agent_name,
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
            "duration_ms": duration_ms,
            
            "input": {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "image_paths": image_paths or [],
                "image_count": len(image_paths) if image_paths else 0,
                "context": {
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "model": model,
                },
            },
            
            "output": {
                "raw_response": raw_response,
                "response_length": len(raw_response),
                "parsed_result": parsed_result if isinstance(parsed_result, dict) else {"text": parsed_result},
                "usage": usage or {},
            },
            
            "metadata": {
                "human_feedback": human_feedback,
                "agent_iteration": iteration,
            },
        }
        
        # 写入文件
        with open(session_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
        
        print(f"[SessionLogger] Saved session: {session_path}")
        return str(session_path)
    
    @classmethod
    def get_session_dir(cls, pipeline_id: str) -> Path:
        """获取指定 pipeline 的 session 目录"""
        return cls.SESSION_DIR / pipeline_id
    
    @classmethod
    def list_sessions(cls, pipeline_id: str) -> list[str]:
        """列出指定 pipeline 的所有 session 文件"""
        session_dir = cls.SESSION_DIR / pipeline_id
        if not session_dir.exists():
            return []
        return sorted([str(p) for p in session_dir.glob("*.json")])
    
    @classmethod
    def load_session(cls, session_path: str) -> dict:
        """加载指定 session 文件"""
        with open(session_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    @classmethod
    def get_session_summary(cls, pipeline_id: str) -> dict:
        """获取指定 pipeline 的 session 概要"""
        sessions = cls.list_sessions(pipeline_id)
        if not sessions:
            return {"total": 0, "sessions": []}
        
        summary = {
            "total": len(sessions),
            "sessions": [],
            "by_agent": {"decompose": 0, "generate": 0, "inspect": 0},
            "total_tokens": {"prompt": 0, "completion": 0},
            "total_duration_ms": 0,
        }
        
        for session_path in sessions:
            session = cls.load_session(session_path)
            agent = session.get("agent_name", "unknown")
            if agent in summary["by_agent"]:
                summary["by_agent"][agent] += 1
            
            usage = session.get("output", {}).get("usage", {})
            summary["total_tokens"]["prompt"] += usage.get("prompt_tokens", 0)
            summary["total_tokens"]["completion"] += usage.get("completion_tokens", 0)
            
            summary["total_duration_ms"] += session.get("duration_ms", 0)
            
            summary["sessions"].append({
                "file": session_path,
                "agent": agent,
                "iteration": session.get("iteration", 0),
                "timestamp": session.get("timestamp", ""),
                "duration_ms": session.get("duration_ms", 0),
            })
        
        return summary