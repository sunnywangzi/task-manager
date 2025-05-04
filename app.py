#!/usr/bin/env python3
from flask import Flask, render_template, request, jsonify, redirect, url_for
import subprocess
import os
import json
from datetime import datetime, timedelta

app = Flask(__name__)

# 配置文件路径
DB_FILE = os.path.join(os.path.dirname(__file__), 'task_db.json')
HISTORY_FILE = os.path.join(os.path.dirname(__file__), 'task_history.json')

def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, 'r') as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return {}
    with open(HISTORY_FILE, 'r') as f:
        return json.load(f)

def save_history(data):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def record_task_run(task_name, success=True):
    history = load_history()
    if task_name not in history:
        history[task_name] = []
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    history[task_name].append({
        'time': timestamp,
        'status': 'success' if success else 'failed'
    })
    
    # 只保留最近30次记录
    history[task_name] = history[task_name][-30:]
    save_history(history)

def get_cron_jobs():
    try:
        output = subprocess.check_output(['crontab', '-l'], stderr=subprocess.PIPE).decode()
        return output.splitlines()
    except subprocess.CalledProcessError:
        return []

def add_cron_job(schedule, command):
    current_cron = get_cron_jobs()
    new_job = f"{schedule} {command}"
    
    # 检查是否已存在相同命令的任务
    for job in current_cron:
        if job.strip().endswith(command.strip()):
            return False
    
    # 添加新任务
    current_cron.append(new_job)
    cron_content = '\n'.join(current_cron) + '\n'
    
    # 写入crontab
    process = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE)
    process.communicate(input=cron_content.encode())
    return True

def remove_cron_job(command):
    current_cron = get_cron_jobs()
    new_cron = [job for job in current_cron if not job.strip().endswith(command.strip())]
    
    if len(new_cron) == len(current_cron):
        return False
    
    # 写入crontab
    cron_content = '\n'.join(new_cron) + '\n'
    process = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE)
    process.communicate(input=cron_content.encode())
    return True

@app.route('/')
def index():
    tasks = load_db()
    history = load_history()
    cron_jobs = get_cron_jobs()
    
    # 检查每个任务今天是否运行过
    today = datetime.now().strftime('%Y-%m-%d')
    for task_name in tasks:
        tasks[task_name]['ran_today'] = False
        tasks[task_name]['last_run'] = None
        
        if task_name in history and history[task_name]:
            last_run = history[task_name][-1]['time']
            tasks[task_name]['last_run'] = last_run
            if last_run.startswith(today):
                tasks[task_name]['ran_today'] = True
    
    return render_template('index.html', tasks=tasks, cron_jobs=cron_jobs)

@app.route('/task/add', methods=['GET', 'POST'])
def add_task():
    if request.method == 'POST':
        tasks = load_db()
        task_name = request.form['name']
        
        tasks[task_name] = {
            'name': task_name,
            'schedule': request.form['schedule'],
            'command': request.form['command'],
            'description': request.form['description'],
            'log_file': request.form['log_file']
        }
        
        # 添加到crontab
        add_cron_job(request.form['schedule'], request.form['command'])
        
        save_db(tasks)
        return redirect(url_for('index'))
    
    return render_template('edit_task.html', task=None)

@app.route('/task/edit/<task_name>', methods=['GET', 'POST'])
def edit_task(task_name):
    tasks = load_db()
    if task_name not in tasks:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # 先移除旧cron任务
        old_command = tasks[task_name]['command']
        remove_cron_job(old_command)
        
        # 更新任务信息
        tasks[task_name] = {
            'name': task_name,
            'schedule': request.form['schedule'],
            'command': request.form['command'],
            'description': request.form['description'],
            'log_file': request.form['log_file']
        }
        
        # 添加新cron任务
        add_cron_job(request.form['schedule'], request.form['command'])
        
        save_db(tasks)
        return redirect(url_for('index'))
    
    return render_template('edit_task.html', task=tasks[task_name])

@app.route('/task/delete/<task_name>')
def delete_task(task_name):
    tasks = load_db()
    if task_name in tasks:
        # 从crontab中移除
        remove_cron_job(tasks[task_name]['command'])
        
        del tasks[task_name]
        save_db(tasks)
    
    return redirect(url_for('index'))

@app.route('/task/run/<task_name>')
def run_task(task_name):
    tasks = load_db()
    if task_name not in tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    command = tasks[task_name]['command']
    try:
        result = subprocess.run(
            command.split(), 
            capture_output=True, 
            text=True,
            timeout=300
        )
        
        # 记录执行历史
        record_task_run(task_name, result.returncode == 0)
        
        return jsonify({
            'success': True,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr
        })
    except Exception as e:
        record_task_run(task_name, False)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/task/log/<task_name>')
def get_task_log(task_name):
    tasks = load_db()
    if task_name not in tasks or not tasks[task_name].get('log_file'):
        return jsonify({'error': 'Log file not configured'}), 404
    
    log_file = tasks[task_name]['log_file']
    if not os.path.exists(log_file):
        return jsonify({'error': 'Log file not found'}), 404
    
    try:
        with open(log_file, 'r') as f:
            content = f.read()
        return jsonify({'log': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/task/history/<task_name>')
def get_task_history(task_name):
    history = load_history()
    if task_name not in history:
        return jsonify({'history': []})
    
    return jsonify({'history': history[task_name]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)