"""
名词释意：

- 主库：存放原始图片、视频的文件夹
- 随库：存放压缩版图片、视频的文件夹

脚本功能：

- 将 主库 中的图片、视频创建一份压缩后的副本到 随库


对脚本的功能要求：

- 要增量压缩，不能说主库有 10000 张图片，就要每次都压缩 10000 张
- 要检测损坏视频，例如上一回正在压缩视频，中断了，就会有视频压缩未完成，不能因为这个文件存在，就跳过压缩。
  实际测试发现，每检测一个视频，就要花 0.1 秒，那如果有 1000 个视频，就要花 100 秒检测完整性，这可不行
  所以，在实现上，要在随库新建一个文本文件，叫 .intact_video
  将已经检测过的、完好的视频，放到这个文本文件中
  这样，每次只要对不在记录中的视频进行损坏检测即可
"""

from ntpath import join
import os
import subprocess
import glob
import json
import shlex
import time
from os import path
from io import TextIOWrapper
from pathlib import Path
from pprint import pprint

主库位置 = r'D:\Users\Haujet\Code\Python 我的仓库\为移动设备优化的照片、视频存储方案\Camera'
随库位置 = r'D:\Users\Haujet\Code\Python 我的仓库\为移动设备优化的照片、视频存储方案\Camera-small'

# 忽略文件夹，支持通配符，一行一个
忽略文件夹 = '''
.*
'''

# 合法图片后缀，一行一个
图片后缀 = '''
.jpg
.jpeg
.png
.webp
.heic
'''

# 合法视频后缀，一行一个
视频后缀 = '''
.mp4
.webm
.flv
.mkv
'''

# 在随库中用于存放完好视频的记录文件
完好视频记录文件 = '.intact_video'

# 是否要删除随库中的冗余的照片、视频？
# 解释一下：随库中的图片是主库中的压缩版本
#    但有时，我们会整理主库中的图片，例如删除、移动、重命名
#    这时，如果只将新图片增量压缩到随库
#    随库中就会有以往的旧照片、视频，不干净，需要手动再去清理随库
#    如果启用删除，则会比较随库相比主库，有哪些多余的照片、视频，然后删除
#    但是，这会导致你在随库中新创建的图片、视频也被删掉
#    所以，请辩证性考虑要不要删除
删除随库冗余媒体 = True


