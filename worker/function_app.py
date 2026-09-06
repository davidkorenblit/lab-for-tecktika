import json
import base64
import logging
import azure.functions as func

from config import settings
from models.queue_message import QueueMessage
from services.dispatcher import EventDispatcher
from services.job_service import JobService


app = func.FunctionApp()
dispatcher = EventDispatcher()
job_service = JobService()


def parse_queue_message(msg_body: str) -> QueueMessage:
    """
    Parses incoming queue message string into a QueueMessage pydantic model.
    Handles both plain JSON and Base64 encoded JSON safely.
    """
    try:
        data = json.loads(msg_body)
    except json.JSONDecodeError:
        decoded = base64.b64decode(msg_body).decode("utf-8")
        data = json.loads(decoded)

    return QueueMessage(**data)


@app.queue_trigger(
    arg_name="msg",
    queue_name=settings.JOBS_QUEUE_NAME,
    connection="AzureWebJobsStorage"
)
def process_queue_message(msg: func.QueueMessage) -> None:
    """
    Queue Listener: Triggers on queue message, parses it, delegates to EventDispatcher,
    and handles errors by updating Table Storage to FAILED and forwarding to Poison Queue.
    """
    raw_body = msg.get_body().decode("utf-8")
    logging.info(f"Received raw queue message ID {msg.id}: {raw_body}")

    parsed_event = None
    try:
        parsed_event = parse_queue_message(raw_body)
        dispatcher.dispatch(parsed_event)
    except Exception as err:
        logging.error(f"Error processing queue message ID {msg.id}: {err}")
        
        # If parsing succeeded but execution failed, mark job as FAILED in Table Storage
        if parsed_event:
            job_service.mark_failed(
                job_id=parsed_event.job_id,
                document_id=parsed_event.document_id,
                blob_name=parsed_event.blob_name,
                error_msg=str(err)
            )

        # Re-raise exception so Azure Queue trigger increments dequeue count and routes to poison queue after retries
        raise err
