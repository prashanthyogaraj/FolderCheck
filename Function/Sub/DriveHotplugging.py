import argparse
import paramiko
import socket
import time
import logging
import random
import os
import re
import threading
import Start_Load

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',datefmt="%Y-%m-%d %H:%M:%S")

WAIT_1_MIN=180
RETRIES_DISK_POWER_CONTROL  = 5
DRIVE_REBUILDING_SLEEP=500
ITERATIONS_DRIVE_HOTPLUG=200
ssh=None
cmd_get_diskid = '/usr/tintri/bin/platcmd --diskinfo | awk \'{print $1 \" \" $NF}\''
cmd_get_spare_disk = '/usr/tintri/bin/platcmd --diskinfo | grep "spare" | awk \'{print $1 \" \" $NF}\''
cmd_get_rebuild_disk = '/usr/tintri/bin/platcmd --diskinfo | grep "REBUILD" | awk \'{print $1 \" \" $(NF-2)}\''
cmd_get_error_disk = '/usr/tintri/bin/platcmd --raid | grep -i "1." | awk \'{print $2 \" \" $NF}\''
cmd_print_raid = '/usr/tintri/bin/platcmd --raid'
cmd_print_disk = '/usr/tintri/bin/platcmd --disk'


class DriveHotpluggingException(Exception):
    def __init__(self,msg):
        self.msg=msg
        
def login(ip,username,password):

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print("Connecting to realstore %s" % ip)
        error_status = ssh.connect(ip, username=username, password=password, timeout=60, allow_agent=False,
                                       look_for_keys=False)
        print("error status is", error_status)
        if error_status is None:
            print("SSH login successful for IP %s" % ip)
                #time.sleep(10)
            connect = ssh.invoke_shell()
            return ssh
    except  paramiko.AuthenticationException:
            print("Authentication Error for server:%s" % ip)
    except paramiko.BadHostKeyException:
            print("Server's host key could not be verified")
    except paramiko.SSHException:
            print("Error connecting or establishing  SSH session")
    except socket.error:
            print("Connection Error for IP:%s" % ip)
    except Exception as e:
            print(str(e))
            

def get_disk_id(ssh,cmd=cmd_get_diskid):
    diskId_dic={}
    #cmd_get_diskid='/usr/tintri/bin/platcmd --diskinfo | awk \'{print $1 \" \" $NF}\''
    #cmd_get_diskstatus='/usr/tintri/bin/PlatCmd --diskinfo | awk \'{print $NF}\''
    logging.info("Executing: %s"%cmd)
    sd_inp, sd_out, sd_err = ssh.exec_command(cmd)
    time.sleep(1)
    disk_out_st=sd_out.read().decode().strip()
    disk_out_list=disk_out_st.split("\n")
    for disk in disk_out_list:
        diskId,state=disk.split(" ")
        if(state not in ['EMPTY']):
            diskId_dic[diskId] = state
            
    print(diskId_dic)
    return diskId_dic
    
def get_rebuilding_drives(ssh):
    logging.info("Verifying rebuild status of Drive...")
    rebuild_list=[]
    logging.info(cmd_get_rebuild_disk)
    sd_inp, sd_out, sd_err = ssh.exec_command(cmd_get_rebuild_disk)
    #print(sd_out.read().decode().strip())
    
    try:
        disk_rebuild=sd_out.read().decode().strip()
        disk_rebuild_list=disk_rebuild.split("\n")
        for disk in disk_rebuild_list:
            diskId,state=disk.split(" ")
            logging.info("DiskID is %s and state is %s"%(diskId,state))
            rebuild_list.append([diskId,state])
        drives_rebuilding=[rebuild_list[i][0] for i in range(len(rebuild_list))]
        
        return drives_rebuilding
    except Exception as e:
        pass
    
def get_ctrl_id(ssh):
    sd_inp, sd_out, sd_err = ssh.exec_command("/usr/local/tintri/bin/get_ctrlid")
    ctrlid=sd_out.read().decode().strip()
    logging.info("Controller Id is %s"%ctrlid)
    return ctrlid
    
def get_failed_missing_drives(ssh,status):
    logging.info("checking %s drives.."%status)
    diskId_dic = get_disk_id(ssh,cmd_get_error_disk)
    failed_disk=[]
    missing_disk=[]
    if(status == 'failed'):
        list_failures = ['OFFLINE','POWEROFF','FAILED']
        for k,v in diskId_dic.items():
            if v in list_failures:
               failed_disk.append(k)
        
    elif(status == 'missing'):
        for k,v in diskId_dic.items():
            if v == 'MISSING':
                missing_disk.append(k)
    
    elif(status == 'spare'):
        count=0
        for k,v in diskId_dic.items():          
            if(count<=1):
                if v=='spare':
                    count+=1
            else:
                raise DriveHotpluggingException("Found More than 1 spare Drive please check the status of the drives")
                exit()
        logging.info("spare count is %s"%count)
 
    return failed_disk or missing_disk

