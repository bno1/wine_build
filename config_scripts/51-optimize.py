COMMON_CFLAGS = (
    # '-march=skylake -mmmx -mno-3dnow -msse -msse2 -msse3 -mssse3 '
    # '-mno-sse4a -mcx16 -msahf -mmovbe -maes -mno-sha -mpclmul -mpopcnt -mabm '
    # '-mno-lwp -mfma -mno-fma4 -mno-xop -mbmi -msgx -mbmi2 -mno-pconfig '
    # '-mno-wbnoinvd -mno-tbm -mavx -mavx2 -msse4.2 -msse4.1 -mlzcnt -mrtm '
    # '-mhle -mrdrnd -mf16c -mfsgsbase -mrdseed -mprfchw -madx -mfxsr -mxsave '
    # '-mxsaveopt -mno-avx512f -mno-avx512er -mno-avx512cd -mno-avx512pf '
    # '-mno-prefetchwt1 -mclflushopt -mxsavec -mxsaves -mno-avx512dq '
    # '-mno-avx512bw -mno-avx512vl -mno-avx512ifma -mno-avx512vbmi '
    # '-mno-avx5124fmaps -mno-avx5124vnniw -mno-clwb -mno-mwaitx -mno-clzero '
    # '-mno-pku -mno-rdpid -mno-gfni -mno-shstk -mno-avx512vbmi2 '
    # '-mno-avx512vnni -mno-vaes -mno-vpclmulqdq -mno-avx512bitalg -mno-movdiri '
    # '-mno-movdir64b -mno-waitpkg -mno-cldemote -mno-ptwrite '
    # '--param l1-cache-size=32 --param l1-cache-line-size=64 '
    # '--param l2-cache-size=6144 -mtune=skylake -ftree-vectorize '
    # '-Wa,-mbranches-within-32B-boundaries'
    # '-march=native -mtune=native -ftree-vectorize '
    # '-Wa,-mbranches-within-32B-boundaries '
    #'-ftree-vectorize -Wa,-mbranches-within-32B-boundaries'
    ''
)

COMMON_LDFLAGS = (
    '' # '-Wl,-O1,--sort-common '  # ,--as-needed'
)

WINE_CFLAGS = COMMON_CFLAGS
WINE_LDFLAGS = COMMON_LDFLAGS

DXVK_MINGW_CFLAGS = COMMON_CFLAGS + ' -flto '
DXVK_MINGW_LDFLAGS = COMMON_LDFLAGS + ' -flto '


def configure_options(project_name, options):
    if project_name.startswith('dxvk-mingw-'):
        for arg in ['c_args', 'cpp_args']:
            flags = options.get(arg, '')
            options[arg] = flags + ' ' + DXVK_MINGW_CFLAGS

        for arg in ['c_link_args', 'cpp_link_args']:
            flags = options.get(arg, '')
            options[arg] = flags + ' ' + DXVK_MINGW_LDFLAGS
    elif project_name.startswith('dxvk-winelib-'):
        for arg in ['c_args', 'cpp_args']:
            flags = options.get(arg, '')
            options[arg] = flags + ' ' + WINE_CFLAGS

        for arg in ['c_link_args', 'cpp_link_args']:
            flags = options.get(arg, '')
            options[arg] = flags + ' ' + WINE_LDFLAGS
    elif project_name.startswith('wine-'):
        for arg in ['CFLAGS', 'CPPFLAGS']:
            flags = options.get(arg, '')
            options[arg] = flags + ' ' + WINE_CFLAGS

        for arg in ['LDFLAGS']:
            flags = options.get(arg, '')
            options[arg] = flags + ' ' + WINE_LDFLAGS
