from fabric.operations import run
import sys
from lib import gh_task, pid_running
import time


@gh_task
def restart():
    """ restart supervisord (must do if changed supervisor.ini config)
    """
    pid_file = '~/var/run/supervisord.pid'
    if pid_running(pid_file):
        run('kill -1 $(cat {})'.format(pid_file))
        # will re-start itself
    else:
        run('supervisord -c ~/conf/supervisor.ini')
    secs = 10
    for n in xrange(secs):
        if pid_running(pid_file):
            return
        time.sleep(1)
    print "Failed start supervisor in {}s!".format(secs)
    sys.exit(1)


def supervisorctl(*args):
    run('supervisorctl -c conf/supervisor.ini {}'.format(" ".join(args)))


@gh_task
def start_program(program='all'):
    """ start [all] servers
    """
    supervisorctl('start', program)


@gh_task
def reload_program(program='all'):
    """ reload [all] servers
    """
    supervisorctl('reload', program)


@gh_task
def stop_program(program='all'):
    """ stop [all] servers
    """
    supervisorctl('stop', program)


@gh_task
def restart_program(program='all'):
    """ restart [all]servers
    """
    supervisorctl('restart', program)


@gh_task
def install():
    run('pip install "supervisor>=3.0"')

