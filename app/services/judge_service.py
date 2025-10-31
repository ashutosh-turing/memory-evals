"""Judge service for evaluating agent performance using multiple judge types."""

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

import openai
import anthropic

from app.config import settings
from app.domain.entities import RubricDimension

logger = logging.getLogger(__name__)


class JudgeError(Exception):
    """Base exception for judge errors."""
    pass


class Judge(ABC):
    """Abstract base class for judges."""
    
    @abstractmethod
    def evaluate(
        self,
        questions: List[str],
        pre_compression_answers: List[str],
        post_compression_answers: List[str],
        rubric: List[RubricDimension],
    ) -> Tuple[Dict[RubricDimension, float], str]:
        """
        Evaluate agent performance.
        
        Args:
            questions: List of evaluation questions
            pre_compression_answers: Agent answers before compression
            post_compression_answers: Agent answers after compression
            rubric: List of rubric dimensions to evaluate
            
        Returns:
            Tuple of (scores_dict, rationale_string)
        """
        pass


class HeuristicJudge(Judge):
    """Heuristic-based judge using keyword matching and analysis."""
    
    def __init__(self):
        self.logger = logging.getLogger("judge.heuristic")
    
    def evaluate(
        self,
        questions: List[str],
        pre_compression_answers: List[str],
        post_compression_answers: List[str],
        rubric: List[RubricDimension],
    ) -> Tuple[Dict[RubricDimension, float], str]:
        """Evaluate using heuristic methods."""
        
        self.logger.info(f"Evaluating with heuristic judge: {len(questions)} questions")
        
        scores = {}
        rationale_parts = []
        
        # Analyze each rubric dimension
        for dimension in rubric:
            score, rationale = self._evaluate_dimension(
                dimension, questions, pre_compression_answers, post_compression_answers
            )
            scores[dimension] = score
            rationale_parts.append(f"{dimension.value}: {rationale}")
        
        combined_rationale = "\n".join(rationale_parts)
        
        self.logger.info(f"Heuristic evaluation complete: {scores}")
        return scores, combined_rationale
    
    def _evaluate_dimension(
        self,
        dimension: RubricDimension,
        questions: List[str],
        pre_answers: List[str],
        post_answers: List[str],
    ) -> Tuple[float, str]:
        """Evaluate a specific rubric dimension."""
        
        if dimension == RubricDimension.AR:  # Accurate Retrieval
            return self._evaluate_accurate_retrieval(questions, pre_answers, post_answers)
        elif dimension == RubricDimension.TTL:  # Test-Time Learning
            return self._evaluate_test_time_learning(questions, pre_answers, post_answers)
        elif dimension == RubricDimension.LRU:  # Long-Range Understanding
            return self._evaluate_long_range_understanding(questions, pre_answers, post_answers)
        elif dimension == RubricDimension.SF:  # Selective Forgetting
            return self._evaluate_selective_forgetting(questions, pre_answers, post_answers)
        else:
            return 0.5, f"Unknown dimension: {dimension}"
    
    def _evaluate_accurate_retrieval(
        self, questions: List[str], pre_answers: List[str], post_answers: List[str]
    ) -> Tuple[float, str]:
        """Evaluate accurate retrieval capability."""
        
        # Look for specific details that should be retained
        detail_keywords = [
            "function", "method", "class", "variable", "file", "import",
            "def ", "async ", "await", "return", "raise", "except",
            "if ", "for ", "while ", "with "
        ]
        
        pre_details = self._count_keywords(pre_answers, detail_keywords)
        post_details = self._count_keywords(post_answers, detail_keywords)
        
        # Score based on retention of specific details
        if pre_details == 0:
            score = 0.5  # No baseline details
            rationale = "No specific details found in pre-compression answers"
        else:
            retention_ratio = min(post_details / pre_details, 1.0)
            score = 0.3 + (0.7 * retention_ratio)  # Base 0.3, up to 1.0
            rationale = f"Retained {post_details}/{pre_details} specific details ({retention_ratio:.2%})"
        
        return score, rationale
    
    def _evaluate_test_time_learning(
        self, questions: List[str], pre_answers: List[str], post_answers: List[str]
    ) -> Tuple[float, str]:
        """Evaluate test-time learning and adaptation."""
        
        # Look for learning indicators
        learning_keywords = [
            "would", "could", "should", "approach", "strategy", "implement",
            "similar", "adapt", "modify", "improve", "optimize", "consider"
        ]
        
        learning_indicators = self._count_keywords(post_answers, learning_keywords)
        total_words = len(" ".join(post_answers).split())
        
        if total_words == 0:
            score = 0.0
            rationale = "No answers provided"
        else:
            learning_density = learning_indicators / max(total_words, 1) * 100
            score = min(learning_density / 2, 1.0)  # Normalize to 0-1 range
            rationale = f"Learning indicators: {learning_indicators} in {total_words} words ({learning_density:.1f}%)"
        
        return score, rationale
    
    def _evaluate_long_range_understanding(
        self, questions: List[str], pre_answers: List[str], post_answers: List[str]
    ) -> Tuple[float, str]:
        """Evaluate long-range understanding and connections."""
        
        # Look for connection indicators
        connection_keywords = [
            "connect", "relate", "depend", "impact", "affect", "integrate",
            "system", "architecture", "component", "module", "service",
            "because", "therefore", "however", "moreover", "furthermore"
        ]
        
        connections = self._count_keywords(post_answers, connection_keywords)
        
        # Look for architectural terms
        arch_keywords = [
            "pattern", "design", "structure", "framework", "library",
            "database", "api", "interface", "protocol", "service"
        ]
        
        arch_terms = self._count_keywords(post_answers, arch_keywords)
        
        total_indicators = connections + arch_terms
        score = min(total_indicators / 10, 1.0)  # Normalize to 0-1
        rationale = f"Connection indicators: {connections}, Architecture terms: {arch_terms}"
        
        return score, rationale
    
    def _evaluate_selective_forgetting(
        self, questions: List[str], pre_answers: List[str], post_answers: List[str]
    ) -> Tuple[float, str]:
        """Evaluate selective forgetting and updating."""
        
        # Look for update/change indicators
        change_keywords = [
            "change", "update", "modify", "replace", "remove", "delete",
            "revert", "undo", "preserve", "keep", "maintain", "retain"
        ]
        
        change_indicators = self._count_keywords(post_answers, change_keywords)
        
        # Look for conditional reasoning
        conditional_keywords = [
            "if", "when", "unless", "provided", "assuming", "given",
            "depends", "varies", "different", "alternative"
        ]
        
        conditionals = self._count_keywords(post_answers, conditional_keywords)
        
        total_indicators = change_indicators + conditionals
        score = min(total_indicators / 8, 1.0)  # Normalize to 0-1
        rationale = f"Change indicators: {change_indicators}, Conditionals: {conditionals}"
        
        return score, rationale
    
    def _count_keywords(self, texts: List[str], keywords: List[str]) -> int:
        """Count keyword occurrences in texts."""
        combined_text = " ".join(texts).lower()
        count = 0
        for keyword in keywords:
            count += combined_text.count(keyword.lower())
        return count


