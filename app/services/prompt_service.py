"""GPT-powered dynamic prompt generation service."""

import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional
import openai

from app.config import settings
from app.services.pr_service import PRAnalysisResult

logger = logging.getLogger(__name__)


class PromptGenerationError(Exception):
    """Error during prompt generation."""
    pass


class GPTPromptService:
    """Service for generating human-like prompts using GPT."""
    
    def __init__(self):
        self.logger = logging.getLogger("services.gpt_prompt")
        
        # Initialize OpenAI client
        if not settings.openai_api_key:
            raise PromptGenerationError(
                "OpenAI API key is required for GPT prompt generation. "
                "Please set OPENAI_API_KEY in your environment."
            )
        
        self.client = openai.OpenAI(api_key=settings.openai_api_key)
        self.logger.info(f"Initialized GPT prompt service with model: {settings.prompt_model}")
    
    def generate_prompts(
        self,
        pr_result: PRAnalysisResult,
        max_files: int,
        template_names: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """
        Generate all prompts for a PR analysis result using GPT.
        
        Args:
            pr_result: PR analysis result with repo info and changed files
            max_files: Maximum number of files to include (from UI, no hardcoding)
            template_names: Optional list of prompt types to generate
            
        Returns:
            Dictionary mapping prompt names to generated content
            
        Raises:
            PromptGenerationError: If prompt generation fails
        """
        
        # Default prompt types
        if template_names is None:
            template_names = ["precompression", "deepdive", "memory_only", "evaluator_set"]
        
        self.logger.info(
            f"Generating GPT prompts for PR {pr_result.pr_number} "
            f"in {pr_result.repo_full_name}: {template_names} (max_files: {max_files})"
        )
        
        try:
            # Build context for GPT prompt generation
            context = self._build_pr_context(pr_result, max_files)
            
            # Generate each prompt type using GPT
            prompts = {}
            for prompt_type in template_names:
                prompt_content = self._generate_single_prompt_with_gpt(prompt_type, context)
                prompts[prompt_type] = prompt_content
            
            self.logger.info(f"Successfully generated {len(prompts)} GPT prompts")
            
            return prompts
            
        except Exception as e:
            self.logger.error(f"Failed to generate GPT prompts: {e}")
            raise PromptGenerationError(f"GPT prompt generation failed: {e}")
    
    def get_prompt_hash(self, prompts: Dict[str, str]) -> str:
        """Generate hash for prompt reproducibility."""
        
        # Create deterministic hash based on prompt content and settings
        combined_content = f"model:{settings.prompt_model}|temp:{settings.prompt_temperature}|"
        for name in sorted(prompts.keys()):
            combined_content += f"{name}:{prompts[name]}\n"
        
        return hashlib.sha256(combined_content.encode()).hexdigest()[:16]
    
    def _build_pr_context(self, pr_result: PRAnalysisResult, max_files: int) -> Dict:
        """Build comprehensive context about the PR for GPT."""
        
        # Build file contents with size limits (using max_files from UI)
        at_files_content = self._build_at_files_content(pr_result, max_files)
        
        # Create file list
        limited_files = pr_result.changed_files[:max_files]
        file_list = "\n".join([f"- {file_path}" for file_path in limited_files])
        
        context = {
            # Repository information
            "repo_name": pr_result.repo_full_name,
            "repo_owner": pr_result.owner,
            "repo_short_name": pr_result.repo_name,
            "pr_number": pr_result.pr_number,
            "base_branch": pr_result.base_branch,
            "head_branch": pr_result.head_branch,
            "commit_sha": pr_result.commit_sha,
            
            # File information (using max_files from UI)
            "changed_files": limited_files,
            "file_count": len(limited_files),
            "total_files": len(pr_result.changed_files),
            "file_list": file_list,
            "max_files": max_files,
            
            # Content for analysis
            "at_files": at_files_content,
            
            # Metadata
            "truncated": len(pr_result.changed_files) > max_files
        }
        
        return context
    
    def _generate_single_prompt_with_gpt(self, prompt_type: str, context: Dict) -> str:
        """Generate a single prompt using GPT based on the type and context."""
        
        # Define prompt generation instructions for each type
        generation_instructions = {
            "precompression": {
                "role": "Write a casual message asking someone to look at a PR",
                "requirements": [
                    "Write like you're messaging a coworker on Slack",
                    "Keep sentences short and direct",
                    "No emojis, no formal sections",
                    "Just explain what you need them to check",
                    "Be specific about the files but keep it natural",
                    "Tell them not to make stuff up about code they don't see"
                ],
                "focus": "Quick, natural request to analyze the PR"
            },
            "deepdive": {
                "role": "Ask someone to dig deeper into the technical details",
                "requirements": [
                    "Casual tone like chatting with a teammate",
                    "Ask them to look at specific technical stuff",
                    "Short sentences, direct questions",
                    "No fancy formatting or structure",
                    "Just say what technical aspects to check",
                    "Keep it conversational"
                ],
                "focus": "Getting them to look at implementation details"
            },
            "memory_only": {
                "role": "Tell someone to recall what they remember without looking back",
                "requirements": [
                    "Be clear they can't look at the code again",
                    "Keep it casual but firm about the rules",
                    "Tell them it's okay to say they don't remember",
                    "Short, direct instructions",
                    "No formal structure",
                    "Like asking a friend to recall something"
                ],
                "focus": "Testing what they remember from before"
            },
            "evaluator_set": {
                "role": "Ask specific questions to test their memory and understanding",
                "requirements": [
                    "Write 12 straightforward questions",
                    "Keep each question short and clear",
                    "No fancy formatting",
                    "Just ask what you want to know",
                    "Tell them to be honest if they don't know",
                    "Casual but specific"
                ],
                "focus": "Direct questions about what they learned"
            }
        }
        
        instruction = generation_instructions.get(prompt_type, generation_instructions["precompression"])
        
        # Create GPT prompt for prompt generation
        gpt_prompt = f"""Write a casual message asking someone to analyze this PR. Write like you're messaging a colleague on Slack.

PR: {context['repo_name']} #{context['pr_number']}
Files changed: {context['file_count']}
{context['file_list']}

What you need to do: {instruction['role']}

Keep it natural and conversational. Short sentences. No emojis. No fancy formatting. Just tell them what to look at and remind them to only talk about code they actually see.

This is for {prompt_type} - {instruction['focus']}

Requirements:
{chr(10).join(f"- {req}" for req in instruction['requirements'])}

Use the actual repo name and PR number above. Don't use template variables. Write it like you're talking directly to them."""

        try:
            response = self.client.chat.completions.create(
                model=settings.prompt_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a casual developer writing quick messages to a colleague. Write naturally like you're on Slack - short sentences, direct, no fluff. Skip emojis and formal structure. Sound human, not AI."
                    },
                    {"role": "user", "content": gpt_prompt}
                ],
                temperature=settings.prompt_temperature,
                max_completion_tokens=settings.prompt_max_tokens
            )
            
            generated_prompt = response.choices[0].message.content.strip()
            
            # Replace template variables with actual values
            filled_prompt = self._fill_template_variables(generated_prompt, context)
            
            # Log if there are still unfilled templates
            if '{{' in filled_prompt:
                self.logger.warning(f"Unfilled templates detected in {prompt_type} prompt")
                self.logger.warning(f"Sample: {filled_prompt[:300]}")
            
            self.logger.info(f"Generated {prompt_type} prompt: {len(filled_prompt)} characters")
            
            return filled_prompt
            
        except Exception as e:
            self.logger.error(f"GPT API call failed for {prompt_type}: {e}")
            # Fallback to a basic template if GPT fails
            fallback = self._get_fallback_prompt(prompt_type, context)
            return self._fill_template_variables(fallback, context)
    
    def _fill_template_variables(self, prompt: str, context: Dict) -> str:
        """Replace template variables in the prompt with actual values."""
        
        # Define all possible template variables and their replacements
        replacements = {
            "{{ repo_name }}": context.get("repo_name", ""),
            "{{repo_name}}": context.get("repo_name", ""),
            "{{ pr_number }}": str(context.get("pr_number", "")),
            "{{pr_number}}": str(context.get("pr_number", "")),
            "{{ file_count }}": str(context.get("file_count", "")),
            "{{file_count}}": str(context.get("file_count", "")),
            "{{ file_list }}": context.get("file_list", ""),
            "{{file_list}}": context.get("file_list", ""),
            "{{ at_files }}": context.get("at_files", ""),
            "{{at_files}}": context.get("at_files", ""),
            "{{ base_branch }}": context.get("base_branch", ""),
            "{{base_branch}}": context.get("base_branch", ""),
            "{{ head_branch }}": context.get("head_branch", ""),
            "{{head_branch}}": context.get("head_branch", ""),
        }
        
        filled_prompt = prompt
        for template_var, value in replacements.items():
            filled_prompt = filled_prompt.replace(template_var, str(value))
        
        return filled_prompt
    
    def _build_at_files_content(self, pr_result: PRAnalysisResult, max_files: int) -> str:
        """Build the file contents section with EXTREME memory safety to prevent segfaults."""
        
        try:
            from app.services.pr_service import PRService
            import gc
            import signal
            
            # CRITICAL: Ultra-conservative limits to prevent crashes
            ABSOLUTE_MAX_TOTAL = 15000      # Drastically reduced total size
            ABSOLUTE_MAX_FILE = 1000        # Much smaller per-file limit  
            ABSOLUTE_MAX_FILES = 10         # Severely limit file count
            MAX_FILE_SIZE_BYTES = 10240     # 10KB max file size on disk
            
            pr_service = PRService()
            at_files_parts = []
            total_chars = 0
            
            # Ultra-conservative file count
            safe_max_files = min(max_files, ABSOLUTE_MAX_FILES)
            files_to_process = pr_result.changed_files[:safe_max_files]
            
            self.logger.info(f"SAFE MODE: Processing only {len(files_to_process)} files with ultra-conservative limits")
            
            # Process files with extreme caution
            processed_count = 0
            for i, file_path in enumerate(files_to_process):
                try:
                    # CRITICAL: Check current memory usage
                    if len('\n'.join(at_files_parts)) > ABSOLUTE_MAX_TOTAL // 2:
                        at_files_parts.append("... [STOPPED: Memory limit approached]")
                        break
                    
                    # CRITICAL: File size check BEFORE reading
                    full_path = pr_result.repo_path / file_path
                    if not full_path.exists() or not full_path.is_file():
                        continue
                    
                    file_size = full_path.stat().st_size
                    if file_size > MAX_FILE_SIZE_BYTES:
                        at_files_parts.extend([
                            f"📄 **{file_path}** (size: {file_size:,} bytes - SKIPPED)",
                            "File too large for safe processing",
                            ""
                        ])
                        continue
                    
                    # CRITICAL: Read file with extreme safety
                    try:
                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                            # Read only small chunks to prevent memory explosion
                            content = f.read(ABSOLUTE_MAX_FILE)
                            
                        # CRITICAL: Aggressive truncation
                        if len(content) > ABSOLUTE_MAX_FILE:
                            content = content[:ABSOLUTE_MAX_FILE] + "\n... [TRUNCATED]"
                        
                        # CRITICAL: Safe content filtering  
                        content = self._sanitize_content(content, ABSOLUTE_MAX_FILE // 2)
                        
                    except Exception as read_error:
                        at_files_parts.extend([
                            f"📄 **{file_path}** - READ ERROR",
                            f"Could not read: {str(read_error)[:50]}",
                            ""
                        ])
                        continue
                    
                    # CRITICAL: Check total size before adding
                    new_section = f"📄 **{file_path}**\n{content}\n"
                    if total_chars + len(new_section) > ABSOLUTE_MAX_TOTAL:
                        at_files_parts.append("... [STOPPED: Total size limit reached]")
                        break
                    
                    # Safe to add
                    at_files_parts.extend([
                        f"📄 **{file_path}**",
                        content,
                        ""
                    ])
                    
                    total_chars += len(new_section)
                    processed_count += 1
                    
                    # CRITICAL: Force garbage collection every few files
                    if processed_count % 3 == 0:
                        gc.collect()
                    
                    # CRITICAL: Emergency brake
                    if processed_count >= 5:  # Process max 5 files
                        at_files_parts.append("... [STOPPED: Safety limit reached]")
                        break
                        
                except Exception as file_error:
                    self.logger.warning(f"Error processing {file_path}: {file_error}")
                    at_files_parts.extend([
                        f"📄 **{file_path}** - ERROR",
                        "Processing failed",
                        ""
                    ])
                    continue
            
            # CRITICAL: Build result with final safety checks
            result_parts = at_files_parts[:50]  # Limit number of parts
            result = "\n".join(result_parts)
            
            # CRITICAL: Final truncation if needed
            if len(result) > ABSOLUTE_MAX_TOTAL:
                result = result[:ABSOLUTE_MAX_TOTAL] + "\n... [FINAL TRUNCATION]"
            
            # Force garbage collection before return
            gc.collect()
            
            self.logger.info(f"SAFE MODE: Generated {len(result)} chars from {processed_count} files")
            return result
            
        except Exception as e:
            self.logger.error(f"CRITICAL ERROR in file processing: {e}")
            # CRITICAL: Return absolute minimal content to prevent crash
            try:
                file_list = ', '.join(pr_result.changed_files[:3])
                return f"Files: {file_list}\n\nERROR: {str(e)[:100]}"
            except:
                return "ERROR: Unable to process files safely"
    
    def _sanitize_content(self, content: str, max_length: int) -> str:
        """Sanitize content to prevent memory issues."""
        if not content:
            return ""
        
        try:
            # Remove very long lines that might cause issues
            lines = content.split('\n')
            safe_lines = []
            
            for line in lines[:50]:  # Max 50 lines
                if len(line) > 200:  # Truncate long lines
                    line = line[:200] + "..."
                safe_lines.append(line)
                
                # Stop if we're getting too much content
                if len('\n'.join(safe_lines)) > max_length:
                    break
            
            result = '\n'.join(safe_lines)
            
            # Final truncation
            if len(result) > max_length:
                result = result[:max_length] + "..."
                
            return result
            
        except Exception:
            return "Content could not be processed safely"
    
    def _get_fallback_prompt(self, prompt_type: str, context: Dict) -> str:
        """Provide fallback prompts if GPT generation fails."""
        
        fallbacks = {
            "precompression": f"""# 🔍 Pull Request Analysis: {{{{ repo_name }}}} #{{{{ pr_number }}}}

I need you to analyze this GitHub Pull Request that modifies {{{{ file_count }}}} files. Please provide a thorough, fact-based analysis.

## 📋 PR Details
- **Repository**: {{{{ repo_name }}}}
- **PR Number**: #{{{{ pr_number }}}}
- **Files Changed**: {{{{ file_count }}}}

## 📁 Files Modified
{{{{ file_list }}}}

## 📄 File Contents
{{{{ at_files }}}}

**⚠️ IMPORTANT:** Base your analysis only on the actual code shown above. Do not make assumptions about code you cannot see.

Please analyze the purpose, implementation, and impact of these changes.""",

            "deepdive": """# 🧠 Technical Deep Dive

Now let's examine the technical implementation details more closely.

Please analyze:
1. **Implementation patterns** you observe in the code
2. **Technical approaches** used 
3. **Error handling** mechanisms present
4. **Integration points** with existing code

Focus on what you can specifically observe in the provided code.""",

            "memory_only": """# 🧠 Memory-Only Analysis

**⚠️ CRITICAL:** You are now in memory-only mode. Do NOT reference the original code.

Based purely on your memory from the previous analysis:
1. What was the main purpose of this PR?
2. Which files were most important?
3. What implementation details do you remember?

If you don't remember something clearly, say so rather than guessing.""",

            "evaluator_set": """# 📊 Evaluation Questions

Answer based only on your memory from previous analysis:

**AR (Accurate Retrieval):**
1. What was the main purpose of this PR?
2. Which key files were changed?

**TTL (Test-Time Learning):**
3. How would you implement something similar?
4. What would be most challenging?

**LRU (Long-Range Understanding):**
5. How do these changes fit the broader system?
6. What other parts might be affected?

**SF (Selective Forgetting):**
7. What would need to be reverted if this PR was rolled back?
8. Which parts are core vs peripheral?

Be specific and honest about what you remember."""
        }
        
        return fallbacks.get(prompt_type, fallbacks["precompression"])


def get_prompt_service() -> GPTPromptService:
    """Get global GPT prompt service instance."""
    global _gpt_prompt_service
    
    if '_gpt_prompt_service' not in globals():
        if settings.use_gpt_prompts:
            _gpt_prompt_service = GPTPromptService()
        else:
            # Fallback to template-based service if GPT is disabled
            from app.services.template_prompt_service import TemplatePromptService
            _gpt_prompt_service = TemplatePromptService()
    
    return _gpt_prompt_service


# Backwards compatibility
PromptService = GPTPromptService
