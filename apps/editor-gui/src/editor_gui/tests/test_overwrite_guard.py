"""The save/export dialogs guard against silently replacing an existing file.

The portable file dialog does not confirm overwriting on macOS (it wraps AppleScript's
"choose file name"), so ``KnxGuiApp._maybe_overwrite_then`` adds the confirmation. These
tests drive that decision logic against a stub so no imgui app has to be constructed: an
existing target queues behind a prompt; a fresh path runs immediately; only a plain "Save
as" over the currently-open project (``save_in_place_ok``) skips the prompt, while New /
Import / Export targeting that same file still confirm (they replace it with new content).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

from editor_gui.main import KnxGuiApp


def _stub(project_path: Path | None) -> SimpleNamespace:
    return SimpleNamespace(
        _project_service=SimpleNamespace(path=project_path),
        _overwrite_queue=[],
    )


def _maybe_overwrite_then(
    stub: SimpleNamespace,
    path: str,
    action: Callable[[], None],
    *,
    save_in_place_ok: bool = False,
) -> None:
    KnxGuiApp._maybe_overwrite_then(  # type: ignore[arg-type]
        stub, path, action, save_in_place_ok=save_in_place_ok
    )


def test_new_path_runs_action_without_prompt(tmp_path: Path) -> None:
    stub = _stub(project_path=None)
    ran: list[str] = []
    dest = tmp_path / "new.xknx"
    _maybe_overwrite_then(stub, str(dest), lambda: ran.append("go"))
    assert ran == ["go"]
    assert stub._overwrite_queue == []


def test_existing_path_queues_behind_prompt(tmp_path: Path) -> None:
    stub = _stub(project_path=None)
    ran: list[str] = []
    dest = tmp_path / "existing.xknx"
    dest.write_text("data")
    _maybe_overwrite_then(stub, str(dest), lambda: ran.append("go"))
    assert ran == []  # action held until the user confirms
    assert [q[0] for q in stub._overwrite_queue] == [str(dest)]


def test_save_in_place_over_open_project_never_prompts(tmp_path: Path) -> None:
    dest = tmp_path / "open.xknx"
    dest.write_text("data")
    stub = _stub(project_path=dest)
    ran: list[str] = []
    _maybe_overwrite_then(
        stub, str(dest), lambda: ran.append("go"), save_in_place_ok=True
    )
    assert ran == ["go"]  # a plain save over the project's own file is not a loss
    assert stub._overwrite_queue == []


def test_new_or_import_over_open_project_still_prompts(tmp_path: Path) -> None:
    # New / Import replace the open project with different content, so even targeting its own
    # path must confirm: save_in_place_ok is left False for those flows.
    dest = tmp_path / "open.xknx"
    dest.write_text("data")
    stub = _stub(project_path=dest)
    ran: list[str] = []
    _maybe_overwrite_then(stub, str(dest), lambda: ran.append("go"))
    assert ran == []
    assert [q[0] for q in stub._overwrite_queue] == [str(dest)]


def test_two_requests_queue_without_dropping_the_first(tmp_path: Path) -> None:
    # A second dialog resolving while the first confirmation is pending must not clobber it.
    stub = _stub(project_path=None)
    first = tmp_path / "a.xknx"
    second = tmp_path / "b.xknx"
    first.write_text("data")
    second.write_text("data")
    ran: list[str] = []
    _maybe_overwrite_then(stub, str(first), lambda: ran.append("first"))
    _maybe_overwrite_then(stub, str(second), lambda: ran.append("second"))
    assert ran == []
    assert [q[0] for q in stub._overwrite_queue] == [str(first), str(second)]
