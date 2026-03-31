from one_think.context_provider import ContextPrompt
from one_think.conversation_context import ConversationContext
from one_think.tools.credentials_tool import CredentialsTool
from one_think.tools.google_workspace_tool import GoogleWorkspaceTool
from one_think.tools.memory_tool import MemoryTool
from one_think.tools.messenger_tool import MessengerTool
from one_think.tools.python_executor_tool import PythonExecutorTool
from one_think.tools.soul_tool import SoulTool
from one_think.tools.user_tool import UserTool
from one_think.tools.web_fetch import WebFetch
from one_think.tools.write_to_file import WriteToFile

VERSION = "1.0.0"


def run():
    context = ConversationContext(
        included_tools=[WebFetch(), WriteToFile(), CredentialsTool(), SoulTool(), UserTool(), MemoryTool(),
                        GoogleWorkspaceTool(), PythonExecutorTool(), MessengerTool()])
    while True:
        prompt = input("Enter your prompt: ")
        prompt1 = ContextPrompt(prompt=prompt)
        response = context.execute_prompt_waterfall(prompt1)
        print(response)
