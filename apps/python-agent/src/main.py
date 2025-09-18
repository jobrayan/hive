"""
Python Agent Worker entrypoint (HTTP mode).
Accepts POST /run with a JobInput-like payload and reports progress/done to callbackUrl.
"""
import os
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from .job_input import JobInput, Change, GitUser
from .logging_utils import progress, done
from .git_ops import (
    setup_git_identity,
    clone_and_checkout,
    apply_changes,
    commit_and_push,
    has_diff_against_base,
    ensure_marker_commit,
)
from .gemini_agent import plan_edits
from .github_api import create_pr, comment_pr, ensure_label, add_labels, find_open_pr_by_head, update_pr_base

def sh(cmd: str) -> None:
    import subprocess
    subprocess.run(cmd, shell=True, check=True)

def run_job(ji: JobInput, run_id: str) -> None:
    setup_git_identity(ji.gitUser.name, ji.gitUser.email)
    progress(ji.callbackUrl, ji.callbackSecret, ji.jobId, "Cloning repository...", run_id=run_id)
    repo_root = clone_and_checkout(ji.repo, ji.githubToken, ji.branch, ji.base)

    changed = apply_changes([c.__dict__ for c in ji.changes], repo_root)
    if changed:
        progress(ji.callbackUrl, ji.callbackSecret, ji.jobId, f"Applied {changed} direct file changes.", run_id=run_id)

    if ji.task == "agent" and ji.instructions:
        plan = plan_edits(ji.instructions, repo_root)
        if plan:
            progress(ji.callbackUrl, ji.callbackSecret, ji.jobId, "Plan generated.", logs=plan, run_id=run_id)

    progress(ji.callbackUrl, ji.callbackSecret, ji.jobId, f"Running task: {ji.task}", run_id=run_id)
    try:
        repo_has_node = os.path.exists("package.json") or os.path.exists("pnpm-lock.yaml") or os.path.exists("yarn.lock") or os.path.exists("package-lock.json")
        if repo_has_node:
            sh("corepack enable && pnpm i --frozen-lockfile")
            is_workspace = os.path.exists("pnpm-workspace.yaml")
            ws_flag = "-w " if is_workspace else ""
            if ji.task == "build":
                sh(f"pnpm {ws_flag}build")
            elif ji.task == "lint":
                sh(f"pnpm {ws_flag}lint -f compact || true")
            elif ji.task == "test":
                sh(f"pnpm {ws_flag}test || true")
    except Exception as e:
        done(ji.callbackUrl, ji.callbackSecret, ji.jobId, False, f"Task failed: {e}", run_id=run_id)
        return

    try:
        if not has_diff_against_base(ji.base, ji.branch):
            if ensure_marker_commit(".codimir/agent-marker.md", "ci(agent): marker to open PR"):
                progress(ji.callbackUrl, ji.callbackSecret, ji.jobId, "Added marker commit to ensure PR can be created.", run_id=run_id)
    except Exception:
        pass

    commit_and_push(ji.branch)

    pr_num = create_pr(ji.repo, ji.githubToken, ji.branch, base=ji.base, title="Codimir Agent PR", body="Automated changes by Codimir Agent")
    if not pr_num:
        existing = find_open_pr_by_head(ji.repo, ji.githubToken, ji.branch)
        if existing:
            try:
                update_pr_base(ji.repo, ji.githubToken, existing, ji.base)
            except Exception:
                pass
            pr_num = existing
    if pr_num:
        summary = f"Agent task: **{ji.task}**\n\nBranch: `{ji.branch}`\n"
        if ji.instructions:
            summary += f"\n**Instructions**:\n```\n{ji.instructions}\n```"
        comment_pr(ji.repo, ji.githubToken, pr_num, summary)
        label = os.environ.get("CODIMIR_LABEL", "codimir")
        try:
            ensure_label(ji.repo, ji.githubToken, label, color="0E8A16", description="Changes created by Codimir Agent")
            add_labels(ji.repo, ji.githubToken, pr_num, [label])
        except Exception:
            pass

    done(ji.callbackUrl, ji.callbackSecret, ji.jobId, True, f"Pushed {ji.branch}" + (f", PR #{pr_num}" if pr_num else ""), run_id=run_id)

def _parse_job_input_from_json(data: dict) -> JobInput:
    return JobInput(
        jobId=str(data.get("jobId", "")),
        repo=str(data["repo"]),
        branch=str(data.get("branch", "ci/agent")),
        base=str(data.get("base", "development")),
        task=str(data.get("task", "agent")),
        instructions=data.get("instructions"),
        changes=[Change(path=c["path"], content=c["content"]) for c in data.get("changes", [])],
        callbackUrl=str(data["callbackUrl"]),
        callbackSecret=str(data["callbackSecret"]),
        gitUser=GitUser(name=str(data["gitUser"]["name"]), email=str(data["gitUser"]["email"])),
        githubToken=str(data.get("githubToken", "")),
    )

class RunHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # type: ignore[override]
        if self.path != "/run":
            self.send_response(404); self.end_headers(); self.wfile.write(b"Not Found"); return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            data = json.loads(raw.decode("utf-8"))
            ji = _parse_job_input_from_json(data)
        except Exception as e:
            self.send_response(400); self.end_headers(); self.wfile.write(f"Bad Request: {e}".encode("utf-8")); return
        run_id = os.environ.get("FLY_MACHINE_ID") or "local"
        from threading import Thread
        def _run():
            try:
                run_job(ji, run_id)
            except Exception as ex:
                try:
                    done(ji.callbackUrl, ji.callbackSecret, ji.jobId, False, str(ex), run_id=run_id)
                except Exception:
                    pass
        Thread(target=_run, daemon=True).start()
        self.send_response(202); self.end_headers(); self.wfile.write(b"{\"ok\":true}")

    def do_GET(self):  # type: ignore[override]
        if self.path in ("/health", "/"):
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok"); return
        self.send_response(404); self.end_headers(); self.wfile.write(b"Not Found")

def main() -> None:
    raw = os.environ.get("JOB_INPUT")
    run_id = os.environ.get("FLY_MACHINE_ID") or "local"
    if raw:
        ji = JobInput.from_env(); run_job(ji, run_id); return
    host = os.environ.get("WORKER_HOST", "0.0.0.0")
    port = int(os.environ.get("WORKER_PORT", "8088"))
    httpd = HTTPServer((host, port), RunHandler)
    print(f"[worker] Listening on http://{host}:{port} (POST /run)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            raw = os.environ.get("JOB_INPUT")
            if raw:
                ji = JobInput.from_env(); run_id = os.environ.get("FLY_MACHINE_ID") or "local"
                done(ji.callbackUrl, ji.callbackSecret, ji.jobId, False, str(e), run_id=run_id)
        finally:
            raise

