def new_message_list(system_prompt: str) -> list[dict]:
    """Start a fresh conversation with the system prompt."""
    return [{"role": "system", "content": system_prompt}]


def add_user(messages: list[dict], content: str) -> None:
    messages.append({"role": "user", "content": content})


def add_assistant(messages: list[dict], response) -> None:
    """Append the raw assistant message from a Groq completion choice."""
    messages.append(response.choices[0].message.to_dict())


def add_tool_result(messages: list[dict], tool_call_id: str, result: str) -> None:
    messages.append({
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": result,
    })