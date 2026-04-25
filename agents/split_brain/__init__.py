"""
agents/split_brain/__init__.py
Exports the Split-Brain Collapse environment class and task definitions.
"""
from agents.split_brain.environment import SplitBrainEnv

AGENT_META = {
    "id":          "split_brain",
    "name":        "Split-Brain Collapse",
    "icon":        "🧠",
    "description": "Multi-agent DC partition recovery — network, storage & database crisis.",
    "tasks": [
        {"id": "partition_basic",   "name": "The Partition",       "difficulty": 1, "max_steps": 15, "label": "BASIC",    "color": "#10b981"},
        {"id": "replication_storm", "name": "Replication Storm",   "difficulty": 2, "max_steps": 25, "label": "STORM",    "color": "#fbbf24"},
        {"id": "split_brain",      "name": "The Split-Brain",     "difficulty": 3, "max_steps": 35, "label": "SPLIT",    "color": "#ef4444"},
        {"id": "cascading_deadlock", "name": "Cascading Deadlock", "difficulty": 4, "max_steps": 35, "label": "DEADLOCK", "color": "#7c3aed"},
        {"id": "regional_wipeout",   "name": "Regional Wipeout",   "difficulty": 5, "max_steps": 50, "label": "WIPEOUT",  "color": "#b91c1c", "label_color": "#ff6b6b"},
    ],
}

ENV_CLASS = SplitBrainEnv
