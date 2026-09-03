from app.azure_clients import get_table_service_client
from app.core.config import settings
from app.schemas.jobs import JobEntity


def get_job_table_client():
    service_client = get_table_service_client()

    return service_client.get_table_client(
        table_name=settings.azure_table_name,
    )


def create_job(job: JobEntity) -> None:
    table_client = get_job_table_client()

    entity = job.model_dump(
        by_alias=True,
        mode="json",
    )

    table_client.create_entity(
        entity=entity,
    )

def get_job(job_id: str):
    table_client = get_job_table_client()

    return table_client.get_entity(
        partition_key="JOB",
        row_key=job_id,
    )
