import wx
from .session_manager import SessionManager
from .accessible_terminal import AccessibleTerminal
from .file_manager import FileManager
from speech import speak


class ConnectionDialog(wx.Dialog):
    def __init__(self, parent, title="SSH Connection Details", session_data=None):
        super(ConnectionDialog, self).__init__(parent, title=title, size=(400, 480))
        self.session_data = session_data
        self.edit_mode = session_data is not None
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
        self.password_text = wx.TextCtrl(panel)
        vbox.Add(self.password_text, 0, wx.ALL | wx.EXPAND, 5)

        self.save_password_checkbox = wx.CheckBox(panel, label="Save Password")
        vbox.Add(self.save_password_checkbox, 0, wx.ALL | wx.ALIGN_LEFT, 5)

        key_file_label = wx.StaticText(panel, label="Server key file:")
        vbox.Add(key_file_label, 0, wx.ALL | wx.ALIGN_LEFT, 5)

        key_file_hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.key_file_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        key_file_hbox.Add(self.key_file_text, 1, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
        browse_button = wx.Button(panel, label="Browse...")
        browse_button.Bind(wx.EVT_BUTTON, self.on_browse_key_file)
        key_file_hbox.Add(browse_button, 0, wx.ALIGN_CENTER_VERTICAL)
        vbox.Add(key_file_hbox, 0, wx.ALL | wx.EXPAND, 5)
        
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        ok_button = wx.Button(panel, id=wx.ID_OK, label="Save")
        cancel_button = wx.Button(panel, id=wx.ID_CANCEL, label="Cancel")
        hbox.Add(ok_button, 0, wx.ALL, 5)
        hbox.Add(cancel_button, 0, wx.ALL, 5)
        vbox.Add(hbox, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        panel.SetSizer(vbox)
        panel.Layout()
        # Then set the dialog size based on the panel's preferred size
        self.SetClientSize(panel.GetBestSize())
        self.Centre()

        if self.edit_mode and self.session_data:
            self._load_session_data(self.session_data)


    def _load_session_data(self, session_data):
        """Pre-fills the dialog controls with existing session data."""
        name, host, port, username, password, key_file_path = session_data
        self.name_text.SetValue(name)
        self.host_text.SetValue(host)
        self.port_text.SetValue(str(port))
        self.username_text.SetValue(username)
        self.password_text.SetValue(password)
        self.key_file_text.SetValue(key_file_path if key_file_path else "")
        # Check 'Save Password' if password was loaded
        self.save_password_checkbox.SetValue(bool(password))

    def on_browse_key_file(self, event):
        """Opens a file dialog to select an SSH key file."""
        dlg = wx.FileDialog(self, "Choose SSH Key File",
                           wildcard="SSH Key Files (*.pem;*.ppk;*id_rsa;*id_dsa)|*.pem;*.ppk;*id_rsa;*id_dsa|All files (*.*)|*.*",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.key_file_text.SetValue(dlg.GetPath())
        dlg.Destroy()


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

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        sessions_label = wx.StaticText(panel, label="Saved Sessions:")
        vbox.Add(sessions_label, 0, wx.ALL | wx.ALIGN_LEFT, 5)

        self.sessions_listbox = wx.ListBox(panel)
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
        self.load_sessions()


    def load_sessions(self):
        """Loads sessions from DB and populates the listbox."""
        self.sessions = self.session_manager.load_sessions()
        self.sessions_listbox.Clear()
        for name, _, _, _, _, _ in self.sessions:
            self.sessions_listbox.Append(name)

    def on_context_menu(self, event):
        selected_index = self.sessions_listbox.GetSelection()
        if selected_index != wx.NOT_FOUND:
            menu = wx.Menu()
            edit_item = menu.Append(wx.ID_ANY, "Edit Session") # Add Edit item
            self.Bind(wx.EVT_MENU, self.on_edit_session, edit_item)

            file_manager_item = menu.Append(wx.ID_ANY, "File Manager")
            self.Bind(wx.EVT_MENU, self.on_file_manager, file_manager_item)
            self.PopupMenu(menu, event.GetPosition())

    def on_file_manager(self, event):
        selected_index = self.sessions_listbox.GetSelection()
        if selected_index != wx.NOT_FOUND:
            session_name, host, port, username, password, key_file_path = self.sessions[selected_index]

            if not key_file_path and not password:
               password_dialog = PasswordPromptDialog(self, session_name)
               if password_dialog.ShowModal() == wx.ID_OK:
                   password = password_dialog.password_text.GetValue()
               else:
                   return
               password_dialog.Destroy()
            file_manager = FileManager(self, host, port, username, password, session_name, key_file_path=key_file_path)
            self.GetParent().add_child_frame(file_manager)
            self.Hide()
        else:
            wx.MessageBox("Please select a session to open the file manager.", "Error", wx.OK | wx.ICON_ERROR)

    def on_connect(self, event):
        selected_index = self.sessions_listbox.GetSelection()
        if selected_index != wx.NOT_FOUND:
            session_name, host, port, username, password, key_file_path = self.sessions[selected_index] # Get key_file_path

            if not key_file_path and not password:
               password_dialog = PasswordPromptDialog(self, session_name)
               if password_dialog.ShowModal() == wx.ID_OK:
                   password = password_dialog.password_text.GetValue()
               else:
                   return
               password_dialog.Destroy()
            ssh_terminal = AccessibleTerminal(self, host, port, username, password, session_name, key_file_path=key_file_path)
            self.GetParent().add_child_frame(ssh_terminal)
        else:
            wx.MessageBox("Please select a session to connect to.", "Error", wx.OK | wx.ICON_ERROR)

    def on_add_session(self, event):
        connection_dialog = ConnectionDialog(self)
        if connection_dialog.ShowModal() == wx.ID_OK:
           session_name = connection_dialog.name_text.GetValue()
           server_host = connection_dialog.host_text.GetValue()
           server_port = int(connection_dialog.port_text.GetValue())
           username = connection_dialog.username_text.GetValue()
           password = connection_dialog.password_text.GetValue()
           save_password = connection_dialog.save_password_checkbox.GetValue()
           key_file_path = connection_dialog.key_file_text.GetValue()

           # Validate input
           if not session_name or not server_host or not username:
                wx.MessageBox("Session Name, Host, and Username are required.", "Validation Error", wx.OK | wx.ICON_WARNING)
                connection_dialog.Destroy()
                return
           if session_name in [s[0] for s in self.sessions]:
               wx.MessageBox(f"A session with the name '{session_name}' already exists. Please use a different name.", "Duplicate Name", wx.OK | wx.ICON_WARNING)
               connection_dialog.Destroy()
               return

           # Ensure port is an integer, default to 22 if invalid
           try:
              server_port = int(server_port)
           except (ValueError, TypeError):
              server_port = 22
              wx.MessageBox("Invalid port number entered. Using default port 22.", "Warning", wx.OK | wx.ICON_WARNING)

           self.session_manager.save_session(session_name, server_host, server_port, username, password, save_password, key_file_path if key_file_path else None)
           self.load_sessions()
           speak(f"Session {session_name} Saved")
        connection_dialog.Destroy()

    def on_edit_session(self, event):
        selected_index = self.sessions_listbox.GetSelection()
        if selected_index != wx.NOT_FOUND:
            original_session_data = self.sessions[selected_index]
            original_session_name = original_session_data[0]

            connection_dialog = ConnectionDialog(self, title=f"Edit Session: {original_session_name}", session_data=original_session_data)
            if connection_dialog.ShowModal() == wx.ID_OK:
               new_session_name = connection_dialog.name_text.GetValue().strip()
               server_host = connection_dialog.host_text.GetValue()
               server_port = connection_dialog.port_text.GetValue()
               username = connection_dialog.username_text.GetValue()
               password = connection_dialog.password_text.GetValue()
               save_password = connection_dialog.save_password_checkbox.GetValue()
               key_file_path = connection_dialog.key_file_text.GetValue()

               if not server_host or not username:
                    wx.MessageBox("Host and Username are required.", "Validation Error", wx.OK | wx.ICON_WARNING)
                    connection_dialog.Destroy()
                    return

               # Check for duplicate name if the name was changed, excluding the original name itself
               if new_session_name != original_session_name and new_session_name in [s[0] for s in self.sessions if s[0] != original_session_name]:
                   wx.MessageBox(f"A session with the name '{new_session_name}' already exists. Please use a different name.", "Duplicate Name", wx.OK | wx.ICON_WARNING)
                   connection_dialog.Destroy()
                   return

               try:
                  server_port = int(server_port)
               except (ValueError, TypeError):
                  server_port = 22
                  wx.MessageBox("Invalid port number entered. Using default port 22.", "Warning", wx.OK | wx.ICON_WARNING)

               self.session_manager.remove_session(original_session_name)
               self.session_manager.save_session(new_session_name, server_host, server_port, username, password, save_password, key_file_path if key_file_path else None)
               self.load_sessions()
               edited_index = self.sessions_listbox.FindString(new_session_name)
               if edited_index != wx.NOT_FOUND:
                   self.sessions_listbox.SetSelection(edited_index)
               speak(f"Session {original_session_name} Updated to {new_session_name}")
            connection_dialog.Destroy()
        else:
            wx.MessageBox("Please select a session to edit.", "Error", wx.OK | wx.ICON_ERROR)

    def on_remove_session(self, event):
        selected_index = self.sessions_listbox.GetSelection()
        if selected_index != wx.NOT_FOUND:
            session_name = self.sessions[selected_index][0]
            dlg = wx.MessageDialog(self, f"Are you sure you want to remove session '{session_name}'?", "Confirm Removal", wx.YES_NO | wx.ICON_QUESTION)
            result = dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_YES:
                self.session_manager.remove_session(session_name)
                self.sessions_listbox.Delete(selected_index)
                del self.sessions[selected_index]
                self.load_sessions()
                speak(f"Session {session_name} removed.")
        else:
            wx.MessageBox("Please select a session to remove.", "Error", wx.OK | wx.ICON_ERROR)
