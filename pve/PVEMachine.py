from pve.PVETools import runCli, DEBUG
import json
import subprocess

class PVEGuest:

    def __init__(self, id, path, minimal=False):
        try:
            file = open(path, 'r')
        except FileNotFoundError:
            raise ValueError("No VM with id {} has been found".format(id))
        data = file.readlines()
        file.close()
        self.id = id
        for elt in data:
            if "[PENDING]" in elt:
                break
            line = elt.strip()
            if line.startswith('#'):
                continue
            attr = line.split(':')[0]
            value = ':'.join(line.split(':')[1:])
            setattr(self, attr, value.strip())


        self.networks = self.getNetworks()
        self.disks = self.getDisks()
        if minimal is not True:
            self.owner = self.getOwner()            
        

    @property
    def totalDiskSize(self):
        totalDiskSize = 0
        for disk in self.disks:
            totalDiskSize += disk['size']
        return totalDiskSize

    def getOwner(self):
        stdout, stderr = runCli('pvesh get /nodes/proxmox/tasks --start 0 --limit 1 --vmid {} --source all --output-format=json-pretty'.format(self.id))
        if stderr != b'':
            return None
        logs = json.loads(stdout.decode())
        for elt in logs:
            return elt['user']
        return None

    
    def getNetworks(self):
        networkList = []
        for elt, value in self.__dict__.items():
            if elt.startswith('net'):
                try:
                    net = value.split('bridge=')[-1]
                except IndexError:
                    continue
                
                try:
                    net = net.split(',')[0]
                except IndexError:
                    pass
                networkList.append({
                    'name': elt,
                    'bridge': net
                })

        return networkList

    def getDisks(self):
        disksList = []
        for elt, value in self.__dict__.items():
            if (
                (
                    (elt.startswith('ide') and 'media' not in elt) or 
                    elt.startswith('sata') or 
                    elt.startswith('scsi') or 
                    elt.startswith('virtio0') or 
                    elt.startswith('rootfs') or
                    elt.startswith('mp')
                ) and
                'size=' in value
            ):
                try:
                    diskSize = value.split('size=')[1]
                except IndexError:
                    continue
                try:
                    diskSize = diskSize.split(',')[0]
                except IndexError:
                    pass

                if diskSize[-1] == 'G':
                    size = int(diskSize[:-1], 10) * 1048576
                else:
                    size = int(diskSize[:-1], 10)
                
                if 'mp=' in value:
                    path = value.split('mp=')[1]
                    try:
                        path = path.split(',')[0]
                    except IndexError:
                        pass
                else:
                    path = ''
                disksList.append({
                    'name':elt,
                    'size': size,
                    'path': path
                })
        return disksList

    def matchRAMLimit(self, limits):
        if self.id in limits['NOT_REVIEWED'] or self.owner in limits['ADMINISTRATORS']:
            return True
        
        try:
            return int(self.memory, 10) <= limits['RAM'] or limits['RAM'] == -1
        except AttributeError:
            return True
    
    def matchDiskLimit(self, limits):
        if self.id in limits['NOT_REVIEWED'] or self.owner in limits['ADMINISTRATORS']:
            return True
        return self.totalDiskSize <= limits['DISK'] or limits['DISK'] == -1

    def matchNetworkLimit(self, limits):
        if self.id in limits['NOT_REVIEWED'] or self.owner in limits['ADMINISTRATORS']:
            return True
        
        for elt in self.networks:              
            if elt['bridge'] in limits['BRIDGE']:
                return False
        return True
        
    def matchCoreLimit(self, limits):
        if self.id in limits['NOT_REVIEWED'] or self.owner in limits['ADMINISTRATORS']:
            return True
        
        return int(self.cores, 10) <= limits['CORES'] and int(self.sockets, 10) <= limits['SOCKETS']

    def matchMountPointLimit(self, limits):
        if self.id in limits['NOT_REVIEWED'] or self.owner in limits['ADMINISTRATORS']:
            return True
        for disk in self.disks:
            if disk['path'] != '':
                isValid = False
                for validPath in limits["MPPATH"]:
                    if disk['path'].startswith(validPath):
                        isValid = True
                if isValid is not True: 
                    return False
        return True
    
    def matchBootStartLimit(self, limits):
        if self.id in limits['NOT_REVIEWED'] or self.owner in limits['ADMINISTRATORS']:
            return True
        try:
            self.onboot
        except AttributeError:
            return True
        return self.onboot != '1' or limits['BOOTSTART']

    def limitsCheck(self, limits):
        DEBUG('\t[-] Checking limits for \n'.format(self.id))
        DEBUG("\t\t [+] The following limits are applied : \n\t\t\t{}\n".format('\n\t\t\t'.join(json.dumps(limits, indent=4).split('\n'))))
        ram = self.matchRAMLimit(limits)
        DEBUG('\t\t[+] RAM           {}\n'.format(ram))
        disk = self.matchDiskLimit(limits)
        DEBUG('\t\t[+] DISK          {}\n'.format(disk))
        network = self.matchNetworkLimit(limits)
        DEBUG('\t\t[+] NETWORK       {}\n'.format(network))
        cores = self.matchCoreLimit(limits)
        DEBUG('\t\t[+] CORES         {}\n'.format(cores))
        mp = self.matchMountPointLimit(limits)
        DEBUG('\t\t[+] MOUNTPOINT    {}\n'.format(mp))
        bootstart = self.matchBootStartLimit(limits)
        DEBUG('\t\t[+] BOOTSTART     {}\n'.format(bootstart))
        return ram and disk and network and cores and mp and bootstart


