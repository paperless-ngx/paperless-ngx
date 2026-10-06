import re


def dummy_preprocess(content: str) -> str:
    """
    Simpler, faster pre-processing for testing purposes
    """
    content = content.lower().strip()
    content = re.sub(r"\s+", " ", content)
    return content
