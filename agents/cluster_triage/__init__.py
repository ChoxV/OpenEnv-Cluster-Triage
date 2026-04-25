"""
agents/cluster_triage/__init__.py
Exports the Cluster Triage environment class and its task definitions.
"""

# Import from the local package
from .environment import ClusterTriageEnv
from .models import ClusterAction

AGENT_META = {
    "id":          "cluster_triage",
    "name":        "Cluster SRE",
    "icon":        "🖥️",
    "description": "AI SRE triaging infrastructure failures in a 4-node distributed data cluster.",
    "tasks": [
        {"id": "easy",      "name": "The Stuck Job",       "difficulty": 1, "max_steps": 5,  "label": "EASY",      "color": "#10b981"},
        {"id": "medium",    "name": "The Full Disk",        "difficulty": 2, "max_steps": 10, "label": "MEDIUM",    "color": "#fbbf24"},
        {"id": "hard",      "name": "The Cascade Failure",  "difficulty": 3, "max_steps": 15, "label": "HARD",      "color": "#f97316"},
        {"id": "very_hard", "name": "Multi-Vector Attack",  "difficulty": 4, "max_steps": 20, "label": "VERY HARD", "color": "#ef4444"},
        {"id": "nightmare", "name": "The Hydra Protocol",   "difficulty": 5, "max_steps": 25, "label": "NIGHTMARE", "color": "#e879f9"},
    ],
}

ENV_CLASS = ClusterTriageEnv
