import csv
import os
import requests
import mimetypes

# Authentication constants (as provided)
USERNAME = "anthias"
PASSWORD = "Signage!"

# Endpoint templates
URL_TEMPLATE = "http://{}/api/v1/viewer_current_asset"
FILE_UPLOAD_ENDPOINT_TEMPLATE = "http://{}/api/v2/file_asset"  # For file uploads
ASSET_CREATE_ENDPOINT_TEMPLATE = "http://{}/api/v2/assets"  # For asset creation (and listing assets)

# The specific tag you want to extract
TARGET_TAG = "name"

def get_csv_path():
    """Return the path to the 'apis.csv' file."""
    return os.path.join(os.path.dirname(__file__), 'apis.csv')


def read_apis_from_csv(file_path):
    """
    Reads a list of devices from a CSV file.
    The CSV is assumed to be comma-separated.
    Each row should have an IP and a label.
    """
    apis = []
    with open(file_path, newline='', mode='r') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        for row in reader:
            if not row:
                continue
            ip = row[0].strip()
            label = row[1].strip() if len(row) >= 2 else ip
            apis.append({"ip": ip, "label": label})
    return apis


def upload_file_to_device(ip, file_obj):
    """
    Uploads the file to the device at IP using the file asset endpoint.
    Expects the device to return JSON with "uri" and "ext".
    """
    endpoint = FILE_UPLOAD_ENDPOINT_TEMPLATE.format(ip)
    files = {
        "file_upload": (file_obj.filename, file_obj, file_obj.content_type)
    }
    try:
        response = requests.post(endpoint, files=files, auth=(USERNAME, PASSWORD))
        response.raise_for_status()
        return response.json()  # Expected to contain "uri" and "ext"
    except Exception as e:
        return {"error": str(e)}


def create_asset_for_device(ip, payload):
    """
    Sends the asset creation JSON payload to the device at IP.
    """
    endpoint = ASSET_CREATE_ENDPOINT_TEMPLATE.format(ip)
    print(f"Creating asset on {ip} with payload: {payload}")
    try:
        response = requests.post(endpoint, json=payload, auth=(USERNAME, PASSWORD))
        print(f"Response from {ip}: {response.status_code}, {response.text}")
        response.raise_for_status()
        return {"status": response.status_code, "response": response.json()}
    except requests.exceptions.RequestException as e:
        return {
            "error": str(e),
            "response_text": response.text if 'response' in locals() else "No response",
            "status_code": response.status_code if 'response' in locals() else "No status code"
        }


def create_file_asset_on_selected_devices(file_obj, metadata, selected_ips):
    """
    For file uploads: Performs the two-step process on selected devices.

    metadata: dict containing keys: name, start_date, end_date, duration
    selected_ips: list of IP addresses (as strings) to send the asset to.
    """
    results = {}
    file_mimetype = file_obj.content_type or mimetypes.guess_type(file_obj.filename)[0] or "application/octet-stream"

    for ip in selected_ips:
        file_obj.seek(0)  # Reset file pointer for each device
        upload_response = upload_file_to_device(ip, file_obj)
        if "error" in upload_response:
            results[ip] = {"step": "upload", "error": upload_response["error"]}
            continue

        file_uri = upload_response.get("uri")
        file_ext = upload_response.get("ext")
        if not file_uri or not file_ext:
            results[ip] = {"step": "upload", "error": "Missing 'uri' or 'ext' in upload response."}
            continue

        #Appropriately converts mimetype for payload
        if file_mimetype.startswith("image/"):
            mimetype = "image"
        elif file_mimetype.startswith("video/"):
            mimetype = "video"
        else:
            mimetype = file_mimetype

        payload = {
            "ext": file_ext,
            "name": metadata.get("name"),
            "uri": file_uri,
            "start_date": metadata.get("start_date"),
            "end_date": metadata.get("end_date"),
            "duration": metadata.get("duration"),
            "mimetype": mimetype,
            "is_enabled": True,
            "is_processing": True,
            "nocache": True,
            "play_order": 0,
            "skip_asset_check": True
        }
        asset_response = create_asset_for_device(ip, payload)
        results[ip] = {"step": "create_asset", "result": asset_response}
    return results


def create_url_asset_on_selected_devices(metadata, selected_ips):
    """
    For URL assets: Directly creates the asset on selected devices.

    metadata: dict containing keys: name, asset_url, start_date, end_date, duration
    selected_ips: list of IP addresses (as strings) to send the asset to.
    """
    results = {}
    payload = {
        "ext": "string",
        "name": metadata.get("name"),
        "uri": metadata.get("asset_url"),
        "start_date": metadata.get("start_date"),
        "end_date": metadata.get("end_date"),
        "duration": metadata.get("duration"),
        "mimetype": "webpage",
        "is_enabled": True,
        "is_processing": True,
        "nocache": True,
        "play_order": 0,
        "skip_asset_check": True
    }
    for ip in selected_ips:
        asset_response = create_asset_for_device(ip, payload)
        results[ip] = asset_response
    return results


