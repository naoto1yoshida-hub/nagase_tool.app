"""DBステータス確認ユーティリティ"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.config import Config
from modules.database import get_connection, get_drawing_count

report_path = os.path.join(Config.APP_DIR, 'migration_report.txt')

with open(report_path, 'w', encoding='utf-8') as f:
    with get_connection() as conn:
        count = get_drawing_count()
        f.write(f"登録図面数: {count}\n\n")

        cursor = conn.execute("SELECT drawing_path, page_number FROM drawings LIMIT 10")
        rows = cursor.fetchall()
        f.write("サンプルパス:\n")
        for row in rows:
            f.write(f"  {row['drawing_path']} (p.{row['page_number']})\n")

print(f"レポート出力: {report_path}")
