"""把简报发布为可公开访问的网页链接。"""

from __future__ import annotations

import subprocess
import os
from pathlib import Path
from typing import Dict, Optional


def _run(cmd, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _check(cmd, cwd: Path, action: str) -> str:
    result = _run(cmd, cwd)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"{action}失败：{detail}")
    return result.stdout.strip()


def _ensure_gh_ready() -> str:
    result = _run(["gh", "auth", "status"], Path.cwd())
    if result.returncode != 0:
        raise RuntimeError("gh 未登录，请先运行 gh auth login。")
    return ""


def _resolve_owner(cfg: Dict) -> str:
    """从配置或 Actions 环境推断仓库所有者，避免依赖 gh api user。"""
    repo = str(cfg.get("GitHub仓库") or "").strip().lstrip("/")
    if "/" in repo:
        return repo.split("/", 1)[0]
    env_repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if "/" in env_repo:
        return env_repo.split("/", 1)[0]
    actor = os.environ.get("GITHUB_ACTOR", "").strip()
    if actor:
        return actor
    return _check(["gh", "api", "user", "--jq", ".login"], Path.cwd(), "获取 GitHub 用户名").strip()


def _pages_url(cfg: Dict, owner: str, repo: str) -> str:
    base = str(cfg.get("GitHub页面基础地址") or "").strip().rstrip("/")
    if base:
        return base
    repo_name = repo.split("/", 1)[1] if "/" in repo else repo
    return f"https://{owner}.github.io/{repo_name}/"


def _find_repo_root(start: Path) -> Path:
    """从给定目录向上查找已存在的 git 仓库根。"""
    current = start.resolve()
    while True:
        if current.joinpath(".git").exists():
            return current
        if current.parent == current:
            raise RuntimeError("未找到 git 仓库，请先初始化仓库。")
        current = current.parent


def publish_github(
    html_path: Path,
    project_root: Path,
    cfg: Dict,
    target_date,
) -> str:
    """发布 docs/index.html 到 GitHub Pages，返回网页地址。"""
    _ensure_gh_ready()
    owner = _resolve_owner(cfg)
    repo = str(cfg.get("GitHub仓库") or "stock-daily-report").strip().lstrip("/")
    if "/" not in repo:
        repo = f"{owner}/{repo}"

    try:
        repo_root = _find_repo_root(html_path.parent)
    except RuntimeError:
        _check(["git", "init", "-b", "main"], project_root, "初始化 git 仓库")
        repo_root = project_root

    _check(["git", "add", "-A", str(html_path)], repo_root, "暂存报告文件")

    commit_message = f"docs: 更新 {target_date.isoformat()} 股市简报"
    commit_result = _run(
        [
            "git", "-c", "user.name=stock-daily-report-bot",
            "-c", "user.email=stock-daily-report-bot@users.noreply.github.com",
            "commit", "-m", commit_message,
        ],
        repo_root,
    )
    commit_output = (commit_result.stdout or "") + (commit_result.stderr or "")
    if commit_result.returncode != 0 and "nothing to commit" not in commit_output:
        raise RuntimeError(f"提交报告失败：{commit_output.strip()}")

    remote = _run(["git", "remote", "get-url", "origin"], repo_root)
    if remote.returncode != 0:
        _check(
            ["gh", "repo", "create", repo, "--public", "--source=.", "--remote=origin", "--push"],
            repo_root,
            "创建 GitHub 仓库",
        )
    else:
        _check(["git", "push", "-u", "origin", "main"], repo_root, "推送报告")

    pages = _run(["gh", "api", f"repos/{repo}/pages", "--jq", ".html_url"], repo_root)
    if pages.returncode != 0:
        return _pages_url(cfg, owner, repo)
    return pages.stdout.strip()


def publish_local(html_path: Path, project_root: Path) -> str:
    """仅生成本地文件，供测试或无公网环境使用。"""
    site_dir = project_root / "site"
    site_dir.mkdir(parents=True, exist_ok=True)
    target = site_dir / "index.html"
    target.write_text(html_path.read_text(encoding="utf-8"), encoding="utf-8")
    return str(target)


def resolve_publish_url(cfg: Dict, html_path: Path, project_root: Path, target_date) -> Optional[str]:
    """按配置发布文档并返回公开链接。"""
    mode = str(cfg.get("发布方式") or "github").lower()
    if mode == "github":
        return publish_github(html_path, project_root, cfg, target_date)
    if mode == "local":
        return publish_local(html_path, project_root)
    return None
