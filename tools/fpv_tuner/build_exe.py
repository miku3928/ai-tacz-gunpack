# -*- coding: utf-8 -*-
"""把工具打成一个免安装目录（onedir）。

为什么不用 --onefile：单文件 exe 每次启动都要把自己解压到临时目录，
在部分机器上会被杀毒软件拦掉（表现就是"双击闪一下没了"）。目录版没有这个
问题，启动也快得多。代价是一个文件夹而不是一个文件 —— 压缩后差不多大。

用法：
    python build_exe.py            # 打目录版
    python build_exe.py --onefile  # 打单文件版（知道自己机器杀软不拦再用）
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = 'TaCZ第一人称定位调参器'

ONEFILE = '--onefile' in sys.argv

# 打完之后删掉用不上的东西。只删确定没被 import 的：
#   _avif    PIL 的 AVIF 解码器，7.6MB，没人拿 avif 当游戏截图
#   numpy.libs/libscipy_openblas64_*.dll  —— **不能删**，numpy 的 C 扩展依赖它，
#            删了会 "DLL load failed while importing _multiarray_umath"。
PRUNE = ('PIL/_avif.cp314-win_amd64.pyd',)


def _prune():
    root = os.path.join(HERE, 'dist', NAME, '_internal')
    if not os.path.isdir(root):
        return
    for rel in PRUNE:
        p = os.path.join(root, rel.replace('/', os.sep))
        if os.path.exists(p):
            os.remove(p)
            print('pruned', rel)


def main():
    for d in ('build', 'dist'):
        p = os.path.join(HERE, d)
        if os.path.isdir(p):
            shutil.rmtree(p)
    spec = os.path.join(HERE, NAME + '.spec')
    if os.path.exists(spec):
        os.remove(spec)

    args = [
        sys.executable, '-m', 'PyInstaller',
        '--noconfirm', '--clean',
        '--onefile' if ONEFILE else '--onedir',
        '--windowed',
        '--name', NAME,
        '--icon', os.path.join(HERE, 'icon.ico'),
        '--distpath', os.path.join(HERE, 'dist'),
        '--workpath', os.path.join(HERE, 'build'),
        '--specpath', HERE,
        # 只留真正用到的，别把科学计算栈整个拖进来
        '--exclude-module', 'matplotlib',
        '--exclude-module', 'scipy',
        '--exclude-module', 'pandas',
        '--exclude-module', 'pytest',
        '--exclude-module', 'PyInstaller',
        '--hidden-import', 'PIL._tkinter_finder',
        # --selftest 会用到
        '--hidden-import', 'selftest',
        os.path.join(HERE, 'gui.py'),
    ]
    print(' '.join(args))
    r = subprocess.run(args, cwd=HERE)
    print('pyinstaller exit', r.returncode)

    _prune()

    if ONEFILE:
        exe = os.path.join(HERE, 'dist', NAME + '.exe')
        if os.path.exists(exe):
            print('EXE %s  %.1f MB' % (exe, os.path.getsize(exe) / 1e6))
        else:
            print('!! exe not produced')
    else:
        folder = os.path.join(HERE, 'dist', NAME)
        exe = os.path.join(folder, NAME + '.exe')
        if os.path.exists(exe):
            total = sum(os.path.getsize(os.path.join(dp, f))
                        for dp, _dn, fn in os.walk(folder) for f in fn)
            print('DIR %s  exe %.1f MB  目录合计 %.1f MB'
                  % (folder, os.path.getsize(exe) / 1e6, total / 1e6))
        else:
            print('!! exe not produced')
    return r.returncode


if __name__ == '__main__':
    sys.exit(main())