# Copyright (C) 2007, One Laptop Per Child
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

from gettext import gettext as _
import logging
import time
from datetime import datetime, timedelta
import os

import gobject
import gtk

from sugar.graphics.xocolor import XoColor
from sugar.graphics.toolbox import Toolbox
from sugar.graphics.toolcombobox import ToolComboBox
from sugar.graphics.toolbutton import ToolButton
from sugar.graphics.combobox import ComboBox
from sugar.graphics.menuitem import MenuItem
from sugar.graphics.icon import Icon
from sugar.graphics import iconentry
from sugar.graphics import style
from sugar import activity
from sugar import profile
from sugar import mime
try:
    from sugar.datastore import DUMMY_START_ACTIVITY_INFO
    from sugar.datastore import datastore
except:
    import datastore

import volumesmanager
import backup
import misc

_AUTOSEARCH_TIMEOUT = 1000
            
class MainToolbox(Toolbox):
    def __init__(self):
        Toolbox.__init__(self)

        self.search_toolbar = SearchToolbar()
        self.search_toolbar.set_size_request(-1, style.GRID_CELL_SIZE)
        self.add_toolbar(_('Search'), self.search_toolbar)
        self.search_toolbar.show()
        
        #self.backup_toolbar = BackupToolbar()
        #self.add_toolbar(_('Backup'), self.backup_toolbar)
        #self.backup_toolbar.show()
        
        #self.manage_toolbar = ManageToolbar()
        #self.add_toolbar(_('Manage'), self.manage_toolbar)
        #self.manage_toolbar.show()

