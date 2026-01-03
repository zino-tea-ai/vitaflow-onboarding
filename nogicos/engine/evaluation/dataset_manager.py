# -*- coding: utf-8 -*-
"""
NogicOS Dataset Manager for LangSmith

Provides tools for:
- Creating datasets from production runs
- Adding manual test cases
- Managing evaluation datasets

Usage:
    from engine.evaluation.dataset_manager import DatasetManager
    
    manager = DatasetManager()
    
    # Create from runs
    dataset = manager.create_from_runs(
        project_name="nogicos",
        dataset_name="nogicos_golden_set",
        limit=50,
    )
    
    # Add manual example
    manager.add_example(
        dataset_name="nogicos_golden_set",
        inputs={"task": "列出当前目录文件"},
        outputs={"response": "...", "success": True},
    )
"""

import os
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from engine.observability import get_logger
logger = get_logger("dataset_manager")

# LangSmith imports
try:
    from langsmith import Client
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False
    Client = None
    logger.warning("[DatasetManager] LangSmith not available")

# Config
try:
    from config import LANGSMITH_API_KEY, LANGSMITH_PROJECT
except ImportError:
    LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
    LANGSMITH_PROJECT = "nogicos"


@dataclass
class DatasetInfo:
    """Dataset metadata"""
    id: str
    name: str
    description: str
    example_count: int
    created_at: datetime


