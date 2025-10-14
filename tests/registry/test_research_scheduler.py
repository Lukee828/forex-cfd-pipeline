import datetime as dt
from zigzagob.alpha_factory.research_scheduler import ResearchScheduler, deep_merge


def dummy(**kwargs):
    return {"ok": True, "kwargs": kwargs}


def test_interval_due_and_advance():
    sch = ResearchScheduler()
    sch.add_job("heartbeat", dummy, {"every": 60}, params={"x": 1})
    now = dt.datetime(2024, 1, 1, 0, 1, 1)
    ran = sch.tick(now)
    assert len(ran) == 1 and ran[0][0] == "heartbeat"
    # next_run should be > now; second tick at same now should not run again
    ran2 = sch.tick(now)
    assert len(ran2) == 0


def test_daily_due_and_next_day():
    sch = ResearchScheduler()
    sch.add_job("nightly", dummy, {"daily": {"byhour": 9, "byminute": 0, "bysecond": 0}})
    now = dt.datetime(2024, 1, 1, 9, 0, 0)
    ran = sch.tick(now)
    assert len(ran) == 1
    # not due again until tomorrow
    ran2 = sch.tick(now)
    assert len(ran2) == 0
    # tomorrow 09:00 runs again
    ran3 = sch.tick(now + dt.timedelta(days=1))
    assert len(ran3) == 1


def test_deep_merge_overlay():
    base = {
        "jobs": [
            {
                "name": "pulse",
                "task": "dummy",
                "schedule": {"every": 60},
                "params": {"u": "majors", "depth": 100},
            }
        ]
    }
    override = {"jobs": [{"name": "pulse", "params": {"depth": 250}}]}
    merged = deep_merge(base, override)
    # jobs array is replaced (simple policy), but nested dict merged; so emulate controller behavior:
    # controller would merge per-job by name; here we just verify deep_merge semantics on dicts
    assert merged["jobs"][0]["params"]["depth"] == 250


def test_from_config_with_registry_and_tick():
    reg = {"dummy": dummy}
    cfg = {
        "jobs": [{"name": "pulse", "task": "dummy", "schedule": {"every": 5}, "params": {"p": 42}}]
    }
    sch = ResearchScheduler.from_config(cfg, reg)
    ran = sch.tick(dt.datetime(2024, 1, 1, 0, 0, 5))
    assert ran and ran[0][0] == "pulse"
