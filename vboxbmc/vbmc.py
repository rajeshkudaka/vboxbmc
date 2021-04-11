#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import xml.etree.ElementTree as ET
import time
import virtualbox
from virtualbox.library import MachineState as vmstate

import pyghmi.ipmi.bmc as bmc

from vboxbmc import exception
from vboxbmc import log
from vboxbmc import utils

LOG = log.get_logger()

# Power states
POWEROFF = 0
POWERON = 1

# From the IPMI - Intelligent Platform Management Interface Specification
# Second Generation v2.0 Document Revision 1.1 October 1, 2013
# https://www.intel.com/content/dam/www/public/us/en/documents/product-briefs/ipmi-second-gen-interface-spec-v2-rev1-1.pdf
#
# Command failed and can be retried
IPMI_COMMAND_NODE_BUSY = 0xC0
# Invalid data field in request
IPMI_INVALID_DATA = 0xcc

# Boot device maps
GET_BOOT_DEVICES_MAP = {
    'Network': 4,
    'HardDisk': 8,
    'DVD': 0x14,
}

SET_BOOT_DEVICES_MAP = {
    'network': virtualbox.library.DeviceType.network,
    'hd': virtualbox.library.DeviceType.hard_disk,
    'optical': virtualbox.library.DeviceType.dvd,
    'null': virtualbox.library.DeviceType.null,
}


class VBoxBMC(bmc.Bmc):

    def __init__(self, username, password, port, address,
                 vm_name, **kwargs):
        super(VBoxBMC, self).__init__({username: password},
                                         port=port, address=address)
        self.vbox = virtualbox.VirtualBox()
        self.vm_name = vm_name

    def get_power_state(self):
        LOG.debug('Get power state called for vm %(vm)s',
                  {'vm': self.vm_name})
        try:
            vm = self.vbox.find_machine(self.vm_name)
            if vm.state == vmstate.running:
                return POWERON
        except Exception as e:
            msg = ('Error getting the power state of vm %(vm)s. '
                   'Error: %(error)s' % {'vm': self.vm_name,
                                         'error': e})
            LOG.error(msg)
            raise exception.VBoxBMCError(message=msg)
        return POWEROFF

    def power_shutdown(self):
        LOG.debug('Power shutdown(soft) called for vm %(vm)s',
                  {'vm': self.vm_name})
        try:
            vm = self.vbox.find_machine(self.vm_name)
            if vm.state == vmstate.powered_off:
                LOG.info("VM %(vm)s is already in powered off state.", {'vm': self.vm_name })
            else:
                with vm.create_session() as session:
                    session.console.power_button()
        except Exception as e:
            LOG.error('Error power shutdown(soft) the vm %(vm)s. '
                      'Error: %(error)s', {'vm': self.vm_name,
                                           'error': e})
            # Command failed, but let client to retry
            return IPMI_COMMAND_NODE_BUSY

    def power_off(self):
        LOG.debug('Power off called for vm %(vm)s',
                  {'vm': self.vm_name})
        try:
            vm = self.vbox.find_machine(self.vm_name)
            if vm.state == vmstate.powered_off:
                LOG.info("VM %(vm)s is already in powered off state.", {'vm': self.vm_name })
            else:
                with vm.create_session() as session:
                    session.console.power_down()
        except Exception as e:
            LOG.error('Error powering off the vm %(vm)s. '
                      'Error: %(error)s', {'vm': self.vm_name,
                                           'error': e})
            # Command failed, but let client to retry
            return IPMI_COMMAND_NODE_BUSY

    def power_on(self):
        LOG.debug('Power on called for vm %(vm)s',
                  {'vm': self.vm_name})
        try:
            vm = self.vbox.find_machine(self.vm_name)
            if vm.state == vmstate.running:
                LOG.info("VM %(vm)s is already running.", {'vm': self.vm_name })
            else:
                with virtualbox.Session() as session:
                    progress = vm.launch_vm_process(session, 'headless', [])
                    while session.state._value != session.state.locked._value:
                        LOG.info("Waiting for session to reach LOCKED state. Sleeping for 2s")
                        time.sleep(2)
        except virtualbox.library.OleErrorUnexpected as e:
            LOG.warn(e)
        except Exception as e:
            LOG.error('Error powering on the vm %(vm)s. '
                      'Error: %(error)s', {'vm': self.vm_name,
                                           'error': e})
            # Command failed, but let client to retry
            return IPMI_COMMAND_NODE_BUSY

    def power_reset(self):
        LOG.debug('Power reset called for vm %(vm)s',
                  {'vm': self.vm_name})
        try:
            vm = self.vbox.find_machine(self.vm_name)
            if vm.state == vmstate.powered_off:
                LOG.info("VM %(vm)s is in powered off state. Cannot reset.", {'vm': self.vm_name })
            else:
                with vm.create_session() as session:
                    session.console.reset()
            session.unlock_machine()
        except Exception as e:
            LOG.error('Error reseting the vm %(vm)s. '
                      'Error: %(error)s', {'vm': self.vm_name,
                                           'error': e})
            # Command failed, but let client to retry
            return IPMI_COMMAND_NODE_BUSY

    def get_boot_device(self):
        LOG.debug('Get boot device called for %(vm)s',
                  {'vm': self.vm_name})
        vm = self.vbox.find_machine(self.vm_name)
        return GET_BOOT_DEVICES_MAP.get(vm.get_boot_order(1).__str__ ,0)

    def set_boot_device(self, bootdevice):
        LOG.debug('Set boot device called for %(vm)s with boot '
                  'device "%(bootdev)s"', {'vm': self.vm_name,
                                           'bootdev': bootdevice})

	device_types = SET_BOOT_DEVICES_MAP.keys()
        device_types.remove(bootdevice)
        device_types.remove('null')
        device_types.insert(0, bootdevice)
        vm = self.vbox.find_machine(self.vm_name)

        with vm.create_session() as session:
            LOG.debug('Setting all boot devices to null.')
            for pos in range(1,5):
                session.machine.set_boot_order(pos, SET_BOOT_DEVICES_MAP.get('null'))

            for pos, dev in enumerate(device_types):
                LOG.debug('Setting boot order, device: %(device)s, position: %(position)s',
                          {'device': dev, 'position': pos + 1})
                if dev == bootdevice:
                    session.machine.set_boot_order(pos + 1, SET_BOOT_DEVICES_MAP.get(dev))
                else:
                    session.machine.set_boot_order(pos + 1, SET_BOOT_DEVICES_MAP.get(dev))
            session.machine.save_settings()
                
                         