class LLMJudge(Judge):
    """LLM-based judge using external language models."""
    
    def __init__(self, model: str = "gpt-4", provider: str = "openai"):
        self.model = model
        self.provider = provider.lower()
        self.logger = logging.getLogger("judge.llm")
        
        # Initialize API clients
        if self.provider == "openai" and settings.openai_api_key:
            self.openai_client = openai.OpenAI(api_key=settings.openai_api_key)
        elif self.provider == "anthropic" and settings.anthropic_api_key:
            self.anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        else:
            self.logger.warning(f"No API key configured for {provider}")
    
    def evaluate(
        self,
        questions: List[str],
        pre_compression_answers: List[str],
        post_compression_answers: List[str],
        rubric: List[RubricDimension],
    ) -> Tuple[Dict[RubricDimension, float], str]:
        """Evaluate using LLM judge."""
        
        self.logger.info(f"Evaluating with LLM judge ({self.model}): {len(questions)} questions")
        
        # Create evaluation prompt
        evaluation_prompt = self._build_evaluation_prompt(
            questions, pre_compression_answers, post_compression_answers, rubric
        )
        
        try:
            # Get LLM response
            response = self._query_llm(evaluation_prompt)
            
            # Parse response
            scores, rationale = self._parse_llm_response(response, rubric)
            
            self.logger.info(f"LLM evaluation complete: {scores}")
            return scores, rationale
            
        except Exception as e:
            self.logger.error(f"LLM evaluation failed: {e}")
            # Fallback to heuristic judge
            fallback_judge = HeuristicJudge()
            scores, rationale = fallback_judge.evaluate(
                questions, pre_compression_answers, post_compression_answers, rubric
            )
            rationale = f"LLM evaluation failed, used heuristic fallback: {rationale}"
            return scores, rationale
    
    def _build_evaluation_prompt(
        self,
        questions: List[str],
        pre_answers: List[str],
        post_answers: List[str],
        rubric: List[RubricDimension],
    ) -> str:
        """Build evaluation prompt for LLM."""
        
        rubric_descriptions = {
            RubricDimension.AR: "Accurate Retrieval - How well can the agent recall specific details and facts?",
            RubricDimension.TTL: "Test-Time Learning - How well can the agent adapt and apply knowledge to new scenarios?",
            RubricDimension.LRU: "Long-Range Understanding - How well can the agent understand connections and broader context?",
            RubricDimension.SF: "Selective Forgetting - How well can the agent update/modify its understanding when needed?",
        }
        
        prompt_parts = [
            "# AI Agent Memory-Break Evaluation",
            "",
            "You are evaluating an AI agent's performance before and after a memory compression event.",
            "",
            "## Rubric Dimensions:",
        ]
        
        for dim in rubric:
            prompt_parts.append(f"- **{dim.value}**: {rubric_descriptions.get(dim, 'Unknown dimension')}")
        
        prompt_parts.extend([
            "",
            "## Questions and Answers:",
            "",
        ])
        
        for i, question in enumerate(questions, 1):
            pre_answer = pre_answers[i-1] if i-1 < len(pre_answers) else "No answer"
            post_answer = post_answers[i-1] if i-1 < len(post_answers) else "No answer"
            
            prompt_parts.extend([
                f"### Question {i}: {question}",
                "",
                f"**Pre-compression answer**: {pre_answer}",
                "",
                f"**Post-compression answer**: {post_answer}",
                "",
            ])
        
        prompt_parts.extend([
            "## Instructions:",
            "",
            "Please evaluate the agent's performance on each rubric dimension by comparing the pre and post compression answers.",
            "Provide a score from 0.0 to 1.0 for each dimension, where:",
            "- 0.0 = Complete failure",
            "- 0.5 = Moderate performance", 
            "- 1.0 = Excellent performance",
            "",
            "Format your response as JSON:",
            "```json",
            "{",
            '  "scores": {',
        ])
        
        for i, dim in enumerate(rubric):
            comma = "," if i < len(rubric) - 1 else ""
            prompt_parts.append(f'    "{dim.value}": 0.0{comma}')
        
        prompt_parts.extend([
            '  },',
            '  "rationale": "Detailed explanation of the scoring..."',
            "}",
            "```",
        ])
        
        return "\n".join(prompt_parts)
    
    def _query_llm(self, prompt: str) -> str:
        """Query the configured LLM."""
        
        if self.provider == "openai" and hasattr(self, 'openai_client'):
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.1,
            )
            return response.choices[0].message.content
            
        elif self.provider == "anthropic" and hasattr(self, 'anthropic_client'):
            response = self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
            
        else:
            raise JudgeError(f"No configured client for {self.provider}")
    
    def _parse_llm_response(
        self, response: str, rubric: List[RubricDimension]
    ) -> Tuple[Dict[RubricDimension, float], str]:
        """Parse LLM response to extract scores and rationale."""
        
        try:
            # Extract JSON from response
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if not json_match:
                # Try to find JSON without markdown
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
            
            if not json_match:
                raise ValueError("No JSON found in response")
            
            json_data = json.loads(json_match.group(1))
            
            # Extract scores
            scores_data = json_data.get("scores", {})
            scores = {}
            
            for dim in rubric:
                if dim.value in scores_data:
                    score = float(scores_data[dim.value])
                    scores[dim] = max(0.0, min(1.0, score))  # Clamp to [0,1]
                else:
                    scores[dim] = 0.5  # Default score
            
            rationale = json_data.get("rationale", "No rationale provided")
            
            return scores, rationale
            
        except Exception as e:
            self.logger.error(f"Failed to parse LLM response: {e}")
            # Return default scores
            scores = {dim: 0.5 for dim in rubric}
            rationale = f"Failed to parse LLM response: {str(e)}"
            return scores, rationale


