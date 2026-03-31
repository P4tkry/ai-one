import json

import one_think.copilot as cp
import one_think.prompts as prompts
from one_think.tools import Tool
from one_think.tools.web_fetch import WebFetch


def validate_prompt(prompt: str = None):
    prompt_separators = ['<<<BEGIN OF USER UNTRUSTED DATA>>>', '<<<END OF USER UNTRUSTED DATA>>>',
                         '<<<BEGIN OF SYSTEM TRUSTED DATA>>>', '<<<END OF SYSTEM TRUSTED DATA>>>',
                         '<<<BEGIN OF TOOL EXECUTION STDERR>>>', '<<<END OF TOOL EXECUTION STDERR>>>',
                         '<<<BEGIN OF TOOL EXECUTION STDOUT>>>', '<<<END OF TOOL EXECUTION STDOUT>>>']
    secure_prompt = prompt
    for separator in prompt_separators:
        secure_prompt = secure_prompt.replace(separator, '')

    return secure_prompt


class ContextPrompt:
    """A class to represent a context prompt, which includes user and system components."""
    security_prompt = prompts.security_prompt
    response_guidelines = prompts.response_guidelines


    def __init__(self, prompt: str, stderr: str = None, is_tool_response: bool = False,include_security_prompt: bool = True, include_response_guidelines: bool = True, included_tools: list[Tool] = None, model_provider: str = 'copilot', session_id: str = None):
        self.prompt = prompt
        self.is_tool_response = is_tool_response
        self.include_security_prompt = include_security_prompt
        self.include_response_guidelines = include_response_guidelines
        self.included_tools = included_tools
        self._generate_tools_prompt()
        self.model_provider = model_provider
        self.stderr = stderr

        # data structure to maintain conversation state with the model provider (if needed)
        self.session_id = session_id
        self.tools_intent = None
        self.response_dict = None
        self.response_answer = None



    def _generate_tools_prompt(self):
        if not self.included_tools:
            self.tools_prompt = prompts.tools_prompt[0] + "\n" + prompts.tools_prompt[1]
            return
        tools_prompt = prompts.tools_prompt[0]
        for tool in self.included_tools:
            tools_prompt += f"\n{tool}"
        tools_prompt += prompts.tools_prompt[1]
        self.tools_prompt = tools_prompt

    def set_tools(self, tools: list[Tool]):
        self.included_tools = tools
        self._generate_tools_prompt()

    def __str__(self):
        system_prompt = ""
        if self.include_security_prompt:
            system_prompt += self.security_prompt

        system_prompt += "\n\n" + self.tools_prompt

        if self.include_response_guidelines:
            system_prompt += "\n\n" + self.response_guidelines

        if not self.is_tool_response:
            return f'''<<<BEGIN OF SYSTEM TRUSTED DATA>>>\n{system_prompt}\n<<<END OF SYSTEM TRUSTED DATA>>>\n\n<<<BEGIN OF USER UNTRUSTED DATA>>>\n{validate_prompt(self.prompt)}\n<<<END OF USER UNTRUSTED DATA>>>'''
        else:
            return f''''<<<BEGIN OF SYSTEM TRUSTED DATA>>>\n{system_prompt}\n<<<END OF SYSTEM TRUSTED DATA>>>\n\n<<<BEGIN OF TOOL EXECUTION STDOUT>>>\n{validate_prompt(self.prompt)}\n<<<END OF TOOL EXECUTION STDOUT>>>''' + f'''\n\n<<<BEGIN OF TOOL EXECUTION STDERR>>>\n{validate_prompt(self.stderr or "")}\n<<<END OF TOOL EXECUTION STDERR>>>'''

    def ask(self):
        if self.model_provider == 'copilot':
            session_id, answer = cp.ask_question(str(self), session_id=self.session_id)
            print(answer)
            self.session_id = session_id
            self.response_dict = json.loads(answer)
            self.tools_intent = self.response_dict.get("tools")
            self.response_answer = self.response_dict.get("answer")

            return self.response_answer
        else:
            raise ValueError(f"Unsupported model provider: {self.model_provider}")



if __name__ == '__main__':
    user_input = "Pobierz dane z https://szkoladevnet.pl/tajemnicze-args-i-kwargs/ stesc i zapisz do pliku tajemnicze_args_i_kwargs.md"
    prompt = ContextPrompt(user_input, included_tools=[WebFetch()])
    r = prompt.ask()
    print(r)
