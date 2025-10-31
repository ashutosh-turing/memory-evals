#!/usr/bin/env python3
"""
Agent Runner Script - Executes inside agent containers
Handles the complete lifecycle of agent execution in isolation
"""
import os
import sys
import json
import logging
import argparse
import asyncio
import aiohttp
import signal
import traceback
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import subprocess
import resource
import psutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/agent/logs/agent.log')
    ]
)
logger = logging.getLogger(__name__)

class AgentRunner:
    def __init__(self, agent_type: str, task_data: Dict[str, Any]):
        self.agent_type = agent_type
        self.task_data = task_data
        self.task_id = task_data.get('task_id')
        self.orchestrator_url = os.getenv('ORCHESTRATOR_URL', 'http://host.docker.internal:8000')
        self.workspace_dir = Path(f'/agent/workspace/{agent_type}')
        self.logs_dir = Path(f'/agent/logs/{agent_type}')
        self.results_dir = Path(f'/agent/results/{agent_type}')
        self.start_time = datetime.utcnow()
        self.max_execution_time = int(os.getenv('MAX_EXECUTION_TIME', '1800'))  # 30 minutes
        self.max_memory_mb = self._parse_memory_limit(os.getenv('MAX_MEMORY', '3g'))
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Set memory limits
        self._set_resource_limits()

    def _parse_memory_limit(self, memory_str: str) -> int:
        """Parse memory string like '3g' to MB"""
        if memory_str.endswith('g'):
            return int(memory_str[:-1]) * 1024
        elif memory_str.endswith('m'):
            return int(memory_str[:-1])
        else:
            return int(memory_str)  # Assume MB

    def _set_resource_limits(self):
        """Set resource limits for the process"""
        try:
            # Set memory limit (in bytes)
            memory_bytes = self.max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            
            # Set CPU time limit
            resource.setrlimit(resource.RLIMIT_CPU, (self.max_execution_time, self.max_execution_time))
            
            logger.info(f"Set resource limits: {self.max_memory_mb}MB memory, {self.max_execution_time}s CPU")
        except Exception as e:
            logger.warning(f"Failed to set resource limits: {e}")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        asyncio.create_task(self._graceful_shutdown())

    async def _graceful_shutdown(self):
        """Perform graceful shutdown operations"""
        try:
            await self._report_status('TERMINATED', 'Received shutdown signal')
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
        finally:
            sys.exit(0)

    async def _report_status(self, status: str, message: str = '', progress: int = 0):
        """Report status back to orchestrator"""
        try:
            payload = {
                'task_id': self.task_id,
                'agent_type': self.agent_type,
                'status': status,
                'message': message,
                'progress': progress,
                'timestamp': datetime.utcnow().isoformat(),
                'memory_usage': self._get_memory_usage(),
                'cpu_usage': self._get_cpu_usage()
            }
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.orchestrator_url}/api/v1/tasks/{self.task_id}/status"
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        logger.info(f"Status reported: {status}")
                    else:
                        logger.warning(f"Failed to report status: {response.status}")
        except Exception as e:
            logger.error(f"Error reporting status: {e}")

    async def _report_completion(self, success: bool, results: Dict[str, Any], error: str = None):
        """Report task completion to orchestrator"""
        try:
            payload = {
                'task_id': self.task_id,
                'agent_type': self.agent_type,
                'success': success,
                'results': results,
                'error': error,
                'execution_time': (datetime.utcnow() - self.start_time).total_seconds(),
                'memory_peak': self._get_memory_usage(),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.orchestrator_url}/api/v1/tasks/{self.task_id}/complete"
                async with session.post(url, json=payload, timeout=30) as response:
                    if response.status == 200:
                        logger.info("Task completion reported successfully")
                    else:
                        logger.warning(f"Failed to report completion: {response.status}")
        except Exception as e:
            logger.error(f"Error reporting completion: {e}")

    def _get_memory_usage(self) -> int:
        """Get current memory usage in MB"""
        try:
            process = psutil.Process()
            return process.memory_info().rss // (1024 * 1024)
        except:
            return 0

    def _get_cpu_usage(self) -> float:
        """Get current CPU usage percentage"""
        try:
            process = psutil.Process()
            return process.cpu_percent()
        except:
            return 0.0

    async def _clone_repository(self) -> bool:
        """Clone the PR repository"""
        try:
            await self._report_status('RUNNING', 'Cloning repository...', 10)
            
            pr_url = self.task_data['pr_url']
            repo_url = pr_url.replace('/pull/', '/').split('/pull/')[0] + '.git'
            
            clone_dir = self.workspace_dir / 'repo'
            clone_dir.mkdir(parents=True, exist_ok=True)
            
            # Clone repository
            cmd = ['git', 'clone', repo_url, str(clone_dir)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                logger.error(f"Git clone failed: {result.stderr}")
                return False
                
            # Switch to PR branch if specified
            pr_number = pr_url.split('/')[-1]
            if pr_number.isdigit():
                pr_cmd = ['git', 'fetch', 'origin', f'pull/{pr_number}/head:pr-{pr_number}']
                subprocess.run(pr_cmd, cwd=clone_dir, capture_output=True, timeout=60)
                
                checkout_cmd = ['git', 'checkout', f'pr-{pr_number}']
                subprocess.run(checkout_cmd, cwd=clone_dir, capture_output=True, timeout=60)
            
            logger.info(f"Repository cloned successfully to {clone_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Repository cloning failed: {e}")
            await self._report_status('ERROR', f'Repository cloning failed: {str(e)}')
            return False

    async def _initialize_agent(self) -> bool:
        """Initialize the specific agent"""
        try:
            await self._report_status('RUNNING', 'Initializing agent...', 20)
            
            # Import and initialize agent based on type
            if self.agent_type == 'iflow':
                from agents.iflow_agent import IFlowAgent
                self.agent = IFlowAgent()
            elif self.agent_type == 'claude':
                from agents.claude_agent import ClaudeAgent
                self.agent = ClaudeAgent()
            elif self.agent_type == 'gemini':
                from agents.gemini_agent import GeminiAgent
                self.agent = GeminiAgent()
            else:
                raise ValueError(f"Unknown agent type: {self.agent_type}")
            
            # Validate agent configuration
            if hasattr(self.agent, 'validate'):
                await self.agent.validate()
                
            logger.info(f"Agent {self.agent_type} initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Agent initialization failed: {e}")
            await self._report_status('ERROR', f'Agent initialization failed: {str(e)}')
            return False

    async def _execute_evaluation(self) -> Dict[str, Any]:
        """Execute the memory evaluation task"""
        try:
            await self._report_status('RUNNING', 'Executing evaluation...', 50)
            
            # Set up evaluation parameters with crash protection
            eval_params = {
                'pr_url': self.task_data['pr_url'],
                'max_files': min(self.task_data.get('max_files', 5), 5),  # Cap at 5
                'rubric': self.task_data.get('rubric', ['AR', 'TTL']),
                'workspace_dir': str(self.workspace_dir / 'repo'),
                'memory_limit_mb': self.max_memory_mb,
                'timeout_seconds': self.max_execution_time - 300  # Reserve 5 minutes for cleanup
            }
            
            # Execute agent-specific evaluation
            results = await self.agent.execute_evaluation(eval_params)
            
            # Save results to file
            results_file = self.results_dir / f'results_{self.task_id}.json'
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2)
                
            logger.info("Evaluation completed successfully")
            await self._report_status('RUNNING', 'Evaluation completed', 90)
            
            return results
            
        except Exception as e:
            logger.error(f"Evaluation execution failed: {e}")
            await self._report_status('ERROR', f'Evaluation failed: {str(e)}')
            raise

    async def run(self) -> bool:
        """Main execution flow"""
        try:
            logger.info(f"Starting {self.agent_type} agent for task {self.task_id}")
            
            # Step 1: Clone repository
            if not await self._clone_repository():
                return False
                
            # Step 2: Initialize agent
            if not await self._initialize_agent():
                return False
                
            # Step 3: Execute evaluation
            results = await self._execute_evaluation()
            
            # Step 4: Report completion
            await self._report_completion(True, results)
            
            logger.info(f"Task {self.task_id} completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            error_details = {
                'error': str(e),
                'traceback': traceback.format_exc(),
                'agent_type': self.agent_type,
                'task_id': self.task_id
            }
            await self._report_completion(False, {}, str(e))
            return False

def main():
    parser = argparse.ArgumentParser(description='Agent Runner')
    parser.add_argument('--agent', required=True, choices=['iflow', 'claude', 'gemini'])
    args = parser.parse_args()
    
    # Get task data from environment or file
    task_data_file = os.getenv('TASK_DATA_FILE', '/agent/task_data.json')
    try:
        with open(task_data_file, 'r') as f:
            task_data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Task data file not found: {task_data_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid task data JSON: {e}")
        sys.exit(1)
    
    # Initialize and run agent
    runner = AgentRunner(args.agent, task_data)
    
    # Run with asyncio
    try:
        success = asyncio.run(runner.run())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Agent runner interrupted")
        sys.exit(1)

if __name__ == "__main__":
    main()
