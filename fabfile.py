"""

"""

# import os
import admin, glesys, supervisor # want their commands to show up in fab -l    flake8: noqa
from proxy import proxy # want their commands to show up in fab -l    flake8: noqa
from app import app # want their commands to show up in fab -l    flake8: noqa
import os
from fabric.api import env
import sys
from bh.utils import init

env.PREFIX = '/opt/cc_instances'
env.common_dir = '{}/common'.format(env.PREFIX)
env.group = 'cc'
env.PASSWORD_FILE = '~/.credentials.json'
env.PYTHON = "2.7.6"
env.REDIS = "2.8.6"
env.NGINX = "1.5.10"
env.PCRE = "8.34"
env.UWSGI = "2.0.1"
init()

APP_SERVERS = ['example']
PROXY_SERVER = 'example'

servers = glesys.read_conf('.glesys')['servers']

# TODO: how handle keys? one key per role, and then set env.key_filename in the task decorator?
server_conf = glesys.read_conf('.glesys')['servers']['example']
env.key_filename = os.path.expanduser('~/.ssh/{admin_ssh_key}'.format(**server_conf))
if not os.path.isfile(env.key_filename):
    print "must generate the ssh admin key: {}".format(env.key_filename)
    sys.exit(-1)
env.use_ssh_config = True


env.roledefs.update(app.roledefs(app_name='myapp', hostnames=[servers[s]['hostname'] for s in APP_SERVERS]))
env.roledefs.update(proxy.roledefs(servers[PROXY_SERVER]['hostname']))
