"""Tests for counter-based usage collection (services/usage_collector.py)."""
from __future__ import annotations

from schemas import LinkState, LinkStatus
from services.usage_collector import UsageCollector


def _link(link_id="wan", device="eth0", rx_bps=0.0, tx_bps=0.0,
          state=LinkState.up, enabled=True):
    return LinkStatus(id=link_id, label=link_id, device=device, rx_bps=rx_bps,
                      tx_bps=tx_bps, state=state, enabled=enabled)


def test_first_sample_only_arms_baseline():
    # Booking the absolute counter on first sight would charge this month for
    # everything since the router booted.
    c = UsageCollector()
    assert c.sample([_link()], {"eth0": (5e9, 1e9)}, 10) == []


def test_counter_delta_is_booked():
    c = UsageCollector()
    c.sample([_link()], {"eth0": (1000.0, 500.0)}, 10)
    rows = c.sample([_link()], {"eth0": (3000.0, 900.0)}, 10)
    assert rows == [("wan", 2000.0, 400.0)]


def test_counter_reset_books_nothing_and_rearms():
    c = UsageCollector()
    c.sample([_link()], {"eth0": (9e9, 9e9)}, 10)
    # Router reboot: counters restart near zero — must not book a huge delta.
    assert c.sample([_link()], {"eth0": (10.0, 5.0)}, 10) == []
    # Baseline re-armed at the post-reboot value, so the next tick counts again.
    assert c.sample([_link()], {"eth0": (110.0, 25.0)}, 10) == [("wan", 100.0, 20.0)]


def test_falls_back_to_rate_integration_without_counter():
    c = UsageCollector()
    # No counter for this device -> integrate 80 Mbps over 10 s = 100 MB.
    rows = c.sample([_link(rx_bps=80e6, tx_bps=8e6)], {}, 10)
    assert rows == [("wan", 100e6, 10e6)]


def test_disabled_links_are_not_counted():
    c = UsageCollector()
    links = [_link("wan2", "eth1", rx_bps=1e9, enabled=False),
             _link("wan3", "eth2", rx_bps=1e9, state=LinkState.disabled)]
    assert c.sample(links, {}, 10) == []


def test_link_without_device_uses_rate():
    c = UsageCollector()
    link = LinkStatus(id="wan", label="wan", device=None, rx_bps=8e6, tx_bps=0.0)
    assert c.sample([link], {"eth0": (1.0, 1.0)}, 10) == [("wan", 10e6, 0.0)]


def test_counters_are_tracked_per_device():
    c = UsageCollector()
    links = [_link("wan", "eth0"), _link("wan2", "eth1")]
    c.sample(links, {"eth0": (100.0, 100.0), "eth1": (500.0, 500.0)}, 10)
    rows = dict((r[0], r[1:]) for r in
                c.sample(links, {"eth0": (150.0, 100.0), "eth1": (700.0, 500.0)}, 10))
    assert rows["wan"] == (50.0, 0.0)
    assert rows["wan2"] == (200.0, 0.0)
