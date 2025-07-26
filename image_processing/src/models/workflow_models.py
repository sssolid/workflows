# ===== src/models/workflow_models.py =====
from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class WorkflowStep(BaseModel):
    """Individual workflow step."""
    step_id: str
    step_name: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowInstance(BaseModel):
    """Complete workflow instance."""
    workflow_id: str = Field(..., description="Unique workflow identifier")
    file_id: str = Field(..., description="File being processed")
    workflow_type: str = Field(..., description="Type of workflow")
    status: str = Field(default="running")
    steps: List[WorkflowStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def add_step(self, step_name: str, metadata: Optional[Dict[str, Any]] = None) -> WorkflowStep:
        """Add a new step to the workflow."""
        step = WorkflowStep(
            step_id=f"{self.workflow_id}_{len(self.steps)}",
            step_name=step_name,
            status="pending",
            metadata=metadata or {}
        )
        self.steps.append(step)
        self.updated_at = datetime.now()
        return step

    def start_step(self, step_name: str) -> Optional[WorkflowStep]:
        """Start a workflow step."""
        for step in self.steps:
            if step.step_name == step_name and step.status == "pending":
                step.status = "running"
                step.started_at = datetime.now()
                self.updated_at = datetime.now()
                return step
        return None

    def complete_step(self, step_name: str, success: bool = True, error: Optional[str] = None) -> None:
        """Mark a step as completed."""
        for step in self.steps:
            if step.step_name == step_name and step.status == "running":
                step.status = "completed" if success else "failed"
                step.completed_at = datetime.now()
                if error:
                    step.error_message = error
                break
        self.updated_at = datetime.now()

    def retry_step(self, step_name: str) -> bool:
        """Retry a failed step if retries are available."""
        for step in self.steps:
            if step.step_name == step_name and step.status == "failed":
                if step.retry_count < step.max_retries:
                    step.retry_count += 1
                    step.status = "pending"
                    step.error_message = None
                    self.updated_at = datetime.now()
                    return True
        return False

    @property
    def current_step(self) -> Optional[WorkflowStep]:
        """Get the currently running step."""
        for step in self.steps:
            if step.status == "running":
                return step
        return None

    @property
    def is_complete(self) -> bool:
        """Check if workflow is complete."""
        return all(step.status in ["completed", "skipped"] for step in self.steps)

    @property
    def has_failures(self) -> bool:
        """Check if workflow has any failed steps."""
        return any(step.status == "failed" for step in self.steps)


class WorkflowDefinition(BaseModel):
    """Workflow definition/template."""
    name: str
    description: str
    version: str = "1.0.0"
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    triggers: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def create_instance(self, file_id: str, workflow_id: Optional[str] = None) -> WorkflowInstance:
        """Create a workflow instance from this definition."""
        if not workflow_id:
            workflow_id = f"{self.name}_{file_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        instance = WorkflowInstance(
            workflow_id=workflow_id,
            file_id=file_id,
            workflow_type=self.name,
            metadata=self.metadata.copy()
        )

        # Add steps from definition
        for step_def in self.steps:
            step_name = step_def.get("name", "unknown_step")
            step_metadata = step_def.get("metadata", {})
            instance.add_step(step_name, step_metadata)

        return instance