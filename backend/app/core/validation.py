"""
Shared validation for the two client-supplied strings that reach storage and
the model: a file name, and the staged blob path issued by create_upload_url().

Both arrive in the request body, so neither can be trusted on arrival even
though the backend is what originally handed the path to the client.
"""

import re
import unicodedata


FILE_NAME_MAX_LENGTH = 255

# create_upload_url() builds every staged path as f"{file_id}/{file_name}",
# with file_id = f"f_{uuid4().hex}". Anything not shaped like that was not
# issued by this service.
_STAGED_BLOB_PATH_PREFIX = re.compile(r"^f_[0-9a-f]{32}/")


def _has_control_characters(value: str) -> bool:
    # Cc covers newlines and the C0/C1 ranges; Cf covers the bidi and
    # zero-width formatting characters that can hide text from a reviewer.
    return any(unicodedata.category(char) in {"Cc", "Cf"} for char in value)


def validate_file_name(value: str) -> str:
    """
    Accepts an ordinary file name and rejects anything that could traverse a
    path or smuggle instructions into a prompt. Deliberately permissive about
    the character set itself - Hebrew names, spaces and parentheses are all
    normal here - and strict only about the structural characters.
    """
    name = value.strip()

    if not name:
        raise ValueError("File name cannot be empty")

    if len(name) > FILE_NAME_MAX_LENGTH:
        raise ValueError(
            f"File name cannot exceed {FILE_NAME_MAX_LENGTH} characters"
        )

    if "/" in name or "\\" in name:
        raise ValueError("File name cannot contain a path separator")

    if name in {".", ".."} or name.startswith(".."):
        raise ValueError("File name cannot be a relative path segment")

    if _has_control_characters(name):
        # A newline is what turns a file name into extra prompt lines.
        raise ValueError("File name cannot contain control characters")

    return name


def validate_staged_blob_path(value: str) -> str:
    """
    A staged path is only ever accepted in the exact shape this service issues.
    Without this the client could name any blob in the staging container and
    have the worker copy it into the library under a name of its choosing.
    """
    path = value.strip()

    if not _STAGED_BLOB_PATH_PREFIX.match(path):
        raise ValueError(
            "Staged blob path must be one issued by the upload endpoint"
        )

    file_id, _, file_name = path.partition("/")
    validate_file_name(file_name)

    return f"{file_id}/{file_name}"
