"""Desktop-only Qt interface; all game starts require the Launch button action."""
import json
from pathlib import Path
import subprocess
import sys
from PySide6.QtCore import Qt, QSize, QRect, QThread, Signal, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QImageReader, QPainter, QPen, QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QLineEdit, QComboBox, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem, QAbstractItemView,
    QStyledItemDelegate, QStyle, QStyleOptionButton, QScrollArea, QFileDialog, QMessageBox, QDialog, QPlainTextEdit)
from . import discovery, launch, packages, steam_options, diagnostics, compatibility
from .catalog import CATEGORIES, description as catalog_description, matches
from .theme import STYLE, COLORS
from .storage import load, pending_launch, acknowledge_launch_closed, retain_private_uncertainty
from .launch_feedback import LaunchFeedback
from . import game_process


def frame(name, horizontal=False, margins=(16, 12, 16, 12)):
    widget = QFrame(); widget.setObjectName(name)
    layout = QHBoxLayout(widget) if horizontal else QVBoxLayout(widget)
    layout.setContentsMargins(*margins); layout.setSpacing(8)
    return widget, layout


def label(text, name=''):
    item = QLabel(text); item.setObjectName(name); return item


class Job(QThread):
    finished_value = Signal(object)
    failed = Signal(str)
    progress = Signal(str)
    def __init__(self, action, parent, staged=False):
        super().__init__(parent); self.action = action; self.staged = staged
    def run(self):
        try: self.finished_value.emit(self.action(self.progress.emit) if self.staged else self.action())
        except Exception as error:
            self.parent().diagnostics.exception('worker-error', error)
            self.failed.emit(str(error))


