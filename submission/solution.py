from knowledge import KnowledgeSystem
from llm import steps_from_environment


def build() -> KnowledgeSystem:
    return KnowledgeSystem(*steps_from_environment())
