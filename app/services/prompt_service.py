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
                "role": "Create an engaging, human-like prompt for initial PR analysis",
                "requirements": [
                    "Make it conversational and friendly",
                    "Include clear instructions to analyze the code changes",
                    "Emphasize fact-based analysis only",
                    "Include strong anti-hallucination guidelines",
                    "Use emojis and engaging language",
                    "Structure with clear sections and goals"
                ],
                "focus": "Initial comprehensive analysis of the PR changes"
            },
            "deepdive": {
                "role": "Create a technical deep-dive prompt for detailed code analysis",
                "requirements": [
                    "Focus on technical implementation details",
                    "Structure with clear technical categories",
                    "Encourage specific code examples and patterns",
                    "Maintain engaging but professional tone",
                    "Include architectural and performance considerations"
                ],
                "focus": "Detailed technical analysis of implementation"
            },
            "memory_only": {
                "role": "Create a strict memory-only prompt for retention testing",
                "requirements": [
                    "Very clear instructions about memory-only mode",
                    "Strong warnings about not referencing original content",
                    "Encourage honesty about unclear memories",
                    "Structure for comprehensive memory recall",
                    "Include guidelines for honest limitations"
                ],
                "focus": "Testing retention and memory of previous analysis"
            },
            "evaluator_set": {
                "role": "Create specific evaluation questions for memory-break assessment",
                "requirements": [
                    "12 specific questions covering AR, TTL, LRU, SF dimensions",
                    "Clear instructions for each question type",
                    "Emphasize specific, honest answers only",
                    "Include response quality guidelines",
                    "Structure by evaluation dimensions"
                ],
                "focus": "Structured evaluation of memory and understanding"
            }
        }
        
        instruction = generation_instructions.get(prompt_type, generation_instructions["precompression"])
        
        # Create GPT prompt for prompt generation
        gpt_prompt = f"""You are an expert at creating engaging, human-like prompts for AI agents analyzing GitHub Pull Requests. You need to create a {prompt_type} prompt.

**Your Role:** {instruction['role']}

**Context about this PR:**
- Repository: {context['repo_name']}
- PR Number: #{context['pr_number']}
- Files Changed: {context['file_count']} files (showing first {context['max_files']} files)
- Base Branch: {context['base_branch']}
- Head Branch: {context['head_branch']}

**Files in this PR:**
{context['file_list']}

**Requirements for the prompt you create:**
{chr(10).join(f"- {req}" for req in instruction['requirements'])}

**Focus:** {instruction['focus']}

**CRITICAL ANTI-HALLUCINATION GUIDELINES:**
- The prompt MUST emphasize analyzing only the actual code shown
- Include strong warnings against inventing functions/classes not present
- Encourage saying "I don't see this in the code" rather than guessing
- Emphasize fact-based analysis over speculation

**Template variables to include in your prompt:**
- {{{{ repo_name }}}} - Repository name
- {{{{ pr_number }}}} - PR number
- {{{{ file_count }}}} - Number of files
- {{{{ file_list }}}} - List of changed files
- {{{{ at_files }}}} - Complete file contents
- {{{{ base_branch }}}} and {{{{ head_branch }}}} - Branch names

Create an engaging, professional, human-like prompt that will generate high-quality analysis while preventing hallucination. Use markdown formatting, emojis where appropriate, and clear structure."""

        try:
            response = self.client.chat.completions.create(
                model=settings.prompt_model,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert prompt engineer creating high-quality, engaging prompts for code analysis."
                    },
                    {"role": "user", "content": gpt_prompt}
                ],
                temperature=settings.prompt_temperature,
                max_tokens=settings.prompt_max_tokens
            )
            
            generated_prompt = response.choices[0].message.content.strip()
            
            self.logger.info(f"Generated {prompt_type} prompt: {len(generated_prompt)} characters")
            
            return generated_prompt
            
        except Exception as e:
            self.logger.error(f"GPT API call failed for {prompt_type}: {e}")
            # Fallback to a basic template if GPT fails
            return self._get_fallback_prompt(prompt_type, context)
    
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
