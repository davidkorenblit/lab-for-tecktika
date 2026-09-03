import json
import base64
import logging
import azure.functions as func

from config import settings
from models.queue_message import QueueMessage


app = func.FunctionApp()


def parse_queue_message(msg_body: str) -> QueueMessage:
    """
    Parses incoming queue message string into a QueueMessage pydantic model.
    Handles both plain JSON and Base64 encoded JSON safely.
    """
    try:
        # Try parsing plain JSON string
        data = json.loads(msg_body)
    except json.JSONDecodeError:
        # If plain JSON fails, attempt Base64 decoding first
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
    PR 2 Queue Listener: Triggers when a message arrives in the queue,
    parses it safely into QueueMessage, and logs the event.
    """
    raw_body = msg.get_body().decode("utf-8")
    logging.info(f"Received raw queue message ID {msg.id}: {raw_body}")

    try:
        parsed_event = parse_queue_message(raw_body)
        logging.info(
            f"Successfully parsed event: {parsed_event.event_type} "
            f"for Document ID: {parsed_event.document_id} (file: {parsed_event.blob_name})"
        )
    except Exception as err:
        logging.error(f"Failed to parse queue message ID {msg.id}: {err}")
        raise err
