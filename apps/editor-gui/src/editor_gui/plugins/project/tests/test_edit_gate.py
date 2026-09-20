"""Read-only pre-flight self-test gate: what counts as "edited since open".

Regression: after programming a device, the app records its commissioning state
(``SetDeviceCommissioning``: last-download timestamp + loaded ticks) into the same event store as
real edits. That bookkeeping never changes the generated image, so it must NOT flip
``edited_since_open()`` and lock the user out of the read-only self-test on a device they only
(re-)programmed. A genuine configuration edit must still count.
"""

from __future__ import annotations

from pathlib import Path

from editor_gui.plugins.base import Logger
from editor_gui.plugins.catalog.service import CatalogService
from editor_gui.plugins.logger.service import LogService
from editor_gui.plugins.project.service import ProjectService


def _project(tmp_path: Path) -> ProjectService:
    proj = ProjectService(CatalogService(tmp_path / "c.xknxcatalog"))
    proj.set_logger(Logger(LogService(), "project"))
    return proj


def test_commissioning_record_does_not_count_as_edit(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    p = tmp_path / "p.xknx"
    proj.new(p)
    proj.close()
    proj.open(p)  # baseline captured here, the way the app does on open
    assert not proj.edited_since_open()

    # Recording commissioning after a program (device id need not exist: apply is a no-op, the
    # event is still appended to history) must leave the project "unedited" for the gate.
    proj.set_device_commissioning(
        999, last_download="2026-01-01T00:00:00.0Z", parameters_loaded=True
    )
    assert not proj.edited_since_open()

    # A real configuration edit still trips the gate.
    proj.create_group_address(address="1/2/3", name="x")
    assert proj.edited_since_open()
