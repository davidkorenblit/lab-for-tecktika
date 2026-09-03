import json
import base64
import logging
import azure.functions as func

from config import settings
from models.queue_message import QueueMessage
from services.dispatcher import EventDispatcher


app = func.FunctionApp()
dispatcher = EventDispatcher()


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
    Queue Listener: Triggers on queue message, parses it, and delegates to EventDispatcher.
    """
    raw_body = msg.get_body().decode("utf-8")
    logging.info(f"Received raw queue message ID {msg.id}: {raw_body}")

    try:
        parsed_event = parse_queue_message(raw_body)
        dispatcher.dispatch(parsed_event)
    except Exception as err:
        logging.error(f"Failed processing queue message ID {msg.id}: {err}")
        raise err
