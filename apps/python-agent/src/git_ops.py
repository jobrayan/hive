import os
import base64
import subprocess
from typing import List

def sh(cmd: str) -> None:
    subprocess.run(cmd, shell=True, check=True)

def setup_git_identity(name: str, email: str) -> None:
    sh(f'git config --global user.name "{name}"')
    sh(f'git config --global user.email "{email}"')

def clone_and_checkout(repo_url: str, token: str, branch: str, base: str) -> str:
    workdir = os.getcwd()
    if os.path.exists(os.path.join(workdir, "repo")):
        sh("rm -rf repo")
    used_header = False
    is_https = repo_url.startswith("http://") or repo_url.startswith("https://")
    if is_https:
        if token:
            host = "github.com"
            b64 = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("utf-8")
            sh(f'git -c http.extraheader="Authorization: Basic {b64}" clone {repo_url} repo')
            used_header = True
        else:
            sh(f'git clone {repo_url} repo')
    else:
        os.environ.setdefault("GIT_SSH_COMMAND", "ssh -o StrictHostKeyChecking=accept-new")
        sh(f'git clone {repo_url} repo')
    os.chdir(os.path.join(workdir, "repo"))
    if is_https and used_header:
        sh(f'git config --local http.https://github.com/.extraheader "Authorization: Basic {b64}"')
    try:
        sh(f"git fetch origin {base}")
    except subprocess.CalledProcessError:
        sh("git fetch --all")
    sh(f"git checkout -B {branch} origin/{base} || git checkout -B {branch}")
    return os.getcwd()

def apply_changes(changes: List[dict], repo_root: str) -> int:
    import pathlib
    count = 0
    for c in changes:
        dest = pathlib.Path(repo_root) / c["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(c["content"], encoding="utf-8")
        sh(f'git add "{c["path"]}"')
        count += 1
    return count

def commit_and_push(branch: str) -> None:
    try:
        sh('git commit -m "ci(agent): automated changes"')
    except subprocess.CalledProcessError:
        pass
    sh(f"git push -u origin {branch}")

def has_diff_against_base(base: str, branch: str) -> bool:
    try:
        subprocess.run(f"git fetch origin {base}", shell=True, check=True)
    except subprocess.CalledProcessError:
        return False
    res = subprocess.run(f"git diff --quiet origin/{base}..{branch}", shell=True)
    if res.returncode == 0:
        return False
    if res.returncode == 1:
        return True
    return False

def ensure_marker_commit(marker_path: str, message: str) -> bool:
    import pathlib
    p = pathlib.Path(marker_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text("# Codimir Agent Marker\n", encoding="utf-8")
    try:
        sh("git add --all")
        subprocess.run(f"git commit -m \"{message}\" --allow-empty", shell=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False

