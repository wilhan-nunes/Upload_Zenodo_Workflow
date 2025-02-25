import requests
from tqdm import tqdm
import argparse
import yaml


def download_gnps_results(task, output_file, datasource="GNPS2"):
    # If GNPS1, use the old URL, and POST method
    if datasource == "GNPS1":
        url = f"https://gnps.ucsd.edu/ProteoSAFe/DownloadResult?task={task}&view=download_cytoscape_data"
        method = requests.post
    # If GNPS2
    else:
        url = f'https://gnps2.org/taskzip?task={task}'
        method = requests.get

    with method(url, stream=True) as response:
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        with open(output_file, 'wb') as outf:
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

    datasource = params.get('datasource')

    download_gnps_results(task_id, output_path, datasource)

if __name__ == '__main__':
    main()
