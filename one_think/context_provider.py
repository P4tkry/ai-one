import json
from typing import Any

import one_think.copilot as cp
import one_think.prompts as prompts
from one_think.tools import Tool
from one_think.tools.web_fetch import WebFetch


PROMPT_SEPARATORS = [
    '<<<BEGIN OF USER UNTRUSTED DATA>>>',
    '<<<END OF USER UNTRUSTED DATA>>>',
    '<<<BEGIN OF SYSTEM TRUSTED DATA>>>',
    '<<<END OF SYSTEM TRUSTED DATA>>>',
    '<<<BEGIN OF TOOL EXECUTION STDERR>>>',
    '<<<END OF TOOL EXECUTION STDERR>>>',
    '<<<BEGIN OF TOOL EXECUTION STDOUT>>>',
    '<<<END OF TOOL EXECUTION STDOUT>>>',
]


def validate_prompt(prompt: str | None = None) -> str:
    """
    Removes reserved prompt separators from untrusted input.
    """
    if prompt is None:
        return ""

    secure_prompt = str(prompt)
    for separator in PROMPT_SEPARATORS:
        secure_prompt = secure_prompt.replace(separator, "")

    return secure_prompt


class ContextPrompt:
    """
    Represents a secured prompt wrapper with optional tool descriptions
    and parsing support for structured JSON responses.
    """

    security_prompt = prompts.security_prompt
    response_guidelines = prompts.response_guidelines

    def __init__(
        self,
        prompt: str,
        stderr: str | None = None,
        is_tool_response: bool = False,
        include_security_prompt: bool = True,
        include_response_guidelines: bool = True,
        included_tools: list[Tool] | None = None,
        model_provider: str = 'copilot',
        session_id: str | None = None
    ):
        self.prompt = prompt
        self.stderr = stderr
        self.is_tool_response = is_tool_response
        self.include_security_prompt = include_security_prompt
        self.include_response_guidelines = include_response_guidelines
        self.included_tools = included_tools or []
        self.model_provider = model_provider
        self.session_id = session_id

        self.tools_prompt: str = ""
        self.tools_intent: dict[str, Any] | None = None
        self.response_dict: dict[str, Any] | None = None
        self.response_answer: str | None = None
        self.is_pipeline: bool = False
        self.tool_calls: list[dict[str, Any]] = []

        self._generate_tools_prompt()

    def _generate_tools_prompt(self) -> None:
        if not self.included_tools:
            self.tools_prompt = prompts.tools_prompt[0] + "\n" + prompts.tools_prompt[1]
            return

        tools_prompt = prompts.tools_prompt[0]
        for tool in self.included_tools:
            tools_prompt += f"\n{tool}"
        tools_prompt += "\n" + prompts.tools_prompt[1]
        self.tools_prompt = tools_prompt

    def set_tools(self, tools: list[Tool]) -> None:
        self.included_tools = tools or []
        self._generate_tools_prompt()

    def _build_system_prompt(self) -> str:
        parts: list[str] = []

        if self.include_security_prompt:
            parts.append(self.security_prompt)

        parts.append(self.tools_prompt)

        if self.include_response_guidelines:
            parts.append(self.response_guidelines)

        return "\n\n".join(part for part in parts if part)

    def __str__(self) -> str:
        system_prompt = self._build_system_prompt()

        if not self.is_tool_response:
            return (
                f"<<<BEGIN OF SYSTEM TRUSTED DATA>>>\n"
                f"{system_prompt}\n"
                f"<<<END OF SYSTEM TRUSTED DATA>>>\n\n"
                f"<<<BEGIN OF USER UNTRUSTED DATA>>>\n"
                f"{validate_prompt(self.prompt)}\n"
                f"<<<END OF USER UNTRUSTED DATA>>>"
            )

        return (
            f"<<<BEGIN OF SYSTEM TRUSTED DATA>>>\n"
            f"{system_prompt}\n"
            f"<<<END OF SYSTEM TRUSTED DATA>>>\n\n"
            f"<<<BEGIN OF TOOL EXECUTION STDOUT>>>\n"
            f"{validate_prompt(self.prompt)}\n"
            f"<<<END OF TOOL EXECUTION STDOUT>>>\n\n"
            f"<<<BEGIN OF TOOL EXECUTION STDERR>>>\n"
            f"{validate_prompt(self.stderr)}\n"
            f"<<<END OF TOOL EXECUTION STDERR>>>"
        )

    def _parse_model_response(self, answer: str) -> dict[str, Any]:
        try:
            parsed = json.loads(answer)
        except json.JSONDecodeError as e:
            raise ValueError(f"Model did not return valid JSON: {e}\nRaw output:\n{answer}") from e

        if not isinstance(parsed, dict):
            raise ValueError("Model response must be a JSON object")

        if "answer" not in parsed:
            raise ValueError('Model response is missing required key: "answer"')

        if "tools" not in parsed:
            raise ValueError('Model response is missing required key: "tools"')

        tools = parsed["tools"]
        if not isinstance(tools, dict):
            raise ValueError('Field "tools" must be an object')

        if "is_pipeline" not in tools:
            raise ValueError('Field "tools" must contain key: "is_pipeline"')

        if "calls" not in tools:
            raise ValueError('Field "tools" must contain key: "calls"')

        if not isinstance(tools["is_pipeline"], bool):
            raise ValueError('Field "tools.is_pipeline" must be a boolean')

        if not isinstance(tools["calls"], list):
            raise ValueError('Field "tools.calls" must be a list')

        return parsed

    def _extract_tool_plan(self) -> None:
        self.tools_intent = self.response_dict["tools"]
        self.response_answer = self.response_dict["answer"]
        self.is_pipeline = self.tools_intent["is_pipeline"]
        self.tool_calls = self.tools_intent["calls"]

        for index, call in enumerate(self.tool_calls):
            if not isinstance(call, dict):
                raise ValueError(f"Tool call at index {index} must be an object")

            expected_keys = {"tool_name", "params"}
            actual_keys = set(call.keys())
            if actual_keys != expected_keys:
                raise ValueError(
                    f"Tool call at index {index} must contain exactly keys {expected_keys}, got {actual_keys}"
                )

            if not isinstance(call["tool_name"], str) or not call["tool_name"].strip():
                raise ValueError(f'Tool call at index {index} has invalid "tool_name"')

            if not isinstance(call["params"], dict):
                raise ValueError(f'Tool call at index {index} has invalid "params"; expected object')

        self._validate_answer_and_tools_consistency()
        self._validate_pipeline()

    def _validate_answer_and_tools_consistency(self) -> None:
        if self.tool_calls and self.response_answer != "":
            raise ValueError('If "tools.calls" is not empty, "answer" must be an empty string')

        if not self.tool_calls and not isinstance(self.response_answer, str):
            raise ValueError('If "tools.calls" is empty, "answer" must be a string')

    def _validate_pipeline(self) -> None:
        if not self.is_pipeline:
            for index, call in enumerate(self.tool_calls):
                for param_name, value in call["params"].items():
                    if value == "<pipe>":
                        raise ValueError(
                            f'Call at index {index} uses "<pipe>" in param "{param_name}" while is_pipeline is false'
                        )
            return

        if self.is_pipeline and not self.tool_calls:
            raise ValueError('If "is_pipeline" is true, "calls" must not be empty')

        for index, call in enumerate(self.tool_calls):
            params = call["params"]
            contains_pipe = any(value == "<pipe>" for value in params.values())

            if index == 0 and contains_pipe:
                raise ValueError('First pipeline call must not contain "<pipe>"')

            if index > 0 and not contains_pipe:
                raise ValueError(
                    f'Pipeline call at index {index} must contain "<pipe>" in at least one param'
                )

    def ask(self) -> str | None:
        if self.model_provider != 'copilot':
            raise ValueError(f"Unsupported model provider: {self.model_provider}")

        session_id, answer = cp.ask_question(str(self), session_id=self.session_id)
        self.session_id = session_id

        print(answer)

        self.response_dict = self._parse_model_response(answer)
        self._extract_tool_plan()

        return self.response_answer


if __name__ == '__main__':
    user_input = (
        "Pobierz dane z https://szkoladevnet.pl/tajemnicze-args-i-kwargs/ "
        "i zapisz treść do pliku tajemnicze_args_i_kwargs.md"
    )

    prompt = ContextPrompt(
        user_input,
        included_tools=[WebFetch()]
    )

    result = prompt.ask()

    print("\n=== Final answer ===")
    print(result)

    print("\n=== Parsed response ===")
    print("answer:", prompt.response_answer)
    print("tools_intent:", prompt.tools_intent)
    print("is_pipeline:", prompt.is_pipeline)
    print("tool_calls:", prompt.tool_calls)