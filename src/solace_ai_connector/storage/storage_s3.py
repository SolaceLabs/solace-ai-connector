"""AWS S3 storage implementation for the storage interface."""

import boto3
from .storage import Storage


class StorageS3(Storage):
    """AWS S3 storage class for the Solace AI Event Connector. The data is stored as JSON"""

    def __init__(self, config: dict):
        """Initialize the AWS S3 storage class."""
        self.bucket_name = config["bucket_name"]
        self.s3 = boto3.resource("s3")

    def put(self, key: str, value: dict):
        """Put a value into the AWS S3 storage as a JSON object."""
        self.s3.Object(self.bucket_name, key).put(Body=value)

    def get(self, key: str) -> dict:
        """Get a value from the AWS S3 storage"""
        return (
            self.s3.Object(self.bucket_name, key).get()["Body"].read().decode("utf-8")
        )

    def delete(self, key: str):
        """Delete a value from the AWS S3 storage."""
        self.s3.Object(self.bucket_name, key).delete()

    def list(self) -> list:
        """List all keys in the AWS S3 storage."""
        return [obj.key for obj in self.s3.Bucket(self.bucket_name).objects.all()]
