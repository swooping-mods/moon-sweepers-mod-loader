"""Charcoal integrated panes adapted from the user's default UI references."""
COLORS = {'background': '#1b1b1b', 'surface': '#1e1e1e', 'control': '#252525', 'hover': '#303030',
          'selected': '#353535', 'line': '#333333', 'text': '#ececec', 'muted': '#a6a6a6',
          'checked': '#2b3530', 'checked_hover': '#344139', 'checked_selected': '#39483f', 'checked_accent': '#a8c4ae',
          'focus': '#b4b4b4', 'warning': '#dfba7c', 'danger': '#ee8f89'}
STYLE = '''
QWidget { background: #1b1b1b; color: #ececec; font-family: "Noto Sans", "Segoe UI", sans-serif; font-size: 13px; }
QMainWindow, QFrame#workspace { background: #1e1e1e; }
QLabel { background: transparent; }
QLabel#title { font-size: 20px; font-weight: 600; }
QLabel#muted, QLabel#path, QLabel#launchStatusText { color: #a6a6a6; }
QLabel#section { font-size: 15px; font-weight: 600; }
QLabel#message { color: #a6a6a6; padding: 8px 16px; border-top: 1px solid #333333; }
QLabel#message[severity="warning"], QLabel[severity="warning"] { color: #dfba7c; }
QLabel#message[severity="error"], QLabel#launchStatusText[severity="error"], QLabel[severity="error"] { color: #ee8f89; }
QFrame#launchStatus { border-top: 1px solid #333333; }
QFrame#header, QFrame#toolbar { border-bottom: 1px solid #333333; }
QFrame#details { border-left: 1px solid #333333; background: #1e1e1e; }
QFrame#footer { border-top: 1px solid #333333; }
QPushButton, QComboBox, QLineEdit { background: #252525; border: 1px solid #3b3b3b; border-radius: 3px; padding: 7px 10px; min-height: 18px; }
QPushButton:hover, QComboBox:hover { background: #303030; }
QPushButton:focus, QComboBox:focus, QLineEdit:focus, QListWidget:focus { border: 1px solid #b4b4b4; }
QPushButton:checked { background: #393939; border-color: #777777; }
QPushButton:disabled { color: #777777; background: #222222; }
QPushButton#launch { background: #ececec; color: #202020; font-size: 15px; font-weight: 600; padding: 13px 22px; }
QPushButton#launch:hover { background: #ffffff; }
QPushButton#launch:disabled { background: #393939; color: #929292; }
QListWidget { background: #1e1e1e; border: none; outline: none; }
QListWidget::item { padding: 0px; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #252525; selection-background-color: #393939; }
QToolTip { background: #303030; color: #ececec; border: 1px solid #555555; padding: 5px; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 0; }
QScrollBar::handle { background: #454545; border: 2px solid #1e1e1e; border-radius: 3px; min-height: 24px; min-width: 24px; }
QScrollBar:hover::handle, QScrollBar:focus::handle { background: #737373; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
QTextEdit, QPlainTextEdit { background: #1e1e1e; border: 1px solid #333333; }
'''
