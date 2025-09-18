from dataclasses import dataclass
from typing import List, Optional
import json, os

@dataclass
class Change:
  path: str
  content: str

@dataclass
class GitUser:
  name: str
  email: str

@dataclass
class JobInput:
  jobId: str
  repo: str
  branch: str
  base: str
  task: str
  instructions: Optional[str]
  changes: List[Change]
  callbackUrl: str
  callbackSecret: str
  gitUser: GitUser
  githubToken: str

  @staticmethod
  def from_env() -> "JobInput":
    raw = os.environ.get("JOB_INPUT")
    if not raw:
      raise RuntimeError("Missing JOB_INPUT")
    data = json.loads(raw)
    return JobInput(
      jobId=data["jobId"],
      repo=data["repo"],
      branch=data.get("branch", "ci/agent"),
      base=data.get("base", "main"),
      task=data.get("task", "agent"),
      instructions=data.get("instructions"),
      changes=[Change(**c) for c in data.get("changes", [])],
      callbackUrl=data["callbackUrl"],
      callbackSecret=data["callbackSecret"],
      gitUser=GitUser(**data["gitUser"]),
      githubToken=data["githubToken"],
    )

