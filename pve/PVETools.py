import subprocess

def runCli(command):
    cli = command.split(' ')
    try:
        process = subprocess.run(cli, capture_output=True)
        return (process.stdout, process.stderr)
    except subprocess.CalledProcessError as e:
        return (None, e.stderr)

def DEBUG(data, file='/var/log/proxmox.log'):
    file = open(file, 'a')
    file.write(data)
    file.close()