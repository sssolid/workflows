# ===== src/models/workflow_models.py =====
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


class WorkflowInstance(BaseModel):
    """Complete workflow instance."""
    workflow_id: str = Field(..., description="Unique workflow identifier")
    file_id: str = Field(..., description="File being processed")
    workflow_type: str = Field(..., description="Type of workflow")
    status: str = Field(default="running")
    steps: List[WorkflowStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def add_step(self, step_name: str) -> WorkflowStep:
        """Add a new step to the workflow."""
        step = WorkflowStep(
            step_id=f"{self.workflow_id}_{len(self.steps)}",
            step_name=step_name,
            status="pending"
        )
        self.steps.append(step)
        self.updated_at = datetime.now()
        return step

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