"""Regression: the recover number-to-ref map must reflect module-scoped parameter overrides.

The map turns a decoded link's com-object *number* into the reference id a project links by. It is
built from a dynamic UI seeded with the recovered parameters. A module-scoped override
(``…_M-100_MI-1_P-149_R-142``) only routes into its module scope once the module instances are
materialised, so seeding with the parameters alone left the module channels on their raw default and
emitted the default ref. The project persists the *re-instantiated* ref, so the map's stale ref
resolved to no object and the link was silently dropped. ``seed_dynamic_ui`` now discovers the
module instances first and rebuilds with them, so the map matches the persisted object.
"""

from __future__ import annotations

from pathlib import Path

from xknxeditor.prod import load
from xknxeditor.recover.recover import com_object_ref_by_number, seed_dynamic_ui

_APP_ID = "M-0008_A-7072-21-5CC3-O000A"


def _app():  # type: ignore[no-untyped-def]
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
            return load(cand.read_bytes()).applications[_APP_ID]
    raise FileNotFoundError("gira_2gang_button_interface.knxprod not found")


def test_number_to_ref_map_follows_module_override() -> None:
    app = _app()
    prog = app.program.id
    override = {f"{prog}_MD-1_M-100_MI-1_P-149_R-142": "5"}

    seeded = seed_dynamic_ui(app, override)
    mapping = com_object_ref_by_number(app, seeded)

    # The M-100 channel is re-instantiated under R-173 by the override; the map must carry that ref
    # (which the project persists), not the default R-1 that would resolve to nothing.
    assert mapping[253] == f"{prog}_MD-1_M-100_MI-1_O-2-0_R-173"
    assert not any(r.endswith("_M-100_MI-1_O-2-0_R-1") for r in mapping.values())
