#!/usr/bin/env python3
"""
部署脚本
用于快速部署和配置Telegram机器人
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def check_python_version():
    """检查Python版本"""
    if sys.version_info < (3, 8):
        print("❌ 需要Python 3.8或更高版本")
        sys.exit(1)
    print(f"✅ Python版本: {sys.version}")


def install_dependencies():
    """安装依赖"""
    print("📦 正在安装依赖...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      check=True, capture_output=True, text=True)
        print("✅ 依赖安装完成")
    except subprocess.CalledProcessError as e:
        print(f"❌ 依赖安装失败: {e}")
        sys.exit(1)


def setup_environment():
    """设置环境配置"""
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if not env_file.exists() and env_example.exists():
        print("📝 创建环境配置文件...")
        shutil.copy(env_example, env_file)
        print("✅ 已创建 .env 文件，请编辑其中的配置")
        return False
    elif env_file.exists():
        print("✅ 环境配置文件已存在")
        return True
    else:
        print("❌ 找不到环境配置模板文件")
        return False


def setup_directories():
    """创建必要的目录"""
    directories = ["logs"]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ 创建目录: {directory}")


def validate_config():
    """验证配置"""
    print("🔍 验证配置...")
    
    # 检查环境变量
    from dotenv import load_dotenv
    load_dotenv()
    
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        print("❌ 未设置BOT_TOKEN环境变量")
        return False
    
    admin_ids = os.getenv('ADMIN_IDS')
    if not admin_ids:
        print("⚠️  未设置ADMIN_IDS，所有用户都将被视为管理员")
    
    print("✅ 配置验证通过")
    return True


def run_tests():
    """运行测试"""
    print("🧪 运行测试...")
    try:
        result = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ 所有测试通过")
            return True
        else:
            print("⚠️  部分测试失败，但可以继续部署")
            print(result.stdout)
            return True
    except FileNotFoundError:
        print("⚠️  pytest未安装，跳过测试")
        return True
    except Exception as e:
        print(f"⚠️  测试运行失败: {e}")
        return True


def create_systemd_service():
    """创建systemd服务文件（Linux）"""
    if os.name != 'posix':
        return
    
    service_content = f"""[Unit]
Description=Telegram Channel Message Bot
After=network.target

[Service]
Type=simple
User={os.getenv('USER', 'telegram-bot')}
WorkingDirectory={os.getcwd()}
ExecStart={sys.executable} main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    service_file = Path("telegram-bot.service")
    with open(service_file, 'w') as f:
        f.write(service_content)
    
    print(f"✅ 创建systemd服务文件: {service_file}")
    print("   要安装服务，请运行:")
    print(f"   sudo cp {service_file} /etc/systemd/system/")
    print("   sudo systemctl daemon-reload")
    print("   sudo systemctl enable telegram-bot")
    print("   sudo systemctl start telegram-bot")


def main():
    """主部署函数"""
    print("🚀 开始部署Telegram频道消息处理机器人")
    print("=" * 50)
    
    # 检查Python版本
    check_python_version()
    
    # 安装依赖
    install_dependencies()
    
    # 设置环境
    env_configured = setup_environment()
    
    # 创建目录
    setup_directories()
    
    # 如果环境文件是新创建的，提示用户配置
    if not env_configured:
        print("\n⚠️  请先配置 .env 文件中的以下参数:")
        print("   - BOT_TOKEN: 你的Telegram机器人Token")
        print("   - ADMIN_IDS: 管理员用户ID（逗号分隔）")
        print("\n配置完成后，请重新运行此脚本或直接启动机器人")
        return
    
    # 验证配置
    if not validate_config():
        print("❌ 配置验证失败，请检查配置文件")
        return
    
    # 运行测试
    run_tests()
    
    # 创建服务文件
    create_systemd_service()
    
    print("\n" + "=" * 50)
    print("🎉 部署完成！")
    print("\n📋 下一步操作:")
    print("1. 确保已配置 channels.txt 文件（添加要监听的频道）")
    print("2. 运行机器人: python main.py")
    print("3. 在Telegram中向机器人发送 /help 查看管理命令")
    print("\n📚 更多信息请查看 README.md")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ 部署被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 部署失败: {e}")
        sys.exit(1)
