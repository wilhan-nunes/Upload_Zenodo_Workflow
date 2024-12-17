import requests
import argparse
from dotenv import dotenv_values
import json
import yaml
import datetime


def main():
    parser = argparse.ArgumentParser(description='Upload task files to Zenodo')
    parser.add_argument('input_yaml_params', help='YAML containing the deposition parameters')
    parser.add_argument('input_upload_file', help='Task file to upload')
    parser.add_argument('output_deposition_log', help='Path to output log file')

    args = parser.parse_args()

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
        r.raise_for_status()

        new_deposition_json = r.json()
        deposition_id = new_deposition_json['id']
        bucket_url = new_deposition_json["links"]["bucket"]

        # Uploading the file
        with open(path, "rb") as fp:
            r = requests.put(f'{bucket_url}/{path}', data=fp, params=params)
            r.raise_for_status()

        # Sending METADATA to the server
        r = requests.put(f'https://zenodo.org/api/deposit/depositions/{deposition_id}',
                         params={'access_token': ACCESS_TOKEN},
                         data=json.dumps(data),
                         headers=headers)
        r.raise_for_status()

    # logging the results to make it easier to debug
    with open(args.output_deposition_log, 'w') as logf:
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"Log generated on: {current_time}", file=logf)
        print(f"Deposition file: {path}.", file=logf)
        print(f"Deposition metadata sent to Zenodo: \n{json.dumps(data, indent=4)}.", file=logf)

        if not dry_run:
            print(f"Server response code: \n{r.status_code}.", file=logf)
            print(f"Server response : \n{json.dumps(r.json(), indent=4)}.", file=logf)

        if dry_run:
            print(f"### This was just a dry run test. No data was deposited ###", file=logf)


if __name__ == '__main__':
    main()
