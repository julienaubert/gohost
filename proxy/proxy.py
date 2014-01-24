from functools import partial
from fabric.colors import yellow
from fabric.decorators import roles
from fabric.operations import run, put, local
from fabric.state import env
from fabric.tasks import execute
from bh import system
from lib import gh_task, print_successful, total_silence
import supervisor
from template import put_template, get_config
from unipath import Path
from fabric.decorators import task


put_template = partial(put_template, template_dir=str(Path(__file__).parent.child('templates')))


def roledefs(hostname):
    return {
        'proxy_admin': ['admin@{}'.format(hostname)],
        'proxy': ['cc_proxy@{}'.format(hostname)],
    }


def rel_path(*path):
    return str(Path(__file__).parent.child(*path))


def proxy_config():
    return get_config(
        env,
        yaml_file=Path(__file__).parent.child('proxy.yaml'),
        default_yaml_file=Path(__file__).parent.child('server.yaml'),
    )


@roles('proxy')
@gh_task
def configure():
    """ renders config of nginx and restarts gracefully
    """
    env.roles = ['proxy']
    put_template('proxy_nginx.conf', '~/conf/nginx.conf', context=proxy_config())
    put_template('proxy_supervisor.ini', '~/conf/supervisor.ini', context=proxy_config())
    execute(supervisor.restart)
    print_successful()


@gh_task
def update_ssl(ssl_key, ssl_cert):
    """ updates the server ssl key with these files, note the ssl-key should be without passphrase for nginx to restart
    """
    put(ssl_key, proxy_config()['proxy']['ssl_key'])
    run('chmod 400 {ssl_key}'.format(**proxy_config()['proxy']))
    put(ssl_cert, proxy_config()['proxy']['ssl_cert'])


@roles('proxy')
@gh_task
def test():
    keys = dict(ssl_key=rel_path('dummy_ssl.key'), ssl_cert=rel_path('dummy_ssl.cert'))
    local('openssl req -nodes -new -x509 -keyout {ssl_key} -out {ssl_cert}'.format(**keys))
    update_ssl(**keys)


@roles('proxy')
@gh_task
def init():
    """ sets-up reverse-proxy
    """
    with total_silence():
        execute(supervisor.stop_program, 'all')        # in case this is re-init, stop all
    execute(system.python)
    execute(system.nginx)
    execute(supervisor.install)
    execute(configure)
    print(yellow('generating self signed ssl for now (you should have yours signed and use proxy.update_ssl!)'))
    keys = dict(ssl_key=rel_path('dummy_ssl.key'), ssl_cert=rel_path('dummy_ssl.cert'))
    local('openssl req -nodes -new -x509 -keyout {ssl_key} -out {ssl_cert}'.format(**keys))
    update_ssl(**keys)
    print_successful()


@task
def create_ssl_key():
    """ helper when generating ssl-key with intention to have it signed by a CA
    """
    local('openssl genrsa -des3 -out server.key 4096')
    print("removing passphrase... (stored as server_insecure.key, it is this one you should give to nginx)")
    local('openssl rsa -in server.key -out server_insecure.key')
    local('openssl req -new -key server.key -out server.csr')
    print("send the server.csr to a CA and await their signed key")
    print("once you have it, you may need to bundle intermediates certificates into it")
