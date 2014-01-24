import os
import subprocess


def start_supervisors():
    """ start supervisor for all users with home under /opt which has ~/conf/supervisor.ini file
    (used to start on reboot)
    """
    out = subprocess.check_output('cat /etc/passwd |grep "/opt" |cut -d: -f1', shell=True)
    users = out.split()
    for user in users:
        file_exists = os.system('test -f ~{}/conf/supervisor.ini'.format(user)) == 0
        if file_exists:
            os.system('sudo su -l -c "supervisord -c ~{0}/conf/supervisor.ini" {0}'.format(user))


if __name__ == '__main__':
    start_supervisors()
