def configure_options(project_name, options):
    if project_name.startswith('dxvk-'):
        config_args = options.setdefault('config_args', [])
        config_args.extend([
            '--buildtype', 'release',
            '--strip',
            '-Denable_tests=false',
        ])
    elif project_name.startswith('wine-'):
        config_args = options.setdefault('config_args', [])
        config_args.extend([
            '--disable-tests',
            # '--verbose',
            # '--without-mingw',
            '--without-hal',
            '--without-sane',
            '--without-gphoto',
            '--without-oss',
            '--without-capi',
            '--without-vkd3d',
            '--with-x',
            '--with-gstreamer',
        ])
