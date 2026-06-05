import json

from sovereign_cortex.activity import ActivityRecordStore
from sovereign_cortex.events import EventEnvelope, EventType


def test_record_store_writes_jsonl(tmp_path):
    event = EventEnvelope(
        event_type=EventType.COMMAND_RECEIVED,
        sender="test",
        recipient="test",
        workspace="demo-project",
        payload={"ok": True},
    )

    paths = ActivityRecordStore(tmp_path).append([event])

    assert len(paths) == 1
    assert paths[0].exists()
    assert paths[0].suffix == ".jsonl"
    record = json.loads(paths[0].read_text(encoding="utf-8").strip())
    assert record["event_type"] == "CommandReceived"
    assert record["correlation_id"] == event.correlation_id
    assert record["payload"] == {"ok": True}