class JudgeService:
    """Service for managing different judge types."""
    
    def __init__(self):
        self.logger = logging.getLogger("services.judge")
        self._judges = {
            "heuristic": HeuristicJudge(),
            "llm": LLMJudge(
                model=settings.judge_model,
                provider="openai" if settings.openai_api_key else "anthropic"
            ),
        }
    
    def get_judge(self, judge_type: str = None) -> Judge:
        """Get judge instance by type."""
        if judge_type is None:
            judge_type = settings.default_judge
        
        if judge_type not in self._judges:
            self.logger.warning(f"Unknown judge type: {judge_type}, using heuristic")
            judge_type = "heuristic"
        
        return self._judges[judge_type]
    
    def evaluate_agent_performance(
        self,
        questions: List[str],
        pre_compression_answers: List[str],
        post_compression_answers: List[str],
        rubric: List[RubricDimension],
        judge_type: str = None,
    ) -> Tuple[Dict[RubricDimension, float], str, str]:
        """
        Evaluate agent performance using specified judge.
        
        Returns:
            Tuple of (scores, rationale, judge_type_used)
        """
        
        judge = self.get_judge(judge_type)
        judge_type_used = judge_type or settings.default_judge
        
        self.logger.info(f"Evaluating agent performance with {judge_type_used} judge")
        
        scores, rationale = judge.evaluate(
            questions, pre_compression_answers, post_compression_answers, rubric
        )
        
        return scores, rationale, judge_type_used
    
    def get_available_judges(self) -> List[str]:
        """Get list of available judge types."""
        return list(self._judges.keys())


# Global instance
_judge_service = None


def get_judge_service() -> JudgeService:
    """Get global judge service instance."""
    global _judge_service
    
    if _judge_service is None:
        _judge_service = JudgeService()
    
    return _judge_service
