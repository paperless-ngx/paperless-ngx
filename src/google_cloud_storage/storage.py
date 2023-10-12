
from google.cloud import storage
from django.conf import settings
from io import BytesIO

is_gcs_enabled = settings.GOOGLE_CLOUD_STORAGE
client = None
bucket = None

if is_gcs_enabled:
    print("Initializing Google Cloud Storage: " + str(settings.GCP_SERVICE_ACCOUNT_JSON))
    # Prepare Google Cloud Storage client
    # client = storage.Client()
    client = storage.Client.from_service_account_info(settings.GCP_SERVICE_ACCOUNT_JSON)

    print("Getting bucket: " + settings.GCP_BUCKET_NAME)

    bucket = client.bucket(settings.GCP_BUCKET_NAME)


def upload_file(source, target):
    if (not client) or (not bucket): 
        return

    with open(source, "rb") as read_file_2:
        # Reference: https://github.com/GoogleCloudPlatform/getting-started-python/blob/main/bookshelf/storage.py#L59
        print("Uploading to Google Cloud Storage")
        blob = bucket.blob(str(target))
        # Reference: https://cloud.google.com/python/docs/reference/storage/latest/google.cloud.storage.blob.Blob#google_cloud_storage_blob_Blob_upload_from_file
        blob.upload_from_file(read_file_2)

def get_file_from_gcs(bucket_path):
    try:
        if (not client) or (not bucket):
            raise Exception("Google Cloud Storage is not initialized.")

        # print("Getting blob from Google Cloud Storage")
        # Create a blob object representing the path in the bucket
        blob = bucket.blob(str(bucket_path))

        # Download the file as a byte array
        byte_stream = BytesIO()
        # print("Downloading file from Google Cloud Storage")
        blob.download_to_file(byte_stream)

        # Seek to the start of the byte stream to allow reading from the beginning
        byte_stream.seek(0)

        # print("Returning downloaded file to caller")
        return byte_stream
    except:
        return None

def exists():
    return False