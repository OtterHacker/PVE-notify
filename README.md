# PVE-Notify
This project aims to allow Proxmox administrators to setup some limitation on the VM resources created by other users and perform specific action on user creation or modification.

This project is built around python scripts run under inotify events.

# WARNING
Please, read these warnings and the whole README to understand the potential impacts on your infrastructure.

> This is a highly experimental project... Please, spend time reviewing this README and the limit.json configuration to avoid locking down all your proxmox environment.

> Whatever the mess you've done with this script, I cannot be held responsible for it. Either, I cannot be held responsible for any security incident related to one of these scripts.

> If a VM does not match the hardware description set, it will be unable to start

# Scripts
## PVE-inotify
This bash script runs the different inotify hooks.

These hooks will monitor :
- the `user.cfg` file for user creation, allowing environment automation
- the `/etc/pve/nodes/proxmox/qemu-server` directory, allowing `VM` resource restriction
- the `/etc/pve/nodes/proxmox/lxc` directory, allowing `LXC` container resource restriction

## PVE-userenv
This `python` script is called when the `user.cfg` file is modified. It can be used to set a specific environment at user creation or deletion.

At the moment, the script is only designed to perform action that fit my needs. You can easily modify it in the `PVEUser.createEnv` method.

## PVE-vmcreation
This `python` script is called when a `VM` or `LXC` configuration is either created or changed. It can be used to check the different parameters in the configuration and lock the `VM` if it does not comply with the restriction configured.

## PVE-vmstart
This python script is called when a `VM` is started (thanks to `PVE` hookscripts automatically added to every `VM`).
If the `VM` configuration does not comply with the restriction configured, the `VM` start is denied.

# Configuration
## Limits.json 
The `conf/limits.json` file allows defining the VM restriction. At the moment the following value can be configured:

- `NOT_REVIEWED` : list of machines `ID` whose restriction does not apply
- `ADMINISTRATOR` : list of `PVE` groups whose restriction does not apply (every machine created by these users will always comply with the restriction whatever their configuration is)
- `DISK` : Maximal disk size per `VM`
- `RAM` : Maximal RAM size per `VM`
- `BRIDGE` : List of forbidden network interface
- `CORES` : Maximal number of cores per `VM`
- `SOCKETS` : Maximal number of sockets per `VM`
- `LXCPRIVILEGED` : Allow use of privileged `LXC` containers
- `MPPATH` : List of allowed path for `LXC` mountpoint
- `BOOTSTART` : Allow setting the `VM` to start at boot

- `PERUSER.DISK` : Maximal disk size per user (cumulate all `VM` and `LXC`)
- `PERUSER.RAM` : Maximal RAM size per user (cumulate all `VM` and `LXC`)
- `PERUSER.CORE` : Maximal core size per user (cumulate all `VM` and `LXC`)