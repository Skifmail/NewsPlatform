"""Tests for pipeline progress Redis writer."""

from app.services.pipeline_emitter import bind_pipeline, unbind_pipeline
from app.services.pipeline_progress import read_pipeline_progress


def test_pipeline_writer_stores_events() -> None:
    task_id = "test-pipeline-task-001"
    writer = bind_pipeline(task_id, job_type="article", label="Статья: тест")
    try:
        step = writer.begin_step(
            label="DeepSeek → deepseek-chat",
            to_node="deepseek",
            provider="DeepSeek",
            model="deepseek-chat",
            request_summary="system: ideation | user: topic",
        )
        writer.complete_step(step, response_summary='{"topic":"AI"}')
        writer.emit_internal(label="Тема выбрана", detail="AI trends", progress=30)
        writer.finish(status="done")
    finally:
        unbind_pipeline()

    data = read_pipeline_progress(task_id)
    assert data is not None
    assert data["status"] == "done"
    assert data["progress"] == 100
    assert len(data["events"]) >= 3
    assert data["events"][-2]["to_node"] == "deepseek"
    assert data["events"][-2]["status"] == "success"
