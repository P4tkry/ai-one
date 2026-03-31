"""
Centralized truncation management - standardized truncation across all tools and prompts.
All truncation goes through here with consistent formatting and logging.
"""

from typing import Tuple


class TruncationManager:
    """
    Centralized manager for all truncation operations.
    Ensures consistent truncation messages and logging across the system.
    """
    
    MAX_PROMPT_SIZE = 30000  # Hard limit for full prompt sent to shell
    MAX_TOOL_OUTPUT = 15000  # Per-tool output limit
    MAX_LLM_PAYLOAD = 15000  # Total tool output limit in LLM payload
    
    # Truncation markers
    TOOL_TRUNCATED_MARKER = "[OUTPUT TRUNCATED] (use python pypeline to analaze output)"
    PROMPT_TRUNCATED_MARKER = "[TRUNCATED] (use python pypeline to analaze output)"
    
    @staticmethod
    def truncate_tool_output(
        stdout: str | None,
        stderr: str | None,
        tool_name: str = "unknown"
    ) -> Tuple[str, str]:
        """
        Truncate individual tool output with standardized messaging.
        
        Args:
            stdout: Tool's stdout
            stderr: Tool's stderr
            tool_name: Name of the tool (for logging)
        
        Returns:
            Tuple of (truncated_stdout, truncated_stderr)
        """
        stdout = "" if stdout is None else str(stdout)
        stderr = "" if stderr is None else str(stderr)
        
        original_stdout_len = len(stdout)
        original_stderr_len = len(stderr)
        
        truncated = False
        
        # Truncate stdout if needed
        if len(stdout) > TruncationManager.MAX_TOOL_OUTPUT:
            overflow = len(stdout) - TruncationManager.MAX_TOOL_OUTPUT
            stdout = stdout[:TruncationManager.MAX_TOOL_OUTPUT]
            stdout += f"\n\n{TruncationManager.TOOL_TRUNCATED_MARKER} (original: {original_stdout_len} chars, removed: {overflow} chars)\n"
            
            print(f"⚠️  TOOL TRUNCATE [{tool_name}]: stdout {original_stdout_len} → {TruncationManager.MAX_TOOL_OUTPUT} chars (-{overflow})")
            truncated = True
        
        # Truncate stderr if needed
        if len(stderr) > TruncationManager.MAX_TOOL_OUTPUT:
            overflow = len(stderr) - TruncationManager.MAX_TOOL_OUTPUT
            stderr = stderr[:TruncationManager.MAX_TOOL_OUTPUT]
            stderr += f"\n\n{TruncationManager.TOOL_TRUNCATED_MARKER} (original: {original_stderr_len} chars, removed: {overflow} chars)\n"
            
            print(f"⚠️  TOOL TRUNCATE [{tool_name}]: stderr {original_stderr_len} → {TruncationManager.MAX_TOOL_OUTPUT} chars (-{overflow})")
            truncated = True
        
        return stdout, stderr
    
    @staticmethod
    def truncate_prompt_data(
        data: str,
        target_size: int,
        context: str = "tool output"
    ) -> str:
        """
        Truncate prompt data (tool output or user input) with standardized messaging.
        
        Args:
            data: Data to truncate
            target_size: Target size in characters
            context: Context for logging (e.g., "tool output", "user query")
        
        Returns:
            Truncated data with marker
        """
        data = "" if data is None else str(data)
        
        if len(data) <= target_size:
            return data
        
        overflow = len(data) - target_size
        original_len = len(data)
        
        truncated_data = data[:target_size]
        truncated_data += f"\n\n{TruncationManager.PROMPT_TRUNCATED_MARKER} - original: {original_len} chars, kept: {target_size} chars, removed: {overflow} chars\n"
        
        print(f"⚠️  PROMPT TRUNCATE [{context}]: {original_len} → {target_size} chars (-{overflow})")
        
        return truncated_data
    
    @staticmethod
    def verify_total_size(size: int) -> bool:
        """
        Verify that total prompt size is within limits.
        
        Returns:
            True if size is OK, False if exceeds limit
        """
        if size <= TruncationManager.MAX_PROMPT_SIZE:
            return True
        
        overflow = size - TruncationManager.MAX_PROMPT_SIZE
        print(f"\n❌ FATAL: Prompt {size} chars exceeds {TruncationManager.MAX_PROMPT_SIZE} limit (overflow: {overflow})")
        return False
    
    @staticmethod
    def log_approaching_limit(size: int, threshold: int = 25000):
        """
        Log warning if approaching size limit.
        """
        if size > threshold:
            percentage = (size / TruncationManager.MAX_PROMPT_SIZE) * 100
            print(f"\n⚠️  APPROACHING LIMIT: {size}/{TruncationManager.MAX_PROMPT_SIZE} chars ({percentage:.1f}%)\n")
