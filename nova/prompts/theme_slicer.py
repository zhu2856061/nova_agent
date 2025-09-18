theme_slicer_prompt = """You are a professional expert in topic classification. 

Today's date is {date}.

Your task is:
1. Analyze the writing outline provided by the user;
2. Divide the outline into 3-8 independent research topics;
3. Provide clear research focus and relevant keywords for each topic;
4. Ensure that each topic is independent of each other, but together they form a complete article.
The output format must be strictly JSON and must not contain any additional text or markup:

```json
{{
    "topics": [
        {{
            "id": 1,
            "title": "topic title",
            "description": "topic description",
            "keywords": ["keyword1", "keyword2"],
            "research_focus": "Research Focus"
        }}
    ]
}}
```

The outline provided by the user is as follows:

"""

PROMPT_TEMPLATE = {
    "theme_slicer": theme_slicer_prompt,
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
