memorizer_system_prompt = """You are a helpful and friendly chatbot. Get to know the user! Ask questions! Be spontaneous! 
<memories>
{user_info}
</memories>

Today's date is {date}.
"""

PROMPT_TEMPLATE = {
    "memorizer_system": memorizer_system_prompt,
}


def apply_system_prompt_template(prompt_name, state=None):
    # Convert state to dict for template rendering
    if state is None:
        state = {}
    state_vars = {**state}
    try:
        system_prompt = PROMPT_TEMPLATE[prompt_name].format(**state_vars)
        return system_prompt
    except Exception as e:
        raise ValueError(f"Error applying template {prompt_name}: {e}")
