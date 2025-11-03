# Data Flow Documentation

## Overview
This document describes the complete data flow from task creation to agent execution.

## Flow Diagram

```
1. Task Creation (POST /api/v1/tasks)
   │
   ├─> Create task in database
   ├─> Create agent runs for each agent (iflow, claude, gemini)
   └─> Enqueue task for processing

2. Task Processing (process_task)
   │
   ├─> Process PR (pr_service.process_pr)
   │   │
   │   ├─> Option A: Use GitHub API (fast, no clone)
   │   │   └─> Get changed files via API
   │   │
   │   └─> Option B: Clone repository (fallback)
   │       └─> Clone to: storage/{task_id}/pr/master/{repo_name}
   │
   ├─> Generate prompts (prompt_service.generate_prompts)
   │
   └─> Process agents in parallel (run_agent_session for each)
       │
       ├─> For each agent (iflow, claude, gemini):
       │   │
       │   ├─> Create isolated repo copy
       │   │   └─> storage/{task_id}/agents/{agent_name}/repo
       │   │
       │   ├─> Create AgentSession with:
       │   │   ├─> repo_dir: agent's isolated repo path
       │   │   ├─> output_dir: agent's output directory
       │   │   └─> prompts: pre, deep, memory_only, eval
       │   │
       │   └─> Run agent session (agent.run_session)
       │       │
       │       ├─> iFlow Agent:
       │       │   ├─> _start_iflow_process(repo_dir)
       │       │   │   └─> Launch: iflow --experimental-acp --port 8090
       │       │   │       └─> cwd: repo_dir
       │       │   ├─> Wait for WebSocket server
       │       │   ├─> Connect via SDK (with retry logic)
       │       │   └─> Automatically send prompts:
       │       │       ├─> /init
       │       │       ├─> precompression prompt
       │       │       ├─> deepdive prompts (loop)
       │       │       ├─> memory_only prompt
       │       │       └─> evaluator_set prompt
       │       │
       │       ├─> Claude Agent:
       │       │   ├─> _load_repo_files(repo_dir)
       │       │   ├─> Initialize with repo context
       │       │   └─> Automatically send prompts via API:
       │       │       ├─> precompression prompt
       │       │       ├─> deepdive prompts (loop)
       │       │       ├─> memory_only prompt
       │       │       └─> evaluator_set prompt
       │       │
       │       └─> Gemini Agent:
       │           ├─> _load_repo_files(repo_dir)
       │           ├─> Initialize with repo context
       │           └─> Automatically send prompts via API:
       │               ├─> precompression prompt
       │               ├─> deepdive prompts (loop)
       │               ├─> memory_only prompt
       │               └─> evaluator_set prompt
       │
       └─> Store results and artifacts
```

## Key Points

### 1. Repository Isolation
- Each agent gets its own isolated repository copy
- Prevents agents from interfering with each other
- Path: `storage/{task_id}/agents/{agent_name}/repo`

### 2. Agent Launch in Repo Directory
- **iFlow**: Launches CLI process with `cwd=repo_dir`
- **Claude/Gemini**: Load files from `repo_dir` via API

### 3. Automatic Prompt Execution
All agents automatically execute prompts in sequence:
- Pre-compression analysis
- Deep-dive analysis (loop until token limit)
- Memory-only evaluation
- Evaluator questions

### 4. Parallel Execution
Agents run in parallel using ThreadPoolExecutor for faster processing.

## File Structure

```
storage/
└── {task_id}/
    ├── pr/
    │   └── master/
    │       └── {repo_name}/          # Master repo (may not exist if using API-only)
    │
    └── agents/
        ├── iflow/
        │   ├── repo/                 # Isolated iFlow repo copy
        │   ├── transcript.txt
        │   └── iflow_logs/
        │       ├── iflow_*_stdout.log
        │       └── iflow_*_stderr.log
        │
        ├── claude/
        │   ├── repo/                 # Isolated Claude repo copy
        │   └── transcript.txt
        │
        └── gemini/
            ├── repo/                 # Isolated Gemini repo copy
            └── transcript.txt
```

## Code References

- **Task Creation**: `app/presentation/routers/tasks.py::create_task()`
- **Task Processing**: `workers/tasks.py::process_task()`
- **PR Processing**: `app/services/pr_service.py::process_pr()`
- **Agent Session**: `workers/tasks.py::run_agent_session()`
- **Agent Implementations**:
  - iFlow: `app/agents/iflow_agent.py::run_session()`
  - Claude: `app/agents/claude_agent.py::run_session()`
  - Gemini: `app/agents/gemini_agent.py::run_session()`
