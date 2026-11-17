"""Keep the Claude Code skill and plugin manifests in sync with the CLI and the package."""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path

import pytest

from audio_cleanup.cli import build_parser

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "audio-cleanup"
SKILL_MD = SKILL_DIR / "SKILL.md"


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md must start with a YAML frontmatter block"
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def _cli_options() -> set[str]:
    """Every long option of the CLI, global or of any sub-command."""
    parser = build_parser()
    parsers = [parser]
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            parsers.extend(action.choices.values())
    return {
        option
        for p in parsers
        for action in p._actions
        for option in action.option_strings
        if option.startswith("--")
    }


def _cli_commands() -> set[str]:
    for action in build_parser()._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    return set()


def test_skill_frontmatter() -> None:
    fields = _frontmatter(SKILL_MD.read_text(encoding="utf-8"))
    assert fields["name"] == SKILL_DIR.name
    assert 0 < len(fields["description"]) <= 1024


def test_skill_only_mentions_existing_options() -> None:
    body = SKILL_MD.read_text(encoding="utf-8")
    # Options of other tools the skill shows: `uv run --project`, `uv sync --extra`,
    # `uvx --python --from` and `winget --id`.
    external_options = {"--project", "--extra", "--python", "--from", "--id"}
    mentioned = set(re.findall(r"(?<![\w-])--[a-z][a-z-]+", body)) - external_options
    assert mentioned, "the option scan found nothing; the regex is probably broken"
    assert mentioned <= _cli_options(), f"unknown options: {sorted(mentioned - _cli_options())}"


@pytest.mark.parametrize("command", ["clean", "fix-chapters", "diagnose", "doctor"])
def test_skill_documents_every_command(command: str) -> None:
    assert command in _cli_commands()
    assert f"`{command}" in SKILL_MD.read_text(encoding="utf-8")


def test_plugin_manifests_match_package() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    marketplace = json.loads(
        (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    assert plugin["name"] == project["name"]
    assert plugin["version"] == project["version"]
    assert [p["name"] for p in marketplace["plugins"]] == [plugin["name"]]