def main(): 
    
    # ========================================================================
    # 初始化排除、匹配条件
    忽略文件夹列表 = [y 
                for x in 忽略文件夹.strip().splitlines() 
                for y in glob.glob(f'{主库位置}/{x}')
                if path.isdir(y)]
    # print('忽略以下文件夹：')
    # pprint(忽略文件夹列表)
    合法图片后缀 = [x for x in 图片后缀.strip().splitlines()]
    合法视频后缀 = [x for x in 视频后缀.strip().splitlines()]
    
    # ========================================================================
    print(f'\n主库位置：{主库位置}')
    print(f'随库位置：{随库位置}\n')
    
    if not path.exists(主库位置) or not path.exists(随库位置):
        input('错误：“主库”或“随库”位置不存在\n请先编辑此脚本，指派正确的“主库”、“随库”位置，再运行脚本\n\n按下回车结束')
        return False
    
    print('正在统计文件中……\n')
    遍历文件开始时间 = time.time()
    # 获得主库中所有文件的相对位置，组成列表，用于比较
    主库文件列表 = []
    for root, dirs, names in os.walk(主库位置):
        
        # 先检查当前文件夹是不是在忽略的文件夹列表中
        if root in 忽略文件夹列表:
            continue

        # 再统计所有文件的相对路径
        for name in names:
            主库文件列表.append([root[len(主库位置):].strip('/\\'), name])

    主库图片列表, 主库视频列表, 主库其它文件列表 = [], [], []
    for file in 主库文件列表: 
        if path.splitext(file[1])[1].lower() in 合法图片后缀:
            主库图片列表.append(file)
        elif path.splitext(file[1])[1].lower() in 合法视频后缀:
            主库视频列表.append(file)
        else:
            主库其它文件列表.append(file)
    # ========================================================================
    # 获得随库中所有文件的相对位置，组成列表，用于比较
    随库文件列表 = []
    for root, dirs, names in os.walk(随库位置):

        # 先检查当前文件夹是不是在忽略的文件夹列表中
        if root in 忽略文件夹列表:
            continue

        # 再统计所有文件的相对路径
        for name in names:
            随库文件列表.append([root[len(随库位置):].strip('/\\'), name])

    随库图片列表, 随库视频列表, 随库其它文件列表 = [], [], []
    for file in 随库文件列表:
        if path.splitext(file[1])[1].lower() in 合法图片后缀:
            随库图片列表.append(file)
        elif path.splitext(file[1])[1].lower() in 合法视频后缀:
            随库视频列表.append(file)
        else:
            随库其它文件列表.append(file)
    
    
    # ========================================================================
    统计文件消耗时间 = time.time() - 遍历文件开始时间
    # ========================================================================
    # 去除已压缩的图片，得到主库中都有哪些图片需要压缩副本到随库
    随库图片前缀列表 = [path.splitext(f'{x[0]}/{x[1]}'.lstrip('/'))[0]
                for x in 随库图片列表]
    主库需要压缩的图片列表 = [y for y in 主库图片列表  
                   if path.splitext(f'{y[0]}/{y[1]}'.lstrip('/'))[0] 
                   not in 随库图片前缀列表]
    
    # 去除已压缩的视频，得到主库中都有哪些视频需要压缩副本到随库
    # 由于视频压制时间较长，有可能上一次压制的时候，强制退出了，导致留下了未压制完成的视频文件
    # 因此，需要对随库中每一个文件检验一下，看是否为完整的视频文件
    检测视频开始时间 = time.time()
    随库完好视频列表 = 筛选出完好的视频列表(随库位置, 随库视频列表, 完好视频记录文件)
    随库视频前缀列表 = [path.splitext(x)[0] 
                for x in 随库完好视频列表]
    主库需要压缩的视频列表 = [x for x in 主库视频列表
                   if path.splitext(path.join(x[0], x[1]))[0] 
                   not in 随库视频前缀列表]
    # print(f'随库完好视频列表:{随库完好视频列表}')
    # print(f'随库视频前缀列表：{随库视频前缀列表}')
    # print(f'主库需要压缩的视频列表：{主库需要压缩的视频列表}')
    # print(f'：{}')
    # input('...')
    
    检测视频消耗时间 = time.time() - 检测视频开始时间
    # ========================================================================
    # 当主库中删除视频图片后，肯定也希望这个希望能同步到随库
    # 所以要检测一下随库中多了哪些文件，将其删除
    主库图片前缀列表 = [path.splitext(
        f'{x[0]}/{x[1]}'.lstrip('/'))[0] for x in 主库图片列表]
    随库需要删除图片列表 = [x for x in 随库图片列表 
                  if path.splitext(f'{x[0]}/{x[1]}'.lstrip('/'))[0]
                  not in 主库图片前缀列表]
    
    主库视频前缀列表 = [path.splitext(
        f'{x[0]}/{x[1]}'.lstrip('/'))[0] for x in 主库视频列表]
    随库需要删除视频列表 = [x for x in 随库视频列表
                  if path.splitext(f'{x[0]}/{x[1]}'.lstrip('/'))[0]
                  not in 主库视频前缀列表]
    # ========================================================================

    

    print(f'主库中共有 {len(主库文件列表)} 个文件')
    print(f'    有 {len(主库图片列表)} 个图片，其中有 {len(主库需要压缩的图片列表)} 个需要压缩到随库副本')
    print(f'    有 {len(主库视频列表)} 个视频，其中有 {len(主库需要压缩的视频列表)} 个需要压缩到随库副本')
    print(f'    有 {len(主库其它文件列表)} 个其它文件\n')

    print(f'随库中目前共有 {len(随库文件列表)} 个文件')
    print(f'    有 {len(随库图片列表)} 个图片，其中有 {len(随库需要删除图片列表)} 个冗余图片')
    print(f'    有 {len(随库视频列表)} 个视频，其中有 {len(随库需要删除视频列表)} 个冗余视频')
    print(f'    有 {len(随库其它文件列表)} 个其它文件\n')
    
    print(f'遍历文件耗时 {"%5.2f" % 统计文件消耗时间}s，检测视频完整性耗时 {"%5.2f" % 检测视频消耗时间}s\n')
    # ========================================================================
    
    压缩主库图片到随库(主库需要压缩的图片列表)
    压缩主库视频到随库(主库需要压缩的视频列表)
    
    if 删除随库冗余媒体:
        if 随库需要删除图片列表 or 随库需要删除视频列表:
            print(f'正在删除随库中的冗余媒体文件……\n')
            依列表删除随库文件(随库需要删除图片列表)
            依列表删除随库文件(随库需要删除视频列表)
        else:
            print(f'随库中没有需要删除的冗余媒体文件\n')
    else:
        print(f'不删除随库中的冗余媒体文件\n')
    
    
    
    input('全部任务执行完毕，回车结束')
    

