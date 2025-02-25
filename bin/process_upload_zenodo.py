import argparse
import json
import logging
import os

import requests
import yaml
from dotenv import dotenv_values

# SERVER_URL = 'https://zenodo.org/api/deposit/depositions'
SERVER_URL = 'https://sandbox.zenodo.org/api/deposit/depositions'  # SANDBOX


def setup_logging(log_file):
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - [%(levelname)s]: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def create_empty_upload(access_token):
    headers = {"Content-Type": "application/json"}
    params = {'access_token': access_token}
    url = SERVER_URL
    try:
        r = requests.post(url, params=params, json={}, headers=headers)
        r.raise_for_status()
        new_deposition_json = r.json()
        deposition_id = new_deposition_json['id']
        bucket_url = new_deposition_json["links"]["bucket"]
        logging.info(f"Empty deposition created successfully with ID: {deposition_id}")
        return deposition_id, bucket_url
    except requests.exceptions.RequestException as e:
        logging.error(f"Error creating empty deposition: {e}")
        raise


def upload_file_to_zenodo(bucket_url, path, access_token):
    params = {'access_token': access_token}
    with open(path, "rb") as fp:
        r = requests.put(f'{bucket_url}/{path}', data=fp, params=params)
        if r.status_code == 201:
            logging.info(f"File uploaded successfully.")
        else:
            logging.error(f"Error uploading file. Status code: {r.status_code}")
        r.raise_for_status()


def send_metadata_to_server(deposition_id, data, access_token):
    headers = {"Content-Type": "application/json"}
    r = requests.put(f'{SERVER_URL}/{deposition_id}',
                     params={'access_token': access_token},
                     data=json.dumps(data),
                     headers=headers)
    if r.status_code == 200:
        logging.info(f"Metadata sent successfully to the server.")
    else:
        logging.error(f"Error sending metadata to the server. Status code: {r.status_code}")
    r.raise_for_status()


def delete_deposited_files(deposition_id, params):
    # Delete files already deposited
    files_url = f'{SERVER_URL}/{deposition_id}/files'
    files_response = requests.get(files_url, params=params)
    files_response.raise_for_status()
    files = files_response.json()
    for file in files:
        delete_url = f'{SERVER_URL}/{deposition_id}/files/{file["id"]}'
        delete_response = requests.delete(delete_url, params=params)
        delete_response.raise_for_status()


def create_new_version(deposition_id, access_token):
    url = f'{SERVER_URL}/{deposition_id}/actions/newversion'
    headers = {"Content-Type": "application/json"}
    params = {'access_token': access_token}
    logging.info(f"Creating new version for deposition ID: {deposition_id}")
    try:
        response = requests.post(url, params=params, headers=headers)
        response.raise_for_status()
        new_version = response.json()
        new_deposition_id = new_version['links']['latest_draft'].split('/')[-1]
        logging.info(f"Zenodo deposition ID (new version): {new_deposition_id}")

        delete_deposited_files(new_deposition_id, params)

        return new_deposition_id, new_version['links']['bucket']
    except requests.exceptions.RequestException as e:
        logging.error(f"Error creating new version: {e}")
        raise


def publish_deposition(deposition_id, access_token):
    params = {'access_token': access_token}
    r = requests.post(f'{SERVER_URL}/{deposition_id}/actions/publish',
                      params=params)
    if r.status_code == 202:
        logging.info(f"Deposition published successfully.")
    else:
        logging.error(f"Error publishing deposition. Status code: {r.status_code}")
    r.raise_for_status()


def main():
    parser = argparse.ArgumentParser(description='Upload task files to Zenodo')
    parser.add_argument('input_yaml_params', help='YAML containing the deposition parameters')
    parser.add_argument('input_upload_file', help='Task file to upload')
    parser.add_argument('output_deposition_log', help='Path to output log file')

    args = parser.parse_args()

    setup_logging(args.output_deposition_log)

    parameters_json = yaml.safe_load(open(args.input_yaml_params))
    config = dotenv_values()
    user_token = parameters_json.get("access_token")
    ACCESS_TOKEN = user_token if user_token != '' else config.get("TOKEN")

    # Extracting metadata from the parameters
    creators_list = [{'name': name.strip(), 'affiliation': affiliation.strip()}
                     for name, affiliation in zip(parameters_json['metadata.creators'].split(';')[::2],
                                                  parameters_json['metadata.creators'].split(';')[1::2])]
    keywords = [keyword.strip() for keyword in parameters_json["metadata.keywords"].split(";") if keyword.strip()]

    access_right = parameters_json["metadata.access_right"]
    embargo_date = parameters_json["metadata.embargo_date"]

    # Check for invalid 'embargo_date' with 'open' or 'embargoed' access_right
    if access_right == "embargoed" and not embargo_date:
        raise ValueError("The 'embargo_date' must be provided when 'access_right' is set to 'embargoed'.")
    elif access_right == "open" and embargo_date:
        raise ValueError("The 'embargo_date' must be empty when 'access_right' is set to 'open'.")

    task_id = parameters_json['uploaded_task_id']
    task_url = f"https://gnps.ucsd.edu/ProteoSAFe/status.jsp?task={task_id}" \
        if parameters_json.get('datasource') == 'true' else f"https://gnps2.org/status?task={task_id}"

    task_url_string = f'<a href="{task_url}">GNPS Task link</a>'
    deposition_notes = f'{parameters_json["metadata.notes"]}; {task_url_string}' \
        if parameters_json[
               "metadata.notes"] != '' else f'{task_url_string}'

    data = {
        "metadata": {
            "title": parameters_json["metadata.title"],
            "creators": creators_list,
            "description": parameters_json["metadata.description"],
            "keywords": keywords,
            "upload_type": parameters_json["metadata.upload_type"],
            "version": parameters_json["metadata.version"],
            "access_right": access_right,
            "license": parameters_json["metadata.license"],
            "embargo_date": embargo_date,
            "notes": deposition_notes,
            "related_identifiers": [
                {"identifier": task_url,
                 "relation": "isSupplementTo",
                 "resource_type": "dataset"}]
        }
    }

    dry_run = True if parameters_json['dry_run'] == 'true' else False
    new_version = True if parameters_json.get('zenodo_deposition_id') != '' else False
    path = args.input_upload_file

    if not dry_run:
        if new_version:
            # Create a new version of the deposition
            deposition_id, bucket_url = create_new_version(parameters_json['zenodo_deposition_id'], ACCESS_TOKEN)
        else:
            # Create a new empty upload
            deposition_id, bucket_url = create_empty_upload(ACCESS_TOKEN)

        # Uploading the file
        upload_file_to_zenodo(bucket_url, path, ACCESS_TOKEN)

        # Sending METADATA to the server
        send_metadata_to_server(deposition_id, data, ACCESS_TOKEN)

        # Publish the deposition
        publish_deposition(deposition_id, ACCESS_TOKEN)

    if dry_run:
        logging.warning("### This was just a dry run test. No data was deposited ###")

    size_bytes = os.path.getsize(path)
    file_size = f"{size_bytes / 1024 ** 2:.2f} MB." if size_bytes < 1024 ** 3 else f"{size_bytes / 1024 ** 3:.2f} GB"
    logging.info(f"Deposited file: {path}")
    logging.info(f"Deposited file size: {file_size}")
    logging.info(f"File generated from task ID: {parameters_json['uploaded_task_id']}")
    logging.info(f"Deposition metadata sent to Zenodo: {json.dumps(data, indent=4)}")


if __name__ == '__main__':
    main()
