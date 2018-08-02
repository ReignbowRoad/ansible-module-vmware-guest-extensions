# VMWare Ansible Module Extensions

This module was written to extend the functionality of the Ansible VMWare modules. 

## Background

I am currently working on an automation project that relies heavily on VMWare. The client has specific use cases they would like to see automated using Ansible. Unfortunately, some of the use cases are not supported by the existing VMWare modules. 

To accomodated the client's request, I wrote this extensions module to provide the desired functionality needed to satisfy their use cases. These functions include:

1. Adding a Network Adapter

2. Removing a Network Adapter

3. Configuring a Network Adapter

   

## Deployment

The recommended way to deploy this would be to `git clone` the project to your Ansible Control Machine. Identify the the Ansible installation path (we'll refer to this as `ANSIBLE_PATH`) and then symlink the files in as below:

```shell
ln -s $PROJECT_PATH/module_utils/vmware_extensions.py $ANSIBLE_PATH/module_utils/
ln -s $PROJECT_PATH/modules/vmware_guest_network_adapter.py $ANSIBLE_PATH/modules/
ln -s $PROJECT_PATH/modules/vmware_guest_network_adapter_facts.py $ANSIBLE_PATH/modules/
```



> **Note**: This is the recommended way to deploy these modules as it will allow you to easily update the modules when new updates are made available via GitHub. To do this, just sync your working copy with the upstream repository.



## Modules

There are two modules provided at the moment:

1. vmware_guest_network_adapter_facts
2. vmware_guest_network_adapter

### vmware_guest_network_adapter_facts

This module will return facts about the specified network adapter. You will need to use the Hardware (MAC) Address as the identifier to get this information.

#### Parameters

| Parameter      | Choices / Defaults | Comments                                                     |
| -------------- | ------------------ | ------------------------------------------------------------ |
| hostname       |                    | The hostname or IP address of the vSphere vCenter or ESXi server. |
| port           |                    | The port number of the vSphere vCenter or ESXi server.       |
| username       |                    | The username of the vSphere vCenter or ESXi server.          |
| password       |                    | The password of the vSphere vCenter or ESXi server.          |
| validate_certs | True      False    | Allows connection when SSL certificates are not valid. Set to `false` when certificates are not trusted. |
| name           |                    | Name of the virtual machine to work with.                    |
| macAddress     |                    | The Hardware Address of the network interface.               |

#### Example

The following example will return facts about the specified Network Interface and display the result:

```yaml
# Gather Facts about a specific Network Interface
- name: Get NIC Facts
  vmware_guest_network_adapter_facts:
    hostname: "vcenter.example.com"
    username: "root"
    password: "p4ssw0rd"
    validate_certs: False
    name: "vm1"
    macAddress: "72:a8:c0:b4:c6:0b"
  register: vm_nic_facts
  
- name: Show NIC Facts
  debug: var=vm_nic_facts
```



### vmware_guest_network_adapter

This module will add, remove or configure the specified Network Adapter:

Parameters

| Parameter      | Choices / Defaults                            | Comments                                                     |
| -------------- | --------------------------------------------- | ------------------------------------------------------------ |
| hostname       |                                               | The hostname or IP address of the vSphere vCenter or ESXi server. |
| port           |                                               | The port number of the vSphere vCenter or ESXi server.       |
| username       |                                               | The username of the vSphere vCenter or ESXi server.          |
| password       |                                               | The password of the vSphere vCenter or ESXi server.          |
| validate_certs | True      False                               | Allows connection when SSL certificates are not valid. Set to false when   certificates are not trusted. |
| state          | absent      present (default)      configured | Specify state of the network   adapter to be in      If `state` is set to `present` and network adapter does not exist then it is   created      If `state` is set to `absent` and network adapter exists, then the specified   network adapter is removed      if `state` is set to `configured` then existing adapater is configured. `ipv4`,   `netmask` and `gateway` must be specified in this state. |
| name           |                                               | Name of the virtual machine to work with.                    |
| macAddress     |                                               | The Hardware Address of the network interface.               |
| ipv4           |                                               | The ipv4 address to assign to Virtual Machine                |
| netmask        |                                               | The subnet mask for the address                              |
| gateway        |                                               | The default gateway for the interface                        |
