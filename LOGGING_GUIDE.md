# Logging Guide - Memory-Break Orchestrator

## Overview

The system now has comprehensive logging at multiple levels that streams to the UI in real-time.

## Log Levels

### 1. **Task-Level Logs** (`storage/{task_id}/task.log`)
High-level orchestration events visible in the UI:

- `TASK_STARTED` - Task begins processing
- `PR_PROCESSING` - Cloning and analyzing PR
- `pr_cloned` - PR clone complete with file counts
- `PROMPT_GENERATION` - Generating evaluation prompts
- `prompt_generated` - Each prompt type generated (with content preview)
- `AGENTS_STARTING` - Agent execution begins
- `AGENT_STARTED` - Individual agent starts
- `AGENT_PROCESSED` - Agent completes
- `AGENT_SUCCESS` / `AGENT_FAILED` - Agent result
- `JUDGING_STARTED` - Judging phase begins
- `judge_scoring` - Individual scoring decisions
- `TASK_COMPLETED` - Task finishes
- `progress_update` - Progress bar updates (0-100%)

### 2. **Container Logs** (`storage/{task_id}/agents/{agent}/container_stdout.log`)
Detailed agent execution logs with enhanced formatting:

```
================================================================================
PHASE: Pre-compression
PROMPT (pre-compression, 1234 chars):
[First 200 chars of prompt...]

RESPONSE (pre-compression, 567 chars):
[First 500 chars of response...]

================================================================================
PHASE: Deep-dive iteration 1/6
COMMAND: /stats (before deep-dive)
STATS OUTPUT:
[Actual stats output from iFlow]
📊 CONTEXT TRACKING: 95% remaining
📈 CONTEXT CHANGE: 100% -> 95% (Δ-5%)

PROMPT (deep-dive #1, 890 chars):
[First 200 chars...]

RESPONSE (deep-dive #1, 1234 chars):
[First 500 chars...]

================================================================================
PHASE: Evaluation Q&A
Total questions: 5
--------------------------------------------------------------------------------
QUESTION 1: What is the main purpose of this PR?
ANSWER 1 (234 chars):
The main purpose is to improve...

================================================================================
📊 FINAL SUMMARY
Compression detected: True
Context history: [100, 95, 85, 75, 65, 55]
Total deep-dive iterations: 6
Milestones completed: initialized, init_command, pre_compression, ...
================================================================================
```

### 3. **Agent Session Logs** (`storage/{task_id}/agents/{agent}/session.log`)
Structured JSON logs for agent interactions (future use).

### 4. **Transcript Files** (`storage/{task_id}/agents/{agent}/transcript.txt`)
Raw iFlow CLI output captured by pexpect.

## Accessing Logs in UI

### Live Log Viewer
```
http://127.0.0.1:8000/logs?taskId={task_id}
```

Shows:
- Real-time task events
- Progress bars
- PR processing details
- Prompt generation with previews
- Agent execution status
- Evaluation Q&A pairs
- Compression detection events
- Judging scores

### Container Log Stream
```
http://127.0.0.1:8000/api/v1/logs/{task_id}/container/{agent_name}/stream?log_type=stdout
```

Streams the detailed container logs in real-time.

### Available Log Files API
```
http://127.0.0.1:8000/api/v1/logs/{task_id}/artifacts/logs
```

Returns list of all available log files for download.

## Log Event Types

### Progress Events
- `pr_clone` (20-40%)
- `prompt_generation` (50-60%)
- `agent_run` (70-85%)
- `judging` (90-95%)
- `complete` (100%)

### Agent Interaction Events
- `prompt_sent` - Prompt sent to agent
- `response_received` - Response from agent
- `command_executed` - Command run in agent
- `context_stats` - Context percentage updates

### Compression Detection
- `compression_detected` - Memory compression event
  - `detection_method`: context_jump, percentage_threshold, heuristic
  - `before_context`: Context before compression
  - `after_context`: Context after compression

### Evaluation Events
- `memory_only_started` - Memory-only phase begins
- `evaluation_qa` - Question and answer logged
  - `question_index`: Question number
  - `question`: Question text
  - `answer`: Answer text (truncated)

### Error Events
- `error` - Any error with context
  - `error_type`: Category of error
  - `error_message`: Error description
  - `exception_type`: Python exception type
  - `exception_details`: Exception details

## UI Features

1. **Filters**
   - Log level (INFO, WARNING, ERROR)
   - Event type (task_started, agent_interaction, etc.)
   - Agent (iflow, claude, gemini)

2. **Display Modes**
   - Structured: Pretty formatted with expandable sections
   - Raw: JSON format

3. **Auto-scroll**
   - Toggle on/off
   - Automatically scrolls to new logs

4. **Statistics**
   - Total logs count
   - Error count
   - Filtered logs count
   - Connection duration

## Example Log Flow

```
[10:00:00] TASK_STARTED - Simple worker started processing task
[10:00:01] PR_PROCESSING - Cloning and analyzing PR
[10:00:05] pr_cloned - Cloned 50 files
[10:00:06] PROMPT_GENERATION - Generating prompts for 5 files
[10:00:10] prompt_generated - Generated precompression prompt: 1749 chars
[10:00:11] prompt_generated - Generated deepdive prompt: 1234 chars
[10:00:12] prompt_generated - Generated memory_only prompt: 890 chars
[10:00:13] prompt_generated - Generated evaluator_set prompt: 2345 chars
[10:00:14] AGENTS_STARTING - Starting 1 agents
[10:00:15] AGENT_STARTED - Starting iflow agent
[10:01:45] AGENT_PROCESSED - iflow completed with status: success
[10:01:46] JUDGING_STARTED - Judging 1 successful agent(s)
[10:01:50] judge_scoring - Scored iflow on AR: 0.85
[10:01:51] judge_scoring - Scored iflow on TTL: 0.90
[10:01:52] TASK_COMPLETED - Task completed successfully in 112.3s
```

## Next Steps

Run a new task and view the logs at:
```
http://127.0.0.1:8000/logs?taskId=YOUR_TASK_ID
```

All the detailed logs from the API log file will now appear in the UI in real-time!

