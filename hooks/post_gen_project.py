#!/usr/bin/env python3

import yaml
import json
import sys
import os
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
        'spine': {
            'platform': dc['spine']['platform'],
            'bgp_as': int(dc['spine']['bgp_as']),
            'leaf_as_range': dc['spine']['leaf_as_range'],
            'nodes': dict()
        },
        'l3leaf': {
            'defaults': {
                'bgp_as': int(dc['l3leaf']['defaults']['bgp_as']),
                'mlag_interfaces': dc['l3leaf']['defaults']['mlag_interfaces'],
                'platform': dc['l3leaf']['defaults']['platform'],
                'spanning_tree_mode': dc['l3leaf']['defaults']['spanning_tree_mode'],
                'spanning_tree_priority': int(dc['l3leaf']['defaults']['spanning_tree_priority']),
                'spines': dc['l3leaf']['defaults']['spines'],
                'uplink_to_spine_interfaces': dc['l3leaf']['defaults']['uplink_to_spine_interfaces'],
                'virtual_router_mac_address': dc['l3leaf']['defaults']['virtual_router_mac_address'],
            },
            'node_groups': dict()
        },
        'spine_bgp_defaults': dc['spine_bgp_defaults'],
        'leaf_bgp_defaults': dc['leaf_bgp_defaults'],
        'p2p_uplinks_mtu': int(dc['p2p_uplinks_mtu']),
        'bfd_multihop': {
            'interval': int(dc['bfd_multihop']['interval']),
            'min_rx': int(dc['bfd_multihop']['min_rx']),
            'multiplier': int(dc['bfd_multihop']['multiplier'])
        }
    }
    write_yaml("group_vars/SPINES.yml", {'type': 'spine'})  # add spine type
    # add spine parameters to group vars for every spine in the inventory
    spine_group_entry = jp2query(dc, '$..group_list[*][?(@.group_name = "DC1_SPINES")]')  # jsonpath query
    spine_list = spine_group_entry[0]['host_list']  # we only expect single match
    for index, spine in enumerate(spine_list):
        fabric_vars['spine']['nodes'].update({
            spine['hostname']: {
                'id': int(index+1),
                'mgmt_ip': f"{spine['ansible_host']}/" + "{{ cookiecutter.mgmt_settings.subnet_mask_length }}"
            }
        })
    # add leaf parameters to group vars
    leaf_index = 1
    for group in dc['group_list']:
        if 'LEAFS' in group['group_name'].upper():
            write_yaml(f"group_vars/{group['group_name']}.yml", {'type': 'l3leaf'})  # add leaf type
            for subgroup in group['subgroup_list']:
                fabric_vars['l3leaf']['node_groups'].update({
                    subgroup['subgroup_name']: {
                        'bgp_as': int(subgroup['bgp_as']),
                        'nodes': dict()
                    }
                })
                for node in subgroup['host_list']:
                    fabric_vars['l3leaf']['node_groups'][subgroup['subgroup_name']]['nodes'].update({
                        node['hostname']: {
                            'id': int(leaf_index),
                            'mgmt_ip': f"{node['ansible_host']}/" + "{{ cookiecutter.mgmt_settings.subnet_mask_length }}",
                            'spine_interfaces': node['spine_interfaces']
                        }
                    })
                    leaf_index += 1

    write_yaml(f"group_vars/{dc['dc_name']}_FABRIC.yml", fabric_vars)
    # create directory for the fabric documentation
    os.mkdir(f'documentation/{dc["dc_name"]}_FABRIC')

    # add tenant group vars
    tenant_group_vars = {"tenants": dict()}
    for tenant_name, tenant_details in dc['tenants'].items():
        tenant_group_vars['tenants'].update({
            f"{tenant_name}": {
                "mac_vrf_vni_base": int(tenant_details["mac_vrf_vni_base"]),
                "vrfs": dict()
            }
        })
        for vrf_name, vrf_details in tenant_details["vrfs"].items():
            tenant_group_vars['tenants'][f"{tenant_name}"]["vrfs"].update({
                    f"{vrf_name}": {
                        "vrf_vni": int(tenant_details["vrfs"][f"{vrf_name}"]["vrf_vni"]),
                        "vtep_diagnostic": {
                            "loopback": int(tenant_details["vrfs"][f"{vrf_name}"]["vtep_diagnostic"]["loopback"]),
                            "loopback_ip_range": tenant_details["vrfs"][f"{vrf_name}"]["vtep_diagnostic"]["loopback_ip_range"]
                        },
                        "svis": dict()
                    }
                })
            for svi_number, svi_details in vrf_details["svis"].items():
                tenant_group_vars['tenants'][f"{tenant_name}"]["vrfs"][f"{vrf_name}"]["svis"].update({
                    int(f"{svi_number}"): {
                        "name": svi_details["name"],
                        "tags": svi_details["tags"],
                        "enabled": svi_details["enabled"],
                        "ip_subnet": svi_details["ip_subnet"]
                    }
                })
    write_yaml(f"group_vars/{dc['dc_name']}_TENANTS_NETWORKS.yml", tenant_group_vars)

    # add server group vars
    write_yaml(f"group_vars/{dc['dc_name']}_SERVERS.yml", {
        'servers': dc['servers'],
        'port_profiles': dc['port_profiles']
    })
