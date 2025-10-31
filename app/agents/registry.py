"""Agent registry and plugin discovery system."""

import logging
from typing import Dict, List, Optional, Type

from app.domain.entities import AgentName
from app.agents.base import AgentAdapter, AgentMetadata, AgentNotFoundError
from app.config import settings

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Registry for managing AI agent adapters."""
    
    def __init__(self):
        self._agents: Dict[AgentName, Type[AgentAdapter]] = {}
        self._metadata: Dict[AgentName, AgentMetadata] = {}
        self._instances: Dict[AgentName, AgentAdapter] = {}
    
    def register_agent(
        self,
        agent_class: Type[AgentAdapter],
        metadata: AgentMetadata,
        force: bool = False
    ) -> None:
        """Register an agent adapter class."""
        agent_name = metadata.name
        
        if agent_name in self._agents and not force:
            logger.warning(f"Agent {agent_name.value} already registered, skipping")
            return
        
        self._agents[agent_name] = agent_class
        self._metadata[agent_name] = metadata
        
        logger.info(f"Registered agent: {agent_name.value}")
    
    def unregister_agent(self, agent_name: AgentName) -> None:
        """Unregister an agent adapter."""
        if agent_name in self._agents:
            del self._agents[agent_name]
            del self._metadata[agent_name]
            
            # Clean up instance if exists
            if agent_name in self._instances:
                del self._instances[agent_name]
            
            logger.info(f"Unregistered agent: {agent_name.value}")
    
    def get_agent(self, agent_name: AgentName) -> AgentAdapter:
        """Get agent adapter instance (singleton pattern)."""
        if agent_name not in self._agents:
            raise AgentNotFoundError(
                agent_name.value, 
                f"Agent {agent_name.value} not registered"
            )
        
        # Return cached instance if exists
        if agent_name in self._instances:
            return self._instances[agent_name]
        
        # Create new instance
        agent_class = self._agents[agent_name]
        try:
            instance = agent_class()
            
            # Validate installation
            if not instance.validate_installation():
                raise AgentNotFoundError(
                    agent_name.value,
                    f"Agent {agent_name.value} installation validation failed"
                )
            
            self._instances[agent_name] = instance
            logger.info(f"Created agent instance: {agent_name.value}")
            return instance
            
        except Exception as e:
            logger.error(f"Failed to create agent {agent_name.value}: {e}")
            raise AgentNotFoundError(
                agent_name.value, 
                f"Failed to create agent instance: {e}"
            )
    
    def get_available_agents(self) -> List[AgentName]:
        """Get list of available (registered and validated) agents."""
        available = []
        
        for agent_name in self._agents:
            try:
                agent = self.get_agent(agent_name)
                if agent.validate_installation():
                    available.append(agent_name)
            except Exception as e:
                logger.warning(f"Agent {agent_name.value} not available: {e}")
        
        return available
    
    def get_agent_metadata(self, agent_name: AgentName) -> Optional[AgentMetadata]:
        """Get agent metadata."""
        return self._metadata.get(agent_name)
    
    def get_all_metadata(self) -> Dict[AgentName, AgentMetadata]:
        """Get metadata for all registered agents."""
        return self._metadata.copy()
    
    def validate_agents(self, agent_names: List[AgentName]) -> Dict[AgentName, bool]:
        """Validate multiple agents and return validation results."""
        results = {}
        
        for agent_name in agent_names:
            try:
                agent = self.get_agent(agent_name)
                results[agent_name] = agent.validate_installation()
            except Exception as e:
                logger.error(f"Validation failed for {agent_name.value}: {e}")
                results[agent_name] = False
        
        return results
    
    def auto_discover_agents(self) -> None:
        """Auto-discover and register agent adapters."""
        logger.info("Starting agent auto-discovery...")
        
        # Import agent implementations
        try:
            from app.agents.iflow_agent import IFlowAgent, IFLOW_METADATA
            self.register_agent(IFlowAgent, IFLOW_METADATA)
        except ImportError as e:
            logger.warning(f"Failed to import iFlow agent: {e}")
        
        try:
            from app.agents.claude_agent import ClaudeAgent, CLAUDE_METADATA
            self.register_agent(ClaudeAgent, CLAUDE_METADATA)
        except ImportError as e:
            logger.warning(f"Failed to import Claude agent: {e}")
        
        try:
            from app.agents.gemini_agent import GeminiAgent, GEMINI_METADATA
            self.register_agent(GeminiAgent, GEMINI_METADATA)
        except ImportError as e:
            logger.warning(f"Failed to import Gemini agent: {e}")
        
        available = self.get_available_agents()
        logger.info(f"Auto-discovery complete. Available agents: {[a.value for a in available]}")
    
    def health_check(self) -> Dict[str, Dict[str, any]]:
        """Perform health check on all registered agents."""
        health_data = {}
        
        for agent_name, agent_class in self._agents.items():
            agent_health = {
                "registered": True,
                "available": False,
                "version_info": {},
                "error": None,
            }
            
            try:
                agent = self.get_agent(agent_name)
                agent_health["available"] = agent.validate_installation()
                if agent_health["available"]:
                    agent_health["version_info"] = agent.get_version_info()
                
            except Exception as e:
                agent_health["error"] = str(e)
            
            health_data[agent_name.value] = agent_health
        
        return health_data


# Global registry instance
registry = AgentRegistry()


def get_agent_registry() -> AgentRegistry:
    """Get the global agent registry instance."""
    return registry


def register_agent(
    agent_class: Type[AgentAdapter], 
    metadata: AgentMetadata,
    force: bool = False
) -> None:
    """Convenience function to register an agent."""
    registry.register_agent(agent_class, metadata, force)


def get_agent(agent_name: AgentName) -> AgentAdapter:
    """Convenience function to get an agent."""
    return registry.get_agent(agent_name)


def validate_agent_list(agent_names: List[AgentName]) -> bool:
    """Validate that all agents in the list are available."""
    if not agent_names:
        return False
    
    validation_results = registry.validate_agents(agent_names)
    return all(validation_results.values())


def initialize_agent_registry() -> None:
    """Initialize the agent registry with auto-discovery."""
    registry.auto_discover_agents()
    
    # Log available agents
    available = registry.get_available_agents()
    if available:
        logger.info(f"Initialized agent registry with agents: {[a.value for a in available]}")
    else:
        logger.warning("No agents are available after initialization")
