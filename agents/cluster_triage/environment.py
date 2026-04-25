import copy
import json
import re
from .models import ClusterObservation, ClusterAction, StepResult, NodeStatus, JobStatus


class ClusterTriageEnv:
    """
    OpenEnv-compliant environment simulating a 4-node distributed data cluster
    under various failure scenarios. An AI agent acting as an SRE must triage
    infrastructure failures using precise terminal commands.
    """

    def __init__(self):
        self.current_task = None
        self.state_data = None
        self.step_count = 0
        self.max_steps = 25

        # --- Task progress trackers ---
        self.rogue_job_killed = False
        self.medium_storage_cleared = False
        self.cleared_nodes = set()
        self.vh_log_killed = False
        self.vh_crypto_killed = False
        self.nm_hydras_killed = set()
        self.nm_nodes_cleared = set()

    def _reset_trackers(self):
        self.step_count = 0
        self.rogue_job_killed = False
        self.medium_storage_cleared = False
        self.cleared_nodes = set()
        self.vh_log_killed = False
        self.vh_crypto_killed = False
        self.nm_hydras_killed = set()
        self.nm_nodes_cleared = set()

    def reset(self, task: str = "easy") -> ClusterObservation:
        """Reset environment to a fresh episode for the given task."""
        self.current_task = task
        self._reset_trackers()

        base_nodes = [
            NodeStatus(node_id="worker_01", status="healthy", cpu_usage=45.0, ram_usage=60.0, disk_usage=30.0),
            NodeStatus(node_id="worker_02", status="healthy", cpu_usage=50.0, ram_usage=55.0, disk_usage=40.0),
            NodeStatus(node_id="worker_03", status="healthy", cpu_usage=42.0, ram_usage=48.0, disk_usage=25.0),
            NodeStatus(node_id="worker_04", status="healthy", cpu_usage=48.0, ram_usage=52.0, disk_usage=35.0),
        ]

        if task == "easy":
            base_jobs = [
                JobStatus(job_id="job_normal_01", status="running", ram_allocated=10.0),
                JobStatus(job_id="job_rogue_99", status="hanging", ram_allocated=99.0),
            ]
            self.state_data = ClusterObservation(
                health_score=0.4, nodes=base_nodes, active_jobs=base_jobs,
                recent_alerts=["CRITICAL: job_rogue_99 is hanging and consuming all RAM on worker_01."],
            )

        elif task == "medium":
            base_nodes[2].status = "disk_full"
            base_nodes[2].disk_usage = 99.9
            self.state_data = ClusterObservation(
                health_score=0.3, nodes=base_nodes, active_jobs=[],
                recent_alerts=["WARNING: worker_03 disk at 99.9% capacity. All writes failing."],
            )

        elif task == "hard":
            base_nodes[0].status = "offline"; base_nodes[0].disk_usage = 100.0
            base_nodes[1].status = "offline"; base_nodes[1].disk_usage = 100.0
            base_nodes[2].status = "high_memory"; base_nodes[2].ram_usage = 95.0
            base_nodes[3].status = "high_memory"; base_nodes[3].ram_usage = 95.0
            base_jobs = [JobStatus(job_id="job_rogue_99", status="hanging", ram_allocated=0.0)]
            self.state_data = ClusterObservation(
                health_score=0.1, nodes=base_nodes, active_jobs=base_jobs,
                recent_alerts=[
                    "ERROR: job_rogue_99 caused a HDFS replication storm.",
                    "FATAL: Nodes worker_01 and worker_02 are OFFLINE. Disk 100% full.",
                    "WARNING: Failover traffic overloading worker_03 and worker_04.",
                ],
            )

        elif task == "very_hard":
            base_nodes[0].status = "offline"; base_nodes[0].disk_usage = 100.0
            base_nodes[1].status = "offline"; base_nodes[1].disk_usage = 100.0
            base_nodes[2].status = "high_memory"; base_nodes[2].ram_usage = 99.0
            base_nodes[3].status = "high_memory"; base_nodes[3].ram_usage = 99.0
            base_jobs = [
                JobStatus(job_id="job_log_spam", status="hanging", ram_allocated=0.0),
                JobStatus(job_id="job_crypto_miner", status="hanging", ram_allocated=99.0),
            ]
            self.state_data = ClusterObservation(
                health_score=0.05, nodes=base_nodes, active_jobs=base_jobs,
                recent_alerts=[
                    "CRITICAL: MULTI-VECTOR ATTACK DETECTED.",
                    "ALERT: job_log_spam is filling disks on worker_01 and worker_02 (100% full).",
                    "ALERT: job_crypto_miner is consuming all RAM on worker_03 and worker_04.",
                    "HINT: Kill BOTH malware jobs before attempting storage recovery.",
                ],
            )

        elif task == "nightmare":
            for node in base_nodes:
                node.status = "offline"
                node.cpu_usage = 0.0
                node.ram_usage = 0.0
                node.disk_usage = 100.0
            base_jobs = [
                JobStatus(job_id="job_hydra_1", status="hanging", ram_allocated=0.0),
                JobStatus(job_id="job_hydra_2", status="hanging", ram_allocated=0.0),
                JobStatus(job_id="job_hydra_3", status="hanging", ram_allocated=0.0),
            ]
            self.state_data = ClusterObservation(
                health_score=0.0, nodes=base_nodes, active_jobs=base_jobs,
                recent_alerts=[
                    "FATAL: TOTAL CLUSTER COLLAPSE. ALL 4 NODES OFFLINE.",
                    "WARNING: HYDRA PROTOCOL DETECTED. 3 self-replicating malware jobs active.",
                    "CRITICAL: All node disks at 100%. Data writes completely blocked.",
                    "HINT: You MUST kill ALL 3 Hydra jobs FIRST. Any surviving Hydra will instantly",
                    "HINT: refill cleared disks. Kill order: hydra_1, hydra_2, hydra_3, then clear nodes.",
                ],
            )
        else:
            self.state_data = ClusterObservation(
                health_score=1.0, nodes=base_nodes, active_jobs=[],
                recent_alerts=["INFO: Cluster is nominal."],
            )

        return self.state()

    def state(self) -> ClusterObservation:
        """Return a snapshot of the current cluster state."""
        return copy.deepcopy(self.state_data)

    def _parse_action(self, action_input) -> ClusterAction:
        """
        Accept either a ClusterAction object or a raw string/JSON from the LLM.
        Handles both formats gracefully.
        """
        if isinstance(action_input, ClusterAction):
            return action_input

        if isinstance(action_input, dict):
            try:
                return ClusterAction(**action_input)
            except Exception:
                return ClusterAction(action_type="noop", target_id="none")

        if isinstance(action_input, str):
            # Strip markdown fences
            text = action_input.replace("```json", "").replace("```", "").strip()
            # Try to find JSON object
            match = re.search(r'\{.*?\}', text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                    if "action_type" in data:
                        return ClusterAction(**data)
                except Exception:
                    pass
            # Try [action] tag format (from sample inference.py)
            match = re.search(r'\[action\]\s*(.*)', text, re.DOTALL | re.IGNORECASE)
            if match:
                inner = match.group(1).strip()
                try:
                    data = json.loads(inner)
                    return ClusterAction(**data)
                except Exception:
                    pass

        return ClusterAction(action_type="noop", target_id="none")

    def step(self, action_input) -> StepResult:
        """
        Execute one action in the environment.
        Accepts ClusterAction object, dict, or raw JSON string.
        Returns StepResult with .observation, .reward, .done, .info
        """
        if self.state_data is None:
            self.reset(task="easy") # Safety check

        self.step_count += 1
        action = self._parse_action(action_input)
        reward = 0.0
        done = False
        msg = "Action registered. No effect."

        # ─────────────────────────────────────────────
        # EASY: Kill the one rogue job
        # ─────────────────────────────────────────────
        if self.current_task == "easy":
            if action.action_type == "kill_job" and action.target_id == "job_rogue_99":
                reward = 1.0
                done = True
                msg = "SUCCESS: Rogue job killed. Cluster stabilized."
                self.state_data.health_score = 1.0
                self.state_data.active_jobs = []
            elif action.action_type == "noop":
                reward = -0.05
                msg = "WARN: No action taken. Rogue job still running."
            else:
                reward = -0.1
                msg = f"WARN: Action {action.action_type} on {action.target_id} has no effect here."

        # ─────────────────────────────────────────────
        # MEDIUM: Clear disk, then restart node
        # ─────────────────────────────────────────────
        elif self.current_task == "medium":
            if action.action_type == "clear_temp_storage" and action.target_id == "worker_03":
                if not self.medium_storage_cleared:
                    self.medium_storage_cleared = True
                    self.state_data.nodes[2].disk_usage = 20.0
                    self.state_data.nodes[2].status = "offline"
                    reward = 0.5
                    msg = "GOOD: Storage cleared on worker_03. Now restart the node."
                else:
                    reward = 0.0
                    msg = "INFO: Storage already cleared."
            elif action.action_type == "restart_node" and action.target_id == "worker_03":
                if self.medium_storage_cleared:
                    reward = 0.5
                    done = True
                    self.state_data.health_score = 1.0
                    self.state_data.nodes[2].status = "healthy"
                    msg = "SUCCESS: worker_03 restarted cleanly. Disk healthy."
                else:
                    reward = -0.3
                    msg = "CRITICAL: Cannot restart worker_03 — disk still full. Clear storage first."
            elif action.action_type == "noop":
                reward = -0.05
                msg = "WARN: No action. Disk still full."
            else:
                reward = -0.1
                msg = f"WARN: {action.action_type} on {action.target_id} has no effect here."

        # ─────────────────────────────────────────────
        # HARD: Kill job → clear 2 nodes → restart 2 nodes
        # ─────────────────────────────────────────────
        elif self.current_task == "hard":
            if action.action_type == "kill_job" and action.target_id == "job_rogue_99":
                if not self.rogue_job_killed:
                    self.rogue_job_killed = True
                    self.state_data.active_jobs = [j for j in self.state_data.active_jobs if j.job_id != "job_rogue_99"]
                    reward = 0.2
                    msg = "GOOD: Replication storm source terminated. Now clear the full disks."
                else:
                    reward = 0.0
                    msg = "INFO: job_rogue_99 already killed."

            elif action.action_type == "clear_temp_storage" and action.target_id in ["worker_01", "worker_02"]:
                if not self.rogue_job_killed:
                    reward = -0.1
                    msg = f"PENALTY: job_rogue_99 still running — it immediately refilled {action.target_id}."
                elif action.target_id not in self.cleared_nodes:
                    self.cleared_nodes.add(action.target_id)
                    idx = 0 if action.target_id == "worker_01" else 1
                    self.state_data.nodes[idx].disk_usage = 20.0
                    reward = 0.2
                    msg = f"GOOD: Storage cleared on {action.target_id}. Ready to reboot."
                else:
                    reward = 0.0
                    msg = f"INFO: {action.target_id} storage already cleared."

            elif action.action_type == "restart_node" and action.target_id in ["worker_01", "worker_02"]:
                if action.target_id not in self.cleared_nodes:
                    reward = -0.2
                    msg = f"CRITICAL: {action.target_id} crashed on boot — disk still full!"
                else:
                    idx = 0 if action.target_id == "worker_01" else 1
                    if self.state_data.nodes[idx].status != "healthy":
                        self.state_data.nodes[idx].status = "healthy"
                        reward = 0.2
                        msg = f"SUCCESS: {action.target_id} rebooted cleanly."
                        # Check win condition
                        if (self.state_data.nodes[0].status == "healthy"
                                and self.state_data.nodes[1].status == "healthy"):
                            self.state_data.nodes[2].status = "healthy"
                            self.state_data.nodes[3].status = "healthy"
                            self.state_data.health_score = 1.0
                            done = True
                            msg += " ALL NODES NOMINAL. Cluster stabilized."
                    else:
                        reward = 0.0
                        msg = f"INFO: {action.target_id} is already healthy."
            else:
                reward = -0.05
                msg = f"WARN: {action.action_type} on {action.target_id} has no effect."

        # ─────────────────────────────────────────────
        # VERY HARD: Kill 2 jobs → clear 2 nodes → restart 2 nodes
        # ─────────────────────────────────────────────
        elif self.current_task == "very_hard":
            if action.action_type == "kill_job":
                if action.target_id == "job_log_spam" and not self.vh_log_killed:
                    self.vh_log_killed = True
                    self.state_data.active_jobs = [j for j in self.state_data.active_jobs if j.job_id != "job_log_spam"]
                    reward = 0.15
                    msg = "GOOD: Disk-filling log spammer terminated. worker_01 and worker_02 disks are now stable."
                elif action.target_id == "job_crypto_miner" and not self.vh_crypto_killed:
                    self.vh_crypto_killed = True
                    self.state_data.active_jobs = [j for j in self.state_data.active_jobs if j.job_id != "job_crypto_miner"]
                    self.state_data.nodes[2].status = "healthy"
                    self.state_data.nodes[2].ram_usage = 48.0
                    self.state_data.nodes[3].status = "healthy"
                    self.state_data.nodes[3].ram_usage = 52.0
                    reward = 0.15
                    msg = "GOOD: Crypto miner terminated. worker_03 and worker_04 RAM pressure relieved."
                else:
                    reward = 0.0
                    msg = f"INFO: {action.target_id} already killed or not a valid target."

            elif action.action_type == "clear_temp_storage" and action.target_id in ["worker_01", "worker_02"]:
                if not self.vh_log_killed:
                    reward = -0.15
                    msg = "PENALTY: job_log_spam still active — it immediately refilled the storage!"
                elif action.target_id not in self.cleared_nodes:
                    self.cleared_nodes.add(action.target_id)
                    idx = 0 if action.target_id == "worker_01" else 1
                    self.state_data.nodes[idx].disk_usage = 20.0
                    reward = 0.15
                    msg = f"GOOD: Junk data cleared from {action.target_id}. Ready to reboot."
                else:
                    reward = 0.0
                    msg = f"INFO: {action.target_id} already cleared."

            elif action.action_type == "restart_node" and action.target_id in ["worker_01", "worker_02"]:
                if action.target_id not in self.cleared_nodes:
                    reward = -0.2
                    msg = f"CRITICAL: {action.target_id} OS crashed on boot — disk still full!"
                else:
                    idx = 0 if action.target_id == "worker_01" else 1
                    if self.state_data.nodes[idx].status != "healthy":
                        self.state_data.nodes[idx].status = "healthy"
                        reward = 0.2
                        msg = f"SUCCESS: {action.target_id} rebooted."
                        # Check win condition
                        if (self.vh_log_killed and self.vh_crypto_killed
                                and "worker_01" in self.cleared_nodes
                                and "worker_02" in self.cleared_nodes
                                and self.state_data.nodes[0].status == "healthy"
                                and self.state_data.nodes[1].status == "healthy"):
                            self.state_data.health_score = 1.0
                            done = True
                            msg += " MULTI-VECTOR ATTACK FULLY THWARTED. SYSTEM NOMINAL."
                    else:
                        reward = 0.0
                        msg = f"INFO: {action.target_id} is already healthy."
            else:
                reward = -0.05
                msg = f"WARN: {action.action_type} on {action.target_id} has no effect."

        # ─────────────────────────────────────────────
        # NIGHTMARE: Kill 3 hydras → clear 4 nodes → restart 4 nodes
        # ─────────────────────────────────────────────
        elif self.current_task == "nightmare":
            if action.action_type == "kill_job" and action.target_id in ["job_hydra_1", "job_hydra_2", "job_hydra_3"]:
                if action.target_id not in self.nm_hydras_killed:
                    self.nm_hydras_killed.add(action.target_id)
                    self.state_data.active_jobs = [j for j in self.state_data.active_jobs if j.job_id != action.target_id]
                    reward = 0.1
                    remaining = 3 - len(self.nm_hydras_killed)
                    if remaining == 0:
                        msg = "ALL HYDRA HEADS SEVERED. Disks are stable. Now clear all 4 nodes."
                    else:
                        msg = f"{action.target_id} terminated. {remaining} Hydra(s) remain. Kill them ALL before clearing."
                else:
                    reward = 0.0
                    msg = f"INFO: {action.target_id} already killed."

            elif action.action_type == "clear_temp_storage":
                node_ids = ["worker_01", "worker_02", "worker_03", "worker_04"]
                if action.target_id not in node_ids:
                    reward = -0.05
                    msg = f"WARN: {action.target_id} is not a valid node."
                elif len(self.nm_hydras_killed) < 3:
                    reward = -0.15
                    msg = f"PENALTY: A surviving Hydra instantly refilled {action.target_id} to 100%. Kill all hydras first!"
                elif action.target_id not in self.nm_nodes_cleared:
                    self.nm_nodes_cleared.add(action.target_id)
                    idx = int(action.target_id.split("_")[1]) - 1
                    self.state_data.nodes[idx].disk_usage = 20.0
                    reward = 0.1
                    msg = f"GOOD: Storage cleared on {action.target_id}. {4 - len(self.nm_nodes_cleared)} node(s) remaining to clear."
                else:
                    reward = 0.0
                    msg = f"INFO: {action.target_id} already cleared."

            elif action.action_type == "restart_node":
                node_ids = ["worker_01", "worker_02", "worker_03", "worker_04"]
                if action.target_id not in node_ids:
                    reward = -0.05
                    msg = f"WARN: {action.target_id} is not a valid node."
                elif action.target_id not in self.nm_nodes_cleared:
                    reward = -0.2
                    msg = f"CRITICAL: {action.target_id} crashed on boot — disk still full!"
                else:
                    idx = int(action.target_id.split("_")[1]) - 1
                    if self.state_data.nodes[idx].status != "healthy":
                        self.state_data.nodes[idx].status = "healthy"
                        reward = 0.075
                        msg = f"{action.target_id} rebooted cleanly."
                        if all(node.status == "healthy" for node in self.state_data.nodes):
                            self.state_data.health_score = 1.0
                            done = True
                            msg += " NIGHTMARE DEFEATED. ALL SYSTEMS NOMINAL."
                    else:
                        reward = 0.0
                        msg = f"INFO: {action.target_id} already healthy."
            else:
                reward = -0.05
                msg = f"WARN: {action.action_type} on {action.target_id} has no effect."

        # Max steps exceeded
        if not done and self.step_count >= self.max_steps:
            done = True
            msg = f"TIMEOUT: Max steps ({self.max_steps}) reached. Episode failed."

        return StepResult(
            observation=self.state(),
            reward=reward,
            done=done,
            info={"message": msg, "step": self.step_count},
        )