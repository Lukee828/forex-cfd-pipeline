from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Traffic-Cop Agent", version="0.1")


class GenerateReq(BaseModel):
    task: str = Field(..., description="Short spec/title")
    files_allowed: list[str] = Field(default=[], description="Paths allowed to edit")
    tests_to_run: list[str] = Field(default=["-q"], description="pytest args")
    dry_run: bool = False


def run(cmd: list[str]) -> tuple[int, str]:
    # Local-only policy: no subprocess; signal blocked status to caller.
    return 1, "blocked by local-only policy"
