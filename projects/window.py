# -*- coding:utf-8 -*-

#  Copyright © 2012-2014  B. Clausius <barcc@gmx.de>
#  Copyright © 2014  alex bodnaru <alexbodn@012.net.il>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function, division

import os, sys
from collections import defaultdict

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import PeasGtk
from gi.repository import Gedit

from projects.idle import IdleHelper, Priority
from projects import settings
from projects import appdata

UI_DIR = os.path.dirname(__file__)


if hasattr(Gedit.MessageBus, 'send'):
    def send_message(window, object_path, method, **kwargs):
        window.get_message_bus().send(object_path, method, **kwargs)
else:
    # For installations that do not have the Gedit.py override file
    def send_message(window, object_path, method, **kwargs):
        bus = window.get_message_bus()
        tp = bus.lookup(object_path, method)
        if not tp.is_a(Gedit.Message.__gtype__):
            return None
        kwargs['object-path'] = object_path
        kwargs['method'] = method
        msg = GObject.new(tp, **kwargs)
        bus.send_message(msg)
        

class PanelHelper(GObject.GObject, IdleHelper):
    __gsignals__ = {
        'open-file': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'open-file-test': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'add-directory': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'open-project': (GObject.SignalFlags.RUN_FIRST, None, (str, bool)),
        'move-to-new-window': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }
    
    def __init__ (self, app_data, builder, uimanager):
        GObject.GObject.__init__ (self)
        IdleHelper.__init__(self)
        self.app_data = app_data
        
        builder.get_object('action_open_project').connect('activate', self.on_action_open_project)
        builder.get_object('action_open_project_newwindow').connect('activate',
                            self.on_action_open_project_newwindow)
        builder.get_object('action_close_project').connect('activate', self.on_action_close_project)
        builder.get_object('action_open_directory').connect('activate', self.on_action_open_directory)
        builder.get_object('action_open_file').connect('activate', self.on_action_open_file)
        builder.get_object('action_add_parent').connect('activate', self.on_action_add_parent)
        builder.get_object('action_add_directory').connect('activate', self.on_action_add_directory)
        builder.get_object('action_remove').connect('activate', self.on_action_remove)
        builder.get_object('action_remove_all').connect('activate', self.on_action_remove_all)
        builder.get_object('action_find').connect('activate', self.on_action_find)
        
        builder.get_object('treeview_open_projects').connect('popup-menu',
                            self.on_treeview_projects_popup_menu)
        builder.get_object('treeview_projects').connect('popup-menu',
                            self.on_treeview_projects_popup_menu)
        
        self.widget = builder.get_object('widget_projects')
        self.treeview_open = builder.get_object('treeview_open_projects')
        self.treeview_open.connect('button_press_event', self.on_treeview_projects_button_press_event)
        self.treeview_open.connect('row-activated', self.on_treeview_projects_row_activated)
        self.treeview = builder.get_object('treeview_projects')
        self.treeview.connect('button_press_event', self.on_treeview_projects_button_press_event)
        self.treeview.connect('row-activated', self.on_treeview_projects_row_activated)
        self.actiongroup_widget = builder.get_object('ProjectsPluginWidgetActions')
        self.actiongroup_active = builder.get_object('ProjectsPluginActiveActions')
        self.actiongroup_test = builder.get_object('ProjectsPluginTestActions')
        
        self.uimanager = uimanager
        self.uimanager.insert_action_group(self.actiongroup_widget, 0)
        self.uimanager.insert_action_group(self.actiongroup_active, 1)
        self.uimanager.insert_action_group(self.actiongroup_test, 2)
        menu_file = os.path.join(UI_DIR, 'menu.ui')
        self.merge_id = self.uimanager.add_ui_from_file(menu_file)
        self.menuitem_default_merge_id = self.uimanager.new_merge_id()
        self.menu_project = self.uimanager.get_widget('/projects_panel_popup')
        self.menu_project.attach_to_widget(self.treeview, None)
        
        self.treeview_open.set_model(self.app_data.sort_model_open)
        self.treeview.set_model(self.app_data.sort_model)
        
    def get_action_info(self):
        action_info = []
        for menuitem in self.menu_project.get_children():
            action = menuitem.get_related_action()
            if menuitem.get_name() != 'menuitem_default' and action is not None:
                action_info.append((action.props.name, action.props.stock_id, action.props.short_label))
        return action_info
        
    def set_default_menuitem(self):
        action_name = self.app_data.settings.default_project_action
        default_action = self.actiongroup_widget.get_action(action_name)
        self.uimanager.remove_ui(self.menuitem_default_merge_id)
        if default_action is not None:
            self.uimanager.add_ui(self.menuitem_default_merge_id,
                                '/projects_panel_popup/placeholder_default',
                                'menuitem_default', action_name,
                                Gtk.UIManagerItemType.MENUITEM, True)
        for menuitem in self.menu_project.get_children():
            action = menuitem.get_related_action()
            if menuitem.get_name() != 'menuitem_default' and action is not None:
                menuitem.props.visible = action != default_action
                
    def deactivate(self):
        IdleHelper.deactivate(self)
        self.uimanager.remove_ui(self.menuitem_default_merge_id)
        self.uimanager.remove_ui(self.merge_id)
        self.uimanager.remove_action_group(self.actiongroup_widget)
        self.uimanager.remove_action_group(self.actiongroup_active)
        self.uimanager.remove_action_group(self.actiongroup_test)
        
        self.menu_project = None
        self.treeview_open = None
        self.treeview = None
        # this line produces the following error:
        #(gedit:32055): GLib-GObject-WARNING **: instance with invalid (NULL) class pointer
        #(gedit:32055): GLib-GObject-CRITICAL **: g_signal_handlers_disconnect_matched: assertion 'G_TYPE_CHECK_INSTANCE (instance)' failed
        #(gedit:32055): GLib-GObject-CRITICAL **: g_object_steal_data: assertion 'G_IS_OBJECT (object)' failed
        #(gedit:32055): GLib-GObject-CRITICAL **: g_object_set_data: assertion 'G_IS_OBJECT (object)' failed
        #self.widget = None
        self.app_data = None
        
    def set_active_project(self, path):
        tpath = self.app_data.set_project_active(path)
        if tpath:
            tpath = self.app_data.sort_model.convert_child_path_to_path(tpath)
            self.treeview.expand_to_path(tpath)
        
    def on_treeview_projects_button_press_event(self, treeview, event):
        if event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS:
            def popup():
                self.set_default_menuitem()
                self.menu_project.detach()
                self.menu_project.attach_to_widget(treeview, None)
                self.menu_project.popup(None, None, None, None, event.button, event.time)
            # this prevents the warning: g_object_ref: assertion `G_IS_OBJECT (object)' failed
            self.idle_add(popup)
        return False
        
    def on_treeview_projects_popup_menu(self, treeview):
        #TODO: Open the popup at the position of the row
        #def menu_position_func(menu, unused_data):
        #    tpath, column = self.treeview.get_cursor()
        #    # How do i get the position at tpath?
        #    return x, y, True
        self.set_default_menuitem()
        self.menu_project.detach()
        self.menu_project.attach_to_widget(treeview, None)
        self.menu_project.popup(None, None, None, None, 0, Gtk.get_current_event_time())
        return True
        
    def on_treeview_projects_row_activated(self, treeview, treepath, unused_column):
        action_name = self.app_data.settings.default_project_action
        default_action = self.actiongroup_widget.get_action(action_name)
        default_action.activate()
            
    def _get_projectpath(self):
        treeview = self.menu_project.get_attach_widget()
        tpath, unused_column = treeview.get_cursor()
        return tpath and treeview.get_model()[tpath][1]
        
    @staticmethod
    def _show_folder(projectpath):
        '''launch the default application to show the projectpath'''
        Gtk.show_uri(None, projectpath, Gdk.CURRENT_TIME)
        
    def on_action_open_project(self, action):
        projectpath = self._get_projectpath()
        if projectpath:
            self.emit('open-project', projectpath, False)
            
    def on_action_open_project_newwindow(self, action):
        projectpath = self._get_projectpath()
        if projectpath:
            self.emit('open-project', projectpath, True)
            
    def on_action_close_project(self, action):
        projectpath = self._get_projectpath()
        if projectpath:
            # close project files in _any_ window
            self.app_data.emit('close-project', projectpath)
            
    def on_action_open_directory(self, action):
        projectpath = self._get_projectpath()
        if projectpath:
            self._show_folder(projectpath)
            
    def on_action_open_file(self, action):
        projectpath = self._get_projectpath()
        if hasattr(action, 'test_directory'):
            # only for testing to avoid dialog
            self.emit('open-file-test', action.test_directory)
            del action.test_directory
        else:
            self.emit('open-file', projectpath)
            
    def on_action_add_parent(self, action):
        projectpath = self._get_projectpath()
        if projectpath:
            location = Gio.File.new_for_uri(projectpath).get_parent()
            if location is not None:
                self.app_data.add_project(location.get_uri())
            
    def on_action_add_directory(self, action):
        projectpath = self._get_projectpath()
        if hasattr(action, 'test_directory'):
            # only for testing to avoid dialog
            self.app_data.add_project(action.test_directory)
            del action.test_directory
        else:
            self.emit('add-directory', projectpath or '')
            
    def on_action_remove(self, action):
        projectpath = self._get_projectpath()
        if projectpath:
            self.app_data.remove_project(projectpath)
            
    def on_action_remove_all(self, action):
        self.app_data.remove_all_projects()
        
    def on_action_find(self, action):
        projectpath = self._get_projectpath()
        if projectpath:
            self.app_data.do_scan_projects(projectpath)
            
        
