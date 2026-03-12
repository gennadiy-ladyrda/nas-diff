from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.services.scan_orchestrator import run_scan_job


def test_group_decision_keep_overrides_primary(
    api_client,
    api_session_factory: sessionmaker[Session],
    test_settings,
    tmp_path,
) -> None:
    dataset_root = tmp_path / "decision-dataset"
    dataset_root.mkdir(parents=True, exist_ok=True)
    (dataset_root / "a.jpg").write_bytes(b"X" * 256)
    (dataset_root / "b.jpg").write_bytes(b"X" * 256)

    with api_session_factory() as session:
        root_id = session.execute(
            text("INSERT INTO scan_roots(path, enabled) VALUES (:path, 1)"),
            {"path": str(dataset_root)},
        ).lastrowid
        session.commit()
    assert root_id is not None

    create_response = api_client.post(
        "/api/v1/scan/jobs",
        json={"mode": "exact", "root_ids": [int(root_id)]},
    )
    assert create_response.status_code == 201
    job_id = create_response.json()["job_id"]

    with api_session_factory() as session:
        run_scan_job(session, test_settings, job_id=job_id)

    groups_response = api_client.get(f"/api/v1/scan/jobs/{job_id}/groups", params={"kind": "exact"})
    assert groups_response.status_code == 200
    group_id = groups_response.json()["items"][0]["id"]

    details_before = api_client.get(f"/api/v1/groups/exact/{group_id}")
    assert details_before.status_code == 200
    items_before = details_before.json()["items"]
    assert len(items_before) == 2
    current_primary = [item for item in items_before if item["is_primary"] is True][0]["file_id"]
    target_file_id = [item for item in items_before if item["file_id"] != current_primary][0]["file_id"]

    decision_response = api_client.post(
        f"/api/v1/groups/exact/{group_id}/decision",
        json={"file_id": target_file_id, "decision": "keep", "note": "manual override"},
    )
    assert decision_response.status_code == 200
    assert decision_response.json()["file_id"] == target_file_id
    assert decision_response.json()["decision"] == "keep"

    details_after = api_client.get(f"/api/v1/groups/exact/{group_id}")
    assert details_after.status_code == 200
    items_after = details_after.json()["items"]
    primaries = [item["file_id"] for item in items_after if item["is_primary"] is True]
    assert primaries == [target_file_id]

    selected_item = [item for item in items_after if item["file_id"] == target_file_id][0]
    assert selected_item["decision"] == "keep"
