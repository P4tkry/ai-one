"""
Execution Engine for AI-ONE.

The Executor is the heart of the system - it orchestrates conversation flow,
parses LLM responses, dispatches tools, and manages the complete request-response cycle.

Architecture:
    User Input → Session → Executor → LLM Provider → Response Processing → Tool Dispatch → Results
"""

import json
import json
import logging
import time
import traceback
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum

from one_think.core.session import Session
from one_think.core.message import (
    Message, SystemMessage, UserMessage, AssistantMessage, 
    ToolResultMessage, SystemRefreshMessage, MessageType
)
from one_think.core.protocol import (
    Protocol, ProtocolParseResult, ToolRequest as ProtocolToolRequest, 
    LLMResponse, SystemRefreshRequest, ToolCall, ResponseType, WorkflowRequest
)
from one_think.core.workflow_executor import WorkflowExecutor
from one_think.tools.registry import ToolRegistry, tool_registry as global_registry
from one_think.tools.base import ToolResponse
from one_think.debug import (
    debug_component, debug_llm_call, debug_llm_response, 
    debug_tool_execution, debug_tool_result, debug_protocol_parse
)


logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Status of execution operation."""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"
    TOOL_ERROR = "tool_error"
    PARSE_ERROR = "parse_error"


@dataclass
class ToolRequest:
    """Tool request for executor compatibility."""
    tool_name: str
    params: Dict[str, Any]
    id: Optional[str] = None


@dataclass  
class ExecutionResult:
    """Result of executing a user request."""
    status: ExecutionStatus
    response: str
    tool_results: List[ToolResponse] = None
    errors: List[str] = None
    execution_time_ms: float = 0
    session_id: str = None
    request_id: str = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = asdict(self)
        result['status'] = self.status.value
        if self.tool_results:
            result['tool_results'] = [tr.to_dict() for tr in self.tool_results]
        return result


class ExecutorError(Exception):
    """Base exception for executor errors."""
    pass


class ToolDispatchError(ExecutorError):
    """Raised when tool dispatching fails."""
    pass


class LLMProviderError(ExecutorError):
    """Raised when LLM provider fails."""
    pass


class Executor:
    """
    Main execution engine for AI-ONE conversations.
    
    The Executor orchestrates the complete conversation flow:
    1. Receives user input and adds to session
    2. Sends conversation to LLM provider
    3. Parses LLM response (text, tool requests, system refresh)
    4. Dispatches tools using Tool Registry
    5. Processes results and continues conversation
    6. Returns final response to user
    
    Features:
    - Tool request parsing and dispatching
    - Session state management
    - Error handling and recovery
    - Structured logging and metrics
    - Provider abstraction (ready for different LLMs)
    """
    
    def __init__(
        self, 
        tool_registry: Optional[ToolRegistry] = None,
        protocol: Optional[Protocol] = None,
        llm_provider: Optional[Union[Callable, 'LLMProvider']] = None,
        max_tool_iterations: int = 5,
        progress_callback: Optional[Callable[[str, str], None]] = None
    ):
        """
        Initialize executor.
        
        Args:
            tool_registry: Registry for tool discovery and dispatch
            protocol: Protocol parser for LLM responses  
            llm_provider: Function OR Provider instance to send messages to LLM
            max_tool_iterations: Maximum number of tool call iterations per request
        """
        self.tool_registry = tool_registry if tool_registry is not None else global_registry
        self.protocol = protocol or Protocol()
        self.llm_provider = llm_provider
        self.max_tool_iterations = max_tool_iterations
        self.progress_callback = progress_callback
        
        # Initialize workflow executor
        self.workflow_executor = WorkflowExecutor(self.tool_registry)
        
        # Ensure tool registry is initialized
        if self.tool_registry and not self.tool_registry._discovery_performed:
            tool_count = self.tool_registry.discover_tools()
            logger.info(f"Executor initialized with {tool_count} tools")
    
    def execute_request(
        self, 
        user_input: str, 
        session: Session,
        system_prompt: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> ExecutionResult:
        """
        Execute a complete user request.
        
        This is the main entry point that handles:
        1. Adding user message to session
        2. LLM communication loop  
        3. Tool dispatching
        4. Response generation
        
        Args:
            user_input: The user's message/request
            session: Session to execute in
            system_prompt: Optional system prompt (if first message)
            request_id: Optional request correlation ID
            
        Returns:
            ExecutionResult with response and metadata
        """
        start_time = datetime.now()
        execution_id = request_id or f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        logger.info(f"Executing request {execution_id} in session {session.id}")
        
        try:
            # Record request start in session statistics
            session.record_request(had_error=False)
            
            # Execute the conversation loop with Copilot CLI session management
            response, tool_results, errors = self._execute_conversation_loop(
                session, execution_id, user_input, system_prompt
            )
            
            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Determine status
            if errors:
                status = ExecutionStatus.TOOL_ERROR if tool_results else ExecutionStatus.ERROR
            else:
                status = ExecutionStatus.SUCCESS
            
            result = ExecutionResult(
                status=status,
                response=response,
                tool_results=tool_results,
                errors=errors,
                execution_time_ms=execution_time,
                session_id=session.id,
                request_id=execution_id
            )
            
            logger.info(f"Request {execution_id} completed: {status.value} in {execution_time:.1f}ms")
            return result
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            error_msg = f"Execution failed: {str(e)}"
            logger.error(f"Request {execution_id} failed: {error_msg}", exc_info=True)
            
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                response=error_msg,
                errors=[error_msg],
                execution_time_ms=execution_time,
                session_id=session.id,
                request_id=execution_id
            )
    
    def _execute_conversation_loop(
        self, 
        session: Session, 
        execution_id: str,
        user_input: str,
        system_prompt: Optional[str] = None
    ) -> tuple[str, List[ToolResponse], List[str]]:
        """
        Execute conversation loop with Copilot CLI session management.
        
        Key changes for Copilot integration:
        - No message history management (handled by Copilot CLI --resume)
        - Build messages incrementally for each iteration including tool results
        - Send structured JSON messages to LLM via Provider
        
        Returns:
            (final_response, tool_results, errors)
        """
        debug_component('executor', 'CONVERSATION_LOOP_START', {
            'execution_id': execution_id,
            'session_id': session.id,
            'max_iterations': self.max_tool_iterations
        })
        
        tool_results = []
        errors = []
        iteration = 0
        
        # Build initial message context
        accumulated_tool_results = []  # Track tool results across iterations
        
        while iteration < self.max_tool_iterations:
            iteration += 1
            debug_component('executor', 'ITERATION_START', {
                'execution_id': execution_id,
                'iteration': iteration,
                'max_iterations': self.max_tool_iterations
            })
            
            logger.debug(f"Conversation loop iteration {iteration}")
            
            # Send current request to LLM via Copilot CLI session
            try:
                llm_response_text = self._call_llm_provider(
                    session, user_input, system_prompt, accumulated_tool_results
                )
                logger.debug(f"LLM response ({len(llm_response_text)} chars): {llm_response_text}")
                debug_llm_response('copilot', llm_response_text, execution_id)
            except Exception as e:
                error = f"LLM provider error: {str(e)}"
                logger.error(error, exc_info=True)
                errors.append(error)
                session.record_request(had_error=True)
                return "I encountered an error communicating with the LLM.", tool_results, errors
            
            # Parse the LLM response
            try:
                parse_result = self.protocol.parse(llm_response_text)
                logger.debug(f"Parsed response type: {parse_result.type}")
            except Exception as e:
                error = f"Protocol parse error: {str(e)}"
                logger.error(error, exc_info=True)
                errors.append(error)
                # Return raw text if we can't parse it
                return llm_response_text, tool_results, errors
            
            # Handle different response types
            if parse_result.type == ResponseType.TOOL_REQUEST:
                # Convert protocol tool calls to executor tool requests
                tool_requests = [
                    ToolRequest(tool_name=tc.tool_name, params=tc.params, id=tc.id)
                    for tc in parse_result.tools
                ]
                
                # Dispatch tools and continue loop
                iteration_tool_results, iteration_errors = self._dispatch_tools(
                    tool_requests, 
                    session, 
                    execution_id
                )
                tool_results.extend(iteration_tool_results)
                errors.extend(iteration_errors)
                
                # Add tool results to accumulated results for next iteration
                accumulated_tool_results.extend(iteration_tool_results)
            
            elif parse_result.type == ResponseType.WORKFLOW_REQUEST:
                # Execute workflow with dependency resolution
                debug_component('executor', 'WORKFLOW_START', {
                    'tool_count': len(parse_result.tools),
                    'execution_mode': parse_result.execution_mode,
                    'error_handling': parse_result.error_handling
                })
                
                workflow_results, workflow_errors = self.workflow_executor.execute_workflow(
                    workflow=parse_result,
                    session_id=session.id,
                    execution_id=execution_id,
                    progress_callback=self.progress_callback
                )
                
                tool_results.extend(workflow_results)
                errors.extend(workflow_errors)
                
                # Add workflow results to accumulated results for next iteration
                accumulated_tool_results.extend(workflow_results)
                
                debug_component('executor', 'WORKFLOW_END', {
                    'results_count': len(workflow_results),
                    'errors_count': len(workflow_errors)
                })
                
            elif parse_result.type == ResponseType.SYSTEM_REFRESH_REQUEST:
                # Handle system refresh request and inject refreshed prompt next iteration
                system_prompt = self._handle_system_refresh(parse_result, session)

            elif parse_result.type == ResponseType.SYSTEM_INSTRUCTION_REMIND:
                # Handle system instruction reminder request as refresh
                system_prompt = self._handle_system_refresh(parse_result, session)
                
            elif parse_result.type == ResponseType.RESPONSE:
                # Text response - we're done
                return parse_result.content, tool_results, errors
                
            else:
                # Unknown response type - treat as text
                logger.warning(f"Unknown response type: {parse_result.type}")
                return llm_response_text, tool_results, errors
        
        # Max iterations reached
        warning = f"Maximum tool iterations ({self.max_tool_iterations}) reached"
        logger.warning(warning)
        errors.append(warning)
        return "I've reached the maximum number of tool iterations for this request.", tool_results, errors
    
    def _call_llm_provider(
        self, 
        session: Session,
        user_input: str,
        system_prompt: Optional[str] = None,
        tool_results: Optional[List[ToolResponse]] = None
    ) -> str:
        """
        Call LLM provider with current request and session context.
        
        With Copilot CLI integration and JSON format:
        - Build messages array including system prompt, runtime prompt, user input, and tool results
        - Send as JSON to Copilot CLI which manages session continuity via --resume
        
        Args:
            session: Session for statistics and session_id 
            user_input: Current user prompt
            system_prompt: Optional system prompt override (sent only once per session)
            tool_results: Tool results from previous iterations to include in context
            
        Returns:
            Raw LLM response text
            
        Raises:
            LLMProviderError: If provider call fails
        """
        if not self.llm_provider:
            raise LLMProviderError("No LLM provider configured")
        
        try:
            # Create current message set with JSON structure
            messages = []

            # Add system prompt if provided (only on first request)
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            else:
                # Add runtime prompt (persistent directive) ONLY on subsequent requests
                # First request already has full system prompt, so runtime is redundant
                runtime_prompt = self._get_runtime_prompt()
                if runtime_prompt:
                    messages.append({"role": "user", "content": runtime_prompt})
                    debug_component('executor', 'RUNTIME_PROMPT_ADDED', {
                        'length': len(runtime_prompt)
                    })

            # Add current user input
            messages.append({"role": "user", "content": user_input})
            
            # Add tool results if available
            if tool_results:
                for tool_result in tool_results:
                    # Convert ToolResponse to message format
                    tool_content = {
                        "tool_name": tool_result.tool,
                        "success": tool_result.status == "success",
                        "result": tool_result.result,
                        "error": tool_result.error,
                        "execution_time_ms": tool_result.execution_time_ms
                    }
                    messages.append({
                        "role": "tool", 
                        "content": json.dumps(tool_content, ensure_ascii=False)
                    })
            
            # Check if provider is a Provider instance or function
            from one_think.providers import LLMProvider as BaseProvider
            if isinstance(self.llm_provider, BaseProvider):
                # Use Provider interface with session ID for Copilot CLI
                provider_messages = self.llm_provider.format_messages(messages)
                debug_llm_call('copilot', provider_messages, session.id)
                response = self.llm_provider.send_messages(
                    provider_messages, 
                    session_id=session.get_copilot_session_id()
                )
                debug_component('executor', 'LLM_RESPONSE_RECEIVED', {
                    'response_length': len(response.content) if hasattr(response, 'content') else len(str(response))
                })
                return response.content
            else:
                # Use legacy function interface
                debug_llm_call('copilot', messages, session.id)
                response = self.llm_provider(messages)
                
                if not response or not isinstance(response, str):
                    raise LLMProviderError(f"Invalid provider response: {type(response)}")
                    
                return response
            
        except Exception as e:
            raise LLMProviderError(f"Provider call failed: {str(e)}") from e
    
    def _dispatch_tools(
        self, 
        tool_requests: List[ToolRequest], 
        session: Session, 
        execution_id: str
    ) -> tuple[List[ToolResponse], List[str]]:
        """
        Dispatch multiple tool requests.
        
        Args:
            tool_requests: List of tool requests to execute
            session: Session for statistics tracking
            execution_id: Execution ID for correlation
            
        Returns:
            (tool_results, errors)
        """
        tool_results = []
        errors = []
        
        logger.info(f"Dispatching {len(tool_requests)} tools")
        debug_component('executor', 'TOOL_DISPATCH_START', {
            'tool_count': len(tool_requests),
            'tool_names': [tr.tool_name for tr in tool_requests]
        })
        
        for i, tool_request in enumerate(tool_requests):
            request_id = f"{execution_id}_tool_{i+1}"
            logger.debug(f"Dispatching tool: {tool_request.tool_name} (ID: {request_id})")
            debug_tool_execution(tool_request.tool_name, tool_request.params, request_id)
            
            try:
                # Execute the tool
                tool_result = self._execute_single_tool(tool_request, request_id)
                tool_results.append(tool_result)
                
                # Debug tool result
                debug_tool_result(
                    tool_request.tool_name, 
                    tool_result.status,
                    len(str(tool_result.result)) if tool_result.result else 0,
                    request_id
                )
                
                # Add result to session
                tool_msg = ToolResultMessage(
                    content=json.dumps({
                        "tool": tool_result.tool,
                        "status": tool_result.status,
                        "result": tool_result.result,
                        "error": tool_result.error,
                        "execution_time_ms": tool_result.execution_time_ms
                    }),
                    tool_name=tool_request.tool_name,
                    status=tool_result.status,
                    request_id=request_id,
                    execution_time_ms=tool_result.execution_time_ms
                )
                # Record tool execution in session stats
                session.record_request(tool_calls=1)
                
                logger.debug(f"Tool {tool_request.tool_name} executed: {tool_result.status}")
                
            except Exception as e:
                error = f"Tool dispatch error for '{tool_request.tool_name}': {str(e)}"
                logger.error(error, exc_info=True)
                errors.append(error)
                
                # Record tool error in session stats
                session.record_request(tool_calls=1, had_error=True)
        
        return tool_results, errors
    
    def _execute_single_tool(self, tool_request: ToolRequest, request_id: str) -> ToolResponse:
        """
        Execute a single tool request.
        
        Args:
            tool_request: Tool request to execute
            request_id: Request ID for correlation
            
        Returns:
            ToolResponse with result or error
            
        Raises:
            ToolDispatchError: If tool execution fails
        """
        start_time = time.time()
        
        try:
            # Create tool instance
            tool_instance = self.tool_registry.create_tool_instance(tool_request.tool_name)
            
            # Handle help request
            if tool_request.params.get('help') is True:
                help_text = tool_instance.get_help()
                execution_time = (time.time() - start_time) * 1000
                
                return ToolResponse(
                    status="success",
                    tool=tool_request.tool_name,
                    request_id=request_id,
                    result={"help": help_text},
                    error=None,
                    execution_time_ms=execution_time
                )
            
            # Execute tool with parameters
            result = tool_instance.execute_json(
                params=tool_request.params,
                request_id=request_id
            )
            
            return result
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            
            # Create error response
            error_response = ToolResponse(
                status="error",
                result=None,
                error={
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": traceback.format_exc()
                },
                tool=tool_request.tool_name,
                request_id=request_id,
                execution_time_ms=execution_time
            )
            
            return error_response
    
    def _handle_system_refresh(self, refresh_request: SystemRefreshRequest, session: Session) -> str:
        """
        Handle system prompt refresh request.
        
        Rebuilds system prompt with:
        - Core guidelines and instructions
        - Available tools summary  
        - Session context summary
        - Current timestamp and environment
        
        Args:
            refresh_request: System refresh request details
            session: Session to add refresh message to
        """
        reason = refresh_request.reason or "System refresh requested"
        logger.info(f"System refresh requested: {reason}")
        
        # Build refreshed system prompt with current state
        refreshed_prompt = self._build_refreshed_system_prompt(session, reason)
        
        # Record refresh in session metadata with timestamp
        refresh_count = session.get_metadata("system_refresh_count", 0) + 1
        session.set_metadata("system_refresh_count", refresh_count)
        session.set_metadata("last_system_refresh", reason)
        session.set_metadata("last_system_refresh_time", datetime.now(timezone.utc).isoformat())
        
        # Log refresh event with debug info
        debug_component('executor', 'SYSTEM_REFRESH', {
            'reason': reason,
            'refresh_count': refresh_count,
            'prompt_length': len(refreshed_prompt),
            'session_id': session.session_id
        })
        
        logger.info(f"System refresh completed (#{refresh_count}): {len(refreshed_prompt)} chars")
        return refreshed_prompt
    
    def _build_refreshed_system_prompt(self, session: Session, reason: str) -> str:
        """
        Build a refreshed system prompt with current context using instructions.
        
        Args:
            session: Current session for context
            reason: Reason for refresh
            
        Returns:
            Refreshed system prompt string
        """
        from ..templates import instruction_loader
        
        # Get base prompt
        base_prompt = self._get_base_system_prompt()
        
        # Add session context summary (session does not store message history)
        message_count = session.stats.get('requests_count', 0)
        tool_count = session.stats.get('tool_calls_count', 0)
        
        # Build tools summary  
        tools_summary = self.tool_registry.get_tools_formatted("detailed") if self.tool_registry else "No tools available"
        
        # Use instruction loader to build refresh prompt
        return instruction_loader.get_refresh_prompt(
            base_prompt=base_prompt,
            reason=reason,
            message_count=message_count,
            tool_count=tool_count,
            tools_summary=tools_summary
        )
        
    def _get_base_system_prompt(self) -> str:
        """Get base system prompt (same as default but modular)."""
        from ..templates import instruction_loader
        
        # Load from instruction with detailed tool descriptions
        return instruction_loader.get_system_prompt(tool_registry=self.tool_registry)
    
    def _get_runtime_prompt(self) -> str:
        """
        Get runtime prompt that is added to EVERY request.
        
        Runtime prompt is a persistent directive that reminds the LLM of key rules
        and behaviors on every iteration, ensuring consistent behavior throughout
        the conversation.
        
        Returns:
            Runtime prompt string or empty string if not available
        """
        from ..templates import instruction_loader
        
        try:
            return instruction_loader.get_runtime_prompt()
        except Exception as e:
            logger.warning(f"Failed to load runtime prompt: {e}")
            return ""
    
    
    def set_llm_provider(self, provider: Union[Callable, 'LLMProvider']):
        """Set the LLM provider function or Provider instance."""
        self.llm_provider = provider
        provider_type = "Provider instance" if hasattr(provider, 'send_messages') else "function"
        logger.info(f"LLM provider configured: {provider_type}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get executor metrics and statistics."""
        return {
            "tool_count": len(self.tool_registry.list_tools()),
            "max_tool_iterations": self.max_tool_iterations,
            "has_llm_provider": self.llm_provider is not None,
            "protocol_version": "1.0.0"
        }
