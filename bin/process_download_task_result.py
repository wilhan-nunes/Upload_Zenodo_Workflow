import requests
from tqdm import tqdm
import argparse
import yaml


def download_gnps2_results(task, outputfile):
    url = f'https://gnps2.org/taskzip?task={task}'
    # session = requests.Session()
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        with open(outputfile, 'wb') as outf:
            with tqdm(total=total_size, unit='B', unit_scale=True, desc="Downloading") as pbar:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        outf.write(chunk)
                        pbar.update(len(chunk))


def main():
    parser = argparse.ArgumentParser(description='Download task results file')
    parser.add_argument('input_yaml_params', help='YAML containing the deposition parameters')
    parser.add_argument('output_task_path', help='Task ZIP/TAR file output path')

    args = parser.parse_args()
    params = yaml.safe_load(open(args.input_yaml_params))
    task_id = params['uploaded_task_id']
    output_path = args.output_task_path

    download_gnps2_results(task_id, output_path)


if __name__ == '__main__':
    main()