#!/usr/bin/env python3

import argparse
import copy
import os
import sys
import subprocess
import enum
import shutil
import configparser
import pathlib
import importlib
import stat


class Arch(enum.Enum):
    X86 = 1
    X64 = 2
    X86_64 = 3


def clone_attrib(obj, attr):
    new_obj = copy.copy(obj)
    val = getattr(new_obj, attr)
    new_val = copy.deepcopy(val)
    setattr(new_obj, attr, new_val)

    return new_obj


def cat(path, mode='r'):
    with open(path, mode) as f:
        return f.read()


def exec1(args, check=False, env=None, cwd=None):
    print('Executing {}'.format(' '.join(args)))
    return subprocess.run(args, env=env, check=check, cwd=cwd).returncode


def exec2(cmd, args, check=False, env=None, cwd=None):
    return exec1([cmd] + args, check, env, cwd)


def check_exec(*args):
    return exec1(args, check=True)


def prepend_flags(env, **kwargs):
    for k, v in kwargs.items():
        env[k] = ' '.join(flags for flags in [v, env.get(k)] if flags)


def prepend_paths(env, *args):
    env['PATH'] = ':'.join(arg for arg in [*args, env.get('PATH')] if arg)


def get_meson_flags(crossfile):
    flags = {
        'c_args': [],
        'c_link_args': [],
        'cpp_args': [],
        'cpp_link_args': [],
    }

    cross_config = configparser.ConfigParser()
    cross_config.read(crossfile)

    if not cross_config.has_section('properties'):
        return flags

    for k, v in cross_config.items('properties'):
        if k not in flags:
            continue

        try:
            res = eval(v, {'__builtins__': None},
                       {'true': True, 'false': False})
        except Exception:
            raise Exception('Malformed value in cross file variable ' + k)

        if not isinstance(res, list):
            res = [res]

        flags[k].extend(res)

    return flags


def create_bash_env_file(ctx, filename):
    env = {}
    basename = os.path.basename(ctx.builddir)

    env['PATH'] = os.path.join(ctx.builddir, 'wine/install/bin') + ':$PATH'
    env['LD_LIBRARY_PATH'] = '{}:{}:$LD_LIBRARY_PATH'.format(
        os.path.join(ctx.builddir, 'wine/install/lib'),
        os.path.join(ctx.builddir, 'wine/install/lib64'),
    )

    with open(filename, 'w') as f:
        f.write('#!/bin/bash\n\n')
        for key, val in env.items():
            f.write('export {}="{}"\n'.format(key, val))

        f.write('\nexec bash --rcfile <(echo \'source ~/.bashrc; export '
                'PS1="({}) $PS1"\') -i'.format(basename))

        fileno = f.fileno()

        s = os.fstat(fileno)

        os.fchmod(fileno, s.st_mode | stat.S_IXUSR | stat.S_IXGRP)


class Context:
    def __init__(self, srcdir, builddir, env):
        self.srcdir = srcdir
        self.builddir = builddir
        self.env = env


class Project:
    def __init__(self, name, src_dir, dst_dir, env, options):
        self.name = name
        self.dst_dir = dst_dir
        self.src_dir = src_dir
        self.env = env
        self.options = options

        self.build_prio = 10
        self.install_prio = 10

    def pre_configure(self):
        raise NotImplementedError()

    def configure(self):
        raise NotImplementedError()

    def build(self, jobs):
        raise NotImplementedError()

    def install(self, jobs):
        raise NotImplementedError()


class WineProject(Project):
    def __init__(self, name, src_dir, dst_dir, env, options):
        super(WineProject, self).__init__(name, src_dir, dst_dir, env, options)
        self.args = None

    def pre_configure(self):
        self.args = self.options.get('config_args', [])

        for var in ['CFLAGS', 'CPPFLAGS', 'LDFLAGS']:
            self.env[var] = self.options.get(var, '')

    def configure(self):
        os.makedirs(self.dst_dir, exist_ok=True)

        exec2(os.path.join(self.src_dir, 'configure'), self.args, check=True,
              env=self.env, cwd=self.dst_dir)

    def make(self, target, jobs):
        make_args = [target]

        if jobs is not None:
            make_args.append('-j' + jobs)

        exec2('make', make_args, check=True, env=self.env, cwd=self.dst_dir)

    def build(self, jobs):
        self.make('all', jobs)

    def install(self, jobs):
        self.make('install', jobs)
        self.make('clean', jobs)


