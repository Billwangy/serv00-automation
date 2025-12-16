import os
import paramiko
import requests
import json
from datetime import datetime, timezone, timedelta
import socket

def ssh_multiple_connections(hosts_info, command):
    users = []
    hostnames = []
    for host_info in hosts_info:
        # 提取参数并做非空校验
        hostname = host_info.get('hostname', '')
        username = host_info.get('username', '')
        password = host_info.get('password', '')
        if not all([hostname, username, password]):
            print(f"跳过无效配置：缺少hostname/username/password")
            continue
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            # 添加10秒连接超时
            ssh.connect(
                hostname=hostname,
                port=22,
                username=username,
                password=password,
                timeout=10
            )
            stdin, stdout, stderr = ssh.exec_command(command)
            user = stdout.read().decode().strip() or "未知用户"
            users.append(user)
            hostnames.append(hostname)
            print(f"成功连接{hostname}，返回用户：{user}")
        except paramiko.AuthenticationException:
            print(f"{username}连接{hostname}失败：认证错误")
        except socket.timeout:
            print(f"{username}连接{hostname}失败：超时")
        except paramiko.SSHException as e:
            print(f"{username}连接{hostname}失败：SSH协议错误 - {e}")
        except Exception as e:
            print(f"{username}连接{hostname}失败：未知错误 - {e}")
        finally:
            ssh.close()
    return users, hostnames

# 加载并校验SSH配置
ssh_info_str = os.getenv('SSH_INFO', '[]')
try:
    hosts_info = json.loads(ssh_info_str)
    if not isinstance(hosts_info, list):
        raise ValueError("SSH_INFO必须是JSON数组")
except (json.JSONDecodeError, ValueError) as e:
    print(f"SSH_INFO解析失败：{e}")
    hosts_info = []

# 执行SSH命令
command = 'whoami'
user_list, hostname_list = ssh_multiple_connections(hosts_info, command)
user_num = len(user_list)

# 构建通知内容
content = "SSH服务器登录信息：\n"
for user, hostname in zip(user_list, hostname_list):
    content += f"用户名：{user}，服务器：{hostname}\n"
beijing_timezone = timezone(timedelta(hours=8))
time = datetime.now(beijing_timezone).strftime('%Y-%m-%d %H:%M:%S')

# 获取TG菜单（带异常处理和格式校验）
menu = []
try:
    menu_res = requests.get('https://api.zzzwb.com/v1?get=tg', timeout=5)
    menu = menu_res.json() if menu_res.status_code == 200 else []
    if not isinstance(menu, list):
        menu = []
except Exception as e:
    print(f"获取TG菜单失败：{e}")

# 获取登录IP（带异常处理）
loginip = "未知IP"
try:
    loginip_res = requests.get('https://api.ipify.org?format=json', timeout=5)
    loginip = loginip_res.json().get('ip', '未知IP')
except Exception as e:
    print(f"获取IP失败：{e}")

content += f"本次登录用户共： {user_num} 个\n登录时间：{time}\n登录IP：{loginip}"

# 推送配置
push = os.getenv('PUSH', '').lower()
mail_receiver = os.getenv('MAIL', '775836803@qq.com')  # 设置默认邮箱
tg_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')

def mail_push(url):
    if not mail_receiver:
        print("邮件推送失败：未配置接收邮箱")
        return
    data = {"body": content, "email": mail_receiver}
    try:
        response = requests.post(url, json=data, timeout=10)
        response_data = response.json()
        if response_data.get('code') == 200:
            print("邮件推送成功")
        else:
            print(f"邮件推送失败，错误码：{response_data.get('code', '未知')}")
    except requests.exceptions.RequestException as e:
        print(f"邮件接口调用失败：{e}")
    except json.JSONDecodeError:
        print("邮件服务器返回非JSON数据")

def telegram_push(message):
    if not all([tg_bot_token, tg_chat_id]):
        print("Telegram推送失败：缺少TOKEN或CHAT_ID")
        return
    url = f"https://api.telegram.org/bot{tg_bot_token}/sendMessage"
    payload = {
        'chat_id': tg_chat_id,
        'text': message,
        'parse_mode': 'HTML',
        'reply_markup': json.dumps({
            "inline_keyboard": menu,
            "one_time_keyboard": True
        })
    }
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            print("Telegram推送成功")
        else:
            print(f"Telegram推送失败：{response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Telegram接口调用失败：{e}")

# 执行推送
if push == "mail":
    mail_push('https://zzzwb.pp.ua/test')
elif push == "telegram":
    telegram_push(content)
else:
    print(f"推送失败：PUSH参数错误（当前值：{push}），仅支持mail/telegram")

