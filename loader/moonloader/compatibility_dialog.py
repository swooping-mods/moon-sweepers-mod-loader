"""Compact preflight assessment; closing it never admits an unsupported mod."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QTreeWidget, QTreeWidgetItem, QHeaderView, QPlainTextEdit)
from . import compatibility


class CompatibilityDialog(QDialog):
    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Check mods for this game build')
        self.setMinimumWidth(480)
        self.resize(720, 390)
        self.rows = compatibility.compact(result)
        self.excluded_ids = ()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        game = result.get('game', {})
        title = QLabel('Moon Sweepers ' + game['version'] if game.get('version') else 'Unrecognized game build')
        title.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(title)
        blocked = sum(row['status'] == 'Blocked' for row in self.rows)
        unknown = len(self.rows) - blocked
        text = f'{blocked} blocked · {unknown} unverified · {len(result.get("selected", []))} selected'
        if not self.rows:
            text = compatibility.message(result)
        self.summary = QLabel(text)
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.table = QTreeWidget()
        self.table.setHeaderLabels(['Mod', 'Status', 'Reason'])
        self.table.setRootIsDecorated(False)
        self.table.setUniformRowHeights(True)
        self.table.setColumnWidth(0, 200)
        self.table.setColumnWidth(1, 90)
        self.table.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for row in self.rows:
            name = row['name'] + (' ' + row['version'] if row['version'] else '')
            item = QTreeWidgetItem([name, row['status'], row['reason']])
            for column, value in enumerate((name, row['status'], row['reason'])):
                item.setToolTip(column, value)
            self.table.addTopLevelItem(item)
        self.table.setVisible(bool(self.rows))
        layout.addWidget(self.table)
        note = QLabel('These mods will not be started. Unverified means compatibility is unknown, not proven broken.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.details = QPlainTextEdit(compatibility.describe(result))
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(180)
        self.details.hide()
        layout.addWidget(self.details)
        buttons = QHBoxLayout()
        self.details_button = QPushButton('Details')
        self.details_button.setCheckable(True)
        self.details_button.toggled.connect(self.details.setVisible)
        buttons.addWidget(self.details_button)
        buttons.addStretch()
        self.deselect_button = QPushButton('Deselect affected mods')
        self.deselect_button.setEnabled(bool(self.rows))
        self.deselect_button.clicked.connect(self.deselect)
        buttons.addWidget(self.deselect_button)
        self.close_button = QPushButton('Return to mods')
        self.close_button.clicked.connect(self.reject)
        self.close_button.setDefault(True)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

    def deselect(self):
        self.excluded_ids = tuple(row['id'] for row in self.rows)
        self.accept()
