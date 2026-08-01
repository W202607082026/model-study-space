[app]
version = 0.0.1
title = WordTrainer
package.name = wordtrainer
package.domain = org.voice.english
source.dir = .
source.include_exts = py,json
source.include_files = junior.json,senior.json,cet4.json,cet6.json,kaoyan.json,toefl.json,sat.json

requirements = python3,kivy,aiohttp

android.permissions = INTERNET,ACCESS_NETWORK_STATE
android.api = 33
android.ndk = 25b

debug = False
orientation = portrait