import os
import re
from fabric.api import run
from fabric.api import task as _task
from fabric.colors import yellow, green, red
from fabric.context_managers import settings, hide
from fabric.state import env
from bh.utils import setup_env_for_user
from functools import wraps
import inspect
import sys


def print_successful():
    caller = inspect.stack()[1][3]
    print(green('{} - successful '.format(caller)) + red(':') + green(')'))


def host_string_parts():
    """ returns (user, hostname_or_ip, port) from env.host_string
    """
    if not env.host_string:
        return '', '', ''
    parts = env.host_string.split(':')
    port = '' if len(parts) == 1 else parts[1]
    m = re.search('((?P<user>.+)@)?(?P<domain>.+)', parts[0])
    user = '' if not m.group('user') else m.group('user')
    return user, m.group('domain'), port


def env_ip():
    """ returns ip in env.host_string, if exist, otherwise empty str ''
    """
    domain = host_string_parts()[1]
    m = re.search('(?P<ip>(\d{1,3})(\.\d{1,3}){3})', domain)
    return '' if not m else m.group('ip')


def new_host_string(user=None, domain=None, port=None):
    """ returns env.host_string where user has been added/changed to be the given user
     (i.e. if env.host_string is a@server.com then host_string_user('b') will return b@server.com
    """
    given = dict(zip(('user', 'domain', 'port'), (user, domain, port)))
    current = dict(zip(('user', 'domain', 'port'), host_string_parts()))
    updated = {k: v if given[k] is None else given[k]
               for k, v in current.iteritems()}
    new_host_str = ''
    if updated['user']:
        new_host_str += updated['user'] + '@'
    new_host_str += updated['domain']
    if updated['port']:
        new_host_str += ':' + updated['port']
    return new_host_str


def _fix_boolean(f):
    """ each argument passed to f is 'booleanized', if a string 'false' or 'true' is found, it will make them bool
    """
    def fix_bool(value):
        if isinstance(value, basestring):
            if value.lower() == 'false':
                return False
            if value.lower() == 'true':
                return True
        return value

    @wraps(f)
    def wrapper(*args, **kwargs):
        args_ = [fix_bool(arg) for arg in args]
        kwargs_ = {k: fix_bool(v) for k, v in kwargs.iteritems()}
        return f(*args_, **kwargs_)

    return wrapper


def gh_task(f):
    """ fabric task - where strings 'false'/'true' are passed as boolean False/True instead.

    fabric does not sanitizes bool strings, e.g. fab deploy:config=False will pass 'False' instead of False
    (and 'False' evaluates to True, so that is a problem)
    """
    @wraps(f)
    def g(*args, **kwargs):
        setup_env_for_user()
        f(*args, **kwargs)

    return _task(_fix_boolean(g))


def local_append(filename, text, refuse_keywords, use_sudo=False):
    """ appends text to bottom of content in filename (if text is already in content, then does not append it)
    stops and prompts user to fix file if any in without_keywords exists in the file
    """
    while True:
        with open(filename) as f:
            content = f.read()
        original_content = content
        content = content.replace(text, '')
        content_has_any_keyword = any(keyword in content for keyword in refuse_keywords)
        if not content_has_any_keyword:
            break
        else:
            bad_keywords = [keyword for keyword in refuse_keywords if keyword in content]
            print(red("REFUSED: open {} and remove: {}".format(filename, ', '.join(bad_keywords))))
            answer = raw_input("Waiting for you to fix the file.. (Q to abort): ")
            if answer == 'Q':
                print("aborted")
                sys.exit(0)
    if text not in original_content:
        if use_sudo:
            print(yellow("NOTE: sudoing on your local machine"))
        os.system("printf \"{}\" | {} tee -a {}".format(text, 'sudo' if use_sudo else '', filename))


def local_ssh_config(ip, hostname, ssh_port, key_filename):
    """ updates your LOCAL ssh-conf (~/.ssh/conf) to add server's pub key and non-std port
    """
    ssh_conf_data = ("Host {ip} {hostname}\n"
                     "    IdentityFile {key_file}\n"
                     "    ServerAliveInterval 240\n"
                     "    Port {ssh_port}\n"
                     "".format(ip=ip, hostname=hostname, key_file=key_filename, ssh_port=ssh_port))
    local_append(os.path.expanduser('~/.ssh/config'), ssh_conf_data, refuse_keywords=[ip, hostname])


def gen_password(length=20):
    char_set = ("abcdefghijklmnopqrstuvwxyz"
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                "^!\$%&/()=?{[]}+~#-_.:,;<>|\\"
                "0123456789")
    password = ''
    while len(password) != length:
        c = os.urandom(1)
        while c not in char_set:
            c = os.urandom(1)
        password += c
    return password


def total_silence():
    return settings(hide('warnings', 'stdout', 'running'), quite=True, warn_only=True)


def passwd_retry(user):
    """ set password for user (using passwd), will prompt again if fail (e.g. password did not match)
    """
    while True:
        with settings(hide('warnings'), warn_only=True):
            out = run('passwd admin')
            if out.return_code == 0:
                break


def is_running(name, user=None):
    cmd = "ps -Af | grep '{}' | grep -v 'grep'".format(name)
    if user is not None:
        cmd += "| grep '{}'".format(user)
    with total_silence():
        out = run(cmd)
    return out != ''


def pid_running(pid_file):
    with total_silence():
        res = run('test -e {}'.format(pid_file))
        pid = run('cat {}'.format(pid_file))
        if res.return_code == 0:
            res = run('kill -0 {}'.format(pid))
            if res.return_code == 0:
                return True
    return False
