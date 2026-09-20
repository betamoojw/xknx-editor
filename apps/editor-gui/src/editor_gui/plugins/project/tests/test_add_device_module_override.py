"""Regression: adding a module product with a module-scoped parameter override must persist the
com-object set the override *produces*, not the raw application default.

A module-scoped override (``…_M-100_MI-1_P-149_R-142``) only routes into its module scope once that
scope has been materialized. ``add_device`` used to build the fresh device from
``parameter_instance_refs`` alone, so the override was silently ignored and the *default* channel
objects (here ``…_M-100_MI-1_O-2-0_R-1`` / ``…_O-2-1_R-2``) were persisted. On reload,
``_build_device`` supplies the module instances too, so the override then takes effect and the UI
re-instantiates that channel under a different ref (``…_O-2-0_R-173``); the stale persisted refs no
longer exist and the whole M-100 channel was pruned from the visible set -> its group addresses and
links could never resolve. This drove the recover feature to drop module channels.
"""

from __future__ import annotations

from pathlib import Path

from editor_gui.plugins.base import Logger
from editor_gui.plugins.catalog.service import CatalogService
from editor_gui.plugins.logger.service import LogService
from editor_gui.plugins.project.service import ProjectService

_APP_ID = "M-0008_A-7072-21-5CC3-O000A"


def _fixture() -> Path:
    p = Path(__file__).resolve()
    for parent in p.parents:
        cand = (
            parent
            / "packages"
            / "prod"
            / "tests"
            / "fixtures"
            / "gira_2gang_button_interface.knxprod"
        )
        if cand.exists():
            return cand
    raise FileNotFoundError("gira_2gang_button_interface.knxprod not found")


def _project(tmp_path: Path) -> tuple[ProjectService, CatalogService]:
    cat = CatalogService(tmp_path / "c.xknxcatalog")
    cat.import_knxprod(_fixture())
    proj = ProjectService(cat)
    proj.set_logger(Logger(LogService(), "project"))
    proj.new(tmp_path / "p.xknx")
    return proj, cat


def test_module_override_com_objects_survive_reload_and_link(tmp_path: Path) -> None:
    proj, cat = _project(tmp_path)
    product = next(p for p in cat.get_products() if p.application_id == _APP_ID)
    app = cat.get_application(_APP_ID)
    assert app is not None
    prog = app.program.id

    # Select a non-default function on the M-100 channel, which re-instantiates its com-object.
    override = [(f"{prog}_MD-1_M-100_MI-1_P-149_R-142", "5")]
    dev_id = proj.add_device(
        product.product_ref_id,
        product.hardware2program_ref_id,
        "Gira",
        app,
        parameters=override,
    )
    assert dev_id is not None

    device = next(d for d in proj.devices if d.node_id == dev_id)
    visible = device.get_visible_com_objects()

    # The override deactivates one M-100 object and re-refs the other; both channels stay present,
    # every surfaced object carries a db_id, and the re-instantiated M-100 ref is the one persisted.
    ids = {co.id for co in visible}
    assert ids == {
        f"{prog}_MD-1_M-100_MI-1_O-2-0_R-173",
        f"{prog}_MD-1_M-200_MI-1_O-2-0_R-1",
        f"{prog}_MD-1_M-200_MI-1_O-2-1_R-2",
    }
    assert all(co.db_id is not None for co in visible)

    # The recovered M-100 channel can now be linked (its db_id resolves), which is exactly what
    # recover does per decoded group object; the link persists with its sending flag.
    m100 = next(co for co in visible if co.id.endswith("_M-100_MI-1_O-2-0_R-173"))
    assert m100.db_id is not None
    ga_id = proj.create_group_address_value(0x0B00, "chan")
    assert ga_id is not None
    link_id = proj.link_com_object_to_ga(m100.db_id, ga_id, is_sending=True)
    assert link_id is not None

    assignments = proj.get_assignments_for_ga(ga_id)
    assert [(a.com_object_id, a.is_sending) for a in assignments] == [
        (m100.db_id, True)
    ]


def test_add_device_without_override_is_unchanged(tmp_path: Path) -> None:
    # Guard the fast path: a plain add (no overrides) keeps the default channel objects and still
    # attaches a db_id to each, so non-module and unconfigured devices are unaffected by the fix.
    proj, cat = _project(tmp_path)
    product = next(p for p in cat.get_products() if p.application_id == _APP_ID)
    app = cat.get_application(_APP_ID)
    assert app is not None
    prog = app.program.id

    dev_id = proj.add_device(
        product.product_ref_id, product.hardware2program_ref_id, "Gira", app
    )
    assert dev_id is not None
    device = next(d for d in proj.devices if d.node_id == dev_id)
    visible = device.get_visible_com_objects()
    ids = {co.id for co in visible}
    assert ids == {
        f"{prog}_MD-1_M-100_MI-1_O-2-0_R-1",
        f"{prog}_MD-1_M-100_MI-1_O-2-1_R-2",
        f"{prog}_MD-1_M-200_MI-1_O-2-0_R-1",
        f"{prog}_MD-1_M-200_MI-1_O-2-1_R-2",
    }
    assert all(co.db_id is not None for co in visible)