class DXVKProject(Project):
    def __init__(self, name, src_dir, dst_dir, env, options):
        super(DXVKProject, self).__init__(name, src_dir, dst_dir, env, options)
        self.args = None

    def pre_configure(self):
        self.args = self.options.get('config_args', [])

        for arg in ['c_args', 'cpp_args', 'c_link_args', 'cpp_link_args']:
            flags = self.options.get(arg)

            if flags:
                self.args.append('-D{}={}'.format(arg, flags))

    def configure(self):
        os.makedirs(self.dst_dir, exist_ok=True)

        exec2('meson', self.args, check=True, env=self.env, cwd=self.src_dir)

    def build(self, jobs):
        make_args = ['install']

        if jobs is not None:
            make_args.append('-j' + jobs)

        exec2('ninja', make_args, check=True, env=self.env, cwd=self.dst_dir)

    def install(self, jobs):
        pass


def configure_dxvk(ctx, winelib=False):
    prefix = 'dxvk-winelib' if winelib else 'dxvk-mingw'

    srcdir = os.path.join(ctx.srcdir, 'dxvk')
    builddir = os.path.join(ctx.builddir, prefix)
    crossfile = 'build-wine' if winelib else 'build-win'

    builddir_x32 = os.path.join(builddir, 'build.32')
    builddir_x64 = os.path.join(builddir, 'build.64')
    crossfile_x32 = os.path.join(srcdir, crossfile + '32.txt')
    crossfile_x64 = os.path.join(srcdir, crossfile + '64.txt')

    meson_flags_x32 = get_meson_flags(crossfile_x32)
    meson_flags_x64 = get_meson_flags(crossfile_x64)

    def merge_flags(flags, base_flags):
        return ' '.join(flag for flag in [*flags, base_flags] if flag)

    flags_x32 = {}
    flags_x64 = {}

    cflags = ctx.env.get('CFLAGS', '')
    cppflags = ctx.env.get('CPPFLAGS', '')
    ldflags = ctx.env.get('LDFLAGS', '')

    for k, flags in [('c_args', cflags), ('cpp_args', cppflags),
                     ('c_link_args', ldflags), ('cpp_link_args', ldflags)]:
        flags_x32[k] = merge_flags(meson_flags_x32[k], flags)
        flags_x64[k] = merge_flags(meson_flags_x64[k], flags)

    proj_x32 = DXVKProject(
        name=prefix + '-x32',
        src_dir=srcdir,
        dst_dir=builddir_x32,
        env=dict(ctx.env),
        options={
            'config_args': [
                '--cross-file', os.path.join(srcdir, crossfile + '32.txt'),
                '--bindir', 'x32',
                '--libdir', 'x32',
                '--prefix', builddir,
                builddir_x32,
            ],
            **flags_x32,
        },
    )

    proj_x64 = DXVKProject(
        name=prefix + '-x64',
        src_dir=srcdir,
        dst_dir=builddir_x64,
        env=dict(ctx.env),
        options={
            'config_args': [
                '--cross-file', os.path.join(srcdir, crossfile + '64.txt'),
                '--bindir', 'x64',
                '--libdir', 'x64',
                '--prefix', builddir,
                builddir_x64,
            ],
            **flags_x64,
        },
    )

    os.makedirs(builddir, exist_ok=True)
    shutil.copy(os.path.join(srcdir, 'setup_dxvk.sh'),
                os.path.join(builddir, 'setup_dxvk.sh'))

    return [proj_x64, proj_x32]


def configure_wine3264(ctx, arch):
    srcdir = os.path.join(ctx.srcdir, 'wine')
    builddir = os.path.join(ctx.builddir, 'wine')

    builddir_wine32 = os.path.join(builddir, 'wine32')
    builddir_wine64 = os.path.join(builddir, 'wine64')
    builddir_install = os.path.join(builddir, 'install')

    projects = []

    flags = {
        'CFLAGS': ctx.env.get('CFLAGS', ''),
        'CPPFLAGS': ctx.env.get('CPPFLAGS', ''),
        'LDFLAGS': ctx.env.get('LDFLAGS', ''),
    }

    if arch in [Arch.X64, Arch.X86_64]:
        proj_x64 = WineProject(
            name='wine-64',
            src_dir=srcdir,
            dst_dir=builddir_wine64,
            env=dict(ctx.env),
            options={
                'config_args': [
                    '--prefix', builddir_install,
                    '--enable-win64',
                ],
                **flags,
            },
        )

        proj_x64.build_prio -= 1

        projects.append(proj_x64)

    if arch in [Arch.X86, Arch.X86_64]:
        extra_args = []

        if arch == Arch.X86_64:
            extra_args.append('--with-wine64=' + builddir_wine64)

        proj_x86 = WineProject(
            name='wine-32',
            src_dir=srcdir,
            dst_dir=builddir_wine32,
            env=dict(ctx.env),
            options={
                'config_args': [
                    '--prefix', builddir_install,
                    *extra_args,
                ],
                **flags,
            },
        )

        proj_x86.install_prio -= 1

        proj_x86.env['PKG_CONFIG_PATH'] = '/usr/lib32/pkgconfig/'

        projects.append(proj_x86)

    create_bash_env_file(ctx, 'wine-env.sh')

    return projects


