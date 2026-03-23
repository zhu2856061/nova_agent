# -*- coding: utf-8 -*-
# @Time   : 2026/02/27 10:24
# @Author : zip
# @Moto   : Knowledge comes from decomposition
from __future__ import annotations

from typing import Literal

from langchain.tools import tool

ASK_CLARIFICATION_DESCRIPTION = """Ask the user for clarification when you need more information to proceed.

    Use this tool when you encounter situations where you cannot proceed without user input:

    - **Missing information**: Required details not provided (e.g., file paths, URLs, specific requirements)
    - **Ambiguous requirements**: Multiple valid interpretations exist
    - **Approach choices**: Several valid approaches exist and you need user preference
    - **Risky operations**: Destructive actions that need explicit confirmation (e.g., deleting files, modifying production)
    - **Suggestions**: You have a recommendation but want user approval before proceeding

    The execution will be interrupted and the question will be presented to the user.
    Wait for the user's response before continuing.

    When to use ask_clarification:
    - You need information that wasn't provided in the user's request
    - The requirement can be interpreted in multiple ways
    - Multiple valid implementation approaches exist
    - You're about to perform a potentially dangerous operation
    - You have a recommendation but need user approval

    Best practices:
    - Ask ONE clarification at a time for clarity
    - Be specific and clear in your question
    - Don't make assumptions when clarification is needed
    - For risky operations, ALWAYS ask for confirmation
    - After calling this tool, execution will be interrupted automatically

    Args:
        question: The clarification question to ask the user. Be specific and clear.
        clarification_type: The type of clarification needed (missing_info, ambiguous_requirement, approach_choice, risk_confirmation, suggestion).
        context: Optional context explaining why clarification is needed. Helps the user understand the situation.
        options: Optional list of choices (for approach_choice or suggestion types). Present clear options for the user to choose from.
"""


@tool("ask_clarification", description=ASK_CLARIFICATION_DESCRIPTION)
async def ask_clarification_tool(
    question: str,
    clarification_type: Literal[
        "missing_info",
        "ambiguous_requirement",
        "approach_choice",
        "risk_confirmation",
        "suggestion",
    ],
    context: str | None = None,
    options: list[str] | None = None,
) -> str:
    try:
        result = f"Clarification:\n\nquestion: {question}\n\nclarification_type: {clarification_type}\n\nreason: {context}\n\noptions: {options}"
        return result

    except Exception as e:
        return f"Error: Unexpected error: {type(e).__name__}: {e}"


def format_clarification_message(args: dict) -> str:
    """Format the clarification arguments into a user-friendly message.

    Args:
        args: The tool call arguments containing clarification details

    Returns:
        Formatted message string
    """
    question = args.get("question", "")
    clarification_type = args.get("clarification_type", "missing_info")
    context = args.get("context")
    options = args.get("options", [])

    # Type-specific icons
    type_icons = {
        "missing_info": "❓",
        "ambiguous_requirement": "🤔",
        "approach_choice": "🔀",
        "risk_confirmation": "⚠️",
        "suggestion": "💡",
    }

    icon = type_icons.get(clarification_type, "❓")

    # Build the message naturally
    message_parts = []

    # Add icon and question together for a more natural flow
    if context:
        # If there's context, present it first as background
        message_parts.append(f"{icon} {context}")
        message_parts.append(f"\n{question}")
    else:
        # Just the question with icon
        message_parts.append(f"{icon} {question}")

    # Add options in a cleaner format
    if options and len(options) > 0:
        message_parts.append("")  # blank line for spacing
        for i, option in enumerate(options, 1):
            message_parts.append(f"  {i}. {option}")

    return "\n".join(message_parts)


def ask_clarification(
    question: str,
    clarification_type: Literal[
        "missing_info",
        "ambiguous_requirement",
        "approach_choice",
        "risk_confirmation",
        "suggestion",
    ],
    context: str | None = None,
    options: list[str] | None = None,
) -> str:
    return f"Clarification:\n\nquestion: {question}\n\nclarification_type: {clarification_type}\n\nreason: {context}\n\noptions: {options}"
