from __future__ import annotations

from app.workers.queue import RQScanQueueClient, get_scan_queue_client


def test_scan_queue_uses_configured_timeout(test_settings) -> None:
    client = get_scan_queue_client(test_settings)
    assert isinstance(client, RQScanQueueClient)
    assert client.queue_name == "scan_queue"
    assert client.job_timeout_seconds == test_settings.scan_job_timeout_seconds