class ModList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self._wheel_remainder = 0
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event): self.window().dragEnterEvent(event)
    def dragMoveEvent(self, event): self.window().dragEnterEvent(event)
    def dropEvent(self, event): self.window().dropEvent(event)

    def wheelEvent(self, event):
        if self.viewMode() == QListWidget.ViewMode.IconMode and self.verticalScrollMode() == QAbstractItemView.ScrollMode.ScrollPerPixel:
            pixel = event.pixelDelta().y(); angle = event.angleDelta().y()
            if pixel:
                # Touchpads already supply a distance, including natural scrolling.
                self._wheel_remainder = 0; distance = pixel
            elif angle:
                # Travel two card rows per notch regardless of Qt's global line
                # setting. Retain fractional deltas from high-resolution wheels.
                if angle * self._wheel_remainder < 0: self._wheel_remainder = 0
                # A short window must not skip content between wheel notches.
                travel = min(self.gridSize().height() * 2, max(1, self.viewport().height()))
                self._wheel_remainder += angle * travel
                distance = (abs(self._wheel_remainder) // 120) * (1 if self._wheel_remainder >= 0 else -1)
                self._wheel_remainder -= distance * 120
            else:
                super().wheelEvent(event); return
            bar = self.verticalScrollBar(); previous = bar.value()
            bar.setValue(previous - distance)
            moved = bar.value() != previous
            event.setAccepted(moved or not distance)
            if distance and not moved: self._wheel_remainder = 0
            return
        super().wheelEvent(event)


class ModDelegate(QStyledItemDelegate):
    def __init__(self, window): super().__init__(window); self.window = window
    def sizeHint(self, option, index):
        return QSize(238, 192) if self.window.view == 'grid' else QSize(320, 94 if self.window.view == 'details' else 44)

    def checkbox(self, rect):
        return QRect(rect.right() - 34, rect.top() + 12, 22, 22) if self.window.view == 'grid' else QRect(rect.left() + 12, rect.center().y() - 11, 22, 22)

    def paint(self, painter, option, index):
        painter.save(); rect = option.rect; mod = index.data(Qt.ItemDataRole.UserRole)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        # Checked means included at launch; Qt selection only chooses the details
        # target. Keep the enabled treatment visible when focus moves elsewhere.
        checked = packages.game_mod(mod) and index.data(Qt.ItemDataRole.CheckStateRole) in (Qt.CheckState.Checked, Qt.CheckState.Checked.value)
        background = ('checked_selected' if selected else 'checked_hover' if hover else 'checked') if checked else ('selected' if selected else 'hover' if hover else 'surface')
        painter.fillRect(rect, QColor(COLORS[background]))
        painter.setPen(QColor(COLORS['line'])); painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        if self.window.view == 'grid': painter.drawLine(rect.topRight(), rect.bottomRight())
        if checked:
            painter.fillRect(QRect(rect.left(), rect.top()+1, 3, rect.height()-2), QColor(COLORS['checked_accent']))
        if option.state & QStyle.StateFlag.State_HasFocus:
            painter.setPen(QPen(QColor(COLORS['focus']), 1)); painter.drawRect(rect.adjusted(1, 1, -2, -2))
        check = QStyleOptionButton(); check.rect = self.checkbox(rect)
        check.state = QStyle.StateFlag.State_Enabled | (QStyle.StateFlag.State_On if checked else QStyle.StateFlag.State_Off)
        box = check.rect.adjusted(2,2,-2,-2)
        if packages.game_mod(mod):
            painter.setPen(QColor(COLORS['checked_accent'] if checked else COLORS['muted'])); painter.setBrush(QColor(COLORS['checked_accent'] if checked else COLORS['control'])); painter.drawRect(box)
        if packages.game_mod(mod) and check.state & QStyle.StateFlag.State_On:
            painter.setPen(QPen(QColor('#202020'),2)); painter.drawLine(box.left()+3,box.center().y(),box.left()+7,box.bottom()-3); painter.drawLine(box.left()+7,box.bottom()-3,box.right()-2,box.top()+3)
        grid = self.window.view == 'grid'; details = self.window.view == 'details'
        if grid:
            index.data(Qt.ItemDataRole.DecorationRole).paint(painter, QRect(rect.x()+16, rect.y()+15, 64, 64))
            text = QRect(rect.x()+16, rect.y()+90, rect.width()-32, 24)
        elif details:
            index.data(Qt.ItemDataRole.DecorationRole).paint(painter, QRect(rect.x()+48, rect.y()+18, 54, 54))
            text = QRect(rect.x()+118, rect.y()+15, rect.width()-180, 23)
        else: text = QRect(rect.x()+48, rect.y()+10, rect.width()-155, 24)
        painter.setPen(QColor(COLORS['text'])); font = QFont(option.font); font.setBold(True); painter.setFont(font)
        painter.drawText(text, Qt.AlignmentFlag.AlignVCenter, painter.fontMetrics().elidedText(mod['name'], Qt.TextElideMode.ElideRight, text.width()))
        painter.setFont(option.font); painter.setPen(QColor(COLORS['muted']))
        if grid or details:
            summary = QRect(text.x(), text.bottom()+4, text.width(), 40 if grid else 32)
            painter.drawText(summary, Qt.TextFlag.TextWordWrap, mod['summary'])
            status = 'Companion tool' if mod['kind'] == 'companion' else 'Enabled' if check.state & QStyle.StateFlag.State_On else 'Disabled'
            painter.setPen(QColor(COLORS['checked_accent'] if checked else COLORS['muted']))
            painter.drawText(QRect(text.x(), rect.bottom()-27, text.width(), 22), Qt.AlignmentFlag.AlignVCenter, 'v' + mod['version'] + '  ·  ' + status)
        else:
            painter.drawText(QRect(rect.right()-100, rect.y()+10, 88, 24), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, 'v' + mod['version'])
        painter.restore()

    def editorEvent(self, event, model, option, index):
        if not packages.game_mod(index.data(Qt.ItemDataRole.UserRole)): return False
        # PySide 6.8 can store an enum as an opaque QVariant; Qt's checkState()
        # then reads zero. Pass integer role data on both mouse and key paths.
        if event.type() == event.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton and self.checkbox(option.rect).contains(event.position().toPoint()):
            current = index.data(Qt.ItemDataRole.CheckStateRole)
            return model.setData(index, Qt.CheckState.Unchecked.value if current in (Qt.CheckState.Checked, Qt.CheckState.Checked.value) else Qt.CheckState.Checked.value, Qt.ItemDataRole.CheckStateRole)
        if event.type() == event.Type.KeyPress and event.key() == Qt.Key.Key_Space:
            current = index.data(Qt.ItemDataRole.CheckStateRole)
            return model.setData(index, Qt.CheckState.Unchecked.value if current in (Qt.CheckState.Checked, Qt.CheckState.Checked.value) else Qt.CheckState.Checked.value, Qt.ItemDataRole.CheckStateRole)
        return False


class Window(QMainWindow):
    def __init__(self, service, no_launch=False):
        super().__init__(); self.service = service; self.no_launch = no_launch
        self.diagnostics = diagnostics.start(service.root)
        QImageReader.setAllocationLimit(32)
        self.view = service.state.get('view', 'grid'); self.mods = {}; self.installations = []; self.inspection = None
        self.compatibility_report = None
        self.job = None; self.process = None; self._busy = False; self._validation = ''
        self.feedback = LaunchFeedback(); self.launch_record = None
        self._launch_guard_error = ''; self._launch_job = False
        try:
            pending = pending_launch(service.root)
            if pending:
                self.feedback.phase = 'unconfirmed'
                self.feedback.installed = pending['state'].startswith('steam-')
                self.launch_record = {'mode':'installed' if self.feedback.installed else 'private', 'run':pending.get('run', '')}
        except (ValueError, OSError) as error:
            self._launch_guard_error = 'Could not read launch state. Open logs and inspect active.json before launching.'
            self.diagnostics.exception('launch-state-error', error)
        self.setWindowTitle('Moon Sweepers · Mod Loader'); self.resize(1190, 760); self.setMinimumSize(700, 540)
        self.setAcceptDrops(True)
        self.setStyleSheet(STYLE)
        icon_path = service.bundle / 'assets/electricity-toggle.svg'
        self.setWindowIcon(QIcon(str(icon_path)))
        central = QWidget(); self.setCentralWidget(central); layout = QVBoxLayout(central); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        header, head = frame('header', True)
        titles = QVBoxLayout(); titles.setSpacing(2); titles.addWidget(label('Moon Sweepers', 'title')); titles.addWidget(label('Drop mod files or folders to add them', 'muted')); head.addLayout(titles); head.addStretch()
        self.import_button = QPushButton('Add mods…'); self.import_button.clicked.connect(self.import_package); head.addWidget(self.import_button)
        self.import_button.setToolTip('Add downloaded .msmod packages or supported ZIP files. You can select several.')
        self.import_folder_button = QPushButton('Add folder…'); self.import_folder_button.clicked.connect(self.import_folder); head.addWidget(self.import_folder_button)
        self.logs_button = QPushButton('Open logs'); self.logs_button.setToolTip('Open local loader diagnostics. Logs are never uploaded automatically.'); self.logs_button.clicked.connect(self.open_logs); head.addWidget(self.logs_button); layout.addWidget(header)
        setup, setup_layout = frame('header')
        row = QHBoxLayout(); row.addWidget(label('Game'))
        self.game = QComboBox(); self.game.setMinimumWidth(200); self.game.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon); self.game.currentIndexChanged.connect(self.game_changed); row.addWidget(self.game, 1)
        self.browse = QPushButton('Browse…'); self.browse.clicked.connect(self.browse_game); row.addWidget(self.browse)
        self.rescan = QPushButton('Rescan'); self.rescan.clicked.connect(self.scan); row.addWidget(self.rescan); setup_layout.addLayout(row)
        self.game_status = label('Looking for Steam installations…', 'path'); self.game_status.setWordWrap(True); setup_layout.addWidget(self.game_status); layout.addWidget(setup)
        mode_row = QHBoxLayout(); mode_row.addWidget(label('Installation'))
        self.deployment_mode = QComboBox(); self.deployment_mode.addItem('Existing Steam game', 'installed'); self.deployment_mode.addItem('Private game copy', 'private')
        self.deployment_mode.currentIndexChanged.connect(self.mode_changed); mode_row.addWidget(self.deployment_mode, 1)
        self.compatibility_button = QPushButton('Compatibility…'); self.compatibility_button.clicked.connect(self.show_compatibility); mode_row.addWidget(self.compatibility_button)
        self.disable_button = QPushButton('Disable mods'); self.disable_button.clicked.connect(lambda:self.toggle_installed(False)); mode_row.addWidget(self.disable_button)
        self.enable_button = QPushButton('Enable mods'); self.enable_button.clicked.connect(lambda:self.toggle_installed(True)); mode_row.addWidget(self.enable_button)
        self.uninstall_button = QPushButton('Uninstall loader'); self.uninstall_button.clicked.connect(self.uninstall_loader); mode_row.addWidget(self.uninstall_button)
        setup_layout.addLayout(mode_row)
        setup_row = QHBoxLayout()
        self.steam_setup_button = QPushButton('Steam setup…'); self.steam_setup_button.clicked.connect(self.steam_setup); setup_row.addWidget(self.steam_setup_button)
        self.proton_hint = label('', 'muted'); setup_row.addWidget(self.proton_hint, 1); setup_layout.addLayout(setup_row)
        self.proton_hint.setWordWrap(True); self.proton_hint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        toolbar, bar = frame('toolbar', True, (16, 8, 16, 8))
        self.search = QLineEdit(); self.search.setPlaceholderText('Search mods, categories or tags'); self.search.setAccessibleName('Search installed mods, categories or tags'); self.search.setClearButtonEnabled(True); self.search.textChanged.connect(self.render); bar.addWidget(self.search, 1)
        self.search.setAcceptDrops(False)
        self.search.setToolTip('Search names, descriptions, categories and tags. Combine words, for example: vehicles automation.')
        self.filter = QComboBox(); self.filter.addItem('All mods', 'all'); self.filter.addItem('Enabled', 'enabled')
        for value, name in CATEGORIES.items(): self.filter.addItem(name, value)
        self.filter.setAccessibleName('Filter mods by status or category'); self.filter.currentIndexChanged.connect(self.render); bar.addWidget(self.filter)
        self.select_all_button = QPushButton('Select all'); self.select_all_button.setToolTip('Select every game mod in the library, including hidden search results.'); self.select_all_button.clicked.connect(lambda: self.set_all_checked(True)); bar.addWidget(self.select_all_button)
        self.deselect_all_button = QPushButton('Deselect all'); self.deselect_all_button.setToolTip('Clear all game mod checkmarks, including hidden search results.'); self.deselect_all_button.clicked.connect(lambda: self.set_all_checked(False)); bar.addWidget(self.deselect_all_button)
        self.views = {}
        for view, title in [('grid','Grid'), ('details','Details'), ('text','Text')]:
            button = QPushButton(title); button.setCheckable(True); button.setChecked(view == self.view); button.clicked.connect(lambda checked=False, v=view: self.set_view(v)); self.views[view] = button; bar.addWidget(button)
        layout.addWidget(toolbar)
        self.workspace, panes = frame('workspace', True, (0,0,0,0)); panes.setSpacing(0)
        center = QWidget(); center_layout = QVBoxLayout(center); center_layout.setContentsMargins(0,0,0,0); center_layout.setSpacing(0)
        self.list = ModList(); self.list.setMouseTracking(True); self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); self.list.setResizeMode(QListWidget.ResizeMode.Adjust); self.list.setSpacing(0)
        self.list.setAccessibleName('Installed mods. Space toggles the focused mod.'); self.list.setItemDelegate(ModDelegate(self)); self.list.itemChanged.connect(self.checked); self.list.currentItemChanged.connect(self.show_details); self.list.itemDoubleClicked.connect(lambda item: self.details_dialog(item.data(Qt.ItemDataRole.UserRole)))
        center_layout.addWidget(self.list, 1)
        self.empty = label('Drop mod files or folders here, or use Add mods… / Add folder….', 'muted'); self.empty.setWordWrap(True); self.empty.setMargin(24); center_layout.addWidget(self.empty)
        panes.addWidget(center, 1)
        self.details = QScrollArea(); self.details.setObjectName('details'); self.details.setFixedWidth(285); self.details.setWidgetResizable(True); self.details.setFrameShape(QFrame.Shape.NoFrame)
        detail_content, details = frame('detail-content', False, (18,18,18,18)); self.details.setWidget(detail_content)
        self.detail_icon = QLabel(); self.detail_icon.setFixedSize(64,64); details.addWidget(self.detail_icon)
        self.detail_name = label('Select a mod', 'section'); self.detail_name.setWordWrap(True); details.addWidget(self.detail_name)
        self.detail_meta = label('', 'muted'); self.detail_meta.setWordWrap(True); details.addWidget(self.detail_meta)
        self.detail_catalog = label('', 'muted'); self.detail_catalog.setTextFormat(Qt.TextFormat.PlainText); self.detail_catalog.setWordWrap(True); details.addWidget(self.detail_catalog)
        self.detail_text = label('Check a mod to include it in the next launch.'); self.detail_text.setWordWrap(True); details.addWidget(self.detail_text)
        self.detail_verification = label('', 'muted'); self.detail_verification.setWordWrap(True); details.addWidget(self.detail_verification)
        details.addStretch(); self.open_tool_button = QPushButton('Open tool folder'); self.open_tool_button.clicked.connect(self.open_tool_folder); self.open_tool_button.hide(); details.addWidget(self.open_tool_button)
        self.more = QPushButton('Package details…'); self.more.clicked.connect(lambda: self.details_dialog(self.current_mod())); details.addWidget(self.more)
        self.remove_button = QPushButton('Remove from library'); self.remove_button.clicked.connect(self.remove_mod); details.addWidget(self.remove_button); panes.addWidget(self.details); layout.addWidget(self.workspace, 1)
        self.message = label('', 'message'); self.message.setWordWrap(True); self.message.hide(); layout.addWidget(self.message)
        launch_status, status_layout = frame('launchStatus', margins=(16, 8, 16, 8))
        self.launch_status = label('', 'launchStatusText'); self.launch_status.setWordWrap(True)
        self.launch_status.setTextFormat(Qt.TextFormat.PlainText); status_layout.addWidget(self.launch_status)
        status_row = QHBoxLayout()
        self.launch_details_button = QPushButton('Launch diagnostics ▸'); self.launch_details_button.setCheckable(True)
        self.launch_details_button.toggled.connect(self.toggle_launch_details); status_row.addWidget(self.launch_details_button)
        self.launch_reset_button = QPushButton('Game closed / did not start…'); self.launch_reset_button.clicked.connect(self.reset_launch)
        self.launch_reset_button.hide(); status_row.addWidget(self.launch_reset_button); status_row.addStretch(); status_layout.addLayout(status_row)
        self.launch_details = QPlainTextEdit(); self.launch_details.setReadOnly(True); self.launch_details.setMaximumHeight(110)
        self.launch_details.setMaximumBlockCount(80); self.launch_details.hide(); status_layout.addWidget(self.launch_details)
        layout.addWidget(launch_status)
        footer, foot = frame('footer', True)
        facts = QVBoxLayout(); facts.setSpacing(3); self.count = label('0 selected'); facts.addWidget(self.count); self.save_info = label('Fresh private saves', 'muted'); self.save_info.setWordWrap(True); facts.addWidget(self.save_info); foot.addLayout(facts, 1)
        actions = QVBoxLayout(); actions.setSpacing(4); self.plan_button = QPushButton('View launch plan'); self.plan_button.clicked.connect(self.show_plan); actions.addWidget(self.plan_button)
        self.prepare_button = QPushButton('Prepare files'); self.prepare_button.clicked.connect(self.prepare_files); actions.addWidget(self.prepare_button); foot.addLayout(actions)
        self.launch_button = QPushButton('Launch modded game'); self.launch_button.setObjectName('launch'); self.launch_button.clicked.connect(self.start_game); foot.addWidget(self.launch_button); layout.addWidget(footer)
        self.timer = QTimer(self); self.timer.timeout.connect(self.poll_process)
        self.scan(); self.refresh_library(); self.set_view(self.view)
        if self.feedback.blocked:
            self.set_launch_details(); self.show_launch_feedback(); self.timer.start(2000)
        if self._launch_guard_error: self.notice(self._launch_guard_error, 'error')

    def current_installation(self):
        index = self.game.currentIndex(); return self.installations[index] if 0 <= index < len(self.installations) else None

    def current_mod(self):
        item = self.list.currentItem(); return item.data(Qt.ItemDataRole.UserRole) if item else None

    def notice(self, text, severity='info'):
        self.message.setProperty('severity', severity)
        self.message.style().unpolish(self.message); self.message.style().polish(self.message)
        if text and text != self.message.text(): self.diagnostics.event('notice', text)
        self.message.setText(text); self.message.setVisible(bool(text))

    def report_error(self, error):
        self.diagnostics.exception('operation-error', error)
        self.notice(str(error), 'error')

    def open_logs(self):
        installation = self.current_installation()
        if installation:
            result = diagnostics.collect_selected_installed(self.service, installation)
            if result and (result.get('status') == 'adapter-failed' or result.get('preloader_logs')):
                self.notice('Game startup failed. Open the collected logs for the failure report.', 'error')
        self.diagnostics.event('logs-opened', 'Opening local loader diagnostics')
        if self.diagnostics.error:
            self.notice('Could not save logs: '+self.diagnostics.error); return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.diagnostics.folder))):
            self.notice('Could not open the logs folder: '+str(self.diagnostics.folder))

    def scan(self):
        previous = self.service.state.get('installation', '')
        self.installations, errors = self.service.installations()
        self.game.blockSignals(True); self.game.clear()
        for item in self.installations:
            self.game.addItem(('Steam' if item.store == 'steam' else item.store.title()) + ' · ' + item.path)
        self.game.blockSignals(False)
        if not self.installations: self.game.addItem('No game found — choose Browse…')
        else: self.game.setCurrentIndex(next((i for i,x in enumerate(self.installations) if x.path == previous),0))
        self.game_changed()
        if errors:
            self.diagnostics.event('discovery-errors', 'Some Steam libraries could not be read', 'WARNING', errors=errors)
            self.notice('Some Steam libraries could not be read. Browse to the game folder if needed.')

    def game_changed(self, *_):
        installation = self.current_installation(); self.inspection = None
        if installation:
            self.deployment_mode.blockSignals(True); self.deployment_mode.setCurrentIndex(0 if self.service.mode(installation) == 'installed' else 1); self.deployment_mode.blockSignals(False)
            self.service.state['installation'] = installation.path; self.service.save()
            try:
                self.inspection = self.service.inspect(installation); self.game_status.setText(self.inspection['reason'])
            except (ValueError, OSError) as error:
                self.diagnostics.exception('inspection-error', error); self.game_status.setText(str(error))
        else: self.game_status.setText('Steam detection checks native and Flatpak libraries. Browse to its installation folder to add a game manually.')
        self.update_actions()

    def mode_changed(self, *_):
        installation = self.current_installation()
        if installation:
            self.service.set_mode(installation, self.deployment_mode.currentData()); self.update_actions()

    def toggle_installed(self, enabled):
        installation = self.current_installation()
        self.work('Updating next-launch mod state…', lambda:self.service.set_enabled(installation, enabled),
                  lambda _:self.notice('Mods ' + ('enabled' if enabled else 'disabled') + ' on the next launch.'))

    def uninstall_loader(self):
        installation = self.current_installation()
        if QMessageBox.question(self, 'Uninstall loader', 'Remove this loader’s unchanged installed files? Saves and settings are kept. Modded saves may require their frameworks.') != QMessageBox.StandardButton.Yes: return
        self.work('Removing owned installed files…', lambda:self.service.uninstall(installation), lambda _:self.notice('Loader removed. Saves/settings kept; Steam launch options were not changed automatically.'))

    def confirm_save_policy(self, installation):
        if self.service.mode(installation) != 'installed' or not self.service.state['selected']: return True
        try:
            if self.service.save_policy_ready(installation): return True
        except (ValueError, OSError) as error: self.report_error(error); return False
        dialog = QMessageBox(self); dialog.setWindowTitle('Normal Steam saves')
        dialog.setText('Installed mods use your normal Steam saves. Back up the save folder and sidecars before enabling mods that change saved worlds. Removing DLLs does not restore saves.')
        backup = dialog.addButton('Back up Steam save folder…', QMessageBox.ButtonRole.AcceptRole)
        existing = dialog.addButton('Already backed up', QMessageBox.ButtonRole.AcceptRole)
        fresh = dialog.addButton('Fresh Steam profile', QMessageBox.ButtonRole.AcceptRole)
        dialog.addButton(QMessageBox.StandardButton.Cancel); dialog.exec()
        chosen = dialog.clickedButton()
        if chosen == backup:
            source = QFileDialog.getExistingDirectory(self, 'Choose your Steam save folder, including sidecars')
            if not source: return False
            try: self.service.backup_saves(installation, source)
            except (ValueError, OSError) as error: self.report_error(error); return False
        elif chosen in (existing, fresh): self.service.accept_normal_saves(installation, 'backed-up' if chosen == existing else 'fresh')
        else: return False
        return True

    def browse_game(self):
        path = QFileDialog.getExistingDirectory(self, 'Choose Moon Sweepers game folder')
        if path:
            try: self.service.add_installation(path); self.scan()
            except (ValueError, OSError) as error: self.report_error(error)

    def import_package(self):
        if self.launch_blocked(): return
        paths, _ = QFileDialog.getOpenFileNames(self, 'Add downloaded mods', '', 'Mod downloads (*.msmod *.zip);;All files (*)')
        if paths: self.add_mod_paths(paths)

    def import_folder(self):
        if self.launch_blocked(): return
        path = QFileDialog.getExistingDirectory(self, 'Choose a downloaded mod folder')
        if path: self.add_mod_paths([path])

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if not self.launch_blocked() and urls and all(url.isLocalFile() for url in urls):
            event.acceptProposedAction()
        else: event.ignore()

    def dragMoveEvent(self, event): self.dragEnterEvent(event)

    def dropEvent(self, event):
        self.dragEnterEvent(event)
        if event.isAccepted():
            self.add_mod_paths([url.toLocalFile() for url in event.mimeData().urls()])

    def add_mod_paths(self, paths):
        if self.launch_blocked(): return
        self.work('Adding downloaded mods…', lambda: self.service.import_downloads(paths), self.mods_added)

    def mods_added(self, result):
        self.refresh_library()
        installed, errors = result['installed'], result['errors']
        if errors: self.diagnostics.event('import-errors', 'Some mod imports failed', 'ERROR', errors=errors)
        parts = []
        if installed:
            parts.append('Added ' + ', '.join(mod['name'] for mod in installed) + '. Select the mods and dependencies to use them.')
        if any(mod['kind'] == packages.MANAGED_KIND for mod in installed):
            parts.append('BepInEx mods need the supported BepInEx runtime and Private game copy mode before they can run.')
        parts += [Path(item['path']).name + ': ' + item['error'] for item in errors[:5]]
        if len(errors) > 5: parts.append(str(len(errors) - 5) + ' more downloads could not be added.')
        self.notice('\n'.join(parts) or 'These mods are already included in this import.')

    def refresh_library(self):
        self.mods, errors = self.service.library(); self.render()
        if errors:
            self.diagnostics.event('package-errors', 'Package validation failed', 'ERROR', errors=errors)
            self.notice('Package check failed: ' + '; '.join(name + ': ' + error for name,error in errors.items()))

    def render(self, *_):
        old = self.current_mod(); old_id = old['id'] if old else ''
        query = self.search.text().casefold(); self.list.blockSignals(True); self.list.clear()
        for name,(mod, folder) in sorted(self.mods.items(), key=lambda item:item[1][0]['name'].casefold()):
            enabled = name in self.service.state['selected']
            if not matches(mod, query, self.filter.currentData(), enabled): continue
            item = QListWidgetItem(QIcon(str(folder / mod['icon'])), mod['name']); item.setData(Qt.ItemDataRole.UserRole, mod)
            if packages.game_mod(mod):
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable); item.setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
            else: item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            item.setToolTip(mod['name'] + '\n' + mod['summary'] + ('\n' + catalog_description(mod) if catalog_description(mod) else '') + ('\nSpace toggles this mod.' if packages.game_mod(mod) else '\nCompanion tool. Open its folder from package details.') + ' Double-click for details.')
            self.list.addItem(item)
            if mod['id'] == old_id: self.list.setCurrentItem(item)
        if not self.list.currentItem() and self.list.count(): self.list.setCurrentRow(0)
        self.list.blockSignals(False); self.empty.setVisible(not self.list.count()); self.list.setVisible(bool(self.list.count()))
        self.empty.setText('No matching mods. Clear the search or choose All mods.' if self.mods else 'Drop mod files or folders here, or use Add mods… / Add folder….')
        self.show_details(self.list.currentItem()); self.update_actions()

    def checked(self, item):
        if not packages.game_mod(item.data(Qt.ItemDataRole.UserRole)): return
        name = item.data(Qt.ItemDataRole.UserRole)['id']; selected = set(self.service.state['selected'])
        if item.checkState() == Qt.CheckState.Checked: selected.add(name)
        else: selected.discard(name)
        self.service.state['selected'] = sorted(selected); self.service.save(); self.update_actions()
        if self.filter.currentIndex() == 1: QTimer.singleShot(0, self.render)

    def set_all_checked(self, enabled):
        if self.launch_blocked(): return
        # Act on the library rather than visible rows so filters cannot leave
        # hidden mods enabled. Companion tools never participate in game startup.
        previous = self.service.state['selected']
        self.service.state['selected'] = sorted(name for name,(mod,_) in self.mods.items() if packages.game_mod(mod)) if enabled else []
        try: self.service.save()
        except (ValueError,OSError) as error:
            self.service.state['selected'] = previous; self.report_error(error); return
        self.render()

    def set_view(self, view):
        self.view = view if view in ('grid','details','text') else 'grid'
        for name, button in self.views.items(): button.setChecked(name == self.view)
        grid = self.view == 'grid'; self.list.setViewMode(QListWidget.ViewMode.IconMode if grid else QListWidget.ViewMode.ListMode)
        self.list.setFlow(QListWidget.Flow.LeftToRight if grid else QListWidget.Flow.TopToBottom); self.list.setWrapping(grid)
        self.list.setMovement(QListWidget.Movement.Static); self.list.setGridSize(QSize(238,192) if grid else QSize())
        # IconMode uses pixel scrollbar ranges even with ScrollPerItem, whose
        # default one-unit step makes a wheel notch move just three pixels.
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel if grid else QAbstractItemView.ScrollMode.ScrollPerItem)
        self.list.verticalScrollBar().setSingleStep(64 if grid else 1)
        self.list.setUniformItemSizes(True); self.service.state['view'] = self.view; self.service.save(); self.list.doItemsLayout(); self.list.viewport().update()

    def show_details(self, item=None, *_):
        mod = item.data(Qt.ItemDataRole.UserRole) if item else None
        self.more.setEnabled(bool(mod)); self.remove_button.setEnabled(bool(mod))
        self.open_tool_button.setVisible(bool(mod and mod['kind'] == 'companion'))
        if not mod:
            self.detail_name.setText('Select a mod'); self.detail_meta.clear(); self.detail_catalog.clear(); self.detail_catalog.hide(); self.detail_text.setText('Check a mod to include it in the next launch.'); self.detail_verification.clear(); self.detail_icon.clear(); return
        folder = self.mods[mod['id']][1]; self.detail_icon.setPixmap(QIcon(str(folder / mod['icon'])).pixmap(64,64))
        self.detail_name.setText(mod['name']); self.detail_meta.setText('v'+mod['version']+' · '+mod['author']+(' · Companion tool' if mod['kind']=='companion' else ''))
        self.detail_catalog.setText(catalog_description(mod)); self.detail_catalog.setVisible(bool(catalog_description(mod)))
        self.detail_text.setText(mod['summary']+'\n\n'+ ('Runs separately with Python. Open its folder for the application and README.' if mod['kind']=='companion' else 'Game: '+mod['game'].get('version','Pinned build')))
        text = 'Compatibility\nChoose a game to check this mod and its required frameworks.'
        installation = self.current_installation()
        if installation and packages.game_mod(mod):
            try:
                result = self.service.mod_compatibility(installation, mod['id'], library=self.mods, inspection=self.inspection)
                text = compatibility.describe(result, {name: pair[0]['name'] for name, pair in self.mods.items()})
            except (ValueError, OSError) as error: text = 'Compatibility could not be checked: ' + str(error)
        if not packages.game_mod(mod): text = 'Companion tool · runs separately from the game.'
        notes = '\n'.join(key.replace('_', ' ').title() + ': ' + str(value) for key, value in mod.get('verification', {}).items())
        self.detail_verification.setText(text + ('\n\nPackage author notes\n' + notes if notes else ''))

    def details_dialog(self, mod):
        if not mod: return
        self.text_dialog(mod['name'], mod['description'] + ('\n\n' + catalog_description(mod) if catalog_description(mod) else '') + '\n\nPackage manifest\n' + json.dumps(mod, indent=2), mod['id'] if mod['kind']=='companion' else None)

    def text_dialog(self, title, text, tool_id=None):
        dialog = QDialog(self); dialog.setWindowTitle(title); dialog.resize(720,520); layout = QVBoxLayout(dialog)
        edit = QPlainTextEdit(); edit.setReadOnly(True); edit.setPlainText(text); layout.addWidget(edit)
        if tool_id:
            folder = QPushButton('Open tool folder'); folder.clicked.connect(lambda: self.open_tool_folder(tool_id)); layout.addWidget(folder)
        close = QPushButton('Close'); close.clicked.connect(dialog.accept); layout.addWidget(close); dialog.exec()

    def open_tool_folder(self, name=None):
        mod = self.current_mod() if not isinstance(name,str) else self.mods.get(name,(None,None))[0]
        if not mod or mod['kind'] != 'companion': return
        try:
            from .packages import installed
            folder = self.mods[mod['id']][1]; installed(folder)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        except (ValueError,OSError) as error: self.report_error(error)

    def remove_mod(self):
        mod = self.current_mod()
        if mod: self.service.remove(mod['id']); self.refresh_library(); self.notice(mod['name'] + ' removed from the library. Prepared game files remain until the next Prepare files or installed-loader uninstall. Package files are retained for recovery.')

    def update_actions(self):
        selected = self.service.state['selected']; self.count.setText(f'{len(selected)} selected · {len(self.mods)} installed')
        installation = self.current_installation(); installed = bool(installation and self.service.mode(installation) == 'installed')
        reason = ''
        self.compatibility_report = None
        if installation:
            try:
                self.compatibility_report = self.service.compatibility(installation, library=self.mods, inspection=self.inspection)
                if not self.compatibility_report['allowed']: reason = compatibility.message(self.compatibility_report)
                summary = self.compatibility_report['game']['description']
                status = compatibility.LABELS[self.compatibility_report['status']]
                self.game_status.setText(summary if summary.casefold().startswith(status.casefold()) else summary + ' · ' + status)
            except (ValueError, OSError) as error: reason = str(error)
        ready = bool(self.compatibility_report and self.compatibility_report['allowed'] and (selected or installed))
        active = self.launch_blocked()
        self.compatibility_button.setEnabled(bool(installation) and not active)
        native = {name for name,(mod,_) in self.mods.items() if packages.game_mod(mod)}
        self.select_all_button.setEnabled(not active and bool(native - set(selected)))
        self.deselect_all_button.setEnabled(not active and bool(selected))
        self.launch_button.setEnabled(ready and not active and not self.no_launch)
        launch_title = {'waiting':'Starting…', 'running':'Game running', 'unconfirmed':'Launch unconfirmed', 'failed':'Launch needs attention', 'finishing':'Finishing launch…'}.get(self.feedback.phase)
        self.launch_button.setText('Preparing…' if self._launch_job and self._busy else launch_title or ('Launch via Steam' if installed else 'Launch modded game'))
        self.prepare_button.setEnabled(ready and not active); self.plan_button.setEnabled(ready and not active)
        self.launch_button.setToolTip('Game starts are disabled in this UI inspection session.' if self.no_launch else reason or ('Launch automatically applies selected mods, then requests Steam launch. Prepare files is optional.' if installed else 'Prepare a private game copy and launch the checked mods.'))
        self.save_info.setText('Normal Steam saves · back up before save-affecting mods' if installed else 'Fresh private saves')
        self.proton_hint.setVisible(installed and sys.platform == 'linux')
        self.steam_setup_button.setVisible(installed and sys.platform == 'linux'); self.steam_setup_button.setEnabled(not active)
        if installed and sys.platform == 'linux': self.proton_hint.setText(steam_options.inspect(installation, managed=any(self.mods[name][0]['kind'] == packages.MANAGED_KIND for name in self.service.state['selected'] if name in self.mods))['message'])
        for widget in [self.disable_button, self.enable_button, self.uninstall_button]: widget.setVisible(installed); widget.setEnabled(not active)
        for widget in [self.game,self.browse,self.rescan,self.import_button,self.import_folder_button,self.list,self.remove_button,self.deployment_mode]: widget.setEnabled(not active)
        if not active and (reason or self._validation and self.message.text() == self._validation): self.notice(reason, 'warning' if reason else 'info')
        self.launch_details_button.setEnabled(self.launch_record is not None)
        self.launch_reset_button.setVisible(self.feedback.blocked and self.launch_record is not None)
        self.launch_reset_button.setEnabled(not self._busy and self.process is None and self.feedback.phase != 'running')
        self._validation = reason

    def show_compatibility(self):
        installation = self.current_installation()
        if not installation: return
        try:
            result = self.service.compatibility(installation)
            self.text_dialog('Mod compatibility · no game started', compatibility.describe(result, {name: pair[0]['name'] for name, pair in self.mods.items()}))
        except (ValueError, OSError) as error: self.report_error(error)

    def show_plan(self):
        try:
            record = launch.plan(self.service, self.current_installation(), check_client=False)
            self.text_dialog('Launch plan · no game started', json.dumps(record, indent=2))
        except (ValueError,OSError) as error: self.report_error(error)

    def work(self, text, action, done, staged=False, failed=None):
        if self._busy: return
        self.diagnostics.event('operation-start', text)
        self._busy=True; self.notice(text); self.update_actions(); self.job=Job(action,self,staged)
        self.job.finished_value.connect(done); self.job.failed.connect(failed or (lambda text:self.notice(text, 'error'))); self.job.progress.connect(self.notice); self.job.finished.connect(self.job_done); self.job.start()

    def job_done(self): self._busy=False; self._launch_job=False; self.update_actions(); self.job.deleteLater(); self.job=None

    def prepare_files(self):
        if self.launch_blocked(): return
        installation=self.current_installation()
        if not self.confirm_save_policy(installation): return
        installed = self.service.mode(installation) == 'installed'
        self.work('Applying selected mods…' if installed else 'Preparing private game files… This may take a few minutes.', lambda:self.service.prepare(installation), lambda root:self.notice('Installed mods ready. Normal Steam saves are in use.' if installed else 'Files ready. Private saves: '+str(root / 'profile/AppData/LocalLow/DragDropGames/MoonSweepers')))

    def steam_setup(self):
        installation = self.current_installation()
        if not installation: return
        preview = steam_options.inspect(installation, managed=any(self.mods[name][0]['kind'] == packages.MANAGED_KIND for name in self.service.state['selected'] if name in self.mods))
        dialog = QDialog(self); dialog.setWindowTitle('Steam launch setup'); dialog.resize(680, 420); layout = QVBoxLayout(dialog)
        info = label(preview['message'] + '\n\nQuit Steam completely before applying; reopen it afterwards. Existing options are preserved and the original config is backed up.'); info.setWordWrap(True); layout.addWidget(info)
        edit = QPlainTextEdit(); edit.setReadOnly(True); edit.setPlainText('Current launch options\n' + preview.get('current', '(unavailable)') + '\n\nProposed launch options\n' + preview.get('proposed', '(manual setup required)')); layout.addWidget(edit)
        row = QHBoxLayout(); apply = QPushButton('Apply required launch options'); apply.setEnabled(preview['status'] == 'required'); row.addWidget(apply)
        refresh = QPushButton('Refresh preview'); row.addWidget(refresh)
        close = QPushButton('Close'); close.clicked.connect(dialog.accept); row.addWidget(close); layout.addLayout(row)
        def refresh_preview():
            nonlocal preview
            preview = steam_options.inspect(installation, managed=any(self.mods[name][0]['kind'] == packages.MANAGED_KIND for name in self.service.state['selected'] if name in self.mods))
            info.setText(preview['message'] + '\n\nQuit Steam completely before applying; reopen it afterwards. Existing options are preserved and the original config is backed up.')
            edit.setPlainText('Current launch options\n' + preview.get('current', '(unavailable)') + '\n\nProposed launch options\n' + preview.get('proposed', '(manual setup required)'))
            apply.setEnabled(preview['status'] == 'required')
        refresh.clicked.connect(refresh_preview)
        def apply_options():
            try:
                result = steam_options.apply(installation, self.service.root, preview)
                self.notice(result.get('message', 'Steam options are already ready.')); dialog.accept(); self.update_actions()
            except (ValueError, OSError) as error:
                self.diagnostics.exception('steam-setup-error', error); info.setText(str(error))
        apply.clicked.connect(apply_options); dialog.exec()

    def start_game(self):
        if self.no_launch or self.launch_blocked(): return
        installation=self.current_installation()
        if self.service.mode(installation) == 'installed' and self.service.state['selected']:
            status = steam_options.inspect(installation, managed=any(self.mods[name][0]['kind'] == packages.MANAGED_KIND for name in self.service.state['selected'] if name in self.mods))
            if status['status'] not in ('ready', 'not-required'):
                self.steam_setup(); return
        if not self.confirm_save_policy(installation): return
        self.launch_record = None; self._launch_job = True
        self.work('Applying selected mods automatically before launch…', lambda progress:launch.start(self.service,installation,progress), self.started, staged=True, failed=self.launch_failed)

    def launch_blocked(self):
        return self._busy or self.process is not None or self.feedback.blocked or bool(self._launch_guard_error)

    def toggle_launch_details(self, expanded):
        self.launch_details.setVisible(expanded)
        self.launch_details_button.setText('Launch diagnostics ▾' if expanded else 'Launch diagnostics ▸')

    def show_launch_feedback(self):
        self.launch_status.setText(self.feedback.message)
        self.launch_status.setProperty('severity', 'error' if self.feedback.phase == 'failed' else 'info')
        self.launch_status.style().unpolish(self.launch_status); self.launch_status.style().polish(self.launch_status)
        self.update_actions()

    def set_launch_details(self, code=None, detail=''):
        record = self.launch_record or {}
        lines = ['Observed process: ' + ('Steam launch request' if record.get('mode') == 'installed' else 'Private launch process'),
                 'Game startup/mod loading: not established by the launch request',
                 'Logs: ' + record.get('run', '(unavailable)')]
        if code is not None: lines.append('Request/process exit code: ' + str(code))
        if detail: lines.append(detail)
        if record.get('diagnostic_error'): lines.append('Diagnostic write error: ' + record['diagnostic_error'])
        self.launch_details.setPlainText('\n'.join(lines)[:16384])

    def launch_failed(self, text):
        try:
            pending = pending_launch(self.service.root)
            if pending:
                self.feedback.installed = pending['state'].startswith('steam-')
                self.launch_record = {'mode':'installed' if self.feedback.installed else 'private', 'run':pending.get('run', '')}
                self.feedback.phase = 'unconfirmed'; self.timer.start(2000)
                self.show_launch_feedback(); self.set_launch_details(detail=text)
        except (ValueError, OSError) as error:
            self._launch_guard_error = str(error)
        self.notice(text, 'error')

    def started(self, result):
        self.process,self.launch_record=result
        self.feedback.requested(self.launch_record.get('mode') == 'installed')
        self.timer.start(2000); self.set_launch_details(); self.show_launch_feedback()
        self.notice('Files applied. Launch requested through Steam.' if self.feedback.installed else 'Files applied. Starting the private game; startup is unconfirmed.')

    def reset_launch(self):
        if self._busy or self.process is not None or not self.launch_record: return
        if QMessageBox.question(self, 'Confirm game is closed',
                'Confirm Moon Sweepers is closed or did not start. If Steam still says Launching or Running, wait or close the game normally first. This only clears the loader’s launch guard; it does not stop anything.') != QMessageBox.StandardButton.Yes: return
        run = self.launch_record['run']
        def cleared(_):
            self.feedback = LaunchFeedback(); self._launch_guard_error = ''; self.timer.stop(); self.launch_status.setText('Launch guard cleared after your confirmation. Launch will apply selected mods automatically.')
            self.diagnostics.event('launch-acknowledged-closed', 'User confirmed game closed or did not start', run=run)
        self.work('Checking that Moon Sweepers is closed…', lambda:acknowledge_launch_closed(self.service.root, run), cleared)

    def poll_process(self):
        previous_phase = self.feedback.phase
        request_finished = False
        if self.process and self.process.poll() is not None:
            code=self.process.returncode; request_finished = True
            if hasattr(self.process,'_moon_lease'):
                try: retain_private_uncertainty(self.service.root, self.launch_record['run'])
                except (ValueError, OSError) as error:
                    self._launch_guard_error = 'Could not retain launch state; inspect active.json before another launch.'
                    self.diagnostics.exception('launch-state-error', error)
                self.process._moon_lease.__exit__(None,None,None)
            self.process=None
            detail=launch.failure_detail(self.launch_record)
            summary = diagnostics.finish_run(self.service.root, self.launch_record, code, detail)
            self.set_launch_details(code, detail)
            if self.feedback.installed:
                self.feedback.request_finished(code)
                if summary.get('status') in ('preloader-failed', 'adapter-failed'):
                    self.notice('Game startup failed. Expand launch diagnostics or open logs for the failure report.', 'error')
            else:
                self.feedback.request_finished(code)
                self.notice(detail or 'Private launch process finished; game lifetime needs confirmation. See launch diagnostics.', 'error' if detail or code else 'info')
        if self.launch_record and (self.feedback.blocked or request_finished):
            observation = game_process.observe()
            previous = self.feedback.phase
            self.feedback.observe(observation['status'])
            if self.feedback.phase == 'closed' and self.process is not None:
                self.feedback.phase = 'finishing'  # The request outlived the observed game.
            if self.feedback.phase == 'closed' and self.process is None:
                try:
                    acknowledge_launch_closed(self.service.root, self.launch_record['run'])
                    self._launch_guard_error = ''; self.timer.stop()
                except (ValueError, OSError):
                    # An uncertain scan or still-active runner never unlocks launch.
                    self.feedback.phase = 'unconfirmed'
            if previous != self.feedback.phase:
                self.diagnostics.event('launch-lifetime', self.feedback.message, state=self.feedback.phase)
        if request_finished or self.feedback.phase != previous_phase: self.show_launch_feedback()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self,'details'): self.details.setVisible(event.size().width() >= 1020)

    def closeEvent(self, event):
        if self._busy: self.notice('Wait for the current file operation to finish before closing.'); event.ignore()
        else:
            self.diagnostics.event('window-closed', 'Loader closed; a user-started game is left running.')
            event.accept()  # A user-started game is left alone when the loader closes.
