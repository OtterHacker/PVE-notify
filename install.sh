#! /bin/bash
mkdir -p /usr/local/sbin/proxmox-binaries
mkdir -p /var/lib/vz/snippets

cp -r ./conf /usr/local/sbin/proxmox-binaries/conf
cp pve-* /usr/local/sbin/proxmox-binaries/
chmod +x /usr/local/sbin/proxmox-binaries/pve-*

cp ./hookscripts/*.pl /var/lib/vz/snippets/

cp inotify.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable inotify.service
service inotify start