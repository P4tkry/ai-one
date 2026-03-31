from typing import Any

from one_think.context_provider import ContextPrompt
from one_think.tools import Tool
from one_think.tools.credentials_tool import CredentialsTool
from one_think.tools.soul_tool import SoulTool
from one_think.tools.user_tool import UserTool
from one_think.tools.web_fetch import WebFetch
from one_think.tools.write_to_file import WriteToFile


class ConversationContext:
    MAX_LLM_PAYLOAD_CHARS = 20000
    TOOL_OUTPUT_LIMIT_CHARS = 10000

    def __init__(
        self,
        session_id: str | None = None,
        model_provider: str = 'copilot',
        included_tools: list[Tool] | None = None
    ):
        self.session_id = session_id
        self.history: list[ContextPrompt] = []
        self.model_provider = model_provider
        self.included_tools = included_tools or []

    def _find_tool(self, tool_name: str) -> Tool | None:
        return next((t for t in self.included_tools if t.name == tool_name), None)

    @staticmethod
    def _truncate_output(
        stdout: str | None,
        stderr: str | None,
        limit: int = TOOL_OUTPUT_LIMIT_CHARS
    ) -> tuple[str, str]:
        stdout = "" if stdout is None else str(stdout)
        stderr = "" if stderr is None else str(stderr)

        stdout_truncated = False
        stderr_truncated = False

        if len(stdout) > limit:
            stdout = stdout[:limit] + "\n---OUTPUT TRUNCATED---\n"
            stdout_truncated = True

        if len(stderr) > limit:
            stderr = stderr[:limit] + "\n---OUTPUT TRUNCATED---\n"
            stderr_truncated = True

        stderr_prefix_parts: list[str] = []
        if stdout_truncated:
            stderr_prefix_parts.append(
                f"STDOUT WAS TRUNCATED BECAUSE IT WAS LONGER THAN {limit} characters."
            )
        if stderr_truncated:
            stderr_prefix_parts.append(
                f"STDERR WAS TRUNCATED BECAUSE IT WAS LONGER THAN {limit} characters."
            )

        if stderr_prefix_parts:
            stderr = "\n".join(stderr_prefix_parts) + ("\n" + stderr if stderr else "")

        return stdout, stderr

    @staticmethod
    def _inject_pipe(value: Any, previous_output: str) -> Any:
        if isinstance(value, str):
            return value.replace("<pipe>", previous_output)

        if isinstance(value, dict):
            return {
                key: ConversationContext._inject_pipe(subvalue, previous_output)
                for key, subvalue in value.items()
            }

        if isinstance(value, list):
            return [
                ConversationContext._inject_pipe(item, previous_output)
                for item in value
            ]

        return value

    def _resolve_pipeline_params(
        self,
        params: dict[str, Any],
        previous_output: str
    ) -> dict[str, Any]:
        return self._inject_pipe(params, previous_output)

    @staticmethod
    def _format_tool_block(tool_name: str, content: str | None) -> str:
        safe_content = "" if content is None else str(content)
        return (
            f"---TOOL: {tool_name}---\n"
            f"{safe_content}\n"
            f"---END OF TOOL: {tool_name}---\n"
        )

    @staticmethod
    def _truncate_from_end(text: str | None, limit: int, marker: str) -> str:
        text = "" if text is None else str(text)

        if limit <= 0:
            return ""

        if len(text) <= limit:
            return text

        if limit <= len(marker):
            return marker[:limit]

        return marker + text[-(limit - len(marker)):]

    @classmethod
    def _truncate_llm_payload(cls, stdout: str | None, stderr: str | None) -> tuple[str, str]:
        stdout = "" if stdout is None else str(stdout)
        stderr = "" if stderr is None else str(stderr)

        total_len = len(stdout) + len(stderr)
        if total_len <= cls.MAX_LLM_PAYLOAD_CHARS:
            return stdout, stderr

        marker_stdout = "\n---STDOUT PAYLOAD TRUNCATED---\n"
        marker_stderr = "\n---STDERR PAYLOAD TRUNCATED---\n"

        # Preferuj stdout, ale zostaw trochę miejsca na stderr
        stderr_reserved = min(len(stderr), 4000)
        stdout_budget = max(0, cls.MAX_LLM_PAYLOAD_CHARS - stderr_reserved)

        truncated_stdout = cls._truncate_from_end(stdout, stdout_budget, marker_stdout)

        remaining_budget = cls.MAX_LLM_PAYLOAD_CHARS - len(truncated_stdout)
        truncated_stderr = cls._truncate_from_end(stderr, remaining_budget, marker_stderr)

        # Finalny bezpiecznik
        combined_len = len(truncated_stdout) + len(truncated_stderr)
        if combined_len > cls.MAX_LLM_PAYLOAD_CHARS:
            overflow = combined_len - cls.MAX_LLM_PAYLOAD_CHARS
            if overflow >= len(truncated_stderr):
                truncated_stderr = ""
            else:
                truncated_stderr = truncated_stderr[:-overflow]

        return truncated_stdout, truncated_stderr

    def _execute_single_tool(self, tool_name: str, tool_params: dict[str, Any]) -> tuple[str, str]:
        tool = self._find_tool(tool_name)
        if not tool:
            error_message = f'Tool "{tool_name}" not found in included tools.'
            print(error_message)
            return "", error_message

        print(f"Executing tool: {tool_name} with arguments: {tool_params}")

        try:
            stdout, stderr = tool.execute(tool_params)
        except Exception as exc:
            stdout = ""
            stderr = f"Tool execution raised an exception: {type(exc).__name__}: {exc}"

        stdout, stderr = self._truncate_output(stdout, stderr)
        return stdout, stderr

    def _execute_non_pipeline_calls(self, calls: list[dict[str, Any]]) -> tuple[str, str]:
        full_stdout = ""
        full_stderr = ""

        for index, call in enumerate(calls):
            tool_name = call.get("tool_name")
            tool_params = call.get("params", {})

            if not isinstance(tool_name, str) or not tool_name.strip():
                error_message = f'Invalid tool_name at call index {index}.'
                print(error_message)
                full_stderr += self._format_tool_block(f"INVALID_CALL_{index}", error_message)
                continue

            if not isinstance(tool_params, dict):
                error_message = f'Invalid params for tool "{tool_name}" at call index {index}.'
                print(error_message)
                full_stderr += self._format_tool_block(tool_name, error_message)
                continue

            stdout, stderr = self._execute_single_tool(tool_name, tool_params)

            full_stdout += self._format_tool_block(tool_name, stdout)
            full_stderr += self._format_tool_block(tool_name, stderr)

        return full_stdout, full_stderr

    def _execute_pipeline_calls(self, calls: list[dict[str, Any]]) -> tuple[str, str]:
        full_stdout = ""
        full_stderr = ""
        previous_output = ""

        for index, call in enumerate(calls):
            tool_name = call.get("tool_name")
            tool_params = call.get("params", {})

            if not isinstance(tool_name, str) or not tool_name.strip():
                error_message = f'Invalid tool_name at pipeline call index {index}.'
                print(error_message)
                full_stderr += self._format_tool_block(f"INVALID_CALL_{index}", error_message)
                break

            if not isinstance(tool_params, dict):
                error_message = f'Invalid params for pipeline tool "{tool_name}" at call index {index}.'
                print(error_message)
                full_stderr += self._format_tool_block(tool_name, error_message)
                break

            if index == 0:
                resolved_params = dict(tool_params)
            else:
                resolved_params = self._resolve_pipeline_params(tool_params, previous_output)

            print(f"Executing pipeline tool: {tool_name} with arguments: {resolved_params}")
            stdout, stderr = self._execute_single_tool(tool_name, resolved_params)

            full_stdout += self._format_tool_block(tool_name, stdout)
            full_stderr += self._format_tool_block(tool_name, stderr)

            # <pipe> ma zawierać tylko stdout ostatniego kroku
            previous_output = stdout

        return full_stdout, full_stderr

    def _execute_tool_calls_from_prompt(self, prompt: ContextPrompt) -> tuple[str, str]:
        tools = prompt.tools_intent or {}
        is_pipeline = tools.get("is_pipeline", False)
        calls = tools.get("calls", [])

        if not calls:
            return "", ""

        if is_pipeline:
            return self._execute_pipeline_calls(calls)

        return self._execute_non_pipeline_calls(calls)

    def execute_prompt_waterfall(self, prompt: ContextPrompt) -> str | None:
        prompt.set_tools(self.included_tools)
        prompt.model_provider = self.model_provider
        prompt.session_id = self.session_id
        prompt.ask()

        self.session_id = prompt.session_id
        self.history.append(prompt)

        while prompt.tools_intent and prompt.tools_intent.get("calls"):
            full_stdout, full_stderr = self._execute_tool_calls_from_prompt(prompt)
            full_stdout, full_stderr = self._truncate_llm_payload(full_stdout, full_stderr)

            prompt = ContextPrompt(
                prompt=full_stdout,
                stderr=full_stderr,
                is_tool_response=True,
                included_tools=self.included_tools,
                model_provider=self.model_provider,
                session_id=self.session_id
            )
            prompt.ask()

            self.session_id = prompt.session_id
            self.history.append(prompt)

        return prompt.response_answer


if __name__ == "__main__":
    context = ConversationContext(
        included_tools=[
            WebFetch(),
            WriteToFile(),
            CredentialsTool(),
            SoulTool(),
            UserTool()
        ]
    )

    while True:
        prompt = input("Enter your prompt: ")
        prompt1 = ContextPrompt(prompt=prompt)
        response = context.execute_prompt_waterfall(prompt1)
        print(response)