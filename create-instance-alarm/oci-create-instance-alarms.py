"""Script to create and enable Critical Alerts for instances in OCI
There is no static information
The script will obtain a list of instances from a compartment and based on that will generate the correspondent alarms
    - CPU Alarm
    - Memory Alarm
    - Infrastructure Health Alarm
 """
from logging import setLogRecordFactory
#from os.path import basename
import oci
from pathlib import Path
from dotenv import load_dotenv
import os



def obtain_compartment_id(identity_client, base_compartment_id):
    #Function to return the compartment OCID from the name selected
    list_compartments_response = identity_client.list_compartments(compartment_id=base_compartment_id,
                                                                    sort_by="NAME")
    compartments_id = []
    compartments_name = []

    for compartment in list_compartments_response.data:
        compartments_name.append(compartment.name)
        compartments_id.append(compartment.id)

    compartments_dict = {compartments_name[i]: compartments_id[i] for i in range(len(compartments_name))}

    #print(compartments_dict)
    return compartments_dict


def select_compartment(compartments_details):
    #Function to select the compartment that we need to work in
    comparments_names_list = []
    print('\n#####################################################\n')
    print('These are the compartments available')
    
    for each_compartment in compartments_details.keys():
        comparments_names_list.append(each_compartment)
    print(comparments_names_list)

    choose_compartment_name = input("""Write the compartment name you require: """)

    for key in compartments_details:
        if key.lower() in choose_compartment_name.lower():
            compartment_id_selected = compartments_details[key]
    
    return compartment_id_selected


def obtain_instances_names(compute_client, compartment_id_selected):
    #Function that return a list of instances from the previous step
    list_of_instance_names = []
    list_instances_response = compute_client.list_instances(compartment_id=compartment_id_selected,
                                sort_order="DESC",
                                lifecycle_state="RUNNING")
    
    for instance in list_instances_response.data:
        #print(instance.display_name)
        instance_name = instance.display_name
        list_of_instance_names.append(instance_name)
    
    print(list_of_instance_names)
    return list_of_instance_names


def create_criticial_cpu_alarm(monitoring_client, list_of_instance_names, compartment_id_selected, list_of_existing_alarms):
    #Create a Critical CPU Alarm for each instance in the compartment
    for each_instance in list_of_instance_names:
        display_name = "CPU-Above-90%-" + each_instance
        if display_name not in list_of_existing_alarms:
            query_string = "CpuUtilization[1m]{resourceDisplayName = "+ "\"" + each_instance + "\"" +"}.mean() > 90"
            create_alarm_response = monitoring_client.create_alarm(
                create_alarm_details = oci.monitoring.models.CreateAlarmDetails(
                                    display_name = display_name,
                                    compartment_id = compartment_id_selected,
                                    metric_compartment_id = compartment_id_selected,
                                    namespace = "oci_computeagent",
                                    query=query_string,
                                    body="The instance CPU has gone above 90%",
                                    severity="CRITICAL",
                                    is_enabled=True,
                                    destinations=[os.environ.get("NOTIFICATION_OCID")],
                                    message_format="PRETTY_JSON"
            ))
            print(create_alarm_response.data)


def create_non_available_instance_alarm(monitoring_client, list_of_instance_names, compartment_id_selected, list_of_existing_alarms):
    #Create a Critical alarm if an instance is not available.
    for each_instance in list_of_instance_names:
        display_name = "Instance-" + each_instance + " Is not available"
        if display_name not in list_of_existing_alarms:
            query_string = "instance_status[5m]{resourceDisplayName = "+ "\"" + each_instance + "\"" +"}.count() < 1"
            create_alarm_response = monitoring_client.create_alarm(
                create_alarm_details = oci.monitoring.models.CreateAlarmDetails(
                                    display_name = display_name,
                                    compartment_id = compartment_id_selected,
                                    metric_compartment_id = compartment_id_selected,
                                    namespace = "oci_compute_infrastructure_health",
                                    query=query_string,
                                    body="Instance Down for at least 5 minutes.",
                                    severity="CRITICAL",
                                    is_enabled=True,
                                    destinations=[os.environ.get("NOTIFICATION_OCID")],
                                    message_format="PRETTY_JSON"
            ))
            print(create_alarm_response.data)


def create_criticial_memory_alarm(monitoring_client, list_of_instance_names, compartment_id_selected, list_of_existing_alarms):
    #Create a Critical Memory Alarm for each instance in the compartment
    for each_instance in list_of_instance_names:
        display_name = "Memory-Utilization-Above-90%-" + each_instance
        if display_name not in list_of_existing_alarms:
            query_string = "MemoryUtilization[1m]{resourceDisplayName = "+ "\"" + each_instance + "\"" +"}.mean() > 90"
            create_alarm_response = monitoring_client.create_alarm(
                create_alarm_details = oci.monitoring.models.CreateAlarmDetails(
                                    display_name = display_name,
                                    compartment_id = compartment_id_selected,
                                    metric_compartment_id = compartment_id_selected,
                                    namespace = "oci_computeagent",
                                    query=query_string,
                                    body="The instance MEMORY has gone above 90%",
                                    severity="CRITICAL",
                                    is_enabled=True,
                                    destinations=[os.environ.get("NOTIFICATION_OCID")],
                                    message_format="PRETTY_JSON"
            ))
            print(create_alarm_response.data)


def query_existing_alarms(monitoring_client, compartment_id_selected):
    #This function allows to query existing alarms 
    list_of_existing_alarms = []

    list_alarms_response = monitoring_client.list_alarms(
                                compartment_id=compartment_id_selected,
                                limit=800,
                                lifecycle_state="ACTIVE",
                                sort_by="displayName",
                                sort_order="ASC"
        ) 
    
    #print(list_alarms_response.data)

    for alarm in list_alarms_response.data:
        list_of_existing_alarms.append(alarm.display_name)

    print(list_of_existing_alarms)
    return list_of_existing_alarms

def run():

    #To get the connection file
    config = oci.config.from_file(os.environ.get("CONFIG_PATH"), os.environ.get("OCI_PROFILE"))
    base_compartment_id = config['tenancy']
    

    # Initialize compute client with default config file
    compute_client = oci.core.ComputeClient(config)
    monitoring_client = oci.monitoring.MonitoringClient(config)

    # Initialize service client with default config file
    identity_client = oci.identity.IdentityClient(config)

    #SELECT THE REQUIRED COMPARTMENT
    compartments_details = obtain_compartment_id(identity_client, base_compartment_id)
    compartment_id_selected = select_compartment(compartments_details)
    
    #Obtain the ID of instances inside the compartment selected from the previous line
    list_of_instance_names = obtain_instances_names(compute_client, compartment_id_selected)

    #Create alarms for each instance
    list_of_existing_alarms = query_existing_alarms(monitoring_client, compartment_id_selected)
    create_criticial_cpu_alarm(monitoring_client, list_of_instance_names, compartment_id_selected, list_of_existing_alarms)
    create_non_available_instance_alarm(monitoring_client, list_of_instance_names, compartment_id_selected, list_of_existing_alarms)
    create_criticial_memory_alarm(monitoring_client, list_of_instance_names, compartment_id_selected, list_of_existing_alarms)

if __name__ == '__main__':
    load_dotenv()
    env_path = Path('.')/'.env'
    load_dotenv(dotenv_path=env_path)
    print("""WELCOME!!!
    This script will allow you to create a cpu based alarm for each instance inside a specific compartment\n
    """)
    run()
