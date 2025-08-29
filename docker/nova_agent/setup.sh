#!/bin/bash
set -e  # 任何命令失败时立即退出

# build package
module=nova
project_name=nova_agent

# 1. 使用 Nuitka 编译模块
cd ../.. && python -m nuitka --module ${module} --include-package=${module} --output-dir=docker/${project_name}/build

# 2. 复制必要文件到构建目录
cp pyproject.toml docker/${project_name}/build
cp config.yaml docker/${project_name}/build

# 3. 进入构建目录并打包
cd docker/${project_name}/build
rm -f ${module}.so && mv *.so ${module}.so
tar -czvf server.tar.gz config.yaml *.so ../gunicorn_deploy
rm -rf config.yaml *.build *.pyi ${module}.so
# tar -xzvf server.tar.gz
