import os
import uuid
from minio import Minio
from minio.error import S3Error
from io import BytesIO

MINIO_URL = os.getenv("MINIO_URL", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "resumes")

client = Minio(
    MINIO_URL,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

def upload_file_to_minio(file_bytes: bytes, filename: str) -> str:
    try:
        # Ensure bucket exists
        if not client.bucket_exists(MINIO_BUCKET):
            client.make_bucket(MINIO_BUCKET)

        unique_name = f"{uuid.uuid4()}-{filename}"
        file_stream = bytes(file_bytes)

        client.put_object(
            MINIO_BUCKET,
            unique_name,
            data=BytesIO(file_stream),
            length=len(file_stream),
            content_type="application/octet-stream"
        )

        return f"s3://{MINIO_BUCKET}/{unique_name}"

    except S3Error as e:
        raise Exception(f"Failed to upload to MinIO: {str(e)}")
