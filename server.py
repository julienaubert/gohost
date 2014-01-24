from functools import partial
import sys
from fabric.api import run, env, settings, hide
from fabric.colors import red
from fabric.contrib.files import append
from fabric.operations import sudo
from admin import user_add_ssh
from bh.utils import setup_env_for_user
from fabric.decorators import roles
from lib import gh_task, gen_password, local_append, print_successful, env_ip, local_ssh_config, passwd_retry
from template import put_template, get_config


def install(pkgs):
    sudo('apt-get update')
    sudo('apt-get -y --force-yes install {}'.format(' '.join(pkgs)))


def debian_requirements():
    install(['gcc', 'build-essential', 'libaio-dev', 'libxml2-dev', 'libxslt1-dev', 'libreadline-dev',
            'libbz2-dev', 'curl', 'libssl-dev', 'libcurl4-openssl-dev', 'libldap2-dev', 'libsasl2-dev',
            'libpcre3', 'libpcre3-dev', 'libsqlite3-dev'])


def install_pip():
    run('curl https://raw.github.com/pypa/pip/master/contrib/get-pip.py | python')


@roles('root')
@gh_task
def bootstrap(template_dir, server_yaml, pub_key_file):
    """ run once to initialize an 'empty' Debian system. requires root access via password on port 22
    NOTE: after this command, can only login as 'admin' (it has sudo rights)

    - secures ssh access, creates 'admin' account with sudo rights
    - ensures hostname exists both in your /etc/hosts and in remote's /etc/hosts
    - restricts ssh: only login via ssh-key, no root login, ssh-port is non-standard
    - LOCALLY: adds ssh-key and ssh-port to your local ~/.ssh/config
    - installs denyhosts
    - installs some basic libraries (see debian_requirements)
    - iptables: routes 80 to configured port: {server.port_80_via}
    - iptables: routes 443 to configured port: {server.port_443_via}
    """
    server_config = get_config(env, yaml_file=server_yaml)
    my_put_template = partial(put_template, context=server_config, template_dir=template_dir)

    if not env.key_filename:
        print(red('Must generate a key for ssh to this server (see example_app/bootstrap.py)'))
    if 'root@' not in env.host_string or len(env.roles):
        print(red('Must be run as root! (hint: do not run with -R or -H)'))
        sys.exit(-1)
    setup_env_for_user()

    hostname = run('hostname')
    append('/etc/hosts', '127.0.0.1 {}'.format(hostname))
    local_append('/etc/hosts', text='{} {}'.format(env_ip(), hostname), refuse_keywords=[env_ip(), hostname],
                 use_sudo=True)
    run('apt-get -y --force-yes install sudo vim')
    debian_requirements()

    install(['denyhosts'])
    my_put_template('denyhosts.conf', '/etc/denyhosts.conf')
    run('/etc/init.d/denyhosts restart')

    password = gen_password()
    user_account = 'admin'
    with settings(hide('warnings'), warn_only=True):
        run('userdel -f -r {}'.format(user_account))
    run('useradd {user} -g {group}'.format(user=user_account, group='sudo'))
    print(red("Set password for admin (has sudo rights), type in: {} or choose one yourself".format(password)))
    passwd_retry('admin')
    user_add_ssh(user_account, pub_key_file=pub_key_file)
    local_ssh_config(env_ip(), hostname, server_config['server']['ssh_port'], env.key_filename)

    # TODO: lock down: http://rudd-o.com/linux-and-free-software/hardening-a-linux-server-in-10-minutes

    my_put_template('rc.local', '/etc/rc.local')
    my_put_template('init_supervisors.py', '/etc/init_supervisors.py')
    # config iptables
    run('/etc/rc.local')

    my_put_template('sshd_config', '/etc/ssh/sshd_config')
    # note after restart, can only login as admin via public key on ssh-port defined in template
    run('/etc/init.d/ssh restart')
    print_successful()
