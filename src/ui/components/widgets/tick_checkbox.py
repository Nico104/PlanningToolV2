from PySide6.QtWidgets import QCheckBox

class TickCheckBox(QCheckBox):
    def __init__(self, label=None, parent=None):
        super().__init__(label or "", parent)
        check_icon_path = "src/ui/assets/icons/check-marksvg.svg"
        self.setStyleSheet(f'''
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid #bbb;
                border-radius: 4px;
                background: transparent;
            }}
            QCheckBox::indicator:unchecked {{
                image: none;
            }}
            QCheckBox::indicator:checked {{
                image: url('{check_icon_path}');
            }}
        ''')
