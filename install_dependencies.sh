#!/bin/bash
### Crawler original code: https://github.com/tongyuantongyu/WebNovelCrawler
### Fork updated with the script to install dependencies https://github.com/Bunkai9448/WebNovelCrawler
### Dependencies Installer code by Bunkai

echo "Installing webCrawler dependencies:"
sudo apt-get update
### python > 3.7; prueba bajo Python 3.8.10

### https://github.com/aerkalov/ebooklib
sudo apt-get install python3-ebooklib
### https://pypi.org/project/aiohttp 
sudo apt-get install python3-aiohttp
### https://pypi.org/project/Janome
sudo apt-get install python3-pip
### https://pypi.org/project/pykakasi/ 
pip install Janome --break-system-packages
pip install pykakasi --break-system-packages

echo "Dependencies Installed"
