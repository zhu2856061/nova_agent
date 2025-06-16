import os
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field


class Configuration(BaseModel):
    """The configuration for the agent."""

    task_id: str = Field(
        default="",
        description="The id of the task.",
    )

    coordinator_model: str = Field(
        default="BASIC",
        description="The name of the language model to use for the agent's coordinator.",
    )
    planner_model: str = Field(
        default="BASIC",
        description="The name of the language model to use for the agent's planner.",
    )
    supervisor_model: str = Field(
        default="BASIC",
        description="The name of the language model to use for the agent's supervisor.",
    )
    researcher_model: str = Field(
        default="BASIC",
        description="The name of the language model to use for the agent's researcher.",
    )
    reporter_model: str = Field(
        default="BASIC",
        description="The name of the language model to use for the agent's researcher.",
    )

    is_deep_thinking_mode: bool = Field(
        default=False,
        description="Whether to use deep thinking mode.",
    )
    is_serp_before_planning: bool = Field(
        default=False,
        description="Whether to use serp before planning.",
    )
    retry_limit: int = Field(
        default=3,
        description="The maximum number of retries to perform.",
    )
    number_of_initial_queries: int = Field(
        default=3,
        description="The number of initial search queries to generate.",
    )

    max_research_loops: int = Field(
        default=2,
        description="The maximum number of research loops to perform.",
    )

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = (
            config["configurable"] if config and "configurable" in config else {}
        )

        # Get raw values from environment or config
        raw_values: dict[str, Any] = {
            name: os.environ.get(name.upper(), configurable.get(name))
            for name in cls.model_fields.keys()
        }

        # Filter out None values
        values = {k: v for k, v in raw_values.items() if v is not None}

        return cls(**values)
