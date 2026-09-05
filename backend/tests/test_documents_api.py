from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_upload_rejects_file_larger_than_50mb():
    oversized_content = b"a" * (50 * 1024 * 1024 + 1)

    response = client.post(
        "/api/v1/documents",
        files={
            "file": (
                "large.pdf",
                oversized_content,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413
    assert response.json() == {
        "detail": "File size exceeds the 50 MB limit"
    }