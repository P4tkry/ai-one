import subprocess
import uuid

def ask_question(prompt: str, model: str = 'gpt-4.1', session_id: str = None, catalog: str = None) -> tuple[
    str | None, str]:
    session_id = session_id or str(uuid.uuid4())

    command = [
        "copilot",
        f"--resume={session_id}",
        "--model", model,
        "-sp", prompt
    ]

    print(command)

    output = subprocess.check_output(command, cwd=catalog)
    return session_id, output.decode("utf-8").strip()

# debug
if __name__ == '__main__':
    question = "What is the capital of France?"
    answer = ask_question(question)
    print(f"Question: {question}\nAnswer: {answer}")