class SearchToolbar(gtk.Toolbar):
    __gtype_name__ = 'SearchToolbar'

    __gsignals__ = {
        'query-changed': (gobject.SIGNAL_RUN_FIRST,
                          gobject.TYPE_NONE,
                          ([object]))
    }

    _ACTION_ANYTIME = 0
    _ACTION_TODAY = 1
    _ACTION_SINCE_YESTERDAY = 2
    _ACTION_PAST_WEEK = 3
    _ACTION_PAST_MONTH = 4
    _ACTION_PAST_YEAR = 5

    _ACTION_ANYTHING = 0

    _ACTION_EVERYBODY = 0
    _ACTION_MY_FRIENDS = 1
    _ACTION_MY_CLASS = 2
    
    def __init__(self):
        gtk.Toolbar.__init__(self)

        self._volume_id = None

        self._search_entry = iconentry.IconEntry()
        self._search_entry.set_icon_from_name(iconentry.ICON_ENTRY_PRIMARY,
                                              'system-search')
        self._search_entry.connect('activate', self._search_entry_activated_cb)
        self._search_entry.connect('changed', self._search_entry_changed_cb)
        self._search_entry.add_clear_button()
        self._autosearch_timer = None
        self._add_widget(self._search_entry, expand=True)

        self._what_search_combo = ComboBox()
        self._what_combo_changed_sid = \
                self._what_search_combo.connect('changed', self._combo_changed_cb)
        tool_item = ToolComboBox(self._what_search_combo)
        self.insert(tool_item, -1)
        tool_item.show()

        self._when_search_combo = self._get_when_search_combo()
        tool_item = ToolComboBox(self._when_search_combo)
        self.insert(tool_item, -1)
        tool_item.show()

        # TODO: enable it when the DS supports saving the buddies.
        #self._with_search_combo = self._get_with_search_combo()
        #tool_item = ToolComboBox(self._with_search_combo)
        #self.insert(tool_item, -1)
        #tool_item.show()

        self._query = self._build_query()

        self.refresh_filters()

    def _get_when_search_combo(self):
        when_search = ComboBox()
        when_search.append_item(self._ACTION_ANYTIME, _('Anytime'))
        when_search.append_separator()
        when_search.append_item(self._ACTION_TODAY, _('Today'))
        when_search.append_item(self._ACTION_SINCE_YESTERDAY,
                                      _('Since yesterday'))
        # TRANS: Filter entries modified during the last 7 days.
        when_search.append_item(self._ACTION_PAST_WEEK, _('Past week'))
        # TRANS: Filter entries modified during the last 30 days.
        when_search.append_item(self._ACTION_PAST_MONTH, _('Past month'))
        # TRANS: Filter entries modified during the last 356 days.
        when_search.append_item(self._ACTION_PAST_YEAR, _('Past year'))
        when_search.set_active(0)
        when_search.connect('changed', self._combo_changed_cb)
        return when_search

    def _get_with_search_combo(self):
        with_search = ComboBox()
        with_search.append_item(self._ACTION_EVERYBODY, _('Anyone'))
        with_search.append_separator()
        with_search.append_item(self._ACTION_MY_FRIENDS, _('My friends'))
        with_search.append_item(self._ACTION_MY_CLASS, _('My class'))
        with_search.append_separator()

        # TODO: Ask the model for buddies.
        with_search.append_item(3, 'Dan', 'theme:xo') #, XoColor('#6afbf4,#fc5f68'))

        with_search.set_active(0)
        with_search.connect('changed', self._combo_changed_cb)
        return with_search

    def _add_widget(self, widget, expand=False):
        tool_item = gtk.ToolItem()
        tool_item.set_expand(expand)

        tool_item.add(widget)
        widget.show()

        self.insert(tool_item, -1)
        tool_item.show()

    def _build_query(self):
        query = {}
        if self._volume_id:
            query['mountpoints'] = [self._volume_id]
        if self._what_search_combo.props.value:
            value = self._what_search_combo.props.value
            generic_type = mime.get_generic_type(value)
            if generic_type:
                mime_types = generic_type.mime_types
                query['mime_type'] = mime_types
            else:
                query['activity'] = self._what_search_combo.props.value
        if self._when_search_combo.props.value:
            date_from, date_to = self._get_date_range()
            query['mtime'] = {'start': date_from, 'end': date_to}
        if self._search_entry.props.text:
            text = self._search_entry.props.text.strip()

            if not text.startswith('"'):
                query_text = ''
                words = text.split(' ')
                for word in words:
                    query_text += word.strip() + '* '
            else:
                query_text = text

            query['query'] = query_text

        return query

    def _get_date_range(self):
        today_start = datetime.today().replace(hour=0, minute=0, second=0)
        right_now = datetime.today()
        if self._when_search_combo.props.value == self._ACTION_TODAY:
            date_range = (today_start, right_now)
        elif self._when_search_combo.props.value == self._ACTION_SINCE_YESTERDAY:
            date_range = (today_start - timedelta(1), right_now)
        elif self._when_search_combo.props.value == self._ACTION_PAST_WEEK:
            date_range = (today_start - timedelta(7), right_now)
        elif self._when_search_combo.props.value == self._ACTION_PAST_MONTH:
            date_range = (today_start - timedelta(30), right_now)
        elif self._when_search_combo.props.value == self._ACTION_PAST_YEAR:
            date_range = (today_start - timedelta(356), right_now)
        
        return (date_range[0].isoformat(),
                date_range[1].isoformat())

    def _combo_changed_cb(self, combo):
        new_query = self._build_query()
        if self._query != new_query:
            self._query = new_query
            self.emit('query-changed', self._query)

    def _search_entry_activated_cb(self, search_entry):
        if self._autosearch_timer:
            gobject.source_remove(self._autosearch_timer)
        new_query = self._build_query()
        if self._query != new_query:
            self._query = new_query
            self.emit('query-changed', self._query)

    def _search_entry_changed_cb(self, search_entry):
        if not search_entry.props.text:
            search_entry.activate()
            return

        if self._autosearch_timer:
            gobject.source_remove(self._autosearch_timer)
        self._autosearch_timer = gobject.timeout_add(_AUTOSEARCH_TIMEOUT,
                                                     self._autosearch_timer_cb)

    def _autosearch_timer_cb(self):
        logging.debug('_autosearch_timer_cb')
        self._autosearch_timer = None
        self._search_entry.activate()
        return False

    def set_volume_id(self, volume_id):
        self._volume_id = volume_id
        new_query = self._build_query()
        if self._query != new_query:
            self._query = new_query
            self.emit('query-changed', self._query)

    def refresh_filters(self):
        current_value = self._what_search_combo.props.value
        current_value_index = 0

        self._what_search_combo.handler_block(self._what_combo_changed_sid)
        try:
            self._what_search_combo.remove_all()
            # TRANS: Item in a combo box that filters by entry type.
            self._what_search_combo.append_item(self._ACTION_ANYTHING, _('Anng'))

            appended_separator = False
            for service_name in datastore.get_unique_values('activity'):
                activity_info = activity.get_registry().get_activity(service_name)
                if not activity_info is None:
                    if not appended_separator:
                        self._what_search_combo.append_separator()            
                        appended_separator = True

                    if os.path.exists(activity_info.icon):
                        self._what_search_combo.append_item(service_name,
                                                            activity_info.name,
                                                            file_name=activity_info.icon)
                    else:
                        self._what_search_combo.append_item(service_name,
                                                            activity_info.name,
                                                            icon_name='application-octet-stream')

                    if service_name == current_value:
                        current_value_index = len(self._what_search_combo.get_model()) - 1

            self._what_search_combo.append_separator()

            types = mime.get_all_generic_types()
            for generic_type in types :
                self._what_search_combo.append_item(
                    generic_type.type_id, generic_type.name, generic_type.icon)
                if generic_type.type_id == current_value:
                    current_value_index = len(self._what_search_combo.get_model()) - 1

                self._what_search_combo.set_active(current_value_index)
        finally:
            self._what_search_combo.handler_unblock(self._what_combo_changed_sid)

