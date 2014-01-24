#!/usr/bin/env python
import sys
import argparse
import os
from unipath import Path
import admin, server, glesys
from proxy import proxy
from fabric.tasks import execute
from lib import new_host_string, gen_password


def rel_path(*path):
    return str(Path(__file__).parent.child(*path))


def base_bootstrap(name, recreate, template_dir, server_yaml):
    if recreate:
        host = glesys.recreate(name)
    else:
        host = glesys.create(name)
    key_file = os.path.expanduser('~/.ssh/{}'.format(host.admin_ssh_key))
    if not os.path.isfile(key_file):
        os.system('ssh-keygen -q -t rsa -N "" -f {}'.format(key_file))

    # must import fabfile only once we are sure the keyfilename exists (fabfile uses global env.key_filename)
    # and must import fabfile as it sets up the global env which are used in the tasks
    import fabfile # flake8: noqa
    execute(server.bootstrap, template_dir=template_dir, server_yaml=server_yaml, pub_key_file=key_file + '.pub',
            hosts=new_host_string('root', host.ip))
    return host


def bootstrap_proxy(name, recreate):
    """ run as: python bootstrap.py

    note: must be python script, cannot be run via fabfile - as fabric uses global env for ssh-key-setting and we create
    key here.
    """
    host = base_bootstrap(name, recreate, template_dir=rel_path('proxy', 'templates'),
                          server_yaml=rel_path('proxy', 'server.yaml'))
    execute(admin.create_user, 'cc_proxy', gen_password(), hosts=new_host_string('admin', host.ip))
    execute(proxy.init, hosts=new_host_string('cc_proxy', host.ip))


def bootstrap_app(name, recreate):
    host = base_bootstrap(name, recreate, template_dir=rel_path('app', 'templates'),
                          server_yaml=rel_path('app', 'server.yaml'))
    execute(admin.create_user, 'cc_appmin', gen_password(), hosts=new_host_string('admin', host.ip))


def parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("name", help="Name of server to act on")
    parser.add_argument("--verbosity", help="increase output verbosity")
    parser.add_argument("--app", help="bootstrap a new app-server", default=False, action='store_true')
    parser.add_argument("--proxy", help="bootstrap a new proxy-server", default=False, action='store_true')
    parser.add_argument("--recreate", help="will totally delete/destroy the VPS(!!) and recreate it",
                        action='store_true',
                        default=False)
    parser.add_argument("--yes", help="will answer yes on prompts", action='store_true', default=False)
    return parser


if __name__ == '__main__':
    args = parser().parse_args()
    if args.app and args.proxy:
        print "Can only bootstrap either app or proxy, not both"
        sys.exit(1)
    if args.recreate and not args.yes:
        print "Are you sure you want to delete the VPS? You will loose everything! (Y)es?"
        a = raw_input()
        if a != 'Y':
            print "aborted"
            sys.exit(0)
    if args.app:
        bootstrap_app(args.name, args.recreate)
    if args.proxy:
        bootstrap_proxy(args.name, args.recreate)

