"""
agents/split_brain/models.py
=============================
Pydantic data models for the Split-Brain Collapse environment.
Defines observation space, action space, and step result types.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any


# ── NETWORK LAYER ────────────────────────────────────────────────────────────

class NetworkNode(BaseModel):
    """A single node in the datacenter network topology."""
    node_id: str
    datacenter: Literal["dc1", "dc2", "dc3"]
    node_type: Literal["router", "switch", "server"]
    status: Literal["online", "offline", "degraded", "partitioned"]
    cpu_usage: float = Field(0.0, description="CPU usage percentage")
    bandwidth_used: float = Field(0.0, description="Bandwidth used in Mbps")
    bandwidth_capacity: float = Field(1000.0, description="Total bandwidth capacity in Mbps")


class NetworkEdge(BaseModel):
    """A link between two network nodes."""
    edge_id: str
    source: str
    target: str
    status: Literal["healthy", "severed", "congested", "bypass", "offline"]
    latency_ms: float = Field(1.0, description="Link latency in milliseconds")
    bandwidth_used: float = Field(0.0, description="Current bandwidth usage in Mbps")
    bandwidth_capacity: float = Field(1000.0, description="Max bandwidth capacity in Mbps")


# ── STORAGE LAYER ────────────────────────────────────────────────────────────

class HDFSCluster(BaseModel):
    """State of the HDFS distributed storage cluster."""
    total_blocks: int = Field(1000, description="Total data blocks in HDFS")
    io_bandwidth_used_pct: float = Field(0.0, description="I/O bandwidth usage 0-100%")
    replication_storm_active: bool = Field(False, description="Whether a replication storm is in progress")
    replication_factor: int = Field(3, description="Current block replication factor")
    target_replication_factor: int = Field(3, description="Desired replication factor")
    under_replicated_blocks: int = Field(0, description="Blocks below target replication")


# ── DATABASE LAYER ───────────────────────────────────────────────────────────

class LedgerEntry(BaseModel):
    """A single row in the NewSQL ledger showing potential conflict."""
    key: str
    dc1_value: Optional[str] = None
    dc2_value: Optional[str] = None
    conflict: bool = False
    timestamp_dc1: Optional[float] = None
    timestamp_dc2: Optional[float] = None


class DatabaseState(BaseModel):
    """State of the NewSQL distributed database."""
    dc1_role: Literal["leader", "follower", "isolated"] = "leader"
    dc2_role: Literal["leader", "follower", "isolated"] = "follower"
    split_brain_active: bool = False
    conflicting_entries: int = 0
    total_entries: int = Field(500, description="Total ledger rows")
    ledger_sample: List[LedgerEntry] = Field(default_factory=list,
                                             description="Sample rows for agent inspection")


# ── GLOBAL OBSERVATION ───────────────────────────────────────────────────────

class SplitBrainObservation(BaseModel):
    """Full environment state delivered to the agent each step."""
    global_health: float = Field(0.0, ge=0.0, le=1.0, description="Overall system health 0.0-1.0")
    current_actor: Literal["orchestrator", "netops", "dataops"] = "orchestrator"
    step: int = 0
    max_steps: int = 35

    # Network
    network_status: Literal["partitioned", "degraded", "healthy"] = "partitioned"
    dc1_dc2_connected: bool = False
    routing_verified: bool = False
    oob_tunnel_active: bool = False
    network_nodes: List[NetworkNode] = Field(default_factory=list)
    network_edges: List[NetworkEdge] = Field(default_factory=list)

    # Storage
    hdfs: HDFSCluster = Field(default_factory=HDFSCluster)

    # Database
    newsql: DatabaseState = Field(default_factory=DatabaseState)

    # Context
    recent_events: List[str] = Field(default_factory=list)
    delegation_context: Optional[str] = Field(None, description="Instruction from the delegating agent")
    
    # Task 4 Additions
    auth_status: Literal["online", "offline"] = "online"
    redis_cache_usage: float = Field(0.0, description="Redis cache memory usage percentage")


# ── ACTION SPACE ─────────────────────────────────────────────────────────────

class SplitBrainAction(BaseModel):
    """A single action taken by the current actor."""
    action_type: Literal[
        # Orchestrator
        "delegate",
        "assess_situation",
        # NetOps
        "update_route",
        "verify_routing",
        "throttle_bandwidth",
        # DataOps
        "tune_hdfs",
        "stop_replication",
        "force_stepdown",
        "reconcile_ledger",
        "clear_cache",
        # Universal
        "noop",
        "run_diagnostic",
    ]
    target_id: Optional[str] = Field(None, description="Node ID, edge ID, or DC identifier to target")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Action-specific parameters")
    # Delegate-specific fields
    target_agent: Optional[Literal["orchestrator", "netops", "dataops"]] = Field(
        None, description="Agent to delegate to (only for delegate action)")
    instruction_payload: Optional[str] = Field(
        None, description="Instructions for the target agent (only for delegate action)")


# ── STEP RESULT ──────────────────────────────────────────────────────────────

class SplitBrainStepResult(BaseModel):
    """Result of a single environment step — OpenEnv compliant."""
    observation: SplitBrainObservation
    reward: float = Field(0.0, description="Step reward signal")
    done: bool = Field(False, description="Whether the episode has ended")
    info: Dict[str, Any] = Field(default_factory=dict, description="Extra metadata including message")