class ManageToolbar(gtk.Toolbar):
    __gtype_name__ = 'ManageToolbar'

    def __init__(self):
        gtk.Toolbar.__init__(self)

class BackupToolbar(gtk.Toolbar):
    __gtype_name__ = 'BackupToolbar'

    def __init__(self):
        gtk.Toolbar.__init__(self)

        self._backup = ToolButton('document-save')
        self._backup.set_tooltip(_('Backup'))
        self._backup.connect('clicked', self._backup_clicked_cb)
        self.insert(self._backup, -1)
        self._backup.show()

    def _backup_clicked_cb(self, button):
        backup.backup_gui()

class DetailToolbox(Toolbox):
    def __init__(self):
        Toolbox.__init__(self)

        self.entry_toolbar = EntryToolbar()
        self.add_toolbar('', self.entry_toolbar)
        self.entry_toolbar.show()

class EntryToolbar(gtk.Toolbar):
    __gtype_name__ = 'EntryToolbar'

    __gsignals__ = {
        'go-back-clicked': (gobject.SIGNAL_RUN_FIRST,
                            gobject.TYPE_NONE,
                            ([])),
        'entry-erased'   : (gobject.SIGNAL_RUN_FIRST,
                            gobject.TYPE_NONE,
                            ([]))
    }

    def __init__(self):
        gtk.Toolbar.__init__(self)

        go_back_button = ToolButton('go-previous')
        go_back_button.set_tooltip(_('Gock'))
        go_back_button.connect('clicked', self._go_back_button_clicked_cb)
        self.add(go_back_button)
        go_back_button.show()

        separator = gtk.SeparatorToolItem()
        separator.set_expand(True)
        separator.props.draw = False
        self.add(separator)
        separator.show()

        erase_button = ToolButton('erase')
        erase_button.set_tooltip(_('Erase'))
        erase_button.connect('clicked', self._erase_button_clicked_cb)
        self.add(erase_button)
        erase_button.show()

        separator = gtk.SeparatorToolItem()
        self.add(separator)
        separator.show()

        self._copy = ToolButton()

        icon = Icon(icon_name='edit-copy', xo_color=profile.get_color())
        self._copy.set_icon_widget(icon)
        icon.show()

        self._copy.set_tooltip(_('Copy to clipboard'))
        self._copy.connect('clicked', self._copy_clicked_cb)
        self.add(self._copy)
        self._copy.show()

        separator = gtk.SeparatorToolItem()
        self.add(separator)
        separator.show()

        self._resume = ToolButton('activity-start')
        self._resume.connect('clicked', self._resume_clicked_cb)
        self.add(self._resume)
        self._resume.show()

    def set_jobject(self, jobject):
        self._jobject = jobject
        self._refresh_copy_palette()
        self._refresh_resume_palette()

    def _resume_clicked_cb(self, button):
        if self._jobject:
            self._jobject.resume()

    def _copy_clicked_cb(self, button):
        clipboard = gtk.Clipboard()
        clipboard.set_with_data([('text/uri-list', 0, 0)],
                                self._clipboard_get_func_cb,
                                self._clipboard_clear_func_cb)

    def _clipboard_get_func_cb(self, clipboard, selection_data, info, data):
        selection_data.set('text/uri-list', 8, self._jobject.file_path)

    def _clipboard_clear_func_cb(self, clipboard, data):
        pass

    def _erase_button_clicked_cb(self, button):
        if self._jobject:
            bundle = misc.get_bundle(self._jobject)
            if bundle is not None and bundle.is_installed():
                bundle.uninstall()
            datastore.delete(self._jobject.object_id)
            self.emit('entry-erased')

    def _go_back_button_clicked_cb(self, back_bar):
        self.emit('go-back-clicked')
        return False

    def _resume_menu_item_activate_cb(self, menu_item, service_name):
        
        logging.debug("Resuming from menu....")
        if self._jobject:
            if not service_name:
                self._jobject.resume()
            else:
                self._jobject.resume(service_name)

    def _copy_menu_item_activate_cb(self, menu_item, volume):
        if self._jobject:
            datastore.copy(self._jobject, volume.id)

    def _refresh_copy_palette(self):
        palette = self._copy.get_palette()
        
        for menu_item in palette.menu.get_children():
            palette.menu.remove(menu_item)
            menu_item.destroy()

        volumes_manager = volumesmanager.get_volumes_manager()
        for volume in volumes_manager.get_volumes():
            if self._jobject.metadata['mountpoint'] == volume.id:
                continue
            menu_item = MenuItem(volume.name)
            menu_item.set_image(Icon(icon_name=volume.icon_name,
                                     icon_size=gtk.ICON_SIZE_MENU))
            menu_item.connect('activate',
                              self._copy_menu_item_activate_cb,
                              volume)
            palette.menu.append(menu_item)
            menu_item.show()
        
    def _refresh_resume_palette(self):
        logging.debug("Refreshing resume palette....")
        if self._jobject.metadata.get('activity_id', ''):
            # TRANS: Action label for resuming an activity.
            self._resume.set_tooltip(_('Resume'))
        else:
            # TRANS: Action label for starting an entry.
            self._resume.set_tooltip(_('Start'))

        palette = self._resume.get_palette()

        for menu_item in palette.menu.get_children():
            palette.menu.remove(menu_item)
            menu_item.destroy()
            
        activities = self._jobject.get_activities()
        logging.debug("Refreshing resume palette with "+str(activities))
        for activity in activities:
            logging.debug("Refreshing resume palette with"+activity.name)
            menu_item = MenuItem(activity.name)
            menu_item.set_image(Icon(file=activity.icon, icon_size=gtk.ICON_SIZE_MENU))
            menu_item.connect('activate', self._resume_menu_item_activate_cb,
                              activity.bundle_id)
            palette.menu.append(menu_item)
            menu_item.show()
