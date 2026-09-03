from app.azure_clients import get_queue_service_client
from app.core.config import settings
from app.schemas.jobs import QueueMessage


def get_job_queue_client():
    service_client = get_queue_service_client()

    return service_client.get_queue_client(
        queue=settings.azure_queue_name,
    )


def send_job_message(message: QueueMessage) -> None:
    queue_client = get_job_queue_client()

    queue_client.send_message(
        message.model_dump_json(by_alias=True),
    )