# --- NEW FUNCTION FOR VIEWING ASSETS ---
def get_assets_from_device(ip):
    """
    Retrieves the list of assets from the device at IP using a GET request on the assets endpoint.
    Endpoint: http://{ip}/api/v2/assets
    Expects the response to be a JSON array (or an object containing an array) of asset objects.
    """
    endpoint = ASSET_CREATE_ENDPOINT_TEMPLATE.format(ip)
    try:
        response = requests.get(endpoint, auth=(USERNAME, PASSWORD))
        response.raise_for_status()
        return response.json()  # Should return a list of asset objects
    except Exception as e:
        return {"error": str(e)}


def get_all_inactive_assets():
    """
    Retrieves assets from all devices (as listed in the CSV) and returns only those with "is_active": false.
    Returns a dictionary with device IPs as keys and lists of inactive asset objects as values.
    """
    inactive_assets = {}
    csv_file = get_csv_path()
    devices = read_apis_from_csv(csv_file)
    for device in devices:
        ip = device["ip"]
        assets = get_assets_from_device(ip)
        if isinstance(assets, dict) and assets.get("error"):
            inactive_assets[ip] = {"error": assets["error"]}
        else:
            filtered = [asset for asset in assets if asset.get("is_active") is False]
            inactive_assets[ip] = filtered
    return inactive_assets


def delete_asset_from_device(ip, asset_id):
    """
    Deletes a specific asset from the device at IP.
    Uses the DELETE method on the endpoint: http://{ip}/api/v2/assets/{asset_id}
    """
    endpoint = f"http://{ip}/api/v2/assets/{asset_id}"
    try:
        response = requests.delete(endpoint, auth=(USERNAME, PASSWORD))
        response.raise_for_status()
        return {"status": response.status_code, "message": "Deleted"}
    except Exception as e:
        return {"error": str(e)}


def delete_selected_assets(deletion_list):
    """
    deletion_list is a list of strings in the format "ip|asset_id".
    For each, split and delete the asset.
    Returns a dict with deletion results.
    """
    results = {}
    for item in deletion_list:
        try:
            ip, asset_id = item.split("|", 1)
            result = delete_asset_from_device(ip, asset_id)
            results[item] = result
        except Exception as e:
            results[item] = {"error": str(e)}
    return results

def set_asset_enabled(ip, asset_id, enabled):
        """
        Sets the asset's is_active flag on the device.
        Uses PUT to http://{ip}/api/v2/assets/{asset_id} with JSON { "is_active": <bool> }.
        Returns the device response or an error dict.
        """
        endpoint = f"http://{ip}/api/v2/assets/{asset_id}"
        payload = {"is_enabled": bool(enabled)}

        try:
            response = requests.patch(endpoint, json=payload, auth=(USERNAME, PASSWORD))
            response.raise_for_status()
            try:
                resp_json = response.json()
            except ValueError:
                resp_json = {"text": response.text}
            return {"status": response.status_code, "response": resp_json}
        except requests.exceptions.RequestException as e:
            return {"error": str(e), "response_text": response.text if 'response' in locals() else "No response"}


def set_selected_assets_enabled(item_list, enabled):
    """
    item_list: list of "ip|asset_id" strings
    enabled: boolean to set is_enabled to
    Returns a dict mapping item -> result
    """
    results = {}
    for item in item_list:
        try:
            ip, asset_id = item.split("|", 1)
            results[item] = set_asset_enabled(ip, asset_id, enabled)
        except Exception as e:
            results[item] = {"error": str(e)}
    return results

# -- FROM HERE ON IS FOR ANTHIAS STATUS PAGE --
def fetch_specific_tag(api, username, password, tag):
    """Fetches only the specified tag from the API response."""
    url = URL_TEMPLATE.format(api)
    try:
        response = requests.get(url, auth=(username, password), timeout=5)
        response.raise_for_status()  # Raise an error for bad status codes

        # Parse the JSON and retrieve the specific tag
        json_response = response.json()
        return json_response.get(tag, f"Tag '{tag}' not found")  # Return tag or a default message
    except requests.RequestException:
        return "Offline"

def main():
    csv_file = get_csv_path()
    apis = read_apis_from_csv(csv_file)

    # Step 2: Perform GET requests and retrieve the specific tag
    results = []
    for api_entry in apis:
        ip = api_entry["ip"]
        label = api_entry["label"]
        name = fetch_specific_tag(ip, USERNAME, PASSWORD, TARGET_TAG)
        results.append({"label": label, "name": name})

    return results