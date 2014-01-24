from functools import partial
from fabric.context_managers import cd
from fabric.decorators import roles
from fabric.operations import run
from fabric.state import env
from fabric.tasks import execute
from unipath import Path
from bh import system
from lib import gh_task, new_host_string, print_successful, total_silence
from template import put_template, get_role_config
import admin
import supervisor


put_template = partial(put_template, template_dir=str(Path(__file__).parent.child('templates')))


def roledefs(app_name, hostnames):
    return {
        'app_admin': ['admin@{}'.format(name) for name in hostnames],
        'alpha': ['{}_alpha@{}'.format(app_name, name) for name in hostnames],
        'beta': ['{}_beta@{}'.format(app_name, name) for name in hostnames],
        'prod1': ['{}_prod1@{}'.format(app_name, name) for name in hostnames],
        'prod2': ['{}_prod2@{}'.format(app_name, name) for name in hostnames],
    }


@gh_task
def configure():
    put_template('app_nginx.conf', '~/conf/nginx.conf', context=get_role_config(env))
    put_template('app_uwsgi.ini', '~/conf/uwsgi.ini', context=get_role_config(env))
    put_template('app_supervisor.ini', '~/conf/supervisor.ini', context=get_role_config(env))
    execute(supervisor.restart)
    print_successful()


@gh_task
def example_deploy(app_name):
    """ an example of a deploy function (run setup_example first)
    """
    run('pip install django')
    with cd('~/etc'):
        run('django-admin.py startproject {}'.format(app_name))
    run('mv ~/etc/{0}/{0}/wsgi.py ~/conf/wsgi.py'.format(app_name))
    fix_sys_path = ("import os\\n"
                    "import sys\\n"
                    "sys.path.insert(0, os.path.expanduser('~/etc/{}'))".format(app_name))
    run('sed -i "1i {}" ~/conf/wsgi.py'.format(fix_sys_path))
    execute(configure)
    print_successful()


@roles('app_admin')
@gh_task
def create_instance(user_account):
    """ create account for user and install requirements
    """
    with total_silence():
        execute(supervisor.stop_program, 'all')        # in case this is re-init, stop all
    execute(admin.create_user, user_account, password='123', hosts=new_host_string('admin'))
    execute(system.python, hosts=new_host_string(user_account))
    execute(system.nginx, hosts=new_host_string(user_account))
    execute(system.uwsgi, hosts=new_host_string(user_account))
    execute(supervisor.install, hosts=new_host_string(user_account))
    print_successful()


@roles('app_admin')
@gh_task
def create_instances(app_name):
    """ create instances for the app (app_alpha, app_beta, app_prod1, app_prod2)
    """
    execute(create_instance, user_account='{}_alpha'.format(app_name))
    execute(create_instance, user_account='{}_beta'.format(app_name))
    execute(create_instance, user_account='{}_prod1'.format(app_name))
    execute(create_instance, user_account='{}_prod2'.format(app_name))
