from pve.PVETools import runCli, DEBUG
from pve.PVEMachine import PVEVm,PVELxc
import json

class PVEUser:
    def __init__(self, data):
        try:
            self.username = '@'.join(data['userid'].split('@')[:-1])
            self.realm = data['userid'].split('@')[-1]
            self.state = data['enable']
            self.expiration = data['expire']
        except KeyError:
            raise ValueError("Not enough information to build user...")

        try:
            self.firstname = data['firstname']
        except KeyError:
            pass
        try:
            self.lastname = data['lastname']
        except KeyError:
            pass
        try:
            self.mail = data['email']
        except KeyError:
            pass
        try:
            self.comment = data[7]
        except KeyError:
            pass

        self.vmList = []


    @property
    def pool(self):
        return "_".join("{}.{}".format(self.firstname, self.lastname).split('\''))

    @property
    def pveusername(self):
        return '_'.join("{}@{}".format(self.username, self.realm).split('\''))
    
    def totalDiskUse(self,  limits=None, addVm=None):
        if self.activeVmList is None and addVm is None:
            return -1
        totalDiskUse = 0
        for vm in self.activeVmList:
            if (limits is not None and vm.id not in limits['NOT_REVIEWED']):
                totalDiskUse += vm.totalDiskSize
        
        if addVm is not None:
            totalDiskUse == addVm.totalDiskSize

        return totalDiskUse
    
    def totalRAMUse(self, limits=None, addVm=None):
        if self.activeVmList is None and addVm is None:
            return -1
        totalRAMUse = 0
        for vm in self.activeVmList:
            if (limits is not None and vm.id not in limits['NOT_REVIEWED']):
                totalRAMUse += int(vm.memory, 10)

        if addVm is not None:
            totalRAMUse += int(addVm.memory, 10)
        return totalRAMUse
    
    def totalCoreUse(self, limits=None, addVm=None):
        if self.activeVmList is None and addVm is None:
            return -1
        totalCoreUse = 0
        for vm in self.activeVmList:
            if (limits is not None and vm.id not in limits['NOT_REVIEWED']):
                totalCoreUse += int(vm.cores, 10)
        
        if addVm is not None:
            totalCoreUse += int(addVm.cores, 10)
        return totalCoreUse

    @staticmethod
    def isUser(line):
        return 'user' in line.split(':')[0]
        

    @staticmethod
    def dumpUsers():
        users = []
        stdout, stderr = runCli('pveum user list --output-format=json-pretty')
        if stderr != b'':
            DEBUG('[x] Failed to get user list from pveum API: {}\n'.format(stderr))
            return []
        userList = json.loads(stdout)
        for user in userList:
            try:
                users.append(PVEUser(user))
            except ValueError:
                pass
        return users

    def createEnv(self, realm):
        # Only process if the user is part of the selected realm
        if realm != self.realm:
            return

        DEBUG("\n[-] Setting environment for user {}\n".format(self))

        DEBUG("\t[-] Creating pool for user {}\n".format(self))
        cli = "pvesh create /pools --poolid {}".format(self.pool)
        stdout, stderr = runCli(cli)
        if stderr != b'' and b'already exists' not in stderr:
                DEBUG("\t[x] Failed to create {} pool : {}\n".format(self.pool, stderr))
                return
        DEBUG("\t[+] Pool {} created !\n".format(self.pool))

        DEBUG("\n\t[-] Adding Administrator rights on pool {}\n".format(self.pool))
        cli = "pveum acl modify /pool/{} -user {} -role Administrator".format(self.pool, self.pveusername)
        stdout, stderr = runCli(cli)
        if stderr != b'':
                DEBUG("\t[x] Failed to set administrator rights to {}: {}\n".format(self.pool, stderr))
                return
        DEBUG("\t[+] Administrator rights set on {} !\n".format(self.pool))

        DEBUG("\n\t[-] Adding {} to user group\n".format(self.username))
        cli = "pveum user modify {} -group user".format(self.pveusername)
        stdout, stderr = runCli(cli)
        if stderr != b'':
            DEBUG("\t[x] Failed to add {} to user group : {}\n".format(self.username, stderr))
            return
        DEBUG("\t[+] {} added to user group!\n".format(self.username))
        DEBUG("\t[+] User {} environment created\n".format(self.username))


    def loadVMInfo(self):
        vmList = PVEVm.dumpVM(minimal=True)
        lxcList = PVELxc.dumpVM(minimal=True)
        stdout, stderr = runCli('pvesh get /nodes/proxmox/tasks --start 0 --limit 5000 --source all --output-format=json-pretty')
        if stderr != b'':
            return None
        logs = json.loads(stdout.decode())

        self.vmList = []
        self.activeVmList = []
        for vm in lxcList + vmList:
            for elt in logs:
                if elt['id'] == vm.id:
                    vm.owner = elt['user']
                    if vm.owner == self.pveusername:
                        DEBUG('\t[-] Owner for {} VM : {}\n'.format(vm.id, self.pveusername))
                        if ((not hasattr(vm, 'template')) or vm.template == '0')  and vm.status():
                            self.activeVmList.append(vm)
                    break        
        
    def limitsCheck(self, limits, vm=None):
        DEBUG("\t[-] Checking user {} limits:\n".format(self.username))
        DEBUG("\t\t [+] The following limits are applied : \n\t\t\t{}\n".format('\n\t\t\t'.join(json.dumps(limits['PERUSER'], indent=4).split('\n'))))
        if self.pveusername in limits['ADMINISTRATORS']:
            DEBUG("\t\t [+] I see you got unlimited user here, everything all right\n")
            return True
        
        disk =  self.totalDiskUse(limits=limits, addVm=vm)
        ram = self.totalRAMUse(limits=limits, addVm=vm)
        core = self.totalCoreUse(limits=limits, addVm=vm)
        print("SUMMARY OF TOTAL RESOURCE CONSUMPTION:")
        print("\tACTIVE RESOURCES : {}".format(" ".join([vm.id for vm in self.activeVmList])))
        print("\tDISK  : {}/{}".format(disk, limits['PERUSER']['DISK']))
        print("\tRAM   : {}/{}".format(ram, limits['PERUSER']['RAM']))
        print("\tCORES : {}/{}".format(core, limits['PERUSER']['CORES']))

        disk = disk <= limits['PERUSER']['DISK']
        ram = ram <= limits['PERUSER']['RAM']
        core = core <= limits['PERUSER']['CORES']

        DEBUG("\t\t[+] DISK   {}\n".format(disk))
        DEBUG("\t\t[+] RAM    {}\n".format(ram))
        DEBUG("\t\t[+] CORES  {}\n".format(core))
        return disk and ram and core
        
    def __str__(self):
        return "{}@{}".format(self.username, self.realm)

class PVEGroup:
    def __init__(self, data):
        try:
            self.name = data['groupid']
            self.users = data['users'].split(',')
        except KeyError:
            raise ValueError("Not enough information to build group")
        try:
            self.description = data['comment']
        except KeyError:
            pass

    @staticmethod
    def dumpGroups():
        groups = []
        stdout, stderr = runCli('pveum group list --output-format=json-pretty')
        if stderr != b'':
            DEBUG('[x] Failed to get group list from pveum API: {}\n'.format(stderr))
            return []
        groupList = json.loads(stdout)

        for group in groupList:
            try:
                groups.append(PVEGroup(group))
            except ValueError:
                pass
        return groups

    def removePresentPVEUser(self, users):
        result = []
        for user in users:
            if "{}".format(user) not in self.users:
                result.append(user)
        return result

    def __str__(self):
        return "{}".format(self.name)