import requests
import sys
import logging
import json
import os # Import the os module to access environment variables
from dotenv import load_dotenv # Import the dotenv library
# import hyperproof

# --- Configuration ---
# Load environment variables from a .env file in the same directory
load_dotenv()
logger = logging.getLogger("Hyperproof API")

# Load the Client ID and Secret from environment variables.
# These should be in your .env file.
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")

# The API endpoint for fetching controls
CONTROLS_API_URL = "https://api.hyperproof.app/v1/controls"
PROOF_API_URL = "https://api.hyperproof.app/v1/proof/"
LABELS_API_URL = "https://api.hyperproof.app/v1/labels/"
# !!! IMPORTANT !!!                             ###
# You may need to verify this URL. This is a standard OAuth endpoint,
# but Hyperproof might use a different one.
# Common alternatives:
# - https://api.hyperproof.app/v1/oauth/token
# - https://auth.hyperproof.app/oauth/token
OAUTH_TOKEN_URL = "https://accounts.hyperproof.app/oauth/token"

# ---------------------

def get_access_token(client_id, client_secret):
    """
    Exchanges the Client ID and Secret for an access token using OAuth 2.0.
    """
    print(f"Attempting to fetch access token from {OAUTH_TOKEN_URL}...")
    
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        response = requests.post(OAUTH_TOKEN_URL, data=payload, headers=headers)
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get("access_token")
            if access_token:
                print("✅ Successfully obtained access token.")
                return access_token
            else:
                print("❌ Error: 'access_token' not found in response from token URL.")
                print(f"Response Body: {response.text}")
                return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ A network error occurred while getting token: {e}")
        return None
    except json.JSONDecodeError:
        print(f"❌ Error: Failed to decode JSON response from token URL.")
        print(f"Raw Response: {response.text}")
        return None

