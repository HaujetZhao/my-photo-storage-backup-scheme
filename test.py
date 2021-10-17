import time
import subprocess, shlex
from io import TextIOWrapper

命令 = f'ffmpeg -hide_banner -y -i "D:/Users/Haujet/Desktop/VID_20211017_174815.mp4" "D:/Users/Haujet/Desktop/out.mp4"'
# 命令 = f'ffmpeg'
process = subprocess.Popen(shlex.split(命令), shell=True,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT)
# print(process.stdout)
for line in TextIOWrapper(process.stdout, encoding='utf-8', newline='\r'):
    print(f"\r {line}", end='')
    
# for line in process.stdout:
#     print(f"\r {line}", end='')
