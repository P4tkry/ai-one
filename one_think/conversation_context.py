from one_think.context_provider import ContextPrompt
from one_think.tools import Tool
from one_think.tools.credentials_tool import CredentialsTool
from one_think.tools.soul_tool import SoulTool
from one_think.tools.user_tool import UserTool
from one_think.tools.web_fetch import WebFetch
from one_think.tools.write_to_file import WriteToFile


class ConversationContext:
    def __init__(
        self,
        session_id: str = None,
        model_provider: str = 'copilot',
        included_tools: list[Tool] = None
    ):
        self.session_id = session_id
        self.history: list[ContextPrompt] = []
        self.model_provider = model_provider
        self.included_tools = included_tools or []

    def _find_tool(self, tool_name: str) -> Tool | None:
        return next((t for t in self.included_tools if t.name == tool_name), None)

    @staticmethod
    def _truncate_output(stdout: str, stderr: str, limit: int = 10000) -> tuple[str, str]:
        stdout = stdout or ""
        stderr = stderr or ""

        stdout_truncated = False
        stderr_truncated = False

        if len(stdout) > limit:
            stdout = stdout[:limit] + "\n---OUTPUT TRUNCATED---\n"
            stdout_truncated = True

        if len(stderr) > limit:
            stderr = stderr[:limit] + "\n---OUTPUT TRUNCATED---\n"
            stderr_truncated = True

        if stdout_truncated:
            stderr = "STDOUT WAS TRUNCATED BECAUSE IT WAS LONGER THAN 10000 characters.\n" + stderr

        if stderr_truncated:
            stderr = "STDERR WAS TRUNCATED BECAUSE IT WAS LONGER THAN 10000 characters.\n" + stderr

        return stdout, stderr

    @staticmethod
    def _resolve_pipeline_params(params: dict, previous_output: str) -> dict:
        resolved = {}

        for key, value in params.items():
            if value == "<pipe>":
                resolved[key] = previous_output
            else:
                resolved[key] = value

        return resolved

    def _execute_non_pipeline_calls(self, calls: list[dict]) -> tuple[str, str]:
        full_stdout = ""
        full_stderr = ""

        for call in calls:
            tool_name = call["tool_name"]
            tool_params = call["params"]

            tool = self._find_tool(tool_name)
            if not tool:
                error_message = f'Tool "{tool_name}" not found in included tools.'
                print(error_message)
                full_stderr += (
                    f"---TOOL: {tool_name}---\n"
                    f"{error_message}\n"
                    f"---END OF TOOL: {tool_name}---\n"
                )
                continue

            print(f"Executing tool: {tool_name} with arguments: {tool_params}")
            stdout, stderr = tool.execute(tool_params)
            stdout, stderr = self._truncate_output(stdout, stderr)

            full_stdout += (
                f"---TOOL: {tool_name}---\n"
                f"{stdout}\n"
                f"---END OF TOOL: {tool_name}---\n"
            )
            full_stderr += (
                f"---TOOL: {tool_name}---\n"
                f"{stderr}\n"
                f"---END OF TOOL: {tool_name}---\n"
            )

        return full_stdout, full_stderr

    def _execute_pipeline_calls(self, calls: list[dict]) -> tuple[str, str]:
        full_stdout = ""
        full_stderr = ""
        previous_output = None

        for index, call in enumerate(calls):
            tool_name = call["tool_name"]
            tool_params = call["params"]

            tool = self._find_tool(tool_name)
            if not tool:
                error_message = f'Tool "{tool_name}" not found in included tools.'
                print(error_message)
                full_stderr += (
                    f"---TOOL: {tool_name}---\n"
                    f"{error_message}\n"
                    f"---END OF TOOL: {tool_name}---\n"
                )
                break

            if index == 0:
                resolved_params = dict(tool_params)
            else:
                resolved_params = self._resolve_pipeline_params(
                    tool_params,
                    previous_output if previous_output is not None else ""
                )

            print(f"Executing pipeline tool: {tool_name} with arguments: {resolved_params}")
            stdout, stderr = tool.execute(resolved_params)
            stdout, stderr = self._truncate_output(stdout, stderr)

            full_stdout += (
                f"---TOOL: {tool_name}---\n"
                f"{stdout}\n"
                f"---END OF TOOL: {tool_name}---\n"
            )
            full_stderr += (
                f"---TOOL: {tool_name}---\n"
                f"{stderr}\n"
                f"---END OF TOOL: {tool_name}---\n"
            )

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

    def execute_prompt_waterfall(self, prompt: ContextPrompt):
        prompt.set_tools(self.included_tools)
        prompt.model_provider = self.model_provider
        prompt.session_id = self.session_id
        prompt.ask()

        self.session_id = prompt.session_id
        self.history.append(prompt)

        while prompt.tools_intent and prompt.tools_intent.get("calls"):
            full_stdout, full_stderr = self._execute_tool_calls_from_prompt(prompt)

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