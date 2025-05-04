#!/bin/bash

# 获取当前时间
current_time=$(date +"%Y-%m-%d_%H-%M-%S")

# 任务名称
task_name=$1

# 日志目录
log_dir="./logs/$task_name"
mkdir -p $log_dir

# 日志文件路径
log_file="$log_dir/$current_time.log"

# 任务命令
task_command=$2

# 执行任务并将输出重定向到日志文件
$task_command >> $log_file 2>&1
