"""
utility to render template files given yaml files. yaml files inherits from default.yaml
(creds to S.Apostolico)
"""
from functools import partial

import os
import yaml


# utilities to handle inheritance in yaml files
from fabric.contrib.files import upload_template
from bh.utils import get_home_dir


class RUDict(dict):
    def __init__(self, *args, **kw):
        super(RUDict, self).__init__(*args, **kw)

    def update(self, E=None, **F):
        if E is not None:
            if 'keys' in dir(E) and callable(getattr(E, 'keys')):
                for k in E:
                    if k in self:  # existing ...must recurse into both sides
                        self.r_update(k, E)
                    else:  # doesn't currently exist, just update
                        self[k] = E[k]
            else:
                for (k, v) in E:
                    self.r_update(k, {k: v})

        for k in F:
            self.r_update(k, {k: F[k]})

    def r_update(self, key, other_dict):
        if isinstance(self[key], dict) and isinstance(other_dict[key], dict):
            od = RUDict(self[key])
            nd = other_dict[key]
            od.update(nd)
            self[key] = od
        else:
            self[key] = other_dict[key]


def _parse_template(filepath, context, outdir=None):
    """ finds filepath relative root ("/") or relative cwd (".")
    """
    input_name = "%s" % filepath

    from jinja2 import Environment, FileSystemLoader

    jenv = Environment(loader=FileSystemLoader(searchpath=['.', '/']))
    text = jenv.get_template(input_name).render(**context or {})

    filedir = outdir or os.path.dirname(filepath)
    filename = os.path.basename(filepath)
    dest = os.path.join(filedir, filename)
    with open(dest, 'w') as outputfile:
        outputfile.write(text)


put_template = partial(upload_template, use_jinja=True)


def get_config(env, yaml_file, default_yaml_file=None):
    return _get_config(yaml_file, default_yaml_file,
                       context={'USER_HOME': get_home_dir(env.user),
                                'USER_GROUP': env.group,
                                'USER': env.user})


def get_role_config(env=None):
    """ returns rendered config for this env, if none, renders with default.yaml
    """
    if len(env.roles) != 1:
        raise Exception("must invoke with one role: fab -R xxx, roles in env: {}".format(env.roles))
    role = env.roles[0]
    yaml_dir = os.path.join('app', 'envs')
    yaml_file = os.path.join(yaml_dir, '{}.yaml'.format(role))
    default_yaml_file = os.path.join(yaml_dir, 'default.yaml')
    return _get_config(yaml_file, default_yaml_file,
                       context={'USER_HOME': get_home_dir(env.user),
                                'USER_GROUP': env.group,
                                'USER': env.user})


def _get_config(yaml_file, default_yaml_file, build_dir='tmp', context=None):
    os.system('mkdir -p {}'.format(build_dir))

    if default_yaml_file:
        _parse_template(default_yaml_file, context, outdir=build_dir)
        filename = os.path.join(build_dir, os.path.basename(default_yaml_file))
        with open(filename, 'r') as f:
            defaults = yaml.load(f)
    else:
        defaults = {}

    if yaml_file:
        _parse_template(yaml_file, context, outdir=build_dir)
        filename = os.path.join(build_dir, os.path.basename(yaml_file))
        with open(filename, 'r') as f:
            cfg = yaml.load(f) or {}
    else:
        cfg = defaults

    dx = RUDict(defaults)
    dx.update(cfg)

    return dx