def add_proof(file_to_upload, object_id=None, object_type=None):
    access_token = get_access_token(CLIENT_ID, CLIENT_SECRET)
    
    if not access_token:
        print("❌ Halting script: Could not obtain access token.")
        sys.exit(1)

    # Headers: ONLY include Authorization and Accept.
    # DO NOT set "Content-Type" manually.
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    # This 'data' payload is for other form fields, like objectId or objectType,
    # just like in your first example.
    data = {}
    if object_id and object_type:
        data['objectId'] = object_id
        data['objectType'] = object_type

    print(f"\nAttempting to upload proof file: {file_to_upload}...")
    
    try:
        # Open the file in binary-read ('rb') mode
        with open(file_to_upload, 'rb') as f:
            print(f"open {file_to_upload} ........")
            # Use 'files=' to send the file content
            # The key 'file' must match what the API expects
            # files_payload = {'proof': (file_to_upload, f)}
            files_payload = {'proof': (file_to_upload, f, 'application/json')}
            # files_payload = {'proof': (file_to_upload, f, 'application/pdf')}
            
            # Send the request using 'headers=', 'files=', and 'data='
            # DO NOT use 'json='
            response = requests.post(
                PROOF_API_URL, 
                headers=headers, 
                files=files_payload,
                data=data 
            )
            
            response.raise_for_status()  # Raise an exception for 4xx/5xx errors
            
        logger.info(f"Successfully added proof")
        return response.json()
    
    except FileNotFoundError:
        logger.error(f"File not found at path: {file_to_upload}")
        return None
    except requests.exceptions.HTTPError as err:
        logger.error(f"HTTP error occurred: {err} - {err.response.text}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None

def add_proof_version(proof_id, file_to_upload, content_type=None):
    """
    Uploads a new version of an existing proof file.
    """
    access_token = get_access_token(CLIENT_ID, CLIENT_SECRET)
    
    if not access_token:
        print("❌ Halting script: Could not obtain access token.")
        sys.exit(1)

    # Headers: ONLY include Authorization and Accept.
    # DO NOT set "Content-Type" manually.

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
        # DO NOT set Content-Type, 'requests' handles it for multipart/form-data
    }
    
    # Construct the specific URL for this proof version
    version_url = f"{PROOF_API_URL}/{proof_id}/versions"

    print(f"\nAttempting to upload new version for proof {proof_id}...")
    print(f"File: {file_to_upload}")
    print(f"URL: {version_url}")
    
    try:
        # Open the file in binary-read ('rb') mode
        with open(file_to_upload, 'rb') as f:
            
            # Create the files payload
            if content_type:
                # Send with a specific content type
                files_payload = {'proof': (file_to_upload, f, content_type)}
            else:
                # Let 'requests' guess the content type
                files_payload = {'proof': (file_to_upload, f)}
            
            # Note: We are not sending a 'data=' payload, 
            # as the versioning endpoint typically only needs the file.
            response = requests.post(
                version_url, 
                headers=headers, 
                files=files_payload
            )
            
            response.raise_for_status()  # Raise an exception for 4xx/5xx errors
            
        logger.info(f"Successfully added new version for proof {proof_id}")
        return response.json()
    
    except FileNotFoundError:
        logger.error(f"File not found at path: {file_to_upload}")
        return None
    except requests.exceptions.HTTPError as err:
        logger.error(f"HTTP error occurred: {err} - {err.response.text}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None

def add_control_proof(control_id, file_to_upload, content_type=None):
    """
    Uploads a proof file and links it to a specific control.

    :param control_id: The ID of the control to link the proof to.
    :param file_to_upload: Path to the proof file to upload.
    :param content_type: The MIME type of the file (e.g., 'application/pdf'), optional.
    :return: Response data of the newly added proof.
    """
    access_token = get_access_token(CLIENT_ID, CLIENT_SECRET)
    
    if not access_token:
        print("❌ Halting script: Could not obtain access token.")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    # Construct the specific URL for this control's proof endpoint
    control_proof_url = f"{CONTROLS_API_URL}/{control_id}/proof"

    print(f"\nAttempting to upload proof for control {control_id}...")
    print(f"File: {file_to_upload}")
    print(f"URL: {control_proof_url}")
    
    try:
        # Open the file in binary-read ('rb') mode
        with open(file_to_upload, 'rb') as f:
            
            # Create the files payload, using the 'proof' key
            if content_type:
                # Send with a specific content type
                files_payload = {'proof': (file_to_upload, f, content_type)}
            else:
                # Let 'requests' guess the content type
                files_payload = {'proof': (file_to_upload, f)}
            
            response = requests.post(
                control_proof_url, 
                headers=headers, 
                files=files_payload
            )
            
            response.raise_for_status()  # Raise an exception for 4xx/5xx errors
            
        logger.info(f"Successfully added proof to control {control_id}")
        return response.json()
    
    except FileNotFoundError:
        logger.error(f"File not found at path: {file_to_upload}")
        return None
    except requests.exceptions.HTTPError as err:
        logger.error(f"HTTP error occurred: {err} - {err.response.text}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None

def create_label(label_name, description=""):
    """
    Creates a new label in the organization.

    :param label_name: The name for the new label (e.g., "Q4 Evidence Set").
    :param description: An optional description for the label.
    :return: Response data for the new label, or None on failure.
    """
    access_token = get_access_token(CLIENT_ID, CLIENT_SECRET)
    
    if not access_token:
        print("❌ Halting script: Could not obtain access token.")
        sys.exit(1)

    # Headers: Must include 'Content-Type: application/json'
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # This is the JSON data we will send to the API
    payload = {
        "name": label_name,
        "description": description
    }

    print(f"\nAttempting to create label: {label_name}...")
    
    try:
        # Use 'json=payload' to send the data as JSON
        response = requests.post(
            LABELS_API_URL, 
            headers=headers, 
            json=payload
        )
        
        response.raise_for_status()  # Raise an exception for 4xx/5xx errors
            
        logger.info(f"Successfully created label")
        return response.json()
    
    except requests.exceptions.HTTPError as err:
        logger.error(f"HTTP error occurred: {err} - {err.response.text}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None

def add_label_proof(label_id, file_to_upload, content_type=None):
    """
    Uploads a proof file and links it to a specific label.

    :param label_id: The ID of the label to link the proof to.
    :param file_to_upload: Path to the proof file to upload.
    :param content_type: The MIME type of the file (e.g., 'application/pdf'), optional.
    :return: Response data of the newly added proof.
    """
    access_token = get_access_token(CLIENT_ID, CLIENT_SECRET)
    
    if not access_token:
        print("❌ Halting script: Could not obtain access token.")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    # Construct the specific URL for this label's proof endpoint
    label_proof_url = f"{LABELS_API_URL}/{label_id}/proof"

    print(f"\nAttempting to upload proof for label {label_id}...")
    print(f"File: {file_to_upload}")
    print(f"URL: {label_proof_url}")
    
    try:
        # Open the file in binary-read ('rb') mode
        with open(file_to_upload, 'rb') as f:
            
            # Create the files payload, using the 'proof' key
            if content_type:
                # Send with a specific content type
                files_payload = {'proof': (file_to_upload, f, content_type)}
            else:
                # Let 'requests' guess the content type
                files_payload = {'proof': (file_to_upload, f)}
            
            response = requests.post(
                label_proof_url, 
                headers=headers, 
                files=files_payload
            )
            
            response.raise_for_status()  # Raise an exception for 4xx/5xx errors
            
        logger.info(f"Successfully added proof to label {label_id}")
        return response.json()
    
    except FileNotFoundError:
        logger.error(f"File not found at path: {file_to_upload}")
        return None
    except requests.exceptions.HTTPError as err:
        logger.error(f"HTTP error occurred: {err} - {err.response.text}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None

def link_label_to_control(control_id, label_id):
    """
    Links an existing label (and all its proof) to a specific control.

    :param control_id: The ID of the control to link to.
    :param label_id: The ID of the label you want to link.
    :return: True on success, None on failure.
    """
    access_token = get_access_token(CLIENT_ID, CLIENT_SECRET)
    
    if not access_token:
        print("❌ Halting script: Could not obtain access token.")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    # Construct the specific URL for linking
    link_url = f"{CONTROLS_API_URL}/{control_id}/labels/{label_id}"

    print(f"\nAttempting to link label {label_id} to control {control_id}...")
    
    try:
        # This is a POST request, likely with no body, to create the link
        response = requests.post(
            link_url, 
            headers=headers
        )
        
        response.raise_for_status()  # Raise an exception for 4xx/5xx errors
            
        # A 204 (No Content) or 200/201 response means success
        logger.info(f"Successfully linked label to control {control_id}")
        return True
    
    except requests.exceptions.HTTPError as err:
        logger.error(f"HTTP error occurred: {err} - {err.response.text}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None

if __name__ == "__main__":
    file_path = "pony.png"
    """
    # Upload a proof to the control
    
    file_path = "pony.png"
    #my_control_id = "e0683e57-b3d1-11f0-a50c-5a2610f6476"
    my_control_id = "66487523-b549-11f0-a533-66e583c0e6b"
    control_proof_response = add_control_proof(
        control_id=my_control_id, 
        file_to_upload=file_path
    )
    print(control_proof_response)
    print(control_proof_response['id'])
    # Update the proof version
    # existing_proof_id = "d900feff-b544-11f0-887b-225afa432b2"
    # 
    #file_path = "proof_link.pdf"
    #existing_proof_id = "7c0b1e54-b55b-11f0-8f4a-ce80ddcc03c"
    existing_proof_id = control_proof_response['id']
    version_response = add_proof_version(
        proof_id=existing_proof_id, 
        file_to_upload=file_path
    )
    print(version_response)

    """

    new_label_name = "Sophia Shared Evidence"
    new_label_desc = "All evidence collected for the Q4 2025 audit"

    label_response = create_label(new_label_name, new_label_desc)

    if label_response:
        new_label_id = label_response['id']    
        new_label_name = "Sophia Shared Evidence"
        new_label_desc = "All evidence collected for the Q4 2025 audit"

    label_proof_response = add_label_proof(
        label_id=new_label_id, 
        file_to_upload=file_path, 
    )

    control_id_A = "e0683e57-b3d1-11f0-a50c-5a2610f6476"
    control_id_B = "66487523-b549-11f0-a533-66e583c0e6b"
    link_label_to_control(control_id_A, new_label_id)
    link_label_to_control(control_id_B, new_label_id)
