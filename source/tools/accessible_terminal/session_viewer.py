import wx
from tools.accessible_terminal.session_manager import SessionManager
from tools.accessible_terminal.accessible_terminal import AccessibleTerminal
from tools.accessible_terminal.file_manager import FileManager
from speech import speak


class ConnectionDialog(wx.Dialog):
    def __init__(self, parent, edit_mode=False):
        super(ConnectionDialog, self).__init__(parent, title="SSH Connection Details", size=(350, 300))
        self.edit_mode = edit_mode
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        name_label = wx.StaticText(panel, label="Session Name:")
        vbox.Add(name_label, 0, wx.ALL | wx.ALIGN_LEFT, 5)
        self.name_text = wx.TextCtrl(panel)
        vbox.Add(self.name_text, 0, wx.ALL | wx.EXPAND, 5)

        host_label = wx.StaticText(panel, label="Server Host:")
        vbox.Add(host_label, 0, wx.ALL | wx.ALIGN_LEFT, 5)
        self.host_text = wx.TextCtrl(panel)
        vbox.Add(self.host_text, 0, wx.ALL | wx.EXPAND, 5)

        port_label = wx.StaticText(panel, label="Server Port:")
        vbox.Add(port_label, 0, wx.ALL | wx.ALIGN_LEFT, 5)
        self.port_text = wx.TextCtrl(panel, value="22")
        vbox.Add(self.port_text, 0, wx.ALL | wx.EXPAND, 5)

        username_label = wx.StaticText(panel, label="Username:")
        vbox.Add(username_label, 0, wx.ALL | wx.ALIGN_LEFT, 5)
        self.username_text = wx.TextCtrl(panel)
        vbox.Add(self.username_text, 0, wx.ALL | wx.EXPAND, 5)

        password_label = wx.StaticText(panel, label="Password:")
        vbox.Add(password_label, 0, wx.ALL | wx.ALIGN_LEFT, 5)
        self.password_text = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
        vbox.Add(self.password_text, 0, wx.ALL | wx.EXPAND, 5)

        self.save_password_checkbox = wx.CheckBox(panel, label="Save Password")
        vbox.Add(self.save_password_checkbox, 0, wx.ALL | wx.ALIGN_LEFT, 5)
        
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        ok_button = wx.Button(panel, id=wx.ID_OK, label="Save")
        cancel_button = wx.Button(panel, id=wx.ID_CANCEL, label="Cancel")
        hbox.Add(ok_button, 0, wx.ALL, 5)
        hbox.Add(cancel_button, 0, wx.ALL, 5)
        vbox.Add(hbox, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        panel.SetSizer(vbox)
        self.Centre()


class PasswordPromptDialog(wx.Dialog):
    def __init__(self, parent, session_name):
        super().__init__(parent, title=f"Enter Password for {session_name}", size=(300, 150))
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        password_label = wx.StaticText(panel, label="Password:")
        vbox.Add(password_label, 0, wx.ALL | wx.ALIGN_LEFT, 5)
        self.password_text = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
        vbox.Add(self.password_text, 0, wx.ALL | wx.EXPAND, 5)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        ok_button = wx.Button(panel, id=wx.ID_OK, label="OK")
        cancel_button = wx.Button(panel, id=wx.ID_CANCEL, label="Cancel")
        hbox.Add(ok_button, 0, wx.ALL, 5)
        hbox.Add(cancel_button, 0, wx.ALL, 5)
        vbox.Add(hbox, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        panel.SetSizer(vbox)
        self.Centre()

class SessionViewer(wx.Frame):
    def __init__(self, parent, app_name):
        super(SessionViewer, self).__init__(parent, title="Accessible SSH Terminal", size=(400, 300))
        self.app_name=app_name
        self.session_manager = SessionManager(self.app_name)
        self.sessions = self.session_manager.load_sessions()

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        sessions_label = wx.StaticText(panel, label="Saved Sessions:")
        vbox.Add(sessions_label, 0, wx.ALL | wx.ALIGN_LEFT, 5)

        self.sessions_listbox = wx.ListBox(panel)
        for name, _, _, _, _ in self.sessions:
            self.sessions_listbox.Append(name)
        vbox.Add(self.sessions_listbox, 1, wx.ALL | wx.EXPAND, 5)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        connect_button = wx.Button(panel, label="Connect")
        connect_button.Bind(wx.EVT_BUTTON, self.on_connect)
        hbox.Add(connect_button, 0, wx.ALL, 5)

        add_button = wx.Button(panel, label="Add Session")
        add_button.Bind(wx.EVT_BUTTON, self.on_add_session)
        hbox.Add(add_button, 0, wx.ALL, 5)

        remove_button = wx.Button(panel, label="Remove")
        remove_button.Bind(wx.EVT_BUTTON, self.on_remove_session)
        hbox.Add(remove_button, 0, wx.ALL, 5)

        vbox.Add(hbox, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        panel.SetSizer(vbox)
        self.Centre()
        self.sessions_listbox.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)


    def on_context_menu(self, event):
        menu = wx.Menu()
        file_manager_item = menu.Append(wx.ID_ANY, "File Manager")
        self.Bind(wx.EVT_MENU, self.on_file_manager, file_manager_item)
        self.PopupMenu(menu, event.GetPosition())

    def on_file_manager(self, event):
        selected_index = self.sessions_listbox.GetSelection()
        if selected_index != wx.NOT_FOUND:
            session_name, host, port, username, password = self.sessions[selected_index]
            if not password:
               password_dialog = PasswordPromptDialog(self, session_name)
               if password_dialog.ShowModal() == wx.ID_OK:
                   password = password_dialog.password_text.GetValue()
               else:
                   return
               password_dialog.Destroy()
            file_manager = FileManager(self, host, port, username, password, session_name)
            self.GetParent().add_child_frame(file_manager)
            self.Hide()
        else:
            wx.MessageBox("Please select a session to open the file manager.", "Error", wx.OK | wx.ICON_ERROR)

    def on_connect(self, event):
        selected_index = self.sessions_listbox.GetSelection()
        if selected_index != wx.NOT_FOUND:
            session_name, host, port, username, password = self.sessions[selected_index]
            if not password:
               password_dialog = PasswordPromptDialog(self, session_name)
               if password_dialog.ShowModal() == wx.ID_OK:
                   password = password_dialog.password_text.GetValue()
               else:
                   return
               password_dialog.Destroy()
            ssh_terminal = AccessibleTerminal(self, host, port, username, password, session_name)
            self.GetParent().add_child_frame(ssh_terminal)
        else:
            wx.MessageBox("Please select a session to connect to.", "Error", wx.OK | wx.ICON_ERROR)

    def on_add_session(self, event):
        connection_dialog = ConnectionDialog(self, edit_mode=False)
        if connection_dialog.ShowModal() == wx.ID_OK:
           session_name = connection_dialog.name_text.GetValue()
           server_host = connection_dialog.host_text.GetValue()
           server_port = int(connection_dialog.port_text.GetValue())
           username = connection_dialog.username_text.GetValue()
           password = connection_dialog.password_text.GetValue()
           save_password = connection_dialog.save_password_checkbox.GetValue()

           self.session_manager.save_session(session_name, server_host, server_port, username, password, save_password)
           self.sessions_listbox.Append(session_name)
           self.sessions = self.session_manager.load_sessions()
           speak(f"Session {session_name} Saved")
        connection_dialog.Destroy()

    def on_remove_session(self, event):
        selected_index = self.sessions_listbox.GetSelection()
        if selected_index != wx.NOT_FOUND:
            session_name, _, _, _, _= self.sessions[selected_index]
            dlg = wx.MessageDialog(self, f"Are you sure you want to remove session '{session_name}'?", "Confirm Removal", wx.YES_NO | wx.ICON_QUESTION)
            result = dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_YES:
                self.session_manager.remove_session(session_name)
                self.sessions_listbox.Delete(selected_index) # Delete the item
                del self.sessions[selected_index]
                speak(f"Session {session_name} removed.")
        else:
            wx.MessageBox("Please select a session to remove.", "Error", wx.OK | wx.ICON_ERROR)