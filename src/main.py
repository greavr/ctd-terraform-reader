from python_terraform import *
from typing import List
import os, shutil, json

# Variables
project_directory = "/home/rgreaves/code/opencloud"
terraform_folder = "demo/terraform"
terraform_project = "keep-empty-project"
firestore_project = "rgreaves-gke-chaos"
terraform_variables = {
    'project_id' : terraform_project,
    'project_name' : 'test',
    'project_number' : 'test',
    'gcp_account_name' : 'test',
    'deployment_service_account_name' : 'test',
    'org_id' : 'test',
    'data_location' : 'test',
    'secret_stored_project' : 'test'
}

def save_values_to_firestore(save_data: dict, save_project: str):
    """ This function saves values to firestore"""
    import firebase_admin
    from firebase_admin import credentials
    from firebase_admin import firestore

    # Use the application default credentials.
    cred = credentials.ApplicationDefault()

    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print(f"Writing values to firestore in the project: {save_project}")
    # Itterate over dictonary
    for a_repo in save_data:
        print(f"-> Saving values for repo: {a_repo}")
        doc_ref = db.collection(u'terraform_resources').document(a_repo)
        doc_ref.set(save_data[a_repo])


def build_terraform_repo_list(dir_path: str = "/home/rgreaves") -> List[str]:
    """ This function checks each root folder in the project_directory to see if it has a terraform folder, if so adds to return list"""
    found_repos = []

    # Iterate root directory
    for path in os.listdir(dir_path):
        # Check if sub folder exists
        check_path = os.path.join(os.path.join(dir_path, path),terraform_folder)
        print(f"Checking path: {os.path.join(dir_path, path)}")
        if os.path.isdir(check_path):
            found_repos.append(check_path)

    return found_repos

def remove_tf_plan(terraform_path:str ) -> bool:
    """ This function cleans up the git repo folder"""
    print(f"> Cleaning up folder: {terraform_path}")

    # Removing lock file
    try:
        # Lock file
        lock_file = os.path.join(terraform_path,".terraform.lock.hcl")
        if os.path.isfile(lock_file):
            os.remove(lock_file)

        # Modules
        module_folder = os.path.join(terraform_path,".terraform")
        if os.path.exists(module_folder):
            shutil.rmtree(module_folder)

        return True
    except Exception as e:
        print(f"!!!Unable to clean the repo {terraform_path}")
        print(e)
        return False

def build_tf_plan(terraform_path:str ) -> str:
    """ This function returns list of terraform objects"""
    try:
        print(f"Working on repo: {terraform_path}")
        tf = Terraform(working_dir=terraform_path, variables=terraform_variables)
        tf.init()
        return_code, stdout, stderr = tf.plan(input=False, lock=False, detailed_exitcode=False, json=True)

        # Clean up folder
        remove_tf_plan(terraform_path=terraform_path)

        # Send Return
        return stdout.strip()
    except Exception as e:
        print(f"Error: Unable to run TF on {terraform_path}")
        print(e)

def process_plan(plan_details: str, plan_name: str) -> dict:
    """ This function parses the plan and looksup the Google Cloud price for the resource"""
    print(f"- Looking up resources in repo {plan_name}")

    # Split by new line
    plan_list = plan_details.split('\n')
    found_resources = {}

    # Itterate over all lines of the plan
    for a_line in plan_list:
        # Json Load the data
        this_resource_raw = json.loads(a_line)
        # Check if resource_type key exists
        if 'change' in this_resource_raw:
            if 'resource_type' in this_resource_raw['change']['resource']:
                # Resource type found meaning new resource created
                this_resource_type = this_resource_raw['change']['resource']['resource_type']
                this_resource_name = this_resource_raw['change']['resource']['resource_name']

                # Only add google_resouce
                if "google" in this_resource_type:
                    # Add value to found results
                    if this_resource_type not in found_resources:
                        found_resources[this_resource_type] = []

                    # Append resource name
                    found_resources[this_resource_type].append(this_resource_name)

    return found_resources
    
if __name__ == "__main__":
    ## Build project list
    found_repo_list = build_terraform_repo_list(dir_path=project_directory)

    raw_terraform = {}
    #Itterate over list
    for a_repo in found_repo_list:
        repo_name = a_repo.split('/')[-3]
        raw_terraform[repo_name] = build_tf_plan(terraform_path=a_repo)

    deployed_resources_per_repo = {}

    # Build out plan summary
    for a_plan in raw_terraform:
        deployed_resources_per_repo[a_plan] = process_plan(plan_details=raw_terraform[a_plan], plan_name=a_plan)

    # Finally write data to firestore
    save_values_to_firestore(save_data=deployed_resources_per_repo, save_project=firestore_project)
