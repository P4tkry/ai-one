from one_think.context_provider import ContextPrompt
from one_think.tools import Tool
from one_think.tools.credentials_tool import CredentialsTool
from one_think.tools.soul_tool import SoulTool
from one_think.tools.user_tool import UserTool
from one_think.tools.web_fetch import WebFetch
from one_think.tools.write_to_file import WriteToFile


class ConversationContext:
    def __init__(self, session_id: str = None, model_provider: str = 'copilot', included_tools: list[Tool] = None):
        self.session_id = session_id
        self.history: list[ContextPrompt] = []
        self.model_provider = model_provider
        self.included_tools = included_tools


    def execute_prompt_waterfall(self, prompt: ContextPrompt):
        prompt.set_tools(self.included_tools)
        prompt.model_provider = self.model_provider
        prompt.session_id = self.session_id
        prompt.ask()
        self.session_id = prompt.session_id
        self.history.append(prompt)
        while prompt.tools_intent:
            full_stdout, full_stderr = "", ""
            for tool_name, tool_args in prompt.response_dict.get("tools", {}).items():
                tool = next((t for t in self.included_tools if t.name == tool_name), None)
                if tool:
                    print(f"Executing tool: {tool_name} with arguments: {tool_args}")
                    stdout, stderr = tool.execute(tool_args)
                    full_stdout += f'''---TOOL: {tool_name}---\n{stdout}---END OF TOOL: {tool_name}---\n'''
                    full_stderr += f'''---TOOL: {tool_name}---\n{stderr}---END OF TOOL: {tool_name}---\n'''

                else:
                    print(f"Tool {tool_name} not found in included tools.")
                    continue
            prompt = ContextPrompt(prompt=full_stdout, stderr=full_stderr, is_tool_response=True,
                                       included_tools=self.included_tools, model_provider=self.model_provider,
                                       session_id=self.session_id)
            prompt.ask()
            self.history.append(prompt)

        return prompt.response_answer






if __name__ == "__main__":
    context = ConversationContext(included_tools=[WebFetch(), WriteToFile(), CredentialsTool(), SoulTool(), UserTool()])
    while True:
        prompt = input("Enter your prompt: ")
        prompt1 = ContextPrompt(prompt=prompt)
        response = context.execute_prompt_waterfall(prompt1)
        print(response)