class DatasetManager:
    """
    Manages LangSmith datasets for NogicOS evaluation.
    
    Features:
    - Create datasets from production runs
    - Add manual test examples
    - List and query datasets
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize DatasetManager.
        
        Args:
            api_key: LangSmith API key (uses config if not provided)
        """
        if not LANGSMITH_AVAILABLE:
            raise ImportError("LangSmith not installed. Run: pip install langsmith")
        
        self.api_key = api_key or LANGSMITH_API_KEY
        if not self.api_key:
            raise ValueError("LangSmith API key required")
        
        self.client = Client(api_key=self.api_key)
        self.project_name = LANGSMITH_PROJECT
        
        logger.info(f"[DatasetManager] Initialized for project: {self.project_name}")
    
    def create_from_runs(
        self,
        dataset_name: str,
        description: Optional[str] = None,
        project_name: Optional[str] = None,
        limit: int = 50,
        only_successful: bool = True,
        min_latency_ms: Optional[float] = None,
        max_latency_ms: Optional[float] = None,
    ) -> DatasetInfo:
        """
        Create a dataset from existing LangSmith runs.
        
        Args:
            dataset_name: Name for the new dataset
            description: Dataset description
            project_name: Source project (defaults to nogicos)
            limit: Maximum number of runs to include
            only_successful: Only include successful runs
            min_latency_ms: Minimum latency filter
            max_latency_ms: Maximum latency filter
            
        Returns:
            DatasetInfo with the created dataset details
        """
        project = project_name or self.project_name
        
        logger.info(f"Creating dataset '{dataset_name}' from project '{project}'...")
        
        # List runs from project
        runs = list(self.client.list_runs(
            project_name=project,
            execution_order=1,  # Only parent runs
            error=not only_successful if only_successful else None,
            limit=limit,
        ))
        
        logger.info(f"Found {len(runs)} runs")
        
        # Filter by latency if specified
        if min_latency_ms or max_latency_ms:
            filtered_runs = []
            for run in runs:
                if run.end_time and run.start_time:
                    latency_ms = (run.end_time - run.start_time).total_seconds() * 1000
                    if min_latency_ms and latency_ms < min_latency_ms:
                        continue
                    if max_latency_ms and latency_ms > max_latency_ms:
                        continue
                filtered_runs.append(run)
            runs = filtered_runs
            logger.info(f"After latency filter: {len(runs)} runs")
        
        # Create dataset
        dataset = self.client.create_dataset(
            dataset_name=dataset_name,
            description=description or f"Created from {project} runs on {datetime.now().isoformat()}",
        )
        
        # Add examples
        example_count = 0
        for run in runs:
            try:
                self.client.create_example(
                    inputs=run.inputs or {},
                    outputs=run.outputs or {},
                    dataset_id=dataset.id,
                    metadata={
                        "source_run_id": str(run.id),
                        "source_project": project,
                        "latency_ms": (run.end_time - run.start_time).total_seconds() * 1000 if run.end_time and run.start_time else None,
                    },
                )
                example_count += 1
            except Exception as e:
                logger.warning(f"Failed to add example from run {run.id}: {e}")
        
        logger.info(f"Created dataset '{dataset_name}' with {example_count} examples")
        
        return DatasetInfo(
            id=str(dataset.id),
            name=dataset_name,
            description=description or "",
            example_count=example_count,
            created_at=datetime.now(),
        )
    
    def add_example(
        self,
        dataset_name: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Add a manual example to a dataset.
        
        Args:
            dataset_name: Name of the target dataset
            inputs: Example inputs (e.g., {"task": "..."})
            outputs: Expected outputs (e.g., {"response": "...", "success": True})
            metadata: Additional metadata
            
        Returns:
            Example ID
        """
        # Get or create dataset
        try:
            datasets = list(self.client.list_datasets(dataset_name=dataset_name))
            if datasets:
                dataset = datasets[0]
            else:
                dataset = self.client.create_dataset(
                    dataset_name=dataset_name,
                    description="NogicOS evaluation dataset",
                )
        except Exception as e:
            logger.error(f"Failed to get/create dataset: {e}")
            raise
        
        # Create example
        example = self.client.create_example(
            inputs=inputs,
            outputs=outputs,
            dataset_id=dataset.id,
            metadata=metadata or {"source": "manual"},
        )
        
        logger.info(f"Added example to dataset '{dataset_name}'")
        
        return str(example.id)
    
    def list_datasets(self) -> List[DatasetInfo]:
        """List all datasets."""
        datasets = list(self.client.list_datasets())
        
        return [
            DatasetInfo(
                id=str(ds.id),
                name=ds.name,
                description=ds.description or "",
                example_count=ds.example_count or 0,
                created_at=ds.created_at,
            )
            for ds in datasets
        ]
    
    def get_dataset_examples(
        self,
        dataset_name: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get examples from a dataset."""
        datasets = list(self.client.list_datasets(dataset_name=dataset_name))
        if not datasets:
            return []
        
        examples = list(self.client.list_examples(
            dataset_id=datasets[0].id,
            limit=limit,
        ))
        
        return [
            {
                "id": str(ex.id),
                "inputs": ex.inputs,
                "outputs": ex.outputs,
                "metadata": ex.metadata,
            }
            for ex in examples
        ]
    
    def delete_dataset(self, dataset_name: str) -> bool:
        """Delete a dataset."""
        try:
            datasets = list(self.client.list_datasets(dataset_name=dataset_name))
            if datasets:
                self.client.delete_dataset(dataset_id=datasets[0].id)
                logger.info(f"Deleted dataset '{dataset_name}'")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete dataset: {e}")
            return False


# ===========================================
# Convenience Functions
# ===========================================

def create_dataset_from_runs(
    dataset_name: str,
    project_name: str = "nogicos",
    limit: int = 50,
    **kwargs,
) -> DatasetInfo:
    """
    Convenience function to create a dataset from runs.
    
    Args:
        dataset_name: Name for the new dataset
        project_name: Source project
        limit: Maximum runs to include
        **kwargs: Additional filters
        
    Returns:
        DatasetInfo
    """
    manager = DatasetManager()
    return manager.create_from_runs(
        dataset_name=dataset_name,
        project_name=project_name,
        limit=limit,
        **kwargs,
    )


def add_example_to_dataset(
    dataset_name: str,
    task: str,
    expected_response: str,
    expected_success: bool = True,
    expected_tools: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Add a test case to a dataset.
    
    Args:
        dataset_name: Target dataset name
        task: Input task
        expected_response: Expected response (can be partial match)
        expected_success: Whether task should succeed
        expected_tools: List of expected tool names
        metadata: Additional metadata
        
    Returns:
        Example ID
    """
    manager = DatasetManager()
    
    inputs = {"task": task}
    outputs = {
        "success": expected_success,
        "response": expected_response,
    }
    if expected_tools:
        outputs["expected_tools"] = expected_tools
    
    return manager.add_example(
        dataset_name=dataset_name,
        inputs=inputs,
        outputs=outputs,
        metadata=metadata,
    )


# ===========================================
# Golden Dataset Templates
# ===========================================

GOLDEN_EXAMPLES = [
    # File operations
    {
        "task": "列出当前目录的文件",
        "expected_success": True,
        "expected_tools": ["list_directory"],
        "response_contains": ["文件", "目录"],
    },
    {
        "task": "帮我看看桌面有什么",
        "expected_success": True,
        "expected_tools": ["list_directory"],
        "response_contains": ["桌面", "Desktop"],
    },
    {
        "task": "创建一个名为 test_folder 的文件夹",
        "expected_success": True,
        "expected_tools": ["create_directory"],
        "response_contains": ["创建", "test_folder"],
    },
    # Browser operations
    {
        "task": "打开 google.com",
        "expected_success": True,
        "expected_tools": ["browser_navigate"],
        "response_contains": ["google", "打开"],
    },
    # Simple chat (no tools)
    {
        "task": "你好",
        "expected_success": True,
        "expected_tools": [],
        "response_contains": ["你好", "有什么"],
    },
]


def create_golden_dataset(dataset_name: str = "nogicos_golden") -> DatasetInfo:
    """
    Create a golden test dataset with predefined examples.
    
    Args:
        dataset_name: Name for the dataset
        
    Returns:
        DatasetInfo
    """
    manager = DatasetManager()
    
    # Create dataset
    try:
        datasets = list(manager.client.list_datasets(dataset_name=dataset_name))
        if datasets:
            # Delete existing
            manager.delete_dataset(dataset_name)
    except Exception:
        pass
    
    dataset = manager.client.create_dataset(
        dataset_name=dataset_name,
        description="NogicOS golden test set - curated examples for evaluation",
    )
    
    # Add examples
    for ex in GOLDEN_EXAMPLES:
        inputs = {"task": ex["task"]}
        outputs = {
            "success": ex["expected_success"],
            "expected_tools": ex.get("expected_tools", []),
            "response_contains": ex.get("response_contains", []),
        }
        
        manager.client.create_example(
            inputs=inputs,
            outputs=outputs,
            dataset_id=dataset.id,
            metadata={"source": "golden_template"},
        )
    
    logger.info(f"Created golden dataset '{dataset_name}' with {len(GOLDEN_EXAMPLES)} examples")
    
    return DatasetInfo(
        id=str(dataset.id),
        name=dataset_name,
        description="Golden test set",
        example_count=len(GOLDEN_EXAMPLES),
        created_at=datetime.now(),
    )