def 取得视频信息(视频路径):
    # 需要使用 ffprobe
    命令 = f'ffprobe -hide_banner -of json -show_streams -select_streams v "{视频路径}"'
    输出 = subprocess.run(shlex.split(命令), capture_output=True).stdout
    格式化的输出信息 = json.loads(输出)
    
    # 判断输出是否有错误
    if 'streams' not in 格式化的输出信息:
        return False
    
    return 格式化的输出信息['streams'][0]



    
def 判断视频是否已压制完成(压缩视频路径): 
    压缩视频信息 = 取得视频信息(压缩视频路径)
    
    # 如果视频压缩过程被强制中断过，那就会有非法数据
    # ffprobe 会返回空输出
    # 由此断定上次的压制未完成
    if not 压缩视频信息:
        return False
    else:
        return True


def 筛选出完好的视频列表(根目录, 列表, 记录文件):
    # 列表中包含的项是这样的： ['relative/path', 'file.name']
    记录文件 = path.join(根目录, 记录文件)
    if not path.exists(记录文件):
        print(f'创建视频完整性记录文件：{记录文件}')
        with open(记录文件, 'w'):
            ...
    
    # 得到还没有记录的视频有哪些
    with open(记录文件, encoding='utf-8') as f:
        记录内容 = f.read()
        现有列表 = [path.join(x[0], x[1]) for x in 列表] # 随库中的文件列表（相对路径）
        记录列表 = [x.strip() for x in 记录内容.splitlines()] # 记录文件中的文件列表
        新记录列表 = [x for x in 记录列表 if x in 现有列表] # 记录文件更新，去除已删除文件的记录
        待测列表 = [x for x in 现有列表 if x not in 新记录列表]
        if 新记录列表 != 记录列表: 
            f = open(记录文件, 'w', encoding='utf-8')
            f.write('\n'.join(新记录列表))
        
    
    # 对没有记录的视频进行检测
    with open(记录文件, 'a', encoding='utf-8') as f:
        for 待测项 in 待测列表:
            相对路径 = path.join(待测项[0], 待测项[1])
            if 判断视频是否已压制完成(path.join(根目录, 相对路径)):
                记录列表.append(相对路径)
                f.write(相对路径 + '\n')
    
    # 这里返回的列表中，每一项都是相对路径
    return 记录列表


def 依列表删除随库文件(文件列表):
    # 列表中包含的项是这样的： ['relative/path', 'file.name']
    for item in 文件列表:
        完整路径 = path.join(随库位置, item[0], item[1])
        try:
            os.remove(完整路径)
        except Exception as e:
            print(f'删除文件失败：{完整路径}  {e}')


def 压缩主库图片到随库(图片列表):
    # 列表中包含的项是这样的： ['relative/path', 'file.name']
    print(f'开始压缩图片到随库，总共有 {len(图片列表)} 个图片需要压缩\n')
    for index, item in enumerate(图片列表):
        src = path.join(主库位置, item[0], item[1])
        src_rel = path.join(item[0], item[1])
        dst = path.join(随库位置, item[0], item[1])
        dst = path.splitext(dst)[0] + '.webp'  # 将输出文件格式改为 webp
        dst_rel = path.splitext(src_rel)[0] + '.webp'
        
        # 确保目标文件存在
        if not path.exists(path.dirname(dst)):
            os.makedirs(path.dirname(dst))
        
        宽高比 = subprocess.run(shlex.split(
            f'magick identify -format "%[fx:w/h]" "{src}"'),
            capture_output=True).stdout
        
        print(f'    正在压缩第 {index+1} 张图片（共 {len(图片列表)} 张）：')
        print(f'        原文件路径 {path.join("主库", src_rel)}')
        print(f'        原始大小 {文件大小(src)}')
        
        
        
        if float(宽高比) > 0.3 and float(宽高比) < 3:
            print(f'        宽高比 {"%0.2f" % float(宽高比)}，为正常比例图片')
            subprocess.run(
                shlex.split(
                    # 将图像设为 300w 像素大小，只对大图缩小，不对小图放大
                    # 质量 70
                    f'magick "{src}" -resize "3000000@>" -quality 70 "{dst}"'
                ), capture_output=True
            )
        else:
            print(f'        宽高比 {"%0.2f" % float(宽高比)}，为特殊比例图片')
            subprocess.run(
                shlex.split(
                    # 设定图像的最短边，最长为 2000，只对大图缩小，不对小图放大
                    # 质量 70
                    f'magick "{src}" -resize "2000x2000^>" -quality 70 "{dst}"', 
                ), capture_output=True
            )
        print(f'        新文件路径 {path.join("随库", dst_rel)}')
        print(f'        压缩后大小 {文件大小(dst)}')
        压缩比例 = path.getsize(dst) / path.getsize(src) * 100
        print(f'        比原来减小 {"%0.2f" % (100 - 压缩比例)}%\n')
    
    


