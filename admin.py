from fabric.colors import red
from fabric.contrib.files import append
from fabric.decorators import roles
from fabric.operations import sudo, run
from fabric.state import env
from fabric.tasks import execute
import sys
from bh import user, root
from bh.utils import setup_env_for_user
from lib import gh_task, print_successful, new_host_string


@gh_task
def reboot():
    sudo('shutdown -r now')


def user_add_ssh(user_account, pub_key_file, use_sudo=True):
    try:
        with open(pub_key_file) as f:
            pub_key = f.read()
    except IOError:
        print(red('Where is the public key file? (did you run "fab initialize" first?)\n'
                  'expected: {}'.format(pub_key_file)))
        sys.exit(-1)
    run_cmd = run if not use_sudo else sudo
    run_cmd('mkdir -p ~{0}/.ssh'.format(user_account))
    run_cmd('touch ~{0}/.ssh/authorized_keys'.format(user_account))
    append('~{0}/.ssh/authorized_keys'.format(user_account), pub_key, use_sudo=use_sudo)
    secure_account(user_account)


@roles('admin')
@gh_task
def secure_account(user_account):
    """ ensures owner is correctly set on all files under $HOME of user_account, and limit appropriately for ssh
    """
    setup_env_for_user()
    sudo('chown -R {0} ~{0}/.'.format(user_account))
    sudo('chmod 700 ~{0}/. ~{0}/.ssh'.format(user_account))
    sudo('chmod 600 ~{0}/.ssh/authorized_keys'.format(user_account))
    print_successful()


@roles('admin')
@gh_task
def create_user(user_account, password):
    setup_env_for_user()
    execute(root.user_create, user_account, password)
    user_add_ssh(user_account, pub_key_file=env.key_filename + '.pub', use_sudo=True)
    dummy_port = 123  # bh sets env variable 'HTTP_LISTENING_PORT' to this one, but we won't use that env var
    execute(user.init_home_env, dummy_port, hosts=new_host_string(user=user_account))
    sudo('mkdir -p ~{}/conf'.format(user_account))
    secure_account(user_account)
    print_successful()