def test_excessive_disk_replacement(ssh,ctr_id):
    logging.info("Test excessive_disk_replacement Initiating...")
    hotplug_raid_groups = []
    hotplug_raid_groups.append("vm1")
    for hotplug_raid_group in hotplug_raid_groups:
        raid_disks_d = get_disk_id(ssh)
        raid_disks=[disk for disk in raid_disks_d.keys() if raid_disks_d[disk] in ['active']]
        logging.info("Disks in raid group %s:\n%s" % (hotplug_raid_group, raid_disks))
        
        if len(raid_disks) == 0:
            raise DriveHotpluggingException("Did not get any disks from the raid group %s" % raid_group)
        
        random.shuffle(raid_disks)
        count = 1
        while count <= ITERATIONS_DRIVE_HOTPLUG:
            logging.info("drive hotplugging round %d/%d", count, ITERATIONS_DRIVE_HOTPLUG)
            count+=1
            raid_disks_d = get_disk_id(ssh)
            raid_disks=[disk for disk in raid_disks_d.keys() if raid_disks_d[disk] in ['active']]
            logging.info("Disks in raid group in while %s:\n%s" % (hotplug_raid_group, raid_disks))
            num_disks_to_hotplug = len(raid_disks) if len(raid_disks) < 2 else 2
            disks_to_hotplugged = []
            for _ in range(num_disks_to_hotplug):
                disks_to_hotplugged.append(random.choice(raid_disks))
            logging.info("Disks to be Hotplugged %s"%str(disks_to_hotplugged))
            for diskId in disks_to_hotplugged:
                logging.info("Hotplugging disk '%s'", diskId)
                powerCycleSlot(diskId,ssh)
                logging.info("Verifying if the hotplug disks are rebuilding or made spare")
                verify_hotplug(ssh,diskId)
                print_raid_disk(ssh)
                drives_spare=get_failed_missing_drives(ssh,'spare')
                cid=get_ctrl_id(ssh)
                if(cid != ctr_id):
                    logging.info("Change in controller id,check for the Failover reason")
                    exit()
                else:
                    logging.info("Controller Id is same")
                
            status=wait_for_drives_to_rebuild(ssh)
            logging.info("Verifying Raid and disk output Post waiting rebuild")
            print_raid_disk(ssh)
            if(status):
                continue
            else:
                raise DriveHotpluggingException("test_excessive_disk_replacement Failed while wait for rebuilding")
                exit()
    return status

def parse_args():
    parser = argparse.ArgumentParser()
    
    parser.add_argument('--ip', required=True, action='store',
                        help='realstore IP or hostname [e.g tafbm10 or 10.34.83.1]')
    parser.add_argument('--user', required=False, action='store',
                        default='root',help='Realstore username [e.g root] or [default is root]')
    parser.add_argument('--password', required=False, action='store',
                        default= "tintri99",help='realstore password [default is tintri99]')
    #parser.add_argument('--output', required=False, action='store_true',
    #                    default=False, help='Turn on debugging mode')
    args = parser.parse_args()

    return args
    
    
def verify_hotplug(ssh,disk_id):
    logging.info("Wait for Platmon to recognize the hotplug event")
    logging.info("Sleeping %d seconds"%WAIT_1_MIN)
    time.sleep(WAIT_1_MIN)
    diskId_dic = get_disk_id(ssh)
    disk_status = diskId_dic[disk_id]
    cmd_check_diskid_rebuild = '/usr/tintri/bin/platcmd --diskinfo | grep -w '+disk_id+' | awk \'{print $(NF-2)}\''
    logging.info(cmd_check_diskid_rebuild)
    sd_inp, sd_out, sd_err = ssh.exec_command(cmd_check_diskid_rebuild)
    reb_state=sd_out.read().decode().strip()
    logging.info("reb_state %s"%reb_state)
    
    cmd_raid_disk_state= '/usr/tintri/bin/platcmd --raid | grep -w '+disk_id+' | awk \'{print $(NF-1)}\''
    logging.info(cmd_raid_disk_state)
    sd_inp, sd_out, sd_err = ssh.exec_command(cmd_raid_disk_state)
    plat_raid_reb_state=sd_out.read().decode().strip()
    logging.info("platcmd reb_state %s"%plat_raid_reb_state)
    
    logging.info("Sleeping %d seconds"%WAIT_1_MIN)
    time.sleep(WAIT_1_MIN)
    
    disk_status_raid_cmd= '/usr/tintri/bin/platcmd --raid | grep -w '+disk_id+' | awk \'{print $NF}\''
    logging.info(disk_status_raid_cmd)
    sd_inp, sd_out, sd_err = ssh.exec_command(disk_status_raid_cmd)
    disk_status_raid = sd_out.read().decode().strip()
    logging.info("disk_status_raid state %s "%disk_status_raid)
    
    logging.info("hotplug status of disk %s: %s", disk_id, disk_status)
    valid_disk_states=["REBUILD","active","spare","spare|active","rebuilding"]
    if disk_status not in valid_disk_states:
        if reb_state not in valid_disk_states:
            if plat_raid_reb_state not in valid_disk_states or disk_status_raid not in valid_disk_states:
                logging.info("Disk status is '%s'", disk_status)
                raise DriveHotpluggingException("Disk '%s' not rebuilding or spare in last if check" % disk_id)
            else:
                logging.info("Disk '%s' was hotplugged successfully" % disk_id)
        else:
            logging.info("Disk '%s' was hotplugged successfully" % disk_id)
    else:
        logging.info("Disk '%s' was hotplugged successfully" % disk_id)

