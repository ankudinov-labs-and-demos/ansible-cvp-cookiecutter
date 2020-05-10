# ANSIBLE-CVP COOKIECUTTER

<!-- TOC -->

- [ANSIBLE-CVP COOKIECUTTER](#ansible-cvp-cookiecutter)
  - [Description](#description)
  - [Lab Topology](#lab-topology)
  - [Clone Cookiecutter Repository](#clone-cookiecutter-repository)
  - [Preparing the Lab](#preparing-the-lab)
  - [HOW TO RUN](#how-to-run)

<!-- /TOC -->

## Description

A [cokiecutter template](https://github.com/cookiecutter/cookiecutter)  to create an [Arista Ansible-CVP Lab](https://github.com/aristanetworks/ansible-cvp).

## Lab Topology

The lab topology used to test cookiecutter is shown below. It can be adjusted if required.

![Lab Topology](/media/avd-cookiecutter-lab-topology.png)

The lab must be created before using cookiecutter using EVE-NG, GNS3, KVM or similar.

All VMs in the lab should have access to a shared OOB network with a linux machine used to provide DHCP service and to route packets to CVP.

## Clone Cookiecutter Repository

To clone cookiecutter repository run following commands:

```console
python3 -m venv .ccvenv
source .ccvenv/bin/activate
pip install cookiecutter
cookiecutter gh:ankudinov-labs-and-demos/ansible-cvp-cookiecutter --no-input --checkout master --overwrite-if-exists
```

If you want to use different settings, fork/clone the repository and create your own cookiecutter.json first.

Change your current working directory to the project directory created by cookiecutter and run `setup.sh`. This script will create Python virtual environment called `.venv` and install required dependencies.

If you are using VSCode, type `code .`

## Preparing the Lab

Before using the cookiecutter the switches in the lab must be registered on CVP as part of ZTP process.

To accomplish that a DHCP server has to be configured in the OOB network and provide the URL to ZTP script as option 67 (bootfile name).

To install dhcpd run following commands (Ubuntu):

```console
sudo apt install isc-dhcp-server
sudo vi /etc/dhcp/dhcpd.conf
systemctl enable isc-dhcp-server
systemctl start isc-dhcp-server
```

dhcpd.conf file will be generated automatically by cookiecutter. Just copy-paste the content or use it as an example to adjust your DHCP server settings.

All devices should register in Undefined container before you start:
![initial cvp state](media/initial_cvp_state.png)

## HOW TO RUN

tbd
