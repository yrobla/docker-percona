#!/usr/bin/env python

from marathon import MarathonClient
import fileinput
import os
import random
import re
import shutil
import string
import subprocess
import sys
import time

VOLUME_HOME="/var/lib/mysql"
CONF_FILE="/etc/mysql/my.cnf"
LOG="/var/log/mysql/error.log"
APP_ID='yroblapercona'

def start_mysql():
    subprocess.call('/usr/bin/mysqld_safe &', shell=True, stderr=subprocess.STDOUT)
    i = 0
    while i<13:
        print('Waiting for confirmation of mysql service startup, trying %s/13' % str(i))
        time.sleep(5)

        # check status
        p = subprocess.Popen(['mysql', '-u', 'root', '-e', 'status'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        result = p.stdout.read()
        if result:
            break
        i += 1

    if i == 13:
        print 'Timeout starting mysql server\n'
        sys.exit(1)


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

def create_mysql_user():
    start_mysql()

    mysql_user = os.getenv('MYSQL_USER')
    mysql_pass = os.getenv('MYSQL_PASS')
    if mysql_pass == '**Random**':
        os.unsetenv('MYSQL_PASS')
        mysql_pass = None

    if not mysql_pass:
        # generate random pass
        mysql_pass = id_generator(8)

    print 'Create Mysql user %s with password %s\n' % (mysql_user, mysql_pass)
    subprocess.call(['mysql', '-uroot',
        '-e', "CREATE USER '%s'@'%%' IDENTIFIED BY '%s'" % (mysql_user, mysql_pass)])
    subprocess.call(['mysql', '-uroot', '-e',
        "GRANT ALL PRIVILEGES ON *.* TO '%s'@'%%' WITH GRANT OPTION" % mysql_user])
    print 'Done!\n'
    print '========================================================================\n'
    print 'You can now connect to this MySQL Server using:\n'
    print ' mysql -u%s -p%s -h<host> -P<port>\n' % (mysql_user, mysql_pass)
    print 'MySQL user root has no password but only allows local connections\n'

    replica_mysql_user = os.getenv('REPLICA_MYSQL_USER')
    replica_mysql_pass = os.getenv('REPLICA_MYSQL_PASS')
    if replica_mysql_pass == '**Random**':
        os.unsetenv('REPLICA_MYSQL_PASS')
        replica_mysql_pass = None

    if not replica_mysql_pass:
        # generate random pass
        replica_mysql_pass = id_generator(8)

    print 'Create replica Mysql user %s with password %s\n' % (replica_mysql_user, replica_mysql_pass)
    subprocess.call(['mysql', '-uroot',
        '-e', "CREATE USER '%s'@'localhost' IDENTIFIED BY '%s'" % (replica_mysql_user, replica_mysql_pass)])
    subprocess.call(['mysql', '-uroot', '-e',
        "GRANT ALL PRIVILEGES ON *.* TO '%s'@'localhost' WITH GRANT OPTION" % replica_mysql_user])
    print 'Done!\n'
    subprocess.call(['mysqladmin', '-uroot', 'shutdown'])

    # update my.cnf sst_auth
    for line in fileinput.input(CONF_FILE, inplace=True):
        line_content = line
        if line.startswith('wsrep_sst_auth'):
            line_content = 'wsrep_sst_auth = "%s:%s"\n' % (replica_mysql_user, replica_mysql_pass)
        elif line.startswith('wsrep_sst_receive_address'):
            line_content = 'wsrep_sst_receive_address = %s\n' % os.getenv('HOST')
        elif line.startswith('wsrep_node_address'):
            line_content = 'wsrep_node_address = %s\n' % os.getenv('HOST')
        elif line.startswith('wsrep_node_incoming_address'):
            line_content = 'wsrep_node_incoming_address = %s\n' % os.getenv('HOST')
        
        sys.stdout.write(line_content)


# check all percona entries
def bootstrap_cluster():
    print "Checking cluster entries\n"
    endpoint = os.getenv('MARATHON_ENDPOINT')
    peers = []
    if endpoint:
        try:
            print 'Discovering configuration from %s\n' % endpoint
            c = MarathonClient('http://%s' % endpoint)
            tasks = c.list_tasks(APP_ID)
            for task in tasks:
                if task.started_at:
                    peers.append(task.host)
        except:
            pass

    # check entries in wsrep_cluster_address
    if peers and len(peers)>1:
        final_entry = ','.join(peers)
        print 'Found addresses %s\n' % final_entry
        needs_restart = False
        for line in fileinput.input(CONF_FILE, inplace=True):
            line_content = line
            if line.startswith('wsrep_cluster_address'):
                # extract address pattern
                address = re.search('wsrep_cluster_address = gcomm://(.*)', line, re.IGNORECASE)
                if address:
                    extracted = address.group(1)
                    if extracted != final_entry:
                        # replace entry in file
                        line_content = 'wsrep_cluster_address = gcomm://%s\n' % final_entry
                        needs_restart = True
            sys.stdout.write(line_content)

        # restart if needed
        if needs_restart:
            print 'Reboot service\n'
            subprocess.call(['rm', '-f', '/var/lib/mysql/grastate.dat'])
            subprocess.call(['service', 'mysql', 'restart'])


# Set permission of config file
os.chmod(CONF_FILE, 0644)

# check if mounted volume exists
volume_path = VOLUME_HOME+'/mysql'
if not os.path.isdir(volume_path):
    print '=> An empty of uninitialized MySQL volume is detected in %s\n' % volume_path
    print 'Installing MySql...\n'

    if not os.path.isfile('/usr/share/mysql/my-default.cnf'):
        shutil.copy('etc/mysql/my.cnf', '/usr/share/mysql/my-default.cnf')

    subprocess.call(['mysql_install_db'])
    print '=> Done!\n'
    print '=> Creating admin user ...\n'

    create_mysql_user()
else:
    print '=> Using an existing volume of MySQL\n'

sys.stdout.flush()
subprocess.call('service mysql start', shell=True, stderr=subprocess.STDOUT)

bootstrap_cluster()
sys.stdout.flush()

while True:
    time.sleep(1)
