# Minimal Unsloth GRPO Training Script for OpenEnv
# ------------------------------------------------
# Upload this script to a Google Colab notebook to satisfy the Hackathon requirement.
# This script uses Unsloth and TRL's GRPOTrainer to train an LLM on your custom OpenEnv.

# 1. Install dependencies (Run this in a Colab cell first)
# !pip install unsloth trl openenv-core
# !pip install "unsloth[colab] @ git+https://github.com/unslothai/unsloth.git"

import torch
from unsloth import FastLanguageModel, is_bfloat16_supported
from trl import GRPOConfig, GRPOTrainer
import re
import json

# Import your OpenEnv Environment
# Note: You must upload your 'agents' folder and 'models.py' to the Colab instance!
from agents.cluster_triage.environment import ClusterTriageEnv
from agents.cluster_triage.models import ClusterAction

# --- 1. Load the Model via Unsloth ---
max_seq_length = 2048
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Llama-3.2-1B-Instruct", # Fast minimal model for Colab
    max_seq_length=max_seq_length,
    load_in_4bit=True,
    fast_inference=True,
    max_lora_rank=16,
    gpu_memory_utilization=0.6,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    use_gradient_checkpointing="unsloth",
)

# --- 2. Define the OpenEnv Reward Function ---
# GRPO evaluates multiple completions from the LLM and rewards them.
# We will spin up the environment, pass the LLM's action, and return the reward!

def openenv_reward_function(prompts, completions, **kwargs):
    rewards = []
    
    for prompt, completion in zip(prompts, completions):
        # 1. Initialize a fresh environment for this generation
        env = ClusterTriageEnv()
        obs = env.reset(task="easy") # Train on the easy task first
        
        # 2. Extract the JSON action from the LLM's completion
        action_text = completion[0]['content']
        match = re.search(r'\{.*?\}', action_text, re.DOTALL)
        
        step_reward = -0.5 # Default penalty for invalid formatting
        if match:
            try:
                data = json.loads(match.group(0))
                action = ClusterAction(**data)
                
                # 3. Step the environment!
                result = env.step(action)
                step_reward = result.reward
                
                # Bonus for actually solving the task
                if result.done and result.observation.health_score == 1.0:
                    step_reward += 2.0
            except Exception:
                pass
                
        rewards.append(step_reward)
        
    return rewards

# --- 3. Create Training Dataset ---
# We provide the LLM with the initial observation to kick off the generation.
dummy_env = ClusterTriageEnv()
init_obs = dummy_env.reset(task="easy")

system_prompt = "You are an automated DevOps system. Output EXACTLY ONE JSON object."
user_prompt = f"CURRENT CLUSTER STATE:\n{init_obs.model_dump_json(indent=2)}\n\nValid actions: kill_job, restart_node, clear_temp_storage, noop.\nProvide your action in JSON:"

from datasets import Dataset
dataset = Dataset.from_list([
    {
        "prompt": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    }
] * 100) # Duplicate the prompt 100 times to form a batch dataset

# --- 4. Train with GRPO ---
training_args = GRPOConfig(
    output_dir="openenv_outputs",
    learning_rate=5e-6,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,
    max_steps=50,
    logging_steps=5,
    optim="adamw_8bit",
)

trainer = GRPOTrainer(
    model=model,
    processing_class=tokenizer,
    reward_funcs=[openenv_reward_function], # Inject OpenEnv logic here!
    args=training_args,
    train_dataset=dataset,
)

print("Starting OpenEnv GRPO Training...")
trainer.train()

# --- 5. Save the trained agent ---
model.save_pretrained("openenv-cluster-sre-lora")
print("Training Complete! Model saved.")
