#!/usr/bin/python

try:
    import pyVmomi
    from pyVmomi import vim
except ImportError:
    pass

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_text
from ansible.module_utils.vmware_extensions import AnsibleVMWareGuestNic

def main():

    argument_spec = dict(
        hostname=dict(type='str', required=False),
        username=dict(type='str', aliases=['user', 'admin'], required=False),
        password=dict(type='str', aliases=['pass', 'pwd'], required=False, no_log=True),
        port=dict(type='int', default=443),
        validate_certs=dict(type='bool', required=False, default=True),
        name=dict(type='str'),
        macAddress=dict(type='str'),
    )

    module = AnsibleModule(argument_spec=argument_spec)

    vmware = AnsibleVMWareGuestNic(module)

    vm = vmware.FindVMWareObject( [vim.VirtualMachine] , module.params['name'] )

    if vm:
        try:
            facts = vmware.GatherNetworkAdapterFacts( vm , module.params['macAddress'] )
            module.exit_json( facts )
        except Exception as exc:
            module.fail_json(msg="Fact gather failed with exception %s" % to_text(exc))
    else:
        module.fail_json(msg="Unable to gather facts for non-existing VM %s" % module.params.get('uuid') or module.params.get('name'))


if __name__ == '__main__':
    main()

