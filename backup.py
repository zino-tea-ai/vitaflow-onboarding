"""
本地备份脚本
将项目文件复制到 C:\Users\WIN\Desktop\Cursor_Backups\ 目录
"""

import os
import shutil
from datetime import datetime

# 配置
SOURCE_DIR = r"C:\Users\WIN\Desktop\Cursor Project"
BACKUP_ROOT = r"C:\Users\WIN\Desktop\Cursor_Backups"

# 排除的文件夹和文件
EXCLUDE_DIRS = {
    '.git',
    'node_modules',
    '__pycache__',
    '.venv',
    'venv',
    '.pytest_cache',
    '.mypy_cache',
}

EXCLUDE_FILES = {
    '.DS_Store',
    'Thumbs.db',
    '*.pyc',
}


def should_exclude(name, is_dir=False):
    """检查是否应该排除该文件/文件夹"""
    if is_dir:
        return name in EXCLUDE_DIRS
    return name in EXCLUDE_FILES or name.endswith('.pyc')


def backup_project():
    """执行备份"""
    # 创建备份根目录
    if not os.path.exists(BACKUP_ROOT):
        os.makedirs(BACKUP_ROOT)
        print(f"✅ 创建备份目录: {BACKUP_ROOT}")

    # 生成时间戳文件夹名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(BACKUP_ROOT, f"Cursor_Project_{timestamp}")

    # 复制文件
    def copy_tree(src, dst):
        """递归复制目录树，排除指定文件夹"""
        if not os.path.exists(dst):
            os.makedirs(dst)
        
        for item in os.listdir(src):
            src_path = os.path.join(src, item)
            dst_path = os.path.join(dst, item)
            
            if os.path.isdir(src_path):
                if not should_exclude(item, is_dir=True):
                    copy_tree(src_path, dst_path)
            else:
                if not should_exclude(item):
                    shutil.copy2(src_path, dst_path)

    try:
        print(f"📦 开始备份...")
        print(f"   源目录: {SOURCE_DIR}")
        print(f"   目标目录: {backup_dir}")
        
        copy_tree(SOURCE_DIR, backup_dir)
        
        # 计算备份大小
        total_size = 0
        file_count = 0
        for root, dirs, files in os.walk(backup_dir):
            for f in files:
                total_size += os.path.getsize(os.path.join(root, f))
                file_count += 1
        
        size_mb = total_size / (1024 * 1024)
        
        print(f"\n✅ 备份完成!")
        print(f"   文件数量: {file_count}")
        print(f"   备份大小: {size_mb:.2f} MB")
        print(f"   保存位置: {backup_dir}")
        
    except Exception as e:
        print(f"❌ 备份失败: {e}")
        return False
    
    return True


def cleanup_old_backups(keep_count=5):
    """清理旧备份，只保留最近的 N 个"""
    if not os.path.exists(BACKUP_ROOT):
        return
    
    backups = []
    for name in os.listdir(BACKUP_ROOT):
        path = os.path.join(BACKUP_ROOT, name)
        if os.path.isdir(path) and name.startswith("Cursor_Project_"):
            backups.append((name, path))
    
    # 按名称排序（时间戳格式，越新越大）
    backups.sort(reverse=True)
    
    # 删除旧备份
    for name, path in backups[keep_count:]:
        try:
            shutil.rmtree(path)
            print(f"🗑️  删除旧备份: {name}")
        except Exception as e:
            print(f"⚠️  无法删除 {name}: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("🔒 Cursor Project 本地备份工具")
    print("=" * 50)
    print()
    
    backup_project()
    
    print()
    print("-" * 50)
    cleanup_old_backups(keep_count=5)
    print()
    print("💡 提示: 保留最近 5 个备份，旧备份已自动清理")
