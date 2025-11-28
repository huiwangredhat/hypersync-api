import json
import logging
import os
import urllib.parse
import io
import boto3
import requests
import sys

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize AWS Clients
s3_client = boto3.client('s3') 
ssm_client = boto3.client('ssm') 


def get_ssm_parameter(parameter_name):
    """
    Fetches a SecureString from AWS Systems Manager Parameter Store.
    """
    if not parameter_name:
        return None
        
    try:
        response = ssm_client.get_parameter(
            Name=parameter_name,
            WithDecryption=True 
        )
        return response['Parameter']['Value']
    except Exception as e:
        logger.error(f"Error fetching SSM parameter '{parameter_name}': {e}")
        raise e


# Read the CLIENT_ID and CLIENT_SECRET from Env Vars
try:
    CLIENT_ID = get_ssm_parameter(os.environ.get("CLIENT_ID"))
    CLIENT_SECRET = get_ssm_parameter(os.environ.get("CLIENT_SECRET"))
except Exception as e:
    logger.error("Failed to load credentials from SSM.")
    raise e

# API Endpoints
PROOF_API_URL = "https://api.hyperproof.app/v1/proof/"
CONTROLS_API_URL = "https://api.hyperproof.app/v1/controls" # Added as per requirement
OAUTH_TOKEN_URL = "https://accounts.hyperproof.app/oauth/token"


def get_access_token(client_id, client_secret):
    """Exchanges credentials for a Token."""
    if not client_id or not client_secret:
        logger.error("Credentials missing (failed to retrieve from SSM)")
        raise ValueError("Credentials missing")

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    try:
        response = requests.post(OAUTH_TOKEN_URL, data=payload)
        response.raise_for_status()
        return response.json().get("access_token")
    except Exception as e:
        logger.error(f"Token Error: {e}")
        raise e

def add_proof(file_name, file_stream, content_type):
    """
    Uploads a file to the general /proof endpoint (Unlinked to a control).
    """
    access_token = get_access_token(CLIENT_ID, CLIENT_SECRET)
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    logger.info(f"Attempting to upload general proof file: {file_name}...")

    try:
        files_payload = {'proof': (file_name, file_stream, content_type)}

        response = requests.post(
            PROOF_API_URL, 
            headers=headers, 
            files=files_payload
        )
        
        response.raise_for_status()
        
        logger.info(f"Successfully added proof. ID: {response.json().get('id')}")
        return response.json()

    except requests.exceptions.HTTPError as err:
        logger.error(f"HTTP error: {err} - Response: {err.response.text}")
        raise err
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise e

def upload_proof2control(control_id, file_name, file_stream, content_type):
    """
    Uploads a proof file and links it to a specific control.
    """
    access_token = get_access_token(CLIENT_ID, CLIENT_SECRET)
    if not access_token:
        logger.error("Halting script: Could not obtain access token.")
        raise Exception("Could not obtain access token")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    # Construct the specific URL for this control's proof endpoint
    control_proof_url = f"{CONTROLS_API_URL}/{control_id}/proof"

    logger.info(f"\nAttempting to upload proof for control {control_id}...")
    logger.info(f"File: {file_name}")
    logger.info(f"URL: {control_proof_url}")
    
    try:
        # Prepare the 'files' payload using the memory stream
        # Note: We must reset the stream position in case it was read previously
        file_stream.seek(0)
        files_payload = {'proof': (file_name, file_stream, content_type)}

        response = requests.post(
            control_proof_url,
            headers=headers,
            files=files_payload
        )

        response.raise_for_status() 

        logger.info("\nSuccess! File uploaded and linked to control.")
        logger.info(response.json())
        return response.json()
        
    except requests.exceptions.HTTPError as err:
        logger.error(f"HTTP error linking to control: {err} - Response: {err.response.text}")
        raise err
    except Exception as e:
        logger.error(f"Unexpected error in upload_proof2control: {e}")
        raise e


def lambda_handler(event, context):
    try:
        # 1. Get the bucket and key from the S3 Event
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'])
        
        logger.info(f"Processing file: {key} from bucket: {bucket}")

        # 2. Download file from S3 into Memory (RAM)
        s3_response = s3_client.get_object(Bucket=bucket, Key=key)
        file_content = s3_response['Body'].read()
        
        # Get Content-Type
        content_type = s3_response.get('ContentType', 'application/octet-stream')
        
        # Get Control ID from the Envrionment
        control_id = os.environ.get('CONTROL_ID')
        

        # 3. Create a stream
        file_stream = io.BytesIO(file_content)

        # 4. Decide which function to call based on metadata
        if control_id:
            logger.info(f"Control ID '{control_id}' found in S3 Metadata. Linking proof to control.")
            result = upload_proof2control(
                control_id=control_id,
                file_name=key.split('/')[-1],
                file_stream=file_stream,
                content_type=content_type
            )
        else:
            logger.info("No Control ID found in metadata. Uploading as unlinked proof.")
            result = add_proof(
                file_name=key.split('/')[-1],
                file_stream=file_stream,
                content_type=content_type
            )

        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }

    except Exception as e:
        logger.error(f"Handler Failed: {str(e)}")
        raise e
