"""
Workflow Executor for AI-ONE.

This module handles execution of workflows with:
- Dependency resolution (topological sort)
- Parameter templating ({step_id.output})
- Sequential and parallel execution modes
- Error handling (abort, skip, retry)
"""

import logging
import json
import re
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict, deque

from one_think.core.protocol import WorkflowRequest, WorkflowToolCall
from one_think.tools.base import ToolResponse
from one_think.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class WorkflowExecutionError(Exception):
    """Raised when workflow execution fails."""
    pass


class WorkflowExecutor:
    """
    Executes workflows with dependency resolution and parameter templating.
    
    Features:
    - Topological sort for dependency ordering
    - Template parameter substitution ({step_id.output})
    - Sequential/parallel execution modes
    - Error handling: abort/skip/retry
    """
    
    def __init__(self, tool_registry: ToolRegistry):
        """
        Initialize workflow executor.
        
        Args:
            tool_registry: Registry for tool dispatch
        """
        self.tool_registry = tool_registry
    
    def execute_workflow(
        self,
        workflow: WorkflowRequest,
        session_id: str,
        execution_id: str
    ) -> Tuple[List[ToolResponse], List[str]]:
        """
        Execute a workflow with dependency resolution.
        
        Args:
            workflow: Workflow request with tools and configuration
            session_id: Session ID for tracking
            execution_id: Execution ID for logging
            
        Returns:
            Tuple of (tool_results, errors)
        """
        logger.info(f"Executing workflow: mode={workflow.execution_mode}, "
                   f"error_handling={workflow.error_handling}, "
                   f"tools={len(workflow.tools)}")
        
        # Resolve dependencies and get execution order
        try:
            execution_order = self._resolve_dependencies(workflow.tools)
        except Exception as e:
            error = f"Dependency resolution failed: {e}"
            logger.error(error)
            return [], [error]
        
        # Execute based on mode
        if workflow.execution_mode == "sequential":
            return self._execute_sequential(
                workflow.tools,
                execution_order,
                workflow.error_handling,
                session_id,
                execution_id
            )
        elif workflow.execution_mode == "parallel":
            return self._execute_parallel(
                workflow.tools,
                execution_order,
                workflow.error_handling,
                session_id,
                execution_id
            )
        else:
            error = f"Unknown execution_mode: {workflow.execution_mode}"
            logger.error(error)
            return [], [error]
    
    def _resolve_dependencies(self, tools: List[WorkflowToolCall]) -> List[str]:
        """
        Resolve tool dependencies using topological sort.
        
        Args:
            tools: List of workflow tools with dependencies
            
        Returns:
            List of tool IDs in execution order
            
        Raises:
            WorkflowExecutionError: If circular dependency detected
        """
        # Build adjacency list and in-degree count
        graph = defaultdict(list)  # step_id -> [dependent_ids]
        in_degree = defaultdict(int)  # step_id -> count of dependencies
        all_ids = {tool.id for tool in tools}
        
        # Initialize in_degree for all tools
        for tool in tools:
            if tool.id not in in_degree:
                in_degree[tool.id] = 0
        
        # Build graph
        for tool in tools:
            for dep_id in tool.depends_on:
                if dep_id not in all_ids:
                    raise WorkflowExecutionError(
                        f"Tool '{tool.id}' depends on non-existent tool '{dep_id}'"
                    )
                graph[dep_id].append(tool.id)
                in_degree[tool.id] += 1
        
        # Kahn's algorithm for topological sort
        queue = deque([tid for tid in all_ids if in_degree[tid] == 0])
        execution_order = []
        
        while queue:
            current = queue.popleft()
            execution_order.append(current)
            
            # Reduce in-degree for dependents
            for dependent in graph[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        # Check for circular dependencies
        if len(execution_order) != len(all_ids):
            missing = all_ids - set(execution_order)
            raise WorkflowExecutionError(
                f"Circular dependency detected. Affected tools: {missing}"
            )
        
        logger.debug(f"Dependency resolution: {execution_order}")
        return execution_order
    
    def _execute_sequential(
        self,
        tools: List[WorkflowToolCall],
        execution_order: List[str],
        error_handling: str,
        session_id: str,
        execution_id: str
    ) -> Tuple[List[ToolResponse], List[str]]:
        """
        Execute workflow sequentially in dependency order.
        
        Args:
            tools: List of workflow tools
            execution_order: Order to execute tools
            error_handling: Error handling strategy
            session_id: Session ID
            execution_id: Execution ID
            
        Returns:
            Tuple of (results, errors)
        """
        # Create lookup dict
        tools_dict = {tool.id: tool for tool in tools}
        
        # Track results and errors
        results: Dict[str, ToolResponse] = {}
        all_results: List[ToolResponse] = []
        errors: List[str] = []
        
        # Execute in order
        for step_id in execution_order:
            tool = tools_dict[step_id]
            
            logger.info(f"Executing workflow step: {step_id} ({tool.tool_name})")
            
            # Substitute parameters with previous results
            try:
                params = self._substitute_parameters(tool.params, results)
            except Exception as e:
                error = f"Parameter substitution failed for {step_id}: {e}"
                logger.error(error)
                errors.append(error)
                
                if error_handling == "abort":
                    return all_results, errors
                elif error_handling == "skip":
                    continue
                # For retry, we'll continue with original params
                params = tool.params
            
            # Execute tool
            try:
                # Create tool instance
                tool_instance = self.tool_registry.create_tool_instance(tool.tool_name)
                
                # Handle help request (should not happen in workflow, but just in case)
                if params.get('help') is True:
                    help_text = tool_instance.get_help()
                    result = ToolResponse(
                        status="success",
                        tool=tool.tool_name,
                        request_id=step_id,
                        result={"help": help_text},
                        error=None,
                        execution_time_ms=0
                    )
                else:
                    # Execute tool with parameters
                    result = tool_instance.execute_json(
                        params=params,
                        request_id=step_id
                    )
                
                results[step_id] = result
                all_results.append(result)
                
                logger.info(f"Workflow step {step_id} completed: status={result.status}")
                
                # Handle tool errors based on error_handling
                if result.status == "error":
                    error = f"Tool {step_id} failed: {result.error}"
                    errors.append(error)
                    
                    if error_handling == "abort":
                        logger.error(f"Aborting workflow due to error in {step_id}")
                        return all_results, errors
                    elif error_handling == "skip":
                        logger.warning(f"Skipping failed step {step_id}")
                        continue
                    elif error_handling == "retry":
                        # Simple retry once
                        logger.info(f"Retrying step {step_id}")
                        
                        # Create new tool instance for retry
                        tool_instance_retry = self.tool_registry.create_tool_instance(tool.tool_name)
                        result = tool_instance_retry.execute_json(
                            params=params,
                            request_id=f"{step_id}_retry"
                        )
                        results[step_id] = result
                        all_results.append(result)
                        
                        if result.status == "error":
                            error = f"Tool {step_id} failed after retry: {result.error}"
                            errors.append(error)
                            return all_results, errors
                
            except Exception as e:
                error = f"Workflow step {step_id} execution error: {e}"
                logger.error(error, exc_info=True)
                errors.append(error)
                
                if error_handling == "abort":
                    return all_results, errors
                elif error_handling == "skip":
                    continue
                # For retry, we already tried once
                return all_results, errors
        
        return all_results, errors
    
    def _execute_parallel(
        self,
        tools: List[WorkflowToolCall],
        execution_order: List[str],
        error_handling: str,
        session_id: str,
        execution_id: str
    ) -> Tuple[List[ToolResponse], List[str]]:
        """
        Execute workflow with parallel execution of independent steps.
        
        Note: For now, this is implemented as sequential execution.
        True parallel execution would require asyncio/threading.
        
        Args:
            tools: List of workflow tools
            execution_order: Order to execute tools
            error_handling: Error handling strategy
            session_id: Session ID
            execution_id: Execution ID
            
        Returns:
            Tuple of (results, errors)
        """
        # TODO: Implement true parallel execution with asyncio
        # For now, fall back to sequential
        logger.warning("Parallel execution not yet implemented, using sequential")
        return self._execute_sequential(
            tools, execution_order, error_handling, session_id, execution_id
        )
    
    def _substitute_parameters(
        self,
        params: Dict[str, Any],
        results: Dict[str, ToolResponse]
    ) -> Dict[str, Any]:
        """
        Substitute parameter templates with actual values.
        
        Supports templates like:
        - {step_id.output} - full output
        - {step_id.result} - result field
        - {step_id.result.field} - nested field
        
        Args:
            params: Parameters with potential templates
            results: Completed step results
            
        Returns:
            Parameters with substituted values
        """
        substituted = {}
        
        for key, value in params.items():
            if isinstance(value, str):
                substituted[key] = self._substitute_string(value, results)
            elif isinstance(value, dict):
                substituted[key] = self._substitute_parameters(value, results)
            elif isinstance(value, list):
                substituted[key] = [
                    self._substitute_string(v, results) if isinstance(v, str) else v
                    for v in value
                ]
            else:
                substituted[key] = value
        
        return substituted
    
    def _substitute_string(
        self,
        value: str,
        results: Dict[str, ToolResponse]
    ) -> Any:
        """
        Substitute template references in a string.
        
        Args:
            value: String potentially containing templates
            results: Completed step results
            
        Returns:
            Substituted value (str or extracted object)
        """
        # Pattern: {step_id.field.subfield...}
        pattern = r'\{([a-zA-Z0-9_]+)\.([a-zA-Z0-9_.]+)\}'
        
        def replace_match(match):
            step_id = match.group(1)
            field_path = match.group(2)
            
            if step_id not in results:
                logger.warning(f"Step {step_id} not found in results")
                return match.group(0)  # Return original
            
            result = results[step_id]
            
            # Navigate field path
            try:
                value = self._get_nested_field(result, field_path)
                # Convert to string for substitution
                if isinstance(value, (dict, list)):
                    return json.dumps(value)
                return str(value)
            except Exception as e:
                logger.warning(f"Failed to extract {field_path} from {step_id}: {e}")
                return match.group(0)
        
        # If the entire string is a single template, return the extracted value directly
        single_template = re.match(r'^\{([a-zA-Z0-9_]+)\.([a-zA-Z0-9_.]+)\}$', value)
        if single_template:
            step_id = single_template.group(1)
            field_path = single_template.group(2)
            
            if step_id in results:
                try:
                    return self._get_nested_field(results[step_id], field_path)
                except:
                    pass
        
        # Otherwise, do string substitution
        return re.sub(pattern, replace_match, value)
    
    def _get_nested_field(self, obj: ToolResponse, field_path: str) -> Any:
        """
        Get nested field from ToolResponse.
        
        Args:
            obj: ToolResponse object
            field_path: Dot-separated field path (e.g., "output" or "result.data")
            
        Returns:
            Field value
        """
        fields = field_path.split('.')
        current = obj
        
        for field in fields:
            if hasattr(current, field):
                current = getattr(current, field)
            elif isinstance(current, dict) and field in current:
                current = current[field]
            else:
                raise ValueError(f"Field '{field}' not found in {type(current)}")
        
        return current
