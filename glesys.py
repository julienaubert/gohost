import time
import json
from fabric.colors import green, red
from fabric.context_managers import settings
from fabric.operations import local, run
import requests
from urlparse import urljoin
from collections import namedtuple
import logging
from fabric.tasks import execute
import sys
from lib import total_silence, new_host_string

log = logging.getLogger(__name__)


class AuthFailed(Exception):
    pass


class ApiError(Exception):
    pass


Server = namedtuple('GleSysServer', ['server_id', 'root_password', 'ip', 'ipv6', 'hostname', 'admin_ssh_key'])


class GleSys(object):
    base = 'https://api.glesys.com/'

    def __init__(self, cl_user, api_key):
        self.cl_user = cl_user
        self.api_key = api_key

    def _post(self, command, data=None):
        url = urljoin(self.base, '{}/format/json'.format(command))
        response = requests.post(url, data=data, auth=(self.cl_user, self.api_key))
        log.info('{0} get {1}'.format(response.status_code, url))
        if response.status_code == 404:
            raise ApiError("url: {} gave 404!".format(url))
        if response.status_code == 401:
            raise AuthFailed(repr(response.text))
        if response.status_code != 200:
            raise Exception('expect response code 200.\n' + repr(response) + '\n' + response.text)
        log.debug('response: {0}'.format(response.json()))
        return response.json()

    def _json_get(self, command):
        url = urljoin(self.base, '{}/format/json'.format(command))
        response = requests.get(url, auth=(self.cl_user, self.api_key))
        log.info('{0} get {1}'.format(response.status_code, url))
        if response.status_code == 404:
            raise ApiError("url: {} gave 404!".format(url))
        if response.status_code == 401:
            raise AuthFailed(repr(response.text))
        if response.status_code != 200:
            raise Exception('expect response code 200.\n' + repr(response))
        log.debug('response: {0}'.format(response.json()))
        return response.json()

    def server_create(self, platform, template_name, disk_gb, memory_mb, cpu_cores, transfer, root_password, hostname,
                      datacenter, admin_ssh_key, description=None, ip=None, ipv6=None):
        """
            platform:  Allowed: OpenVZ, VMware, Xen
            disk_gb: Allowed: 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 120, 140, 150, 160, 200, 250, 300
            memory_mb: Allowed: 128, 256, 512, 768, 1024, 1536, 2048, 2560, 3072, 3584, 4096, 5120, 6144, 7168, 8192,
                                9216, 10240, 11264, 12288, 14336, 16384, 20480, 24576
            transfer: Allowed: 50, 100, 250, 500, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000
            password: at least 8 characters
            template_name: e.g. 'Debian 7.0 64-bit',
        """
        payload = {
            'platform': platform, 'disksize': disk_gb, 'memorysize': memory_mb, 'cpucores': cpu_cores,
            'transfer': transfer, 'rootpassword': root_password, 'hostname': hostname,
            'datacenter': datacenter, 'templatename': template_name, 'description': description, 'ip': ip, 'ipv6': ipv6
        }
        server_json = self._post(urljoin(self.base, 'server/create'), data=payload)['response']['server']
        ip_v = {4: None, 6: None}
        for ip_info in server_json['iplist']:
            ip_v[ip_info['version']] = ip_info['ipaddress']
        return Server(
            server_id=server_json['serverid'],
            root_password=root_password,
            ip=ip_v[4],
            ipv6=ip_v[6],
            hostname=server_json['hostname'],
            admin_ssh_key=admin_ssh_key
        )

    def server_id(self, hostname):
        res = self._json_get('server/list')
        servers = res['response']['servers']
        for server in servers:
            if server['hostname'] == hostname:
                return server['serverid']

    def server_destroy(self, hostname, keep_ip=False):
        server_id = self.server_id(hostname)
        if server_id is None:
            raise ApiError('No server with that hostname')
        payload = {'serverid': server_id, 'keepip': int(keep_ip)}
        return self._post(urljoin(self.base, 'server/destroy'), data=payload)

    def account_info(self):
        return self._json_get('account/info')


def read_conf(filename):
    with open(filename) as conf_json:
        return json.load(conf_json)


def server_conf(name):
    kw = read_conf('.glesys')['servers'][name]
    kw = {u: v for u, v in kw.iteritems() if u in Server._fields}
    kw['server_id'] = None
    return Server(**kw)


def create(name):
    glesys = GleSys(**read_conf('.glesys')['api'])
    conf = read_conf('.glesys')['servers'][name]
    host = glesys.server_create(**conf)
    local('ssh-keygen -R {}'.format(host.ip))
    local('ssh-keygen -R {}'.format(host.hostname))
    print "waiting for server to become available...",
    wait_until_available(host)
    print(green("OK"))
    return host


def destroy(name):
    glesys = GleSys(**read_conf('.glesys')['api'])
    conf = read_conf('.glesys')['servers'][name]
    glesys.server_destroy(hostname=conf['hostname'], keep_ip=conf['ip'] != '')


def wait_until_available(host):
    def can_ssh():
        host_str = new_host_string('root', host.ip)
        with total_silence():
            class NotReady(Exception):
                pass
            with settings(abort_exception=NotReady):
                try:
                    ret = execute(lambda: run("echo 'OK'"), hosts=host_str)
                except NotReady:
                    return False
                else:
                    if host_str in ret:
                        if 'OK' in ret[host_str]:
                            return True
        return False

    with total_silence():
        local('ping -o {}'.format(host.ip))

    while True:
        if can_ssh():
            break
        else:
            secs = 1
            print(red("ssh may not be up and running yet, retrying in {}s".format(secs)))
            time.sleep(secs)


def recreate(name):
    try:
        print "waiting for server to be destroyed...",
        sys.stdout.flush()
        destroy(name)
        with total_silence():
            while True:
                ip = read_conf('.glesys')['servers'][name]['ip']
                result = local('ping -o -t 1 {}'.format(ip))
                if result.return_code != 0:
                    break
    except ApiError:
        pass
    print(green("OK."))
    sys.stdout.flush()
    host = create(name)
    return host
