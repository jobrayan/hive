import requests
from typing import List

def _gh_headers(token: str):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

def create_pr(repo: str, token: str, head: str, base: str, title: str, body: str):
    if repo.startswith("https://github.com/"):
        repo = repo.replace("https://github.com/", "")
    url = f"https://api.github.com/repos/{repo}/pulls"
    r = requests.post(url, headers=_gh_headers(token), json={
        "title": title,
        "body": body,
        "head": head,
        "base": base,
    }, timeout=30)
    if r.status_code == 201:
        return r.json().get("number")
    return None

def comment_pr(repo: str, token: str, pr_number: int, body: str):
    if repo.startswith("https://github.com/"):
        repo = repo.replace("https://github.com/", "")
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    requests.post(url, headers=_gh_headers(token), json={"body": body}, timeout=30)

def ensure_label(repo: str, token: str, name: str, color: str = "0E8A16", description: str = ""):
    if repo.startswith("https://github.com/"):
        repo = repo.replace("https://github.com/", "")
    url = f"https://api.github.com/repos/{repo}/labels"
    r = requests.post(url, headers=_gh_headers(token), json={
        "name": name,
        "color": color,
        "description": description,
    }, timeout=30)
    if r.status_code in (200, 201, 422):
        return True
    return False

def add_labels(repo: str, token: str, pr_number: int, labels: List[str]):
    if repo.startswith("https://github.com/"):
        repo = repo.replace("https://github.com/", "")
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/labels"
    requests.post(url, headers=_gh_headers(token), json={"labels": labels}, timeout=30)

def find_open_pr_by_head(repo: str, token: str, head: str):
    if repo.startswith("https://github.com/"):
        repo = repo.replace("https://github.com/", "")
    url = f"https://api.github.com/repos/{repo}/pulls?state=open&head={repo.split('/')[0]}:{head}"
    r = requests.get(url, headers=_gh_headers(token), timeout=30)
    if r.status_code == 200:
        data = r.json()
        if data:
            return data[0]["number"]
    return None

def update_pr_base(repo: str, token: str, pr_number: int, base: str):
    if repo.startswith("https://github.com/"):
        repo = repo.replace("https://github.com/", "")
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    requests.patch(url, headers=_gh_headers(token), json={"base": base}, timeout=30)

