#!/usr/bin/env python3
from flask import Flask, render_template, request, jsonify, redirect, url_for
import subprocess
import os
import json
import platform
from datetime import datetime, timedelta
import sqlite3  # 改用SQLite数据库更可靠

app = Flask(__name__)

# 配置文件路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'tasks.db')

def get_log_file_path(task_name):
    # 创建日志目录
    log_dir = os.path.join(BASE_DIR, 'logs', task_name)
    os.makedirs(log_dir, exist_ok=True)
    
    # 按日期命名的日志文件
    date_str = datetime.now().strftime('%Y-%m-%d')
    log_file = os.path.join(log_dir, f"{date_str}.log")
    
    # 如果文件不存在则创建
    if not os.path.exists(log_file):
        open(log_file, 'w').close()
    
    return log_file

# 初始化数据库
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 创建任务表
    c.execute('''CREATE TABLE IF NOT EXISTS tasks
                 (name TEXT PRIMARY KEY,
                  schedule TEXT,
                  command TEXT,
                  description TEXT,
                  log_file TEXT,
                  working_dir TEXT,
                  platform TEXT)''')
    
    # 创建历史记录表
    c.execute('''CREATE TABLE IF NOT EXISTS task_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_name TEXT,
                  run_time TEXT,
                  status TEXT,
                  output TEXT)''')
    
    conn.commit()
    conn.close()

# 数据库操作函数
def get_tasks():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM tasks")
    tasks = {row[0]: dict(zip(['name', 'schedule', 'command', 'description', 'log_file', 'platform'], row)) 
              for row in c.fetchall()}
    conn.close()
    return tasks

def save_task(task):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''REPLACE INTO tasks VALUES (?,?,?,?,?,?,?)''',
              (task['name'], task['schedule'], task['command'], 
               task['description'], task.get('log_file', ''),
               task.get('working_dir', ''), platform.system()))
    conn.commit()
    conn.close()
    update_system_scheduler(task)

def delete_task(task_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 先从系统计划中移除
    task = get_task(task_name)
    if task:
        remove_from_scheduler(task)
    
    c.execute("DELETE FROM tasks WHERE name=?", (task_name,))
    conn.commit()
    conn.close()

def get_task(task_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM tasks WHERE name=?", (task_name,))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(zip(['name', 'schedule', 'command', 'description', 'log_file', 'platform'], row))
    return None

def record_task_run(task_name, success=True, output=""):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''INSERT INTO task_history (task_name, run_time, status, output)
                 VALUES (?,?,?,?)''',
              (task_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
               'success' if success else 'failed', output))
    conn.commit()
    conn.close()

def get_task_history(task_name, limit=10):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''SELECT run_time, status, output FROM task_history 
                 WHERE task_name=? ORDER BY run_time DESC LIMIT ?''',
              (task_name, limit))
    history = [{'time': row[0], 'status': row[1], 'output': row[2]} 
               for row in c.fetchall()]
    conn.close()
    return history

def get_tasks_ran_today():
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''SELECT DISTINCT task_name FROM task_history 
                 WHERE run_time LIKE ?''', (f"{today}%",))
    tasks = [row[0] for row in c.fetchall()]
    conn.close()
    return tasks

# 平台相关的任务调度功能
def update_system_scheduler(task):
    if platform.system() == 'Linux':
        update_cron_job(task)
    elif platform.system() == 'Windows':
        update_windows_task(task)

def remove_from_scheduler(task):
    if platform.system() == 'Linux':
        remove_cron_job(task)
    elif platform.system() == 'Windows':
        remove_windows_task(task)

def check_task_conflict(new_command):
    cron_jobs = get_cron_jobs()
    for job in cron_jobs:
        if new_command in job:
            return True
    return False

# Linux 专用函数
def update_cron_job(task):
    # 获取当前cron任务
    try:
        cron_output = subprocess.check_output(['crontab', '-l'], stderr=subprocess.PIPE).decode()
        cron_lines = cron_output.splitlines()
    except subprocess.CalledProcessError:
        cron_lines = []
    
    # 移除旧任务(如果有)
    task_comment = f"# TaskManager: {task['name']}"
    cron_lines = [line for line in cron_lines if not line.strip().startswith(task_comment)]
    
    # 添加新任务(带标签)
    cron_lines.append(f"# TaskManager: {task['name']} - {task['description']}")
    cron_lines.append(f"{task['schedule']} {task['command']}")
    
    # 写入crontab
    process = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE)
    process.communicate(input='\n'.join(cron_lines).encode())

def remove_cron_job(task):
    try:
        cron_output = subprocess.check_output(['crontab', '-l'], stderr=subprocess.PIPE).decode()
        cron_lines = cron_output.splitlines()
    except subprocess.CalledProcessError:
        return
    
    # 找到要删除的任务索引
    to_remove = []
    task_comment = f"# TaskManager: {task['name']}"
    for i, line in enumerate(cron_lines):
        if line.strip().startswith(task_comment):
            to_remove.extend([i, i+1])  # 删除注释行和命令行
            break
    
    # 创建新cron内容(排除要删除的行)
    new_cron = [line for i, line in enumerate(cron_lines) if i not in to_remove]
    
    # 写入crontab
    process = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE)
    process.communicate(input='\n'.join(new_cron).encode())

