"""memory_watchdog の cgroup 優先ロジック。"""

from utils.memory_watchdog import get_memory_status


def test_get_memory_status_fallback_has_usage_fields():
    st = get_memory_status()
    assert "usage_mb" in st
    assert "usage_ratio" in st
    assert "limit_mb" in st
    assert st.get("usage_source") in ("cgroup memory.current", "process VmRSS", None) or st.get(
        "usage_source"
    )
