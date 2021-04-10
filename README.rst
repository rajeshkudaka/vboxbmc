==========
VBoxBMC
==========

Overview
--------

A virtualbox BMC for controlling virtual machines using IPMI commands.

Installation
~~~~~~~~~~~~

Note: Only works with python2.7 for now.

.. code-block:: bash

  git clone https://github.com/rajeshkudaka/vboxbmc.git
  cd vboxbmc
  pip install .


Supported IPMI commands
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

  # Power the virtual machine on, off, graceful off, NMI and reset
  ipmitool -I lanplus -U admin -P password -H 127.0.0.1 power on|off|soft|reset

  # Check the power status
  ipmitool -I lanplus -U admin -P password -H 127.0.0.1 power status

  # Set the boot device to network, hd or cdrom
  ipmitool -I lanplus -U admin -P password -H 127.0.0.1 chassis bootdev pxe|disk|cdrom

  # Get the current boot device
  ipmitool -I lanplus -U admin -P password -H 127.0.0.1 chassis bootparam get 5

Project resources
~~~~~~~~~~~~~~~~~

* Source: https://opendev.org/openstack/virtualbmc

Hacks
~~~~~

Use "export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES" to escape the below issue.
This is caused due to Multiprocessing, issue with exiting the process gracefully and reinitializing.

.. code-block:: bash

  objc[6941]: +[__NSCFConstantString initialize] may have been in progress in another thread when fork() was called.
  objc[6941]: +[__NSCFConstantString initialize] may have been in progress in another thread when fork() was called. We cannot safely call it or ignore it in the fork() child process. Crashing instead. Set a breakpoint on objc_initializeAfterForkError to debug.

