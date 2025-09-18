import os
from typing import Optional

def plan_edits(instructions: str, repo_root: str) -> Optional[str]:
    # Placeholder for planning with Gemini locally; avoids network during tests.
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    return f"Planned edits for: {instructions[:100]}..."

