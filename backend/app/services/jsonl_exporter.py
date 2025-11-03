"""JSONL exporter service for agent evaluation data."""

import json
import logging
from typing import Dict, List, Any
from uuid import UUID

from app.infrastructure.database import TaskDB, AgentRunDB, ScoreDB
from app.domain.entities import RubricDimension

logger = logging.getLogger(__name__)

# Rubric dimension full names
RUBRIC_NAMES = {
    "AR": "Accurate Retrieval",
    "TTL": "Test-Time Learning",
    "LRU": "Long-Range Understanding",
    "SF": "Selective Forgetting"
}


class JSONLExporter:
    """Service for exporting agent evaluation data to JSONL format."""
    
    @staticmethod
    def generate_task_jsonl(
        task_db: TaskDB,
        agent_runs: List[AgentRunDB],
        scores_map: Dict[str, ScoreDB]
    ) -> str:
        """
        Generate a single JSONL file containing all agents' evaluation data.
        
        Each line in the JSONL file represents one agent's complete evaluation.
        
        Args:
            task_db: Task database record
            agent_runs: List of agent run records for the task
            scores_map: Dictionary mapping agent names to their score records
            
        Returns:
            JSONL string with one JSON object per line (one per agent)
        """
        lines = []
        
        for agent_run in agent_runs:
            # Get agent name
            agent_name = agent_run.agent.value if hasattr(agent_run.agent, 'value') else str(agent_run.agent)
            
            # Get scores for this agent
            scores = scores_map.get(agent_name)
            
            # Build the JSON object for this agent
            agent_data = JSONLExporter._build_agent_data(
                task_db, agent_run, scores, agent_name
            )
            
            # Convert to JSON string and add to lines
            lines.append(json.dumps(agent_data, indent=None))
        
        # Join with newlines to create JSONL
        return '\n'.join(lines)
    
    @staticmethod
    def _build_agent_data(
        task_db: TaskDB,
        agent_run: AgentRunDB,
        scores: ScoreDB,
        agent_name: str
    ) -> Dict[str, Any]:
        """Build the complete evaluation data structure for one agent."""
        
        # Extract stats
        stats = agent_run.stats or {}
        
        # Build session info
        session_info = {
            "context_limit_tokens": int(stats.get("max_tokens_configured", 200000)),
            "compression_trigger_turn": JSONLExporter._extract_compression_turn(stats),
            "compression_note": JSONLExporter._build_compression_note(stats),
            "detection_method": stats.get("detection_method", "unknown")
        }
        
        # Build rubrics with Q&A
        rubrics = JSONLExporter._build_rubrics(
            task_db.rubric,
            agent_run.qa_interactions or [],
            scores
        )
        
        # Calculate metrics
        metrics = JSONLExporter._calculate_metrics(
            agent_run.qa_interactions or [],
            scores
        )
        
        # Build complete agent data
        return {
            "task_id": str(task_db.id),
            "agent": agent_name,
            "project": "Memory-Break Orchestrator",
            "repository": {
                "local_path": task_db.repo,
                "focus_files": task_db.changed_files[:10]  # Top 10 files
            },
            "session_info": session_info,
            "evaluation": {
                "rubrics": rubrics
            },
            "metrics": metrics
        }
    
    @staticmethod
    def _extract_compression_turn(stats: Dict[str, str]) -> int:
        """Extract the turn number when compression was detected."""
        # Look for deep_dive iteration count
        for key in stats.keys():
            if key.startswith("deep_dive_") and key.endswith("_tokens"):
                # Extract number from key like "deep_dive_3_tokens"
                parts = key.split("_")
                if len(parts) >= 3 and parts[2].isdigit():
                    return int(parts[2])
        
        # Default to 0 if not found
        return 0
    
    @staticmethod
    def _build_compression_note(stats: Dict[str, str]) -> str:
        """Build a human-readable compression note."""
        detection_method = stats.get("detection_method", "unknown")
        compression_detected = stats.get("compression_detected", "false").lower() == "true"
        
        if not compression_detected:
            return "No memory compression detected during evaluation"
        
        if detection_method == "token_jump":
            return "Memory compression detected via token count drop (30%+ decrease)"
        elif detection_method == "response_analysis":
            return "Memory compression detected via response keyword analysis"
        elif detection_method == "token_limit_flag":
            return "Memory compression detected via iFlow SDK token limit flag"
        elif detection_method == "token_estimate_exceeded":
            return "Memory compression triggered by token estimate exceeding limit"
        else:
            return f"Memory compression detected via {detection_method}"
    
    @staticmethod
    def _build_rubrics(
        rubric_dimensions: List[str],
        qa_interactions: List[Dict],
        scores: ScoreDB
    ) -> List[Dict[str, Any]]:
        """Build rubrics array with Q&A grouped by dimension."""
        
        rubrics = []
        
        # Group Q&A by rubric dimension
        # For now, we'll distribute Q&A evenly across dimensions
        # In a real implementation, each Q&A would be tagged with its dimension
        qa_per_dimension = len(qa_interactions) // len(rubric_dimensions) if rubric_dimensions else 0
        
        for i, dim in enumerate(rubric_dimensions):
            # Get dimension name
            dim_key = dim if isinstance(dim, str) else dim.value if hasattr(dim, 'value') else str(dim)
            dim_name = RUBRIC_NAMES.get(dim_key, dim_key)
            
            # Get Q&A for this dimension
            start_idx = i * qa_per_dimension
            end_idx = start_idx + qa_per_dimension if i < len(rubric_dimensions) - 1 else len(qa_interactions)
            dimension_qa = qa_interactions[start_idx:end_idx]
            
            # Build questions array
            questions = []
            for qa in dimension_qa:
                questions.append({
                    "turn": qa.get("turn", 0),
                    "question": qa.get("question", ""),
                    "ground_truth": qa.get("ground_truth", ""),
                    "agent_response": qa.get("answer", "")
                })
            
            rubrics.append({
                "name": dim_name,
                "questions": questions
            })
        
        return rubrics
    
    @staticmethod
    def _calculate_metrics(
        qa_interactions: List[Dict],
        scores: ScoreDB
    ) -> Dict[str, Any]:
        """Calculate evaluation metrics."""
        
        # Count total turns
        total_turns = len(qa_interactions)
        
        # Count rubrics passed (dimensions where score >= threshold)
        rubrics_passed = 0
        if scores:
            dimension_scores = scores.scores or {}
            thresholds_used = scores.thresholds_used or {}
            
            for dim, score in dimension_scores.items():
                dim_key = dim if isinstance(dim, str) else dim.value if hasattr(dim, 'value') else str(dim)
                threshold = thresholds_used.get(dim_key, 0.7)
                if score >= threshold:
                    rubrics_passed += 1
        
        # Get overall score
        overall_score = scores.overall_score if scores else 0.0
        
        return {
            "total_turns": total_turns,
            "rubrics_passed": rubrics_passed,
            "overall_score": round(overall_score, 2)
        }


def get_jsonl_exporter() -> JSONLExporter:
    """Get JSONL exporter instance."""
    return JSONLExporter()

