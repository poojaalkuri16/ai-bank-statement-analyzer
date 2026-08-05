"""
Centralized model selection for all AI agents.

This module maps each agent/task to the most suitable Ollama model.
Keeping model selection here makes it easy to change models later
without modifying individual agents.
"""


class ModelRouter:
    """Returns the appropriate Ollama model for a given task."""

    _MODEL_MAP = {
        "categorization": "gemma3:1b",
        "reporting": "qwen2.5:1.5b",
        "validation": "gemma3:1b",
    }

    _DEFAULT_MODEL = "gemma3:1b"

    @classmethod
    def get_model(cls, task: str) -> str:
        """
        Return the configured model for a given task.

        Args:
            task (str): Task or agent name.

        Returns:
            str: Ollama model name.
        """
        return cls._MODEL_MAP.get(task.lower(), cls._DEFAULT_MODEL)