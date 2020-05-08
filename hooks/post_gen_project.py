#!/usr/bin/env python3

import yaml
import sys
from passlib.hash import sha512_crypt
from jsonpath2 import Path


class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def write_yaml(filename, d):
    try:
        with open(filename, 'w') as file:
            yaml.SafeDumper = NoAliasDumper
            yaml.safe_dump(d, file, default_flow_style=False)
    except Exception as _:
        sys.exit('Can not create %s\nERROR: %s' % (filename, _))


def jp2query(json_data_to_query, query_expression):
    """Query JSON data using JSONPath2

    Arguments:
        json_data_to_query {JSON} -- any JSON data
        query_expression {string} -- JSONPath2 query string

    Returns:
        value_list {list} -- list of matched values
    """
    jp2_expr = Path.parse_str(query_expression)
    value_list = list()
    node_jsonpath_list = list()
    for m in jp2_expr.match(json_data_to_query):
        value_list.append(m.current_value)
        node_jsonpath_list.append(m.node.tojsonpath())
    
    return value_list


# buld DC group vars
for dc in {{ cookiecutter.inventory.dc_list }}:

    dc_group_vars = {
        'local_users': {
            '{{ cookiecutter.ansible_user }}': {
                "privilege": 15,
                "role": "network-admin",
                "sha512_password": sha512_crypt.hash("{{cookiecutter.ansible_password}}", salt="mysalt")
            }
        },
        'cvp_instance_ip': '{{ cookiecutter.ansible_host }}',
        'cvp_ingestauth_key': '{{ cookiecutter.cvp.ingest_key }}',
        'mgmt_gateway': '{{ cookiecutter.mgmt_settings.oob_gateway }}'
    }

    name_server_list = list()
    for name_server in {{ cookiecutter.mgmt_settings.name_server_list }}:
        name_server_list.append(name_server)
    dc_group_vars.update({
        'name_servers': name_server_list
    })

    ntp_server_list = list()
    for ntp_server in {{ cookiecutter.mgmt_settings.ntp_server_list }}:
        ntp_server_list.append(ntp_server)
    dc_group_vars.update({
        'ntp_servers': ntp_server_list
    })

    write_yaml(f'group_vars/{dc["dc_name"]}.yml', dc_group_vars)

    # build fabric vars
    fabric_vars = {
        'fabric_name': f"{dc['dc_name']}_FABRIC",
        'underlay_p2p_network_summary': dc['underlay_p2p_network_summary'],
        'overlay_loopback_network_summary': dc['overlay_loopback_network_summary'],
        'vtep_loopback_network_summary': dc['vtep_loopback_network_summary'],
        'mlag_ips': {
            'leaf_peer_l3': dc['mlag_ips']['leaf_peer_l3'],
            'mlag_peer': dc['mlag_ips']['mlag_peer']
        },
        'vxlan_vlan_aware_bundles': dc['vxlan_vlan_aware_bundles'],
        'bgp_peer_groups': {
            # TODO: add encryption
            'IPv4_UNDERLAY_PEERS': {
                'password': dc['bgp_peer_groups']['IPv4_UNDERLAY_PEERS']['password']
            },
            'EVPN_OVERLAY_PEERS': {
                'password': dc['bgp_peer_groups']['EVPN_OVERLAY_PEERS']['password']
            },
            'MLAG_IPv4_UNDERLAY_PEER': {
                'password': dc['bgp_peer_groups']['MLAG_IPv4_UNDERLAY_PEER']['password']
            }
        },
        'spine': dc['spine'],
        'l3leaf': {
            'defaults': dc['l3leaf']['defaults'],
            'node_groups': dict()
        },
        'spine_bgp_defaults': dc['spine_bgp_defaults'],
        'leaf_bgp_defaults': dc['leaf_bgp_defaults'],
        'p2p_uplinks_mtu': dc['p2p_uplinks_mtu'],
        'bfd_multihop': dc['bfd_multihop']
    }
    # add spine parameters to group vars for every spine in the inventory
    spine_group_entry = jp2query(dc, '$..group_list[*][?(@.group_name = "SPINES")]')  # jsonpath query
    spine_list = spine_group_entry[0]['host_list']  # we only expect single match
    fabric_vars['spine'].update({
        'nodes': dict()
    })
    for index, spine in enumerate(spine_list):
        fabric_vars['spine']['nodes'].update({
            spine['hostname']: {
                'id': index+1,
                'mgmt_ip': spine['ansible_host']
            }
        })
    # add leaf parameters to group vars
    leaf_index = 1
    for group in dc['group_list']:
        if 'LEAFS' in group['group_name'].upper():
            for subgroup in group['subgroup_list']:
                fabric_vars['l3leaf']['node_groups'].update({
                    subgroup['subgroup_name']: {
                        'bgp_as': subgroup['bgp_as'],
                        'nodes': dict()
                    }
                })
                for node in subgroup['host_list']:
                    fabric_vars['l3leaf']['node_groups'][subgroup['subgroup_name']]['nodes'].update({
                        node['hostname']: {
                            'id': leaf_index,
                            'mgmt_ip': node['ansible_host'],
                            'spine_interfaces': node['spine_interfaces']
                        }
                    })

    write_yaml(f"group_vars/{dc['dc_name']}_FABRIC.yml", fabric_vars)
