from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any

# --- OBSERVATION SPACE ---
class NodeStatus(BaseModel):
    node_id: str
    status: Literal["healthy", "high_memory", "disk_full", "offline"]
    cpu_usage: float
    ram_usage: float
    disk_usage: float

class JobStatus(BaseModel):
    job_id: str
    status: Literal["running", "hanging", "queued", "failed"]
    ram_allocated: float

class ClusterObservation(BaseModel):
    health_score: float = Field(..., description="Overall cluster health from 0.0 to 1.0")
    nodes: List[NodeStatus]
    active_jobs: List[JobStatus]
    recent_alerts: List[str]

# --- ACTION SPACE ---
class ClusterAction(BaseModel):
    action_type: Literal["kill_job", "restart_node", "clear_temp_storage", "noop"]
    target_id: Optional[str] = Field(None, description="The job_id or node_id to target")

# --- STEP RESULT (OpenEnv spec compliant) ---
# step() returns a StepResult with .observation, .reward, .done, .info
# This matches the inference.py contract:
#   result = env.step(action)
#   observation = result.observation
#   reward = result.reward
#   done = result.done
class StepResult(BaseModel):
    observation: ClusterObservation
    reward: float = Field(..., description="Step reward signal between -1.0 and 1.0")
    done: bool = Field(..., description="Whether the episode has ended")
    info: Dict[str, Any] = Field(default_factory=dict, description="Extra info including message")

# --- RESET REQUEST (for HTTP API) ---
class ResetRequest(BaseModel):
    task: str = Field("easy", description="Task ID: easy, medium, hard, very_hard, nightmare")
    agent_id: Optional[str] = Field(None, description="Agent ID from the registry (e.g. cluster_triage)")
