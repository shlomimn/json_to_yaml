import logging 
from argparse import ArgumentParser 
import json 
import yaml 
import os 

  

  

class IndentDumper(yaml.SafeDumper):  # pylint: disable=too-many-ancestors 
    """ A custom yaml dumper that increases indentation """ 

    def increase_indent(self, flow=False, indentless=False): 
        return super(IndentDumper, self).increase_indent(flow, False) 


def file_is_valid(parser, arg): 
    """ Check whether or not the supplied file exists """ 
    if not os.path.isfile(arg): 
        parser.error("The file %s doesn't exist." % arg) 
    else: 
        return open(arg, 'r') 
  

def directory_is_writeable(parser, path): 
    """ Check if a supplied directory is writeable """ 
    if os.access(path, os.W_OK): 
        return path 
    else: 
        parser.error("%s is not writeable." % path) 
  

def parse_arguments(): 
    """ Parses command line arguments """ 
    parser = ArgumentParser( 
        description='Generate servers.yml from json, the json should conatain Name, ip and components') 
    parser.add_argument('--input-json', dest='input_json', required=True, 
                        type=lambda x: file_is_valid(parser, x), 
                        help='A json with a list of servers with the following data: Name, ip and components.\nExample: [{"Name": "db1","private_ip":"127.0.0.1","components": "solr"}]') 
    parser.add_argument('--output-dir', dest='output_dir', 
                        type=lambda x: directory_is_writeable(parser, x), 
                        default=".", 
                        help='The output directory') 
    parser.add_argument('--alias', dest='alias', 
                        default="no-alias-given", 
                        help='The alias') 
    parser.add_argument('--env', dest='env', 
                        default="onprem", 
                        help='The enviorment') 
    parser.add_argument('--use-public-ip', dest='use_public_ip', action='store_true', 
                        help='Add ansible_host with the public ip of the server') 
    args = parser.parse_args() 
    return args 


def generate_inventory(groups, servers, cluster_tags={}, use_public_ip=False): 
    """ Generate inventory file from servers.yml """ 
    inventoryGroup = 'voyager_servers' 
    inventory = { 
        "all": { 
            "hosts": {}, 
            "children": { 
                inventoryGroup: { 
                    'hosts': {}, 
                    'vars': {} 
                } 
            } 
        } 
    } 

    for server in servers: 
        inventory['all']['hosts'][server] = servers[server] 
        inventory['all']['hosts'][server]['private_ip'] = server 
        if use_public_ip: 
            inventory['all']['hosts'][server]['ansible_host'] = servers[server]['public_ip'] 
        inventory['all']['children'][inventoryGroup]['hosts'][server] = {} 

    for component in groups: 
        inventory['all']['children'][component] = {"hosts": {}} 
        if (component != "cluster"): 
            for server in groups[component]: 
                inventory['all']['children'][component]['hosts'][server] = {} 

    for key in cluster_tags: 
        inventory['all']['children'][inventoryGroup]['vars'][key] = cluster_tags[key] 
    return inventory 
  

def main(): 
    """ Main execution method """ 
    # Configure logger 
    logging.basicConfig( 
        format='[%(levelname)s] %(message)s', level=logging.DEBUG) 
    args = parse_arguments() 
    cluster_tags = { 
        'env': args.env, 
        'alias': args.alias, 
        'project': 'va', 
        'platform': "vmware" 
    } 

    groups = { 
        "cluster": [], 
        "secure": [], 
        "common": [] 
    } 

    servers = {} 
    azure_metadata = {} 

    # Check if input_json was passed and parse it 
    logging.info("input_json supplied, parsing...") 
    input_json = json.load(args.input_json) 

    for custom_host in input_json[1:]: 
        privateIp = custom_host['ip address'] 
        servers[privateIp] = {} 
        if 'extra_disks' in custom_host and not custom_host['extra_disks'].isspace(): 
            logging.info('loading disks for %s...', 
                         custom_host['name']) 
            custom_host['disks'] = json.loads( 
                custom_host['extra_disks'].replace("'", "\"")) 
        custom_host['Name'] = custom_host['name'] 

        if 'componentsNew' in custom_host: 
            custom_host['componentsOld'] = custom_host['components'] 
            custom_host['components'] = custom_host['componentsNew'] 
        custom_components = custom_host['components'].replace(" ", "") 

        for key in custom_host: 
            val = custom_host[key] 
            if isinstance(val, unicode): 
                # remove unicode \n 
                val = ''.join(val.splitlines()) 
            if val: 
                servers[privateIp][key] = val 
        custom_components = custom_components.replace('-', '_') 

        for component in custom_components.split(','): 
            if component not in groups: 
                groups[component] = list() 
            groups[component].extend({privateIp: {}}) 

    with open(args.output_dir+'/servers.yml', 'w') as servers_handler: 
        logging.info('Dumping servers.yml...') 
        yaml.dump(groups, servers_handler, 
                  Dumper=IndentDumper, default_flow_style=False, 
                  explicit_start=True, encoding=('utf-8')) 

    with open(args.output_dir+'/hosts.yml', 'w') as servers_handler: 
        logging.info('Dumping hosts.yml...') 
        yaml.dump(generate_inventory(groups, servers, cluster_tags, args.use_public_ip), servers_handler, 
                  Dumper=IndentDumper, default_flow_style=False, 
                  explicit_start=True, encoding=('utf-8')) 


main() 

