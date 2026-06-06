import json

from sovereign_cortex.activity import ActivityRecordStore
from sovereign_cortex.events import EventEnvelope, EventType


def test_activity_records_are_jsonl_and_preserve_correlation_id(tmp_path):
    first = EventEnvelope(
        event_type=EventType.COMMAND_RECEIVED,
        sender="cli",
        recipient="orchestrator",
        workspace="demo-project",
        payload={"status": "started"},
    )
    second = EventEnvelope(
        event_type=EventType.TASK_COMPLETED,
        sender="orchestrator",
        recipient="cli",
        workspace="demo-project",
        payload={"status": "done"},
    )
    second.correlation_id = first.correlation_id

    paths = ActivityRecordStore(tmp_path).append([first, second])

    assert len(set(paths)) == 1
    assert paths[0].suffix == ".jsonl"
    lines = paths[0].read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    assert len(records) == 2
    assert [record["event_type"] for record in records] == ["CommandReceived", "TaskCompleted"]
    assert {record["correlation_id"] for record in records} == {first.correlation_id}
