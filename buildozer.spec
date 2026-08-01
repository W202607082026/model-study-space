[app]
title = 单词听力训练器
package.name = wordtrainer
package.domain = org.voice.english
source.dir = .
source.include_exts = py,json
source.include_files = 初中_合并.json,高中_合并.json,四级_合并.json,六级_合并.json,考研_合并.json,托福_合并.json,SAT_合并.json

requirements = python3,kivy,edge-tts,aiohttp
android.permissions = INTERNET,ACCESS_NETWORK_STATE
android.api = 33
android.ndk = 25b
android.sdk = 24

pypi_index = https://pypi.tuna.tsinghua.edu.cn/simple
debug = False
orientation = portrait