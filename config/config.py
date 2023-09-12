# -*- coding: UTF-8 -*-
from pathlib import Path

import yaml

# 存储和检索与特定聊天相关联的数据
chat_data = {}

DOWNLOADS_PATH = Path('data/downloads')
OUTPUT_PATH = Path('data/output')

directories = [DOWNLOADS_PATH, OUTPUT_PATH]
for directory in directories:
    directory.mkdir(parents=True, exist_ok=True)


class YAMLHandler:
    def __init__(self, file_path):
        self.file_path = file_path
    
    def read(self):
        with open(self.file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def write(self, modified_config):
        with open(self.file_path, 'w', encoding='utf-8') as f:
            yaml.dump(modified_config, f, allow_unicode=True)


config_handler = YAMLHandler('config.yaml')
config = config_handler.read()

# user
admin = config['user']['admin']
bot_token = config['user']['bot_token']
api_id = config['user']['api_id']
api_hash = config['user']['api_hash']
# proxy
scheme = config['proxy']['scheme']
hostname = config['proxy']['hostname']
port = config['proxy']['port']
proxy = f'{scheme}://{hostname}:{str(port)}' if all([scheme, hostname, port]) else None
