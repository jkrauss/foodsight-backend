import pathlib
import os

cwd = pathlib.os.getcwd()
pathlib.os.chdir('./pipeline')

# pair all steps/modules of the folder/package 'pipeline' in alphabetical order
flist = list()

p = pathlib.Path('.').glob('./*.py')
files = [x for x in p if x != pathlib.Path('util.py')]

for f in files:
    os.system(f'jupytext --set-formats py:percent,ipynb {str(f)}')

pathlib.os.chdir(cwd)
