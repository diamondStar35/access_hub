import wx
from speech import speak
from tools.accessible_terminal.download_dialogs import DownloadDialog
from tools.accessible_terminal.upload_dialogs import UploadDialog, FolderUploadDialog
import paramiko
import os
import stat
import shutil
from datetime import datetime
import time
import concurrent.futures


class FileManager(wx.Frame):
    def __init__(self, parent, host, port, username, password, session_name):
        super(FileManager, self).__init__(parent, title=f"File Manager - {username}@{host}", size=(800, 600))
        self.parent_frame = parent
        self.session_name = session_name
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.ssh_client = None
        self.sftp_client = None
        self.current_path = "/"
        self.history = ["/"]
        self.history_index = 0
        self.is_connected = False
        self.current_files = []
        self.last_focused_item = -1
        self.clipboard = []
        self.clipboard_mode = None  # 'copy' or 'cut'
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Toolbar
        toolbar = wx.ToolBar(panel, style=wx.TB_HORIZONTAL | wx.TB_TEXT)
        back_tool = toolbar.AddTool(wx.ID_ANY, "Back", wx.ArtProvider.GetBitmap(wx.ART_GO_BACK), shortHelp="Go Back")
        forward_tool = toolbar.AddTool(wx.ID_ANY, "Forward", wx.ArtProvider.GetBitmap(wx.ART_GO_FORWARD), shortHelp="Go Forward")
        toolbar.Realize()
        toolbar.Bind(wx.EVT_TOOL, self.on_back, back_tool)
        toolbar.Bind(wx.EVT_TOOL, self.on_forward, forward_tool)
        vbox.Add(toolbar, 0, wx.EXPAND | wx.ALL, 0)

        self.path_label = wx.StaticText(panel, label=f"Path: {self.current_path}")
        vbox.Add(self.path_label, 0, wx.ALL | wx.ALIGN_LEFT, 5)

        self.file_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.file_list.InsertColumn(0, "Name", width=300)
        self.file_list.InsertColumn(1, "Size", width=100)
        self.file_list.InsertColumn(2, "Modified", width=150)
        self.file_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_item_activated)
        self.file_list.Bind(wx.EVT_LIST_ITEM_FOCUSED, self.on_item_focused)
        self.file_list.Bind(wx.EVT_CONTEXT_MENU, self.on_list_context_menu)

        vbox.Add(self.file_list, 1, wx.ALL | wx.EXPAND, 5)
        panel.SetSizer(vbox)

        # Menu Bar
        menu_bar = wx.MenuBar()
        file_menu = wx.Menu()
        new_menu = wx.Menu()
        new_menu_file = new_menu.Append(wx.ID_ANY, "File")
        new_menu_folder = new_menu.Append(wx.ID_ANY, "Folder")
        file_menu.AppendSubMenu(new_menu, "New")
        download_item = file_menu.Append(wx.ID_ANY, "Download")

        upload_menu = wx.Menu()
        upload_file_item = upload_menu.Append(wx.ID_ANY, "File")
        upload_folder_item = upload_menu.Append(wx.ID_ANY, "Folder")
        file_menu.AppendSubMenu(upload_menu, "Upload")

        refresh_item = file_menu.Append(wx.ID_REFRESH, "Refresh", "F5")
        properties_item = file_menu.Append(wx.ID_ANY, "Properties")

        edit_menu = wx.Menu()
        copy_item = edit_menu.Append(wx.ID_COPY, "Copy", "Ctrl+C")
        cut_item = edit_menu.Append(wx.ID_CUT, "Cut", "Ctrl+X")
        paste_item = edit_menu.Append(wx.ID_PASTE, "Paste", "Ctrl+V")
        rename_item = edit_menu.Append(wx.ID_ANY, "Rename", "F2")
        delete_item = edit_menu.Append(wx.ID_DELETE, "Delete", "Del")

        menu_bar.Append(file_menu, "File")
        menu_bar.Append(edit_menu, "Edit")
        self.SetMenuBar(menu_bar)

        self.Bind(wx.EVT_MENU, self.on_new_file, new_menu_file)
        self.Bind(wx.EVT_MENU, self.on_new_folder, new_menu_folder)
        self.Bind(wx.EVT_MENU, self.on_download, download_item)
        self.Bind(wx.EVT_MENU, self.on_upload_file, upload_file_item)
        self.Bind(wx.EVT_MENU, self.on_upload_folder, upload_folder_item)
        self.Bind(wx.EVT_MENU, self.on_properties, properties_item)
        self.Bind(wx.EVT_MENU, self.on_delete, delete_item)
        self.Bind(wx.EVT_MENU, self.on_copy, copy_item)
        self.Bind(wx.EVT_MENU, self.on_cut, cut_item)
        self.Bind(wx.EVT_MENU, self.on_paste, paste_item)
        self.Bind(wx.EVT_MENU, self.on_rename, rename_item)
        self.Bind(wx.EVT_MENU, self.on_refresh, refresh_item)

        self.Centre()
        self.Show(True)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
        self.Bind(wx.EVT_MENU, self.on_forward, id=forward_tool.GetId())
        accel_tbl = wx.AcceleratorTable([
            (wx.ACCEL_ALT, wx.WXK_RIGHT, forward_tool.GetId()),
            (wx.ACCEL_CTRL, ord('C'), wx.ID_COPY),
            (wx.ACCEL_CTRL, ord('X'), wx.ID_CUT),
            (wx.ACCEL_CTRL, ord('V'), wx.ID_PASTE),
            (wx.ACCEL_NORMAL, wx.WXK_DELETE, wx.ID_DELETE),
            (wx.ACCEL_NORMAL, wx.WXK_F2, rename_item.GetId()),
            (wx.ACCEL_CTRL, ord('N'), new_menu_folder.GetId()),
            (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('N'), new_menu_file.GetId()),
            (wx.ACCEL_NORMAL, wx.WXK_F5, wx.ID_REFRESH),
            (wx.ACCEL_ALT, wx.WXK_RETURN, properties_item.GetId())
        ])
        self.SetAcceleratorTable(accel_tbl)

        self.executor.submit(self.connect_ssh)


    def connect_ssh(self):
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(self.host, port=self.port, username=self.username, password=self.password)
            self.sftp_client = self.ssh_client.open_sftp()
            self.is_connected = True
            wx.CallAfter(self.load_directory, self.current_path)
        except Exception as e:
            wx.MessageBox(f"Connection failed: {e}", "Error", wx.OK | wx.ICON_ERROR)
            self.is_connected = False
            wx.CallAfter(self.Destroy)

    def load_directory(self, path):
        if not self.is_connected:
            return
        try:
            files = self.sftp_client.listdir_attr(path)
            files.sort(key=lambda file_attr: file_attr.filename)  # Sort alphabetically
            self.current_files = files
            self.file_list.DeleteAllItems()
            for file_attr in files:
                file_name = file_attr.filename
                file_size = file_attr.st_size
                modified_time = datetime.fromtimestamp(file_attr.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                index = self.file_list.InsertItem(self.file_list.GetItemCount(), file_name)
                self.file_list.SetItem(index, 1, self.format_size(file_size))  # Format to MB
                self.file_list.SetItem(index, 2, modified_time)
            self.current_path = path
            self.path_label.SetLabel(f"Path: {self.current_path}")
            # Set focus to first item after loading
            if self.file_list.GetItemCount() > 0:
                self.file_list.Focus(0)
                self.file_list.Select(0)
        except Exception as e:
            wx.MessageBox(f"Failed to list directory: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def format_size(self, size_bytes):
        """Format file size to MB or KB."""
        if size_bytes < 1024 * 1024:
            size_kb = size_bytes / 1024
            return f"{size_kb:.2f} KB"
        else:
            size_mb = size_bytes / (1024 * 1024)
            return f"{size_mb:.2f} MB"

    def on_item_activated(self, event):
        item_index = event.GetIndex()
        if item_index < 0 or item_index >= len(self.current_files):
            return
        selected_file = self.current_files[item_index]
        full_path = os.path.join(self.current_path, selected_file.filename).replace("\\", "/")  # Normalize path
        if stat.S_ISDIR(selected_file.st_mode):
            self.last_focused_item = item_index  # Remembering the focus before changing the folder
            self.navigate_to(full_path)
        elif stat.S_ISREG(selected_file.st_mode):
            self.download_file(full_path, selected_file.filename)

    def _progress_callback(self, current_bytes, total_bytes, progress_dlg):
        if progress_dlg.is_cancelled or self.is_cancel_download:
            #This is necessary when a very big file is being downloaded, so if cancelled in middle, Stop it
            raise Exception("Download Cancelled")
        if progress_dlg and not progress_dlg.IsBeingDeleted(): #Check if the dialog is still valid before updating the gui
            progress = min(100, int((current_bytes / total_bytes) * 100))
            wx.CallAfter(progress_dlg.Update, progress)

    def on_char_hook(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_BACK:
            if self.current_path != "/":
                self.go_back()
        event.Skip()

    def navigate_to(self, path):
        if path != self.current_path:
            if self.history_index < len(self.history) - 1:
                self.history = self.history[:self.history_index + 1]  # Erase history beyond the current index
            self.history.append(path)
            self.history_index += 1
            self.load_directory(path)

    def go_back(self):
        if self.history_index > 0:
            self.history_index -= 1
            path = self.history[self.history_index]
            current_index = self.file_list.GetFirstSelected()
            self.load_directory(path)
            if current_index > -1:
                self.file_list.Focus(current_index)  # set the focus after going back one folder
                self.file_list.Select(current_index)

    def on_forward(self, event):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            path = self.history[self.history_index]
            current_index = self.last_focused_item
            self.load_directory(path)
            if current_index > -1:
                self.file_list.Focus(current_index)
                self.file_list.Select(current_index)

    def on_back(self, event):
        self.go_back()

    def on_item_focused(self, event):
        self.last_focused_item = event.GetIndex()

    def on_new_file(self, event):
        dlg = wx.TextEntryDialog(self, "Enter the name of the new file:", "Create New File", value="new_file")
        if dlg.ShowModal() == wx.ID_OK:
            new_file_name = dlg.GetValue()
            full_path = os.path.join(self.current_path, new_file_name).replace("\\", "/")
            self.executor.submit(self._create_file, full_path, new_file_name)
        dlg.Destroy()

    def _create_file(self, full_path, new_file_name):
        try:
            with self.sftp_client.open(full_path, "w") as f:
                pass
            wx.CallAfter(self.load_directory, self.current_path)
            speak(f"File {new_file_name} Created")
        except Exception as e:
            wx.MessageBox(f"Failed to create file: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def on_new_folder(self, event):
        dlg = wx.TextEntryDialog(self, "Enter the name of the new folder:", "Create New Folder", value="new_folder")
        if dlg.ShowModal() == wx.ID_OK:
            new_folder_name = dlg.GetValue()
            full_path = os.path.join(self.current_path, new_folder_name).replace("\\", "/")
            self.executor.submit(self._create_folder, full_path, new_folder_name)
        dlg.Destroy()

    def _create_folder(self, full_path, new_folder_name):
        try:
            self.sftp_client.mkdir(full_path)
            wx.CallAfter(self.load_directory, self.current_path)
            speak(f"Folder {new_folder_name} Created")
        except Exception as e:
            wx.MessageBox(f"Failed to create folder: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def on_download(self, event):
        selected_index = self.file_list.GetFirstSelected()
        if selected_index != -1:
            selected_file = self.current_files[selected_index]
            if stat.S_ISREG(selected_file.st_mode):
                full_path = os.path.join(self.current_path, selected_file.filename).replace("\\", "/")
                self.download_file(full_path, selected_file.filename)
            else:
                wx.MessageBox("Please select a file to download.", "Error", wx.OK | wx.ICON_ERROR)
        else:
            wx.MessageBox("Please select a file to download.", "Error", wx.OK | wx.ICON_ERROR)

    def on_upload_file(self, event):
        file_dlg = wx.FileDialog(self, "Choose a file to upload", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if file_dlg.ShowModal() == wx.ID_OK:
            local_path = file_dlg.GetPath()
            file_name = os.path.basename(local_path)
            file_size = os.path.getsize(local_path)
            remote_path = os.path.join(self.current_path, file_name).replace("\\", "/")
            upload_dlg = UploadDialog(self, f"Uploading {file_name}", file_size)

            def _upload():
                try:
                    # Create a new SFTP client for the upload
                    upload_sftp_client = self.ssh_client.open_sftp()
                    # Use a custom callback that checks for cancellation
                    def put_callback(sent, total):
                        if upload_dlg.cancel_event.is_set():
                           raise Exception("Upload cancelled by user")
                        wx.CallAfter(upload_dlg.update_progress, sent, total)

                    upload_sftp_client.put(local_path, remote_path, callback=put_callback)
                    if not upload_dlg.is_cancelled:
                        wx.CallAfter(speak, f"{file_name} uploaded successfully.")
                        wx.CallAfter(upload_dlg.show_notification, file_name)
                        wx.CallAfter(self.load_directory, self.current_path)
                except Exception as e:
                    if not upload_dlg.is_cancelled:
                        wx.MessageBox(f"Error uploading {file_name}: {e}", "Error", wx.OK | wx.ICON_ERROR)
                finally:
                    if not upload_dlg.is_cancelled:
                        wx.CallAfter(upload_dlg.Destroy)
                    upload_sftp_client.close()

            self.executor.submit(_upload)
            upload_dlg.ShowModal()
        file_dlg.Destroy()

    def on_upload_folder(self, event):
        folder_dlg = wx.DirDialog(self, "Choose a folder to upload", style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
        if folder_dlg.ShowModal() == wx.ID_OK:
            local_path = folder_dlg.GetPath()
            folder_name = os.path.basename(local_path)
            self.total_files = 0
            self.total_folders = 0
            self.total_size = 0
            self._count_items(local_path)
            remote_base_path = os.path.join(self.current_path, folder_name).replace("\\", "/")
            upload_dlg = FolderUploadDialog(self, f"Uploading {folder_name}", self.total_files, self.total_folders, self.total_size)

            def _upload():
              #Create a new sftp client
              upload_sftp_client = self.ssh_client.open_sftp()
              try:
                files_done = 0
                folders_done = 0
                size_done = 0

                def upload_recursive(local_path, remote_path):
                  nonlocal files_done, folders_done, size_done
                  # Create remote directory if it doesn't exist
                  try:
                      upload_sftp_client.stat(remote_path)
                  except IOError:
                      upload_sftp_client.mkdir(remote_path)
                      folders_done += 1
                      wx.CallAfter(upload_dlg.update_progress, files_done, folders_done, size_done)

                  # Iterate through items in the local directory
                  for item in os.listdir(local_path):
                      local_item_path = os.path.join(local_path, item)
                      remote_item_path = os.path.join(remote_path, item).replace("\\", "/")

                      if os.path.isdir(local_item_path):
                          # Recursively upload subdirectories
                          upload_recursive(local_item_path, remote_item_path)
                      else:
                          file_size = os.path.getsize(local_item_path)
                          # Check if canceled before uploading each file
                          if upload_dlg.cancel_event.is_set():
                              raise Exception("Folder upload cancelled by user")

                          def put_callback(sent, total):
                              if upload_dlg.cancel_event.is_set():
                                  raise Exception("Upload cancelled by user")
                              wx.CallAfter(upload_dlg.update_file_progress, sent, total)

                          upload_sftp_client.put(local_item_path, remote_item_path, callback=put_callback)
                          wx.CallAfter(upload_dlg.update_file_progress, 0, 1)
                          files_done += 1
                          size_done += file_size
                          wx.CallAfter(upload_dlg.update_progress, files_done, folders_done, size_done)
                upload_recursive(local_path, remote_base_path)
                if not upload_dlg.is_cancelled:
                    wx.CallAfter(speak, f"{folder_name} uploaded successfully.")
                    wx.CallAfter(upload_dlg.show_notification, folder_name)
                    wx.CallAfter(self.load_directory, self.current_path)
              except Exception as e:
                  wx.MessageBox(f"Error uploading {folder_name}: {e}", "Error", wx.OK | wx.ICON_ERROR)
              finally:
                  upload_sftp_client.close()
                  if not upload_dlg.is_cancelled:
                      wx.CallAfter(upload_dlg.Destroy)

            self.executor.submit(_upload)
            upload_dlg.ShowModal()
        folder_dlg.Destroy()

    def on_delete(self, event):
        selected_index = self.file_list.GetFirstSelected()
        if selected_index != -1:
            selected_file = self.current_files[selected_index]
            full_path = os.path.join(self.current_path, selected_file.filename).replace("\\", "/")
            dlg = wx.MessageDialog(self, f"Are you sure you want to delete '{selected_file.filename}'?", "Confirm Delete",
                                  wx.YES_NO | wx.ICON_QUESTION)
            if dlg.ShowModal() == wx.ID_YES:
               progress_dlg = wx.ProgressDialog(
                    "Deleting item",
                    f"Deleting {selected_file.filename}...",
                    maximum=100,
                    parent=self,
                    style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_SMOOTH
                )
               self.executor.submit(self._delete_item, full_path, selected_file, progress_dlg)
            dlg.Destroy()
        else:
            wx.MessageBox("Please select a file or folder to delete.", "Error", wx.OK | wx.ICON_ERROR)

    def on_copy(self, event):
        selected_index = self.file_list.GetFirstSelected()
        if selected_index != -1:
            selected_file = self.current_files[selected_index]
            full_path = os.path.join(self.current_path, selected_file.filename).replace("\\", "/")
            self.clipboard = [full_path]
            self.clipboard_mode = 'copy'
            speak("Copied.")
        else:
            wx.MessageBox("Please select a file or folder to copy.", "Error", wx.OK | wx.ICON_ERROR)

    def _server_side_copy(self, source, destination, progress_dlg):
        """Copies a file or directory on the server using server-side commands."""
        try:
            if stat.S_ISDIR(self.sftp_client.stat(source).st_mode):
                command = f'cp -r "{source}" "{destination}"'
            else:
                command = f'cp "{source}" "{destination}"'

            _, stdout, stderr = self.ssh_client.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()

            if exit_status == 0:
                wx.CallAfter(progress_dlg.Update, 100)
            else:
                error_message = stderr.read().decode()
                raise Exception(f"Server-side copy failed: {error_message}")

        except Exception as e:
            wx.MessageBox(f"Error during copy: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def on_cut(self, event):
        selected_index = self.file_list.GetFirstSelected()
        if selected_index != -1:
            selected_file = self.current_files[selected_index]
            full_path = os.path.join(self.current_path, selected_file.filename).replace("\\", "/")
            self.clipboard = [full_path]
            self.clipboard_mode = 'cut'
            speak("Cut.")
        else:
            wx.MessageBox("Please select a file or folder to cut.", "Error", wx.OK | wx.ICON_ERROR)

    def on_paste(self, event):
        if self.clipboard:
            progress_dlg = wx.ProgressDialog(
                "Pasting item",
                f"Pasting item...",
                maximum=100,
                parent=self,
                style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_SMOOTH
            )
            self.executor.submit(self._paste_items, progress_dlg)

    def _paste_items(self, progress_dlg):
        try:
            for file_path in self.clipboard:
                file_name = os.path.basename(file_path)
                new_file_path = os.path.join(self.current_path, file_name).replace("\\", "/")
                if new_file_path in [os.path.join(self.current_path, f.filename).replace("\\", "/") for f in
                                     self.current_files]:
                    wx.MessageBox("A file with the same name already exists in this directory, Please rename it.",
                                  "Error",
                                  wx.OK | wx.ICON_ERROR)
                    return
                try:
                    if self.clipboard_mode == 'copy':
                        self._server_side_copy(file_path, new_file_path, progress_dlg)
                        speak(f"{file_name} pasted.")
                    elif self.clipboard_mode == 'cut':
                        # Use server-side 'mv' command for efficiency
                        command = f'mv "{file_path}" "{new_file_path}"'
                        _, stdout, stderr = self.ssh_client.exec_command(command)
                        exit_status = stdout.channel.recv_exit_status()

                        if exit_status == 0:
                            speak(f"{file_name} moved.")
                        else:
                            error_message = stderr.read().decode()
                            raise Exception(f"Move failed: {error_message}")
                except Exception as e:
                    wx.MessageBox(f"Failed to paste item: {e}", "Error", wx.OK | wx.ICON_ERROR)
            self.clipboard = []
            self.clipboard_mode = None
            wx.CallAfter(self.load_directory, self.current_path)
        finally:
            wx.CallAfter(progress_dlg.Destroy)

    def _delete_item(self, full_path, selected_file, progress_dlg):
        try:
            if stat.S_ISDIR(selected_file.st_mode):
                command = f'rm -rf "{full_path}"'
            elif stat.S_ISREG(selected_file.st_mode):
                command = f'rm "{full_path}"'

            _, stdout, stderr = self.ssh_client.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()

            if exit_status == 0:
                wx.CallAfter(self.load_directory, self.current_path)
                speak(f"Item {selected_file.filename} deleted.")
            else:
                error_message = stderr.read().decode()
                raise Exception(f"delete failed: {error_message}")

        except Exception as e:
            wx.MessageBox(f"Failed to delete item: {e}", "Error", wx.OK | wx.ICON_ERROR)
        finally:
            wx.CallAfter(progress_dlg.Destroy)

    def on_rename(self, event):
        selected_index = self.file_list.GetFirstSelected()
        if selected_index != -1:
            selected_file = self.current_files[selected_index]
            full_path = os.path.join(self.current_path, selected_file.filename).replace("\\", "/")
            dlg = wx.TextEntryDialog(self, "Enter a new name:", "Rename", value=selected_file.filename)
            if dlg.ShowModal() == wx.ID_OK:
                new_name = dlg.GetValue()
                new_path = os.path.join(self.current_path, new_name).replace("\\", "/")
                try:
                    self.sftp_client.rename(full_path, new_path)
                    self.load_directory(self.current_path)
                    speak(f"Item renamed to {new_name}")
                except Exception as e:
                    wx.MessageBox(f"Failed to rename item: {e}", "Error", wx.OK | wx.ICON_ERROR)
            dlg.Destroy()
        else:
            wx.MessageBox("Please select a file or folder to rename.", "Error", wx.OK | wx.ICON_ERROR)

    def download_file(self, remote_path, file_name):
        save_dlg = wx.FileDialog(
            self, message=f"Save {file_name} as", defaultDir=os.path.expanduser("~"),
            defaultFile=file_name, style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        )
        if save_dlg.ShowModal() == wx.ID_OK:
            local_path = save_dlg.GetPath()
            self.is_cancel_download=False
            download_dlg = DownloadDialog(self, f"Downloading {file_name}", file_name, local_path, remote_path, self.sftp_client)
            download_dlg.ShowModal()
        save_dlg.Destroy()

    def on_list_context_menu(self, event):
        menu = wx.Menu()
        copy_item = menu.Append(wx.ID_COPY, "Copy")
        cut_item = menu.Append(wx.ID_CUT, "Cut")
        rename_item = menu.Append(wx.ID_ANY, "Rename")
        delete_item = menu.Append(wx.ID_DELETE, "Delete")

        self.Bind(wx.EVT_MENU, self.on_copy, copy_item)
        self.Bind(wx.EVT_MENU, self.on_cut, cut_item)
        self.Bind(wx.EVT_MENU, self.on_rename, rename_item)
        self.Bind(wx.EVT_MENU, self.on_delete, delete_item)
        self.PopupMenu(menu, event.GetPosition())

    def on_refresh(self, event):
      self.load_directory(self.current_path)

    def on_properties(self, event):
        selected_index = self.file_list.GetFirstSelected()
        if selected_index != -1:
            selected_file = self.current_files[selected_index]
            full_path = os.path.join(self.current_path, selected_file.filename).replace("\\", "/")
            loading_dlg = wx.ProgressDialog("Loading Properties", "Fetching file properties...", parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)
            self.executor.submit(self._get_properties_data, full_path, selected_file, loading_dlg)
        else:
            wx.MessageBox("Please select a file or folder to view its properties.", "Error", wx.OK | wx.ICON_ERROR)

    def _get_properties_data(self, full_path, selected_file, loading_dlg):
        try:
           properties = {}
           file_stat = self.sftp_client.stat(full_path)
           properties["Name"] = selected_file.filename
           if stat.S_ISDIR(file_stat.st_mode):
              properties["Type"] = "Folder"
           elif stat.S_ISREG(file_stat.st_mode):
               properties["Type"] = "File"
           properties["Size"] = self.format_size(file_stat.st_size)
           properties["Modified"] = datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')

           if hasattr(file_stat, 'st_mode'):
            mode = file_stat.st_mode
            properties["Permissions"] = self._get_permissions_string(mode)

            try:
                _, stdout, _ = self.ssh_client.exec_command(f'stat -c "%U" "{full_path}"') #Get the owner name
                owner_name = stdout.read().decode().strip()
                properties["Owner"] = owner_name
            except Exception as e:
               properties["Owner"] = "N/A"
            try:
                _, stdout, _ = self.ssh_client.exec_command(f'stat -c "%G" "{full_path}"') #Get the group name
                group_name = stdout.read().decode().strip()
                properties["Group"] = group_name
            except Exception as e:
                properties["Group"] = "N/A"

           if stat.S_ISDIR(file_stat.st_mode):
             # Use server-side du command for folder size
             try:
                  _, stdout, _ = self.ssh_client.exec_command(f'du -sb "{full_path}"')
                  output = stdout.read().decode().strip()
                  size_bytes = int(output.split()[0]) if output else 0
                  properties["Total size"] = self.format_size(size_bytes)
             except Exception as e:
                properties["Total size"] = "Unknown"
             try:
                _, stdout, _ = self.ssh_client.exec_command(f'find "{full_path}" -type f | wc -l')
                output = stdout.read().decode().strip()
                file_count=int(output) if output else 0
                properties["Files count"] = file_count
             except Exception:
                   properties["Files count"] ="Unknown"
             try:
                _, stdout, _ = self.ssh_client.exec_command(f'find "{full_path}" -type d | wc -l')
                output = stdout.read().decode().strip()
                folder_count=int(output) - 1  if output else 0 #exclude the folder itself
                properties["Folders count"] = folder_count
             except Exception:
                properties["Folders count"] = "Unknown"

           properties_text = "\n".join(f"{key}: {value}" for key, value in properties.items())
           wx.CallAfter(self._show_properties_dialog, properties_text)
        except Exception as e:
            wx.MessageBox(f"Error retrieving properties: {e}", "Error", wx.OK | wx.ICON_ERROR)
        finally:
           wx.CallAfter(loading_dlg.Destroy)

    def _get_permissions_string(self, mode):
        perms = ""
        # Check file type
        if stat.S_ISDIR(mode):
            perms += "Directory | "
        elif stat.S_ISLNK(mode):
            perms += "Symbolic Link | "
        else:
            perms += "File | "

        # Check permissions for owner, group, and others
        rwx_values = ["Read", "Write", "Execute"]
        targets = ["Owner", "Group", "Others"]
        for i in range(3):
            shift = (2 - i) * 3
            target = targets[i]
            r_perm = (mode >> (shift + 2)) & 1
            w_perm = (mode >> (shift + 1)) & 1
            x_perm = (mode >> (shift)) & 1
            if r_perm or w_perm or x_perm:
              target_perms = []
              if r_perm:
                 target_perms.append("Read")
              if w_perm:
                 target_perms.append("Write")
              if x_perm:
                 target_perms.append("Execute")
              perms += f"{target} - {', '.join(target_perms)}. "
        return perms.strip(" |")

    def _calculate_folder_size(self, folder_path):
        total_size = 0
        file_count=0
        folder_count=0
        try:
            for item in self.sftp_client.listdir_attr(folder_path):
              if stat.S_ISDIR(item.st_mode):
                 folder_count+=1
                 files,folders,size = self._calculate_folder_size(os.path.join(folder_path, item.filename).replace("\\","/"))
                 total_size += size
                 folder_count += folders
                 file_count += files

              elif stat.S_ISREG(item.st_mode):
                  file_count +=1
                  total_size += item.st_size
        except Exception:
           pass
        return file_count,folder_count,total_size

    def _show_properties_dialog(self, properties_text):
        dlg = PropertiesDialog(self, properties_text)
        dlg.ShowModal()
        dlg.Destroy()

    def _count_items(self, local_path):
        """Recursively count files and folders."""
        try:
            if os.path.isdir(local_path):
                self.total_folders += 1
                for item in os.listdir(local_path):
                    item_path = os.path.join(local_path, item)
                    self._count_items(item_path)
            elif os.path.isfile(local_path):
                self.total_files += 1
        except Exception as e:
            wx.MessageBox(f"Error counting items for upload {e}", "Error", wx.OK | wx.ICON_ERROR)


    def on_close(self):
        if self.sftp_client:
            try:
                self.sftp_client.close()
            except Exception as e:
                speak(f"Error closing sftp channel: {e}", interrupt=True)
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except Exception as e:
                speak(f"Error closing ssh connection: {e}", interrupt=True)
        self.is_connected = False
        self.parent_frame.Close()

    def OnClose(self, event):
        self.on_close()
        event.Skip()


class PropertiesDialog(wx.Dialog):
    def __init__(self, parent, properties_text):
       super(PropertiesDialog, self).__init__(parent, title="Properties", size=(400, 400))
       panel = wx.Panel(self)
       vbox = wx.BoxSizer(wx.VERTICAL)

       self.text_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
       self.text_ctrl.SetValue(properties_text)
       vbox.Add(self.text_ctrl, 1, wx.ALL | wx.EXPAND, 10)

       ok_button = wx.Button(panel, id=wx.ID_OK, label="OK")
       vbox.Add(ok_button, 0, wx.ALL | wx.ALIGN_CENTER, 10)

       panel.SetSizer(vbox)
       self.Centre()