def get_cron_jobs():
    try:
        output = subprocess.check_output(['crontab', '-l'], stderr=subprocess.PIPE).decode()
        lines = output.splitlines()
        
        jobs = []
        current_comment = ""
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                if line.startswith("# TaskManager:"):
                    current_comment = line
                continue
            
            if current_comment:
                jobs.append(f"{current_comment}\n{line}")
                current_comment = ""
            else:
                jobs.append(line)
        
        return jobs
    except subprocess.CalledProcessError:
        return []

# Windows 专用函数
def update_windows_task(task):
    # 先删除同名任务(如果存在)
    remove_windows_task(task)
    
    # 创建新任务
    task_name = f"TaskManager_{task['name']}"
    command = f'python -c "import os; os.system(\'{task["command"]}\')"'
    
    # 使用schtasks命令创建计划任务
    try:
        subprocess.run([
            'schtasks', '/Create', '/TN', task_name,
            '/TR', command,
            '/SC', 'DAILY',
            '/ST', '00:00',
            '/F'
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to create Windows task: {e}")

def remove_windows_task(task):
    task_name = f"TaskManager_{task['name']}"
    try:
        subprocess.run(['schtasks', '/Delete', '/TN', task_name, '/F'], check=True)
    except subprocess.CalledProcessError:
        pass

# Web 路由
@app.route('/')
def index():
    tasks = get_tasks()
    tasks_ran_today = get_tasks_ran_today()
    
    # 为每个任务添加状态信息
    for name, task in tasks.items():
        task['ran_today'] = name in tasks_ran_today
        history = get_task_history(name, 1)
        task['last_run'] = history[0]['time'] if history else '从未运行'
    
    # 获取系统当前计划任务
    if platform.system() == 'Linux':
        try:
            cron_jobs = subprocess.check_output(['crontab', '-l']).decode().splitlines()
        except:
            cron_jobs = ["无法获取cron任务"]
    elif platform.system() == 'Windows':
        try:
            cron_jobs = subprocess.check_output(
                ['schtasks', '/Query', '/FO', 'LIST', '/V'],
                creationflags=subprocess.CREATE_NO_WINDOW).decode().splitlines()
        except:
            cron_jobs = ["无法获取计划任务"]
    else:
        cron_jobs = ["不支持的系统平台"]
    
    return render_template('index.html', 
                         tasks=tasks, 
                         cron_jobs=cron_jobs,
                         platform=platform.system())

@app.route('/task/add', methods=['GET', 'POST'])
def add_task():
    if request.method == 'POST':
        task = {
            'name': request.form['name'],
            'schedule': request.form['schedule'],
            'command': request.form['command'],
            'description': request.form['description'],
            'log_file': request.form['log_file']
        }
        save_task(task)
        return redirect(url_for('index'))
    
    return render_template('edit_task.html', task=None)

@app.route('/task/edit/<task_name>', methods=['GET', 'POST'])
def edit_task(task_name):
    task = get_task(task_name)
    if not task:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        updated_task = {
            'name': task_name,
            'schedule': request.form['schedule'],
            'command': request.form['command'],
            'description': request.form['description'],
            'log_file': request.form['log_file']
        }
        save_task(updated_task)
        return redirect(url_for('index'))
    
    return render_template('edit_task.html', task=task)

@app.route('/task/delete/<task_name>')
def delete_task(task_name):
    delete_task(task_name)
    return redirect(url_for('index'))

@app.route('/task/run/<task_name>')
def run_task(task_name):
    task = get_task(task_name)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    # 获取日志文件路径
    log_file = get_log_file_path(task_name)
    
    try:
        # 在指定工作目录运行命令
        working_dir = task.get('working_dir', BASE_DIR)
        os.makedirs(working_dir, exist_ok=True)
        
        if platform.system() == 'Windows':
            result = subprocess.run(
                task['command'],
                shell=True,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=300
            )
        else:
            result = subprocess.run(
                task['command'].split(),
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=300
            )
        
        # 记录日志
        with open(log_file, 'a') as f:
            f.write(f"=== 任务执行于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            f.write(f"命令: {task['command']}\n")
            f.write(f"返回码: {result.returncode}\n")
            f.write("\n标准输出:\n")
            f.write(result.stdout)
            f.write("\n错误输出:\n")
            f.write(result.stderr)
            f.write("\n\n")
        
        output = f"Return code: {result.returncode}\n\nStdout:\n{result.stdout}\n\nStderr:\n{result.stderr}"
        record_task_run(task_name, result.returncode == 0, output)
        
        return jsonify({
            'success': True,
            'returncode': result.returncode,
            'output': output,
            'log_file': log_file
        })
    except Exception as e:
        with open(log_file, 'a') as f:
            f.write(f"=== 任务执行失败于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            f.write(f"错误: {str(e)}\n\n")
        
        record_task_run(task_name, False, str(e))
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/task/log/<task_name>')
def get_task_log(task_name):
    task = get_task(task_name)
    if not task or not task.get('log_file'):
        return jsonify({'error': 'Log file not configured'}), 404
    
    log_file = task['log_file']
    if not os.path.exists(log_file):
        return jsonify({'error': 'Log file not found'}), 404
    
    try:
        with open(log_file, 'r') as f:
            content = f.read()
        return jsonify({'log': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/task/history/<task_name>')
def get_task_history_route(task_name):
    history = get_task_history(task_name, 10)
    return jsonify({'history': history})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)