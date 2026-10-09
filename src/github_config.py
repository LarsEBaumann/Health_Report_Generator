"""Shared GitHub repository selection for the optional connector."""
import os
import re


def resolve_repository():
    primary = os.getenv("GITHUB_REPOSITORY", "").strip()

    if primary:
        parts = primary.split("/")
        if len(parts) != 2:
            raise ValueError("GITHUB_REPOSITORY must have the form owner/repo.")
        owner, repo = parts
    else:
        owner = os.getenv("GITHUB_OWNER", "LarsEBaumann").strip()
        repo = os.getenv("GITHUB_REPO", "Health_Report_Generator").strip()

    if (
        not re.fullmatch(r"[A-Za-z0-9-]+", owner)
        or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo)
        or repo in {".", ".."}
    ):
        raise ValueError(
            "Invalid GitHub repository configuration: "
            "provide non-empty owner/repo components without spaces or URLs."
        )

    return owner, repo