def 压缩主库视频到随库(视频列表):
    # 列表中包含的项是这样的： ['relative/path', 'file.name']
    print(f'开始压缩视频到随库，总共有 {len(视频列表)} 个视频需要压缩\n')
    for index, item in enumerate(视频列表):
        src = path.join(主库位置, item[0], item[1])
        src_rel = path.join(item[0], item[1])
        dst = path.join(随库位置, item[0], item[1])
        dst_rel = src_rel
        
        # 确保目标文件存在
        if not path.exists(path.dirname(dst)):
            os.makedirs(path.dirname(dst))
        
        print(f'    正在压缩第 {index+1} 个视频（共 {len(视频列表)} 个）：')
        print(f'        原视频路径 {path.join("主库", src_rel)}')
        print(f'        原始大小   {文件大小(src)}')

        原视频信息 = 取得视频信息(src)
        if not 原视频信息:
            print(f'        原文件路径格式损坏，跳过：{src}')
            continue
        
        视频时长 = float(原视频信息['duration'])
        视频编码 = 原视频信息['codec_name']
        视频比特率 = int(原视频信息['bit_rate']) / 1024 / 1024
        视频宽度 = int(原视频信息['width'])
        视频高度 = int(原视频信息['height'])
        视频帧率 = 原视频信息['r_frame_rate']
        if 'tags' in 原视频信息:
            if 'rotate' in 原视频信息['tags']:
                if 原视频信息['tags']['rotate'] in ['90', '-90']:
                    视频宽度, 视频高度 = 视频高度, 视频宽度
        
        print(f'        视频时长   {"%0.1f" % (视频时长 / 60)}min')
        print(f'        视频编码   {视频编码}')
        print(f'        视频比特率 {"%0.2f" % 视频比特率}Mbps')
        print(f'        视频分辨率 {视频宽度}x{视频高度}')
        print(f'        视频帧率   {视频帧率}')
        
        if 视频宽度 > 视频高度:
            新分辨率 = '-2:480'
        else:
            新分辨率 = '480:-2'
        print(f'        新分辨率   {新分辨率}')
        
        命令 = f'ffmpeg -hide_banner -y -i "{src}" -vf "scale={新分辨率}" -crf 23 "{dst}"'
        process = subprocess.Popen(shlex.split(命令), 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.STDOUT)
        for line in TextIOWrapper(process.stdout, encoding='utf-8', newline='\r'):
            if line.startswith('frame='):
                print(f"\r{line}", end='')
        print('')
        
        新视频信息 = 取得视频信息(dst)
        新视频比特率 = int(新视频信息['bit_rate']) / 1024 / 1024
        
        print(f'        新视频路径 {path.join("随库", dst_rel)}')
        print(f'        新比特率   {"%0.2f" % 新视频比特率}Mbps')
        print(f'        压缩后大小 {文件大小(dst)}')
        压缩比例 = path.getsize(dst) / path.getsize(src) * 100
        print(f'        比原来减小 {"%0.2f" % (100 - 压缩比例)}%\n')
        
        # 既然这个视频压缩完了，就把它记录下来，下次就不用检查这个视频了
        with open(path.join(随库位置, 完好视频记录文件), 'a', encoding='utf-8') as f:
            f.write(f'{dst_rel}\n')
            

    print('视频压缩任务执行完毕\n')

def 适当大小(size):
    # 将一个字节大小转成合适的单位显示
    进位 = 0
    while size > 1 and 进位 <= 4:
        if size / 1024 < 1:
            break
        size = size / 1024
        进位 += 1
    进位单位 = {0:'Bytes', 1:'KB', 2:'MB', 3:'GB', 4:'TB', 5:'EB'}
    return (f'{"%0.2f" % size}{进位单位[进位]}')

def 文件大小(文件路径):
    if not path.exists(文件路径):
        return False
    return 适当大小(path.getsize(文件路径))



if __name__ == '__main__': 
    main()
