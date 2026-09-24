"""Tests for scan_programming_mode_devices: dedup of retransmitted answers and per-device
error isolation."""

import editor_gui.programming as programming
from editor_gui.programming import DeviceOverview, scan_programming_mode_devices


class _FakeManagement:
    async def connect(self, target: object) -> object:  # pragma: no cover - unused
        raise AssertionError("read_device_overview is patched, connect must not run")


class _FakeXKNX:
    def __init__(self) -> None:
        self.management = _FakeManagement()


async def test_dedups_retransmitted_addresses(monkeypatch) -> None:
    # A device in programming mode retransmits its answer, so the broadcast yields duplicates.
    answers = ["1.1.10", "1.1.11", "1.1.10", "1.1.11"]

    async def fake_read(_xknx, timeout=3.0):
        return answers

    reads: list[str] = []

    async def fake_overview(_xknx, address):
        reads.append(address)
        return DeviceOverview(manufacturer="M-0083")

    monkeypatch.setattr(
        "xknx.management.procedures.nm_individual_address_read", fake_read
    )
    monkeypatch.setattr(programming, "read_device_overview", fake_overview)

    results = await scan_programming_mode_devices(_FakeXKNX())

    assert [r.address for r in results] == ["1.1.10", "1.1.11"]
    assert reads == ["1.1.10", "1.1.11"]  # each device read exactly once
    assert all(r.overview is not None and r.error is None for r in results)


async def test_read_error_is_isolated_per_device(monkeypatch) -> None:
    async def fake_read(_xknx, timeout=3.0):
        return ["1.1.10", "1.1.11"]

    async def fake_overview(_xknx, address):
        if address == "1.1.10":
            raise TimeoutError("device dropped the link")
        return DeviceOverview(manufacturer="M-0002")

    monkeypatch.setattr(
        "xknx.management.procedures.nm_individual_address_read", fake_read
    )
    monkeypatch.setattr(programming, "read_device_overview", fake_overview)

    results = await scan_programming_mode_devices(_FakeXKNX())

    assert len(results) == 2
    failed, ok = results
    assert failed.address == "1.1.10"
    assert failed.overview is None
    assert failed.error is not None and "dropped the link" in failed.error
    assert ok.address == "1.1.11"
    assert ok.overview is not None and ok.error is None