class PVEVm(PVEGuest):
    def __init__(self, id, minimal=False):
        PVEGuest.__init__(self, id, '/etc/pve/nodes/proxmox/qemu-server/{}.conf'.format(id), minimal)
        try:
            self.hookscript
        except AttributeError:
            runCli('qm set {} --hookscript local:snippets/confcheck_hookscript.pl'.format(self.id))

    @staticmethod
    def dumpVM(minimal=False):
        file = open('/etc/pve/.vmlist', 'r')
        vmData = json.loads(file.read())
        file.close()
        vms = [PVEVm(key, minimal=minimal) for key, values in vmData['ids'].items() if values['type'] == 'qemu']
        return vms
    
    def selfDestroy(self):
        DEBUG('\t[x] Stop and locking VM {}\n'.format(self.id))
        stdout, stderr = runCli('qm stop {}'.format(self.id))
        #stdout, stderr = runCli('qm set {} --lock create'.format(self.id))
    
    def status(self):
        stdout, stderr = runCli('qm status {}'.format(self.id))
        if stderr == b'':
            return b'stopped' not in stdout

class PVELxc(PVEGuest):
    def __init__(self, id, minimal=False):
        PVEGuest.__init__(self, id, '/etc/pve/nodes/proxmox/lxc/{}.conf'.format(id), minimal)
        # LXC can have unlimited core... Must check that
        try:
            self.cores
        except AttributeError:
            self.cores = '9999999'
        self.sockets = '1'
        try:
            self.unprivileged
        except AttributeError:
            self.unprivileged = '0'
        try:
            self.hookscript
        except AttributeError:
            runCli('pct set {} --hookscript local:snippets/confcheck_hookscript.pl'.format(self.id))
    
    @staticmethod
    def dumpVM(minimal=False):
        file = open('/etc/pve/.vmlist', 'r')
        vmData = json.loads(file.read())
        file.close()
        vms = [PVELxc(key, minimal=minimal) for key, values in vmData['ids'].items() if values['type'] == 'lxc']
        return vms
    
    def selfDestroy(self):
        DEBUG('\t[x] Stop and locking LXC {}\n'.format(self.id))
        stdout, stderr = runCli('pct stop {}'.format(self.id))
        #stdout, stderr = runCli('pct set {} --lock destroyed'.format(self.id))

    def limitsCheck(self, limits):
        result = PVEGuest.limitsCheck(self, limits)
        unpriv = self.unprivileged == '1' or limits['LXCPRIVILEGED']
        DEBUG('\t\t[+] UNPRIVILEGED  {}\n'.format(unpriv))
        return result and unpriv

    def status(self):
        stdout, stderr = runCli('pct status {}'.format(self.id))
        if stderr == b'':
            return b'stopped' not in stdout