def print_raid_disk(ssh):
    logging.info(cmd_print_raid)
    sd_inp, sd_out, sd_err = ssh.exec_command(cmd_print_raid)
    raid_out=sd_out.read().decode().strip()
    logging.info(raid_out)
    logging.info(cmd_print_disk)
    sd_inp, sd_out, sd_err = ssh.exec_command(cmd_print_disk)
    disk_out=sd_out.read().decode().strip()
    logging.info(disk_out)
    
    
def wait_for_drives_to_rebuild(ssh):
    
    retries=1
    logging.info('waiting for drives to rebuild')
    drives_rebuilding= get_rebuilding_drives(ssh)
    logging.info('drives rebuilding: %s', str(drives_rebuilding))
    if(drives_rebuilding is not None):
        while(drives_rebuilding):
            logging.info('drives rebuilding: %s', str(drives_rebuilding))
            logging.info('Retries: %s'%retries)
            drives_rebuilding = get_rebuilding_drives(ssh)
            logging.info('drives rebuilding: %s', str(drives_rebuilding))
            if(drives_rebuilding is not None):
                if len(drives_rebuilding) != 0:
                    logging.info("drives remaining: %s, waiting another %d s for rebuild ",str(drives_rebuilding), DRIVE_REBUILDING_SLEEP)
                    time.sleep(DRIVE_REBUILDING_SLEEP)
                    retries+=1
    
    drives_missing=get_failed_missing_drives(ssh,'missing')
    drives_failed=get_failed_missing_drives(ssh,'failed')
    drives_spare=get_failed_missing_drives(ssh,'spare')
    
    return len(drives_failed) == 0 and len(drives_missing) == 0

def powerCycleSlot(diskId,ssh):
    for operation in ["off", "on"]:
        powerControlSlot(diskId,operation,ssh)


def powerControlSlot(diskId, operation, ssh,pollInterval=120):
    operation = operation.lower()
    logging.info("Going to power %s disk slot %s" % (operation, diskId))
    power_control_dict = {'off': ['power-off', 'power_off'], 'on':['Disk 1.\d+\s+[\w\W]+\s+\w+', 'power_on']}
    for i in range(RETRIES_DISK_POWER_CONTROL):
        #self._rs.run_cmd("/usr/local/tintri/bin/tbolt_slot_control.sh -s %s -o %s" % (diskId, power_control_dict[operation][1]))
        sd_inp, sd_out, sd_err = ssh.exec_command("/usr/local/tintri/bin/tbolt_slot_control.sh -s %s -o %s" % (diskId, power_control_dict[operation][1]))
        logging.info("Going to sleep for %s sec for changes to reflect"%pollInterval)
        time.sleep(pollInterval)
        cmd = "/usr/tintri/bin/PlatCmd --disk | grep -w %s" % diskId
        sd_inp, sd_out, sd_err = ssh.exec_command(cmd)
        disk_sd_out=sd_out.read().decode().strip()
        logging.info("Output of the command %s"%disk_sd_out)
        #(_, _, so) = self._rs.run_cmd(cmd, timeout=60)
        if re.search(power_control_dict[operation][0], disk_sd_out):
            logging.info("%s drive power-%s finished" % (diskId, operation))
            break
    else:
        raise Exception("Failed to power-%s %s drive after %s retries" % (operation, diskId, 5))
        
            
if __name__ == '__main__':
    try:
        args=parse_args()
        ssh=login(args.ip,args.user,args.password)
        ctr_id=get_ctrl_id(ssh)
        t1 = threading.Thread(target=test_excessive_disk_replacement, args=(ssh,ctr_id,))
        t1.start()
        t2 = threading.Thread(target=Start_Load.main_start_nvxlite,args=(t1,args.ip,args.user,args.password))
        t2.start()
        t1.join()
        t2.join()
        logging.info("test_excessive_disk_replacement Completed")
    except Exception as e:
        print(e)
    finally:
        if(ssh):
            logging.info("Closing ssh Connection")
            ssh.close()