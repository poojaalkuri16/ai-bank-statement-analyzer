"""
Shared Ollama client for all AI agents.

This module provides a single interface for interacting with local
Ollama models. Model selection is delegated to the ModelRouter.
"""

from ollama import Client

from src.llm.model_router import ModelRouter


class OllamaClient:
    """Reusable client for communicating with Ollama."""

    def __init__(self, host: str = "http://localhost:11434"):
        self.client = Client(host=host)

    def generate(
        self,
        task: str,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.2,
    ) -> str:
        """
        Generate a response from the appropriate Ollama model.

        Args:
            task: Agent/task name
            prompt: User prompt
            system_prompt: Optional system instruction
            temperature: Model creativity

        Returns:
            Generated text response.
        """

        model = ModelRouter.get_model(task)

        print("\n" + "=" * 60)
        print("[LLM] Starting Request")
        print(f"[LLM] Task       : {task}")
        print(f"[LLM] Model      : {model}")
        print(f"[LLM] Temperature: {temperature}")
        print("=" * 60)

        messages = []

        if system_prompt.strip():
            messages.append(
                {
                    "role": "system",
                    "content": system_prompt,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        response = self.client.chat(
            model=model,
            messages=messages,
            options={
                "temperature": temperature,
            },
        )

        print("[LLM] Response received successfully.")
        print("=" * 60 + "\n")

        return response["message"]["content"].strip()