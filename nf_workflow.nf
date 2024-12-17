#!/usr/bin/env nextflow
nextflow.enable.dsl=2

// Parameters for the workflow
params.OMETALINKING_YAML = "flow_filelinking.yaml"
params.OMETAPARAM_YAML = "job_parameters.yaml"

//This publish dir is mostly  useful when we want to import modules in other workflows, keep it here usually don't change it
TOOL_FOLDER = "$baseDir/bin"


process downloadTaskResult {
    publishDir "./nf_output", mode: "copy"
    conda "$TOOL_FOLDER/conda_env.yml"

    input:
    path input_params

    output:
    path "task_result.zip", emit: task_file

    script:
    """
    python $TOOL_FOLDER/process_download_task_result.py $input_params task_result.zip
    """
}

process uploadToZenodo {
    publishDir "./nf_output", mode: "copy"
    conda "$TOOL_FOLDER/conda_env.yml"

    input:
    path input_params
    path input_task_file

    output:
    path "output_zenodo_log.txt"

    script:
    """
    python $TOOL_FOLDER/process_upload_zenodo.py $input_params $input_task_file output_zenodo_log.txt
    """
}

workflow {
    yaml_params_ch = Channel.fromPath(params.OMETAPARAM_YAML)

    task_file = downloadTaskResult(yaml_params_ch)
    uploadToZenodo(yaml_params_ch, task_file)
}


