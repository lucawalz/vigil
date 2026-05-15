"""Shared runtime constants for vigil agents."""

import os

GIT_COMMIT_BUDGET: int = int(os.environ.get("GIT_COMMIT_BUDGET", "1"))