class ProjectsWindow(GObject.Object, Gedit.WindowActivatable, PeasGtk.Configurable, IdleHelper):
    __gtype_name__ = "ProjectsWindow"
    window = GObject.property(type=Gedit.Window)
    app_data = None
    
    def __init__(self):
        GObject.Object.__init__(self)
        IdleHelper.__init__(self)
        self.panel_helper = None
        self.handlers = []
        self.uimanager = None
        self.recent_merge_id = None
        self.actiongroup_recent = None
        self.tab_data = defaultdict(lambda: (None, None))  # key: tab, value: (projectpath, filepath)
        
    def do_activate(self):
        if self.app_data is None:
            try:
                self.__class__.app_data = appdata.ApplicationData()
            except settings.GSettingsSchemaNotFound:
                dialog = Gtk.MessageDialog(self.window,
                                     Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                     Gtk.MessageType.ERROR,
                                     Gtk.ButtonsType.CLOSE)
                dialog.props.text = 'GSettings schema for the Projects Plugin is not installed.'
                dialog.props.secondary_text = (
                        "If you've installed the plugin manually (and this is most likely"
                        " the case if you see this message), you should read the file"
                        " README.install file included with this plugin on how to install"
                        " the schema. After that you have to restart gedit.")
                dialog.run()
                dialog.destroy()
                return
        
        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(UI_DIR, 'projects.ui'))
        self.uimanager = self.window.get_ui_manager()
        self.panel_helper = PanelHelper(self.app_data, builder, self.uimanager)
        self.app_data.settings.action_info = self.panel_helper.get_action_info()
        
        icon = Gtk.Image.new_from_icon_name('applications-development', Gtk.IconSize.MENU)
        panel = self.window.get_side_panel()
        panel.add_item(self.panel_helper.widget, "ProjectsSidePanel", "Projects", icon)
        
        self._connect('tab-added', self.on_window_tab_added)
        self._connect('active-tab-changed', self.on_window_tab_changed)
        self._connect('tab-removed', self.on_window_tab_removed)
        self._connect("delete-event", self.on_window_delete_event)
        # or focus-in-event?
        self._connect("notify::is-active", self.on_window_notify_is_active)
        self.app_data.settings.settings.connect('changed::max-recents', self.on_settings_changed_max_recents)
        
        for action_name, func in [
                    ('action_move_to_new_window', self.on_action_move_to_new_window),
                    ('action_open_directory_from_active', self.on_action_open_directory_from_active),
                    ('action_close_active_project', self.on_action_close_active_project),
                ]:
            builder.get_object(action_name).connect('activate', func)
            
        self.recent_merge_id = self.uimanager.new_merge_id()
        self.actiongroup_recent = Gtk.ActionGroup('actiongroup_recent_projects')
        self.uimanager.insert_action_group(self.actiongroup_recent)
        for i in range(self.app_data.settings.max_recents_range[1]):
            action_name = 'action_recent_%d' % i
            action = Gtk.Action(action_name, None, None, None)
            action.connect('activate', self.on_action_recent_project)
            self.actiongroup_recent.add_action(action)
            self.uimanager.add_ui(self.recent_merge_id,
                                '/MenuBar/ExtraMenu_1/ProjectsPluginMenu/project_recent',
                                'project_recent_%d' % i,
                                action_name,
                                Gtk.UIManagerItemType.AUTO, False)
        self.app_data.connect('close-project', self.on_app_data_close_project)
        self.panel_helper.connect('open-file', self.on_panel_open_file)
        self.panel_helper.connect('open-file-test', self.on_panel_open_file_test)
        self.panel_helper.connect('open-project', self.on_panel_open_project)
        self.panel_helper.connect('add-directory', self.on_panel_add_directory)
        self.panel_helper.connect('move-to-new-window', self.on_panel_move_to_new_window)
        self.app_data.connect('reassign-project', self.on_app_data_reassign_project)
        
        self._update_recent_menu()
        
        # this is necessary if activated via plugin manager
        for doc in self.window.get_documents():
            tab = Gedit.Tab.get_from_document(doc)
            doc.connect('notify::location', self.on_document_notify_location)
            self._init_new_tab(tab, doc)
        tab = self.window.get_active_tab()
        if tab:
            self._init_active_tab(tab)
        
    def do_deactivate(self):
        IdleHelper.deactivate(self)
        self._disconnect_all()
        if self.app_data is None:
            return
        
        self.uimanager.remove_ui(self.recent_merge_id)
        self.uimanager.remove_action_group(self.actiongroup_recent)
        self.actiongroup_recent = None
        panel = self.window.get_side_panel()
        panel.remove_item(self.panel_helper.widget)
        self.panel_helper.deactivate()
        self.panel_helper = None
        
        if len(Gedit.App.get_default().get_windows()) <= 1:
            self.app_data.deactivate()
            self.__class__.app_data = None
        
    #def do_update_state(self):
    #    pass
        
    def do_create_configure_widget(self):
        return self.app_data.settings.create_widget(self.window)
        
    def _connect(self, signal, func):
        self.handlers.append(self.window.connect(signal, func))
    def _disconnect_all(self):
        for handler in self.handlers:
            self.window.disconnect(handler)
        self.handlers = []
        
    def _update_recent_menu(self):
        max_recents = self.app_data.settings.max_recents
        recent_projects = self.app_data.settings.recent_projects
        for action in self.actiongroup_recent.list_actions():
            i = int(action.props.name.rsplit('_', 1)[1])
            if i >= max_recents:
                action.props.visible = False
                continue
            try:
                projectpath = recent_projects[i]
                location = Gio.File.new_for_uri(projectpath)
            except IndexError:
                projectpath = location = None
            if location:
                action.props.label = Gedit.utils_replace_home_dir_with_tilde(location.get_parse_name())
            action.props.visible = bool(location)
            
    def _init_new_tab(self, tab, doc):
        location = doc and doc.get_location()
        filepath = location and location.get_uri()
        if filepath is not None:
            try:
                projectpath = self.app_data.add_filename(filepath)
            except appdata.NotReady:
                self.tab_data[tab] = (False, None)
                self.idle_add(self._init_new_tab, tab, doc, priority=Priority.new_tab)
            else:
                self.tab_data[tab] = (projectpath, filepath)
                recent_projects = self.app_data.settings.recent_projects
                if projectpath:
                    if projectpath in recent_projects:
                        recent_projects.remove(projectpath)
                    recent_projects.insert(0, projectpath)
                    max_recents_max = self.app_data.settings.max_recents_range[1]
                    del recent_projects[max_recents_max:]
                    if recent_projects != self.app_data.settings.recent_projects:
                        self.app_data.settings.recent_projects = recent_projects
                self._update_recent_menu()
                
    def on_window_tab_added(self, unused_window, tab):
        doc = tab.get_document()
        doc.connect('notify::location', self.on_document_notify_location)
        self._init_new_tab(tab, doc)
        
    def _init_active_tab(self, tab):
        projectpath = self.tab_data[tab][0]
        if projectpath is None:
            # file not part of a project
            self.panel_helper.set_active_project(None)
        elif not projectpath:
            # not ready
            self.idle_add(self._init_active_tab, tab, priority=Priority.active_tab)
        else:
            doc = tab.get_document()
            location = doc and doc.get_location()
            filename = location and location.get_uri()
            self.app_data.settings.get_project(projectpath).active_file = filename
            self.app_data.settings.projects_modified()
            self.panel_helper.set_active_project(projectpath)
            
    def on_window_tab_changed(self, unused_window, tab):
        self._init_active_tab(tab)
        
    def _remove_if_unused(self, projectpath, filepath=None):
        app = Gedit.App.get_default()
        cnt_files = 0
        cnt_projects = 0
        for doc in app.get_documents():
            loc = doc.get_location()
            if loc and loc.get_uri() == filepath:
                cnt_files += 1
            tab = Gedit.Tab.get_from_document(doc)
            if self.tab_data[tab][0] == projectpath:
                cnt_projects += 1
        if filepath is not None and not cnt_files:
            self.app_data.remove_filename(projectpath, filepath)
        if not cnt_projects:
            self.app_data.remove_from_open_projects(projectpath)
        
    def on_window_tab_removed(self, unused_window, tab):
        projectpath = self.tab_data[tab][0]
        del self.tab_data[tab]
        if not projectpath:
            return
        doc = tab.get_document()
        location = doc and doc.get_location()
        filepath = location and location.get_uri()
        if filepath is None:
            return
        self._remove_if_unused(projectpath, filepath)
        
    def on_window_delete_event(self, unused_window, unused_event):
        self._disconnect_all()
        app = Gedit.App.get_default()
        if len(app.get_windows()) <= 1:
            return
        for wdoc in self.window.get_documents():
            projectpath = self.tab_data[Gedit.Tab.get_from_document(wdoc)][0]
            if not projectpath:
                continue
            for window in app.get_windows():
                if window == self.window:
                    continue
                for doc in window.get_documents():
                    if self.tab_data[Gedit.Tab.get_from_document(doc)][0] == projectpath:
                        break
                else:
                    continue
                break
            else:
                self.app_data.remove_from_open_projects(projectpath)
                
    def on_window_notify_is_active(self, window, unused_paramspec):
        if window.props.is_active:
            tab = window.get_active_tab()
            if tab:
                self._init_active_tab(tab)
            
    def on_document_notify_location(self, doc, param):
        tab = Gedit.Tab.get_from_document(doc)
        #TODO: is the filepath thing really needed?
        projectpath, filepath = self.tab_data[tab]
        location = doc.get_location()
        filepath_new = location and location.get_uri()
        if filepath != filepath_new:
            try:
                projectpath_new = self.app_data.add_filename(filepath_new)
            except appdata.NotReady:
                self.tab_data[tab] = (False, None)
                self.idle_add(self.on_document_notify_location, doc, param, priority=Priority.new_tab)
            else:
                self.tab_data[tab] = (projectpath_new, filepath_new)
                if projectpath:
                    self._remove_if_unused(projectpath, filepath)
                if not projectpath_new:
                    pass
                elif self.window.get_active_tab() == tab:
                    self.app_data.settings.get_project(projectpath_new).active_file = filepath_new
                    self.app_data.settings.projects_modified()
                    self.panel_helper.set_active_project(projectpath_new)
                elif projectpath_new == projectpath:
                    project = self.app_data.settings.get_project(projectpath_new)
                    if project.active_file == filepath:
                        project.active_file = filepath_new
                        self.app_data.settings.projects_modified()
                        
    def _open_file(self, window, filename, jump_to):
        location = Gio.File.new_for_uri(filename)
        tab = window.get_tab_from_location(location)
        if tab is None:
            tab = window.create_tab_from_location(location, None, 0, 0, False, jump_to)
        elif jump_to:
            window.set_active_tab(tab)
        if jump_to:
            self.idle_add(tab.get_view().grab_focus)
        
    def on_action_move_to_new_window(self, action):
        tab = self.window.get_active_tab()
        projectpath = tab and self.tab_data[tab][0]
        if projectpath:
            self.panel_helper.emit('move-to-new-window', projectpath)
            
    def on_action_open_directory_from_active(self, action):
        tab = self.window.get_active_tab()
        projectpath = tab and self.tab_data[tab][0]
        if projectpath:
            self.panel_helper._show_folder(projectpath)
            
    def on_action_close_active_project(self, action):
        tab = self.window.get_active_tab()
        projectpath = tab and self.tab_data[tab][0]
        if projectpath:
            # close project files in _any_ window
            self.app_data.emit('close-project', projectpath)
            
    def on_action_recent_project(self, action):
        i = int(action.props.name.rsplit('_', 1)[1])
        projectpath = self.app_data.settings.recent_projects[i]
        if projectpath:
            self._open_project(projectpath, False)
            
    def on_panel_open_file(self, unused_panel, dirname):
        dialog = Gtk.FileChooserDialog("Open File",
                                      self.window,
                                      Gtk.FileChooserAction.OPEN,
                                      [Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                      Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT])
        dialog.set_local_only(False)
        if dirname:
            dialog.set_current_folder_uri(dirname)
        if dialog.run() == Gtk.ResponseType.ACCEPT:
            filename = dialog.get_uri()
            self._open_file(self.window, filename, jump_to=True)
        dialog.destroy()
        
    def on_panel_open_file_test(self, unused_panel, filename):
        self._open_file(self.window, filename, jump_to=True)
        
    def on_panel_add_directory(self, unused_panel, dirname):
        dialog = Gtk.FileChooserDialog("Add Folder",
                                      self.window,
                                      Gtk.FileChooserAction.SELECT_FOLDER,
                                      [Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                      Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT])
        dialog.set_local_only(False)
        if dirname:
            dialog.set_current_folder_uri(dirname)
        if dialog.run() == Gtk.ResponseType.ACCEPT:
            filename = dialog.get_uri()
            if filename:
                self.app_data.add_project(filename)
        dialog.destroy()
        
    def _open_project(self, projectpath, newwindow):
        try:
            project = self.app_data.settings.get_project(projectpath)
        except KeyError:
            #TODO: Remove the item that caused the exception
            # Happens if Projects-menuitem activated (GSettings) that is not
            # a known project (stored in file).
            # * config file was removed or replace with an older version
            # * Project was removed from side pane
            return
        self.app_data.settings.projects_modified()
        if newwindow:
            window = Gedit.App.get_default().create_window(None)
            window.show()
        else:
            window = self.window
        # project.files and project.active_file may be modified in on_window_tab_added inside the loop, so use a copy
        active_file = project.active_file
        for filename in project.files[:]:
            if not Gio.File.new_for_uri(filename).query_exists(None):
                project.files.remove(filename)
        if active_file and not Gio.File.new_for_uri(active_file).query_exists(None):
            project.active_file = active_file = None
        if project.files:
            if active_file not in project.files:
                project.active_file = active_file = project.files[-1] if project.files else None
        elif active_file:
            project.files.append(active_file)
        for filename in project.files[:]:
            if Gio.File.new_for_uri(filename).query_exists(None):
                self._open_file(window, filename, jump_to=(filename == active_file))
        if self.app_data.settings.filebrowser_set_root_on_project_open:
            location = Gio.File.new_for_uri(projectpath)
            try:
                send_message(window, '/plugins/filebrowser', 'set_root', location=location)
            except TypeError:
                pass
            
    def on_panel_open_project(self, unused_panel, projectpath, newwindow):
        self._open_project(projectpath, newwindow)
        
    def on_app_data_close_project(self, unused_app_data, projectpath):
        tabs = []
        for doc in self.window.get_documents():
            tab = Gedit.Tab.get_from_document(doc)
            if self.tab_data[tab][0] == projectpath:
                del self.tab_data[tab]
                tabs.append(tab)
        # Now that projectpath is removed from the tabs, the handlers
        # on_window_tab_removed and on_window_tab_changed will not modify
        # project metadata.
        self.app_data.remove_from_open_projects(projectpath)
        for tab in tabs:
            self.window.close_tab(tab)
            
    def on_panel_move_to_new_window(self, unused_panel, projectpath):
        # close project files in _any_ window
        self.app_data.emit('close-project', projectpath)
        self._open_project(projectpath, True)
        
    def on_app_data_reassign_project(self, unused_app_data, old_projectpath):
        for doc in self.window.get_documents():
            tab = Gedit.Tab.get_from_document(doc)
            if self.tab_data[tab][0] == old_projectpath:
                del self.tab_data[tab]
                self._remove_if_unused(old_projectpath)
                self._init_new_tab(tab, doc)
                
    def on_settings_changed_max_recents(self, unused_settings, unused_key):
        self._update_recent_menu()
        
        
def main(args):
    import appdata, settings, idle
    filenames = args or [__file__]
    filenames = ['file://'+os.path.abspath(f) for f in filenames]
    window = Gtk.Window()
    window.connect("destroy", Gtk.main_quit)
    window.set_title('Projects')
    window.resize(200, 400)
    settings.ProjectsLoadSaver.data_file += '.test'
    app_data = appdata.ApplicationData()
    panel = PanelHelper(app_data)
    panel.connect('open-file', lambda panel, filename: sys.stdout.write(filename+'\n'))
    window.add(panel.widget)
    window.show_all()
    def add_filename(filename):
        app_data.add_filename(filename)
    for f in filenames:
        GLib.idle_add(add_filename, f, priority=idle.Priority.new_tab)
        GLib.idle_add(panel.set_active_project, f, priority=idle.Priority.active_tab)
    Gtk.main()
    app_data.settings.deactivate()

if __name__ == '__main__':
    main(sys.argv[1:])
    
