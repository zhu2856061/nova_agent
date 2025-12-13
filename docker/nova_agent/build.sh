#!/bin/bash
set -e  # 任何命令失败时立即退出

# build package
module=nova
project_name=nova_agent
API_URL=http://localhost:2022

# 0. 构建 chat-ui 的项目
OLD_PWD=$(pwd)
[ -d "build" ] || mkdir build
cd ../../chat-ui && [ -d "dist" ] || mkdir dist && API_URL=${API_URL} reflex export --env prod --zip --zip-dest-dir ./dist && cd ${OLD_PWD} && mv ../../chat-ui/dist/* ./build/

# 1. 使用 Nuitka 编译模块
cd ../.. && python -m nuitka --module ${module} --include-package=${module} --output-dir=docker/${project_name}/build

# 2. 复制必要文件到构建目录
cp pyproject.toml docker/${project_name}/build
cp config.yaml docker/${project_name}/build
cp -r prompts docker/${project_name}/build
cp .env docker/${project_name}/build

# 3. 进入构建目录并打包
cd docker/${project_name}/build
rm -f ${module}.so && mv *.so ${module}.so
tar -czvf server.tar.gz config.yaml *.so
rm -rf config.yaml *.build *.pyi ${module}.so
# tar -xzvf server.tar.gz
