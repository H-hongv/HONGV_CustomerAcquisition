"""外贸 AI SDR 多 Agent 获客系统桌面入口。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="外贸 AI SDR 多 Agent 获客系统")
    parser.add_argument('--ui', default='flet', choices=['flet', 'pyqt5'],
                        help='UI 类型（flet=现代界面，pyqt5=传统界面）')
    parser.add_argument('--web', action='store_true', help='用浏览器打开 Flet Web 界面')
    args = parser.parse_args()

    # Startup config validation
    try:
        from config_validator import validate_config, print_startup_banner
        warnings = validate_config()
        if warnings:
            print_startup_banner(warnings)
    except Exception:
        pass

    if args.ui == 'pyqt5':
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtGui import QFont
        from gui.main_window import MainWindow
        app = QApplication(sys.argv)
        app.setFont(QFont('Microsoft YaHei', 9))
        app.setStyle('Fusion')
        window = MainWindow()
        window.show()
        sys.exit(app.exec_())
    else:
        import flet as ft
        from gui.flet_app import main as flet_main
        if args.web:
            ft.app(flet_main, view=ft.AppView.WEB_BROWSER)
        else:
            ft.app(flet_main)


if __name__ == '__main__':
    main()
