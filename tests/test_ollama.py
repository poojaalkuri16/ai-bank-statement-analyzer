from src.llm.ollama_client import OllamaClient

client = OllamaClient()

response = client.generate(
    task="validation",
    prompt="Reply with exactly: Hello Finance AI!",
)

print(response)