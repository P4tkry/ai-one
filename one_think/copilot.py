import subprocess
import uuid


def ask_question(
    prompt: str,
    model: str = 'gpt-4.1',
    session_id: str = None,
    catalog: str = None
) -> tuple[str | None, str]:

    session_id = session_id or str(uuid.uuid4())

    command = [
        "copilot",
        f"--resume={session_id}",
        "--model", model,
        "-sp", prompt
    ]

    print("COMMAND:", command)

    result = subprocess.run(
        command,
        cwd=catalog,
        capture_output=True,
        text=True,
        encoding="utf-8"
    )

    # print("\n=== SUBPROCESS DEBUG ===")
    # print("RETURN CODE:", result.returncode)
    # print("STDOUT:\n", result.stdout)
    # print("STDERR:\n", result.stderr)
    # print("=== END DEBUG ===\n")

    if result.returncode != 0:
        raise RuntimeError(
            f"copilot failed (code {result.returncode})\n"
            f"STDERR:\n{result.stderr}\n"
            f"STDOUT:\n{result.stdout}"
        )

    return session_id, result.stdout.strip()

# debug
if __name__ == '__main__':
    question = "What is the capital of France?"
    answer = ask_question(question)
    print(f"Question: {question}\nAnswer: {answer}")