#!/usr/bin/python

import requests
import atexit
import ssl
import requests
import json

from pyVim import connect
from pyVim.connect import SmartConnect
from pyVmomi import vim, vmodl
from ansible.module_utils.basic import AnsibleModule

class AnsibleVMWareGuestNic( object ):


  def __init__( self , module ):

    self.module = module
    self.result = { 'changed' : False }
    self.params = module.params
    self.sslVerify = ssl.SSLContext( ssl.PROTOCOL_TLSv1 )
    self.sslVerify.verify_mode = ssl.CERT_NONE
    self.service_instance = SmartConnect( host = self.params['hostname'] , user = self.params['username'] , pwd = self.params['password'] , sslContext = self.sslVerify )
    self.content = self.service_instance.content


  def FindVMWareObject( self , vimtype, name, first=True):
    container = self.content.viewManager.CreateContainerView(container=self.content.rootFolder, recursive=True, type=vimtype)
    obj_list = container.view
    container.Destroy()

    # Backward compatible with former get_obj() function
    if name is None:
      if obj_list:
        return obj_list[0]
      return None

    # Select the first match
    if first is True:
      for obj in obj_list:
        if obj.name == name:
          return obj

      # If no object found, return None
      return None

    # Return all matching objects if needed
    return [obj for obj in obj_list if obj.name == name]


  def WaitForTasks( self , service_instance, tasks ):
      
    property_collector = service_instance.content.propertyCollector
    task_list = [str(task) for task in tasks]

    # Create filter
    obj_specs = [vmodl.query.PropertyCollector.ObjectSpec(obj=task) for task in tasks]
    property_spec = vmodl.query.PropertyCollector.PropertySpec(type=vim.Task , pathSet=[] , all=True)

    filter_spec = vmodl.query.PropertyCollector.FilterSpec()
    filter_spec.objectSet = obj_specs
    filter_spec.propSet = [property_spec]

    pcfilter = property_collector.CreateFilter(filter_spec, True)

    try:
      version, state = None, None

      # Loop looking for updates till the state moves to a completed state.
      while len(task_list):
        update = property_collector.WaitForUpdates(version)
        for filter_set in update.filterSet:
          for obj_set in filter_set.objectSet:
            task = obj_set.obj
            for change in obj_set.changeSet:
              if change.name == 'info':
                state = change.val.state
              elif change.name == 'info.state':
                state = change.val
              else:
                continue
  
              if not str(task) in task_list:
                continue
  
              if state == vim.TaskInfo.State.success:
                # Remove task from taskList
                task_list.remove(str(task))
              elif state == vim.TaskInfo.State.error:
                raise task.info.error
        # Move to next version
        version = update.version
    finally:
      if pcfilter:
        pcfilter.Destroy()


  def NetworkAdapterCount( self , vm ):
    
    count = 0

    for attr in vm.config.hardware.device:
      if isinstance(attr, vim.vm.device.VirtualEthernetCard):
        count += 1

    return count


  def HardwareAddresses( self , vm ):

    addresses = []

    while len(addresses) == 0:
      for mac in vm.guest.net:
        addresses.append(mac.macAddress)

    return addresses


  def GetListDelta( self , list1 , list2 ):

    diff = None

    for itm in list1:
      if itm not in list2:
        diff = itm

    return diff


  def NetworkAdapterFacts( self , vm , hwAddress ):

    facts = {
      'hostName'            :     None,
      'macAddress'          :     None,
      'addresses'           :     { 'ipv4' : 'unassigned' , 'ipv6' : 'unassigned' },
      'deviceInfo'          :     {},
      'connectInfo'         :     {}
    }

    # Set Hostname
    facts['hostName'] = vm.guest.hostName

    # Set the Virtual Ethernet Card info
    for attr in vm.config.hardware.device:
      if isinstance(attr, vim.vm.device.VirtualEthernetCard):
        if attr.macAddress == hwAddress:
          facts['macAddress'] = attr.macAddress
          facts['wakeOnLanEnabled'] = attr.wakeOnLanEnabled
          facts['addressType'] = attr.addressType

          # vim.Description
          facts['deviceInfo']['label'] = attr.deviceInfo.label
          facts['deviceInfo']['summary'] = attr.deviceInfo.summary

          # vim.vm.device.VirtualDevice.ConnectInfo
          facts['connectInfo']['startConnected'] = attr.connectable.startConnected
          facts['connectInfo']['allowGuestControl'] = attr.connectable.allowGuestControl
          facts['connectInfo']['connected'] = attr.connectable.connected
          facts['connectInfo']['status'] = attr.connectable.status  

    # Get Ip Information for Virtual Ethernet Card
    for nic in vm.guest.net:
      if nic.macAddress == hwAddress:
        for ipAddress in nic.ipConfig.ipAddress:
          if ipAddress.state == 'preferred':
            facts['addresses']['ipv4'] = ipAddress.ipAddress
          else:
            facts['addresses']['ipv6'] = ipAddress.ipAddress

    if facts['macAddress'] is None:
      self.module.fail_json( msg='No interface with hardware address ' + hwAddress + ' found on VM ' + self.module.params['name'] )
    else:
      return facts


  def GatherNetworkAdapterFacts( self , vm , hwAddress ):
    facts = self.NetworkAdapterFacts( vm , hwAddress )
    self.module.exit_json( json=facts )


  def DeleteNetworkAdapter( self , vm , hwAddress ):

    nic_facts = self.NetworkAdapterFacts( vm , hwAddress )

    if nic_facts['macAddress'] is None:
      self.result['changed'] = False
      self.module.fail_json( msg='No interface with hardware address ' + hwAddress + ' found on VM ' + self.module.params['name'] )
    else:
      nic_label = nic_facts['deviceInfo']['label']    

    nic_count = self.NetworkAdapterCount( vm )

    if nic_count == 1:
      self.result['changed'] = False
      self.module.fail_json( msg='There is only 1 Network Interface attached to this Virtual Machine. So, we wont be deleting it.' )

    nic = None

    for dev in vm.config.hardware.device:
      if isinstance(dev, vim.vm.device.VirtualEthernetCard):
        if dev.deviceInfo.label == nic_label:
          nic = dev

    if not nic:
      self.module.exit_json( msg='No interface with hardware address ' + hwAddress + ' found on VM ' + self.module.params['name'] )

    virtual_nic_spec = vim.vm.device.VirtualDeviceSpec()
    virtual_nic_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove
    virtual_nic_spec.device = nic

    spec = vim.vm.ConfigSpec()
    spec.deviceChange = [virtual_nic_spec]

    task = vm.ReconfigVM_Task(spec=spec)
    self.WaitForTasks(self.service_instance, [task])

    self.result['changed'] = True


  def CreateNetworkAdapter( self , vm ):

    configSpec = vim.vm.ConfigSpec()
    nicSpecProperties = []

    nicSpec = vim.vm.device.VirtualDeviceSpec()
    nicSpec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add

    nicSpec.device = vim.vm.device.VirtualVmxnet3()
    nicSpec.device.deviceInfo = vim.Description()
    nicSpec.device.deviceInfo.summary = self.module.params['network']

    # Make sure the network exists
    network = self.FindVMWareObject( [vim.Network], self.module.params['network'] )

    if not network:
      self.result['changed'] = False
      self.module.fail_json( msg='Unable to find network: ' + self.module.params['network'] )
    else:
      nicSpec.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
      nicSpec.device.backing.useAutoDetect = False
      nicSpec.device.backing.network = network
      nicSpec.device.backing.deviceName = self.module.params['network']

    # Setting Default Properties for the new NIC
    nicSpec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
    nicSpec.device.connectable.startConnected = True
    nicSpec.device.connectable.allowGuestControl = True
    nicSpec.device.connectable.connected = False
    nicSpec.device.connectable.status = 'untried'
    nicSpec.device.wakeOnLanEnabled = True
    nicSpec.device.addressType = 'assigned'

    nicSpecProperties.append(nicSpec)
    configSpec.deviceChange = nicSpecProperties

    # Add the NIC and wait for the task to complete in vCenter
    macPreSnapshot = self.HardwareAddresses( vm )
    task = vm.ReconfigVM_Task(spec=configSpec)
    self.WaitForTasks(self.service_instance, [task])

    # Get new MAC Address
    macPostSnapshot = self.HardwareAddresses( vm )
    newMacAddress = self.GetListDelta( macPostSnapshot , macPreSnapshot )

    # Get facts for new NIC
    facts = self.NetworkAdapterFacts( vm , newMacAddress )

    self.result['changed'] = True
    self.module.exit_json( json=facts )


  def ConfigureNetworkAdapter( vm , macAddress ):
  
    adapter_maps = list()
    
    if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
      self.module.fail_json( msg='Virtual Machine is powered on. Turn it off before configuring.' )
  
    for device in vm.config.hardware.device:
      if isinstance(device, vim.vm.device.VirtualEthernetCard):
        adaptermap = vim.vm.customization.AdapterMapping()
        adaptermap.adapter = vim.vm.customization.IPSettings()
        adaptermap.adapter.ip = vim.vm.customization.FixedIp()
        adaptermap.adapter.ip.ipAddress = self.module.params['ipv4']
        adaptermap.adapter.subnetMask = self.module.params['netmask']
        adaptermap.adapter.gateway = self.module.params['gateway']
        adaptermap.macAddress = macAddress
  
        adapter_maps.append(adaptermap)
  
    globalip = vim.vm.customization.GlobalIPSettings()
  
    identity = vim.vm.customization.LinuxPrep()
    identity.hostName = vim.vm.customization.FixedName()
    identity.hostName.name = self.module.params['name']
  
    ipSpec = vim.vm.customization.Specification()
    ipSpec.identity = identity
    ipSpec.nicSettingMap = adapter_maps
    ipSpec.globalIPSettings = globalip
  
    task = vm.Customize(spec=ipSpec)
    self.WaitForTasks(si, [task])
    
    facts = self.NetworkAdapterFacts( vm , macAddress )  

    self.result['changed'] = True
    self.module.exit_json( json=facts )
