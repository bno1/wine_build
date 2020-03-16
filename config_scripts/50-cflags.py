CFLAGS = ' -O3 -pipe'
LDFLAGS = ' -pipe'


def configure_options(project_name, options):
    if project_name.startswith('dxvk-'):
        for arg in ['c_args', 'cpp_args']:
            flags = options.get(arg, '')
            options[arg] = flags + CFLAGS

        for arg in ['c_link_args', 'cpp_link_args']:
            flags = options.get(arg, '')
            options[arg] = flags + LDFLAGS
    elif project_name.startswith('wine-'):
        for arg in ['CFLAGS', 'CPPFLAGS']:
            flags = options.get(arg, '')
            options[arg] = flags + CFLAGS

        for arg in ['LDFLAGS']:
            flags = options.get(arg, '')
            options[arg] = flags + LDFLAGS
