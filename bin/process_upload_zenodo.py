import requests
import argparse
from dotenv import dotenv_values
import json
import yaml
import os
import logging

def setup_logging(log_file):
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - [%(levelname)s]: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def main():
    parser = argparse.ArgumentParser(description='Upload task files to Zenodo')
    parser.add_argument('input_yaml_params', help='YAML containing the deposition parameters')
    parser.add_argument('input_upload_file', help='Task file to upload')
    parser.add_argument('output_deposition_log', help='Path to output log file')

    args = parser.parse_args()

    setup_logging(args.output_deposition_log)

    parameters_json = yaml.safe_load(open(args.input_yaml_params))
    config = dotenv_values()

    # Workaround to allow multiple creators and affiliations as a txt input string
    creators_string = parameters_json['metadata.creators']
    names = [name.strip() for i, name in enumerate(creators_string.split(';')) if i % 2 == 0]
    affiliations = [affiliation.strip() for i, affiliation in enumerate(creators_string.split(';')) if i % 2 == 1]
    creators_list = [{'name': name, 'affiliation': affiliation} for name, affiliation in
                     dict(zip(names, affiliations)).items()]

    # metadata creation
    keywords = [keyword.strip() for keyword in parameters_json["metadata.keywords"].split(";")]

    access_right = parameters_json["metadata.access_right"]
    embargo_date = parameters_json["metadata.embargo_date"]

    # Check for invalid 'embargo_date' with 'open' or 'embargoed' access_right
    if access_right == "embargoed" and not embargo_date:
        raise ValueError("The 'embargo_date' must be provided when 'access_right' is set to 'embargoed'.")
    elif access_right == "open" and embargo_date:
        raise ValueError("The 'embargo_date' must be empty when 'access_right' is set to 'open'.")

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
            "notes": parameters_json["metadata.notes"]
        }
    }

    dry_run = True if parameters_json['dry_run'] == 'true' else False
    path = args.input_upload_file

    if not dry_run:
        # Create a new empty upload
        ACCESS_TOKEN = parameters_json['access_token']
        headers = {"Content-Type": "application/json"}
        params = {'access_token': ACCESS_TOKEN}
        r = requests.post('https://zenodo.org/api/deposit/depositions', params=params, json={}, headers=headers)
        if r.status_code == 201:
            logging.info(f"Empty deposition created successfully.")
        else:
            logging.error(f"Error creating empty deposition. Status code: {r.status_code}")
        r.raise_for_status()

        new_deposition_json = r.json()
        deposition_id = new_deposition_json['id']
        bucket_url = new_deposition_json["links"]["bucket"]

        # Uploading the file
        with open(path, "rb") as fp:
            r = requests.put(f'{bucket_url}/{path}', data=fp, params=params)
            if r.status_code == 201:
                logging.info(f"File uploaded successfully.")
            else:
                logging.error(f"Error uploading file. Status code: {r.status_code}")
            r.raise_for_status()

        # Sending METADATA to the server
        r = requests.put(f'https://zenodo.org/api/deposit/depositions/{deposition_id}',
                         params={'access_token': ACCESS_TOKEN},
                         data=json.dumps(data),
                         headers=headers)
        if r.status_code == 200:
            logging.info(f"Metadata sent successfully to the server.")
        else:
            logging.error(f"Error sending metadata to the server. Status code: {r.status_code}")
        r.raise_for_status()

        # logging.info(f"Server response code: {r.status_code}")
        # logging.info(f"Server response: {json.dumps(r.json(), indent=4)}")

    if dry_run:
        logging.info("### This was just a dry run test. No data was deposited ###")

    size_bytes = os.path.getsize(path)
    file_size = f"{size_bytes / 1024 ** 2:.2f} MB." if size_bytes < 1024**3 else f"{size_bytes / 1024**3:.2f} GB"
    logging.info(f"Deposited file: {path}")
    logging.info(f"Deposited file size: {file_size}")
    logging.info(f"File generated from task ID: {parameters_json['uploaded_task_id']}")
    logging.info(f"Deposition metadata sent to Zenodo: {json.dumps(data, indent=4)}")

if __name__ == '__main__':
    main()