def load_options(ctx, projects):
    scripts_dir = pathlib.Path(ctx.srcdir).joinpath('config_scripts')
    files = scripts_dir.glob('*.py')

    for script_path in sorted(files):
        spec = importlib.util.spec_from_file_location(
            script_path.stem, str(script_path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, 'configure_options'):
            continue

        for project in projects:
            module.configure_options(project.name, project.options)


def make_ccache_symlinks(ctx):
    names = [
        'clang',
        'clang++',
    ]

    for prefix in ['', 'x86_64-w64-mingw32-', 'i686-w64-mingw32-']:
        for bin_name in ['cc', 'c++', 'gcc', 'g++']:
            names.append(prefix + bin_name)

    ccache_bin = shutil.which('ccache', path=ctx.env.get('PATH'))
    if not ccache_bin:
        raise ValueError("Cannot find path to ccache binary")

    bindir = os.path.join(ctx.builddir, 'build_bin')

    os.makedirs(bindir, exist_ok=True)

    for name in names:
        path = os.path.join(bindir, name)
        try:
            os.symlink(src=ccache_bin, dst=path)
        except FileExistsError:
            print('Warning: file {} already exists'.format(path))


def make_context(no_ccache=False):
    srcdir = os.path.dirname(os.path.realpath(sys.argv[0]))
    builddir = os.getcwd()
    env = dict(os.environ)

    if not no_ccache:
        env['CCACHE_CONFIGPATH'] = os.path.join(srcdir, 'ccache/ccache.conf')
        prepend_paths(env, os.path.join(builddir, 'build_bin'))

    return Context(
        srcdir=srcdir,
        builddir=builddir,
        env=env,
    )


def main(cmd, no_ccache=False, kinds=None, args=None, jobs=None):
    WINE_ARCH_MAP = {
        'wine32': Arch.X86,
        'wine64': Arch.X64,
        'wine': Arch.X86_64,
    }

    ctx = make_context(no_ccache)

    if not no_ccache:
        make_ccache_symlinks(ctx)

    if cmd not in ['configure', 'build']:
        raise ValueError('Invalid command {}'.format(cmd))

    projects = []
    for kind in kinds:
        wine_arch = WINE_ARCH_MAP.get(kind)
        dxvk_winelib = kind == 'dxvk-winelib'
        dxvk_mingw = kind == 'dxvk-mingw'

        if wine_arch:
            projects.extend(configure_wine3264(ctx, wine_arch))
        elif dxvk_mingw:
            projects.extend(configure_dxvk(ctx, False))
        elif dxvk_winelib:
            projects.extend(configure_dxvk(ctx, True))
        else:
            raise ValueError('Unknown configure kind: ' + kind)

    load_options(ctx, projects)

    if cmd == 'configure':
        for project in projects:
            print('Pre-onfiguring ' + project.name)
            project.pre_configure()

        for project in projects:
            print('Configuring ' + project.name)
            project.configure()
    elif cmd == 'build':
        projects.sort(key=lambda c: c.build_prio)
        for project in projects:
            print('Building ' + project.name)
            project.build(jobs)

        projects.sort(key=lambda c: c.install_prio)
        for project in projects:
            print('Installing ' + project.name)
            project.install(jobs)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--no-ccache', action='store_true', default=False)

    subparsers = parser.add_subparsers(dest='cmd')

    parser_conf = subparsers.add_parser('configure')
    parser_conf.add_argument(
        'kinds', nargs='+', choices=[
            'wine32', 'wine64', 'wine', 'dxvk-winelib', 'dxvk-mingw'
        ]
    )

    parser_build = subparsers.add_parser('build')
    parser_build.add_argument(
        'kinds', nargs='+', choices=[
            'wine32', 'wine64', 'wine', 'dxvk-winelib', 'dxvk-mingw'
        ]
    )
    parser_build.add_argument('--jobs', '-j')

    main(**vars(parser.parse_args()))
