import wx
import wx.adv
import time
import threading
import os
import subprocess

class DownloadDialog(wx.Dialog):
    def __init__(self, parent, title, file_name, local_path, remote_path, sftp_client):
        super().__init__(parent, title=title, size=(600, 350), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.file_name = file_name
        self.local_path = local_path
        self.remote_path = remote_path
        self.sftp_client = sftp_client
        self.start_time = time.time()
        self.is_cancelled = False
        self.is_background_download = False
        self._action_id_map = {}
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.update_elapsed_time, self.timer)
        self.timer.Start(1000)

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        file_name_label = wx.StaticText(panel, label=f"File: {self.file_name}")
        vbox.Add(file_name_label, 0, wx.ALL | wx.EXPAND, 10)

        self.elapsed_time_label = wx.StaticText(panel, label="Elapsed Time: 00:00")
        vbox.Add(self.elapsed_time_label, 0, wx.ALL | wx.EXPAND, 10)

        self.progress_bar = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)
        vbox.Add(self.progress_bar, 0, wx.ALL | wx.EXPAND, 10)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        cancel_button = wx.Button(panel, label="Cancel")
        cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)

        background_button = wx.Button(panel, label="Download in Background")
        background_button.Bind(wx.EVT_BUTTON, self.on_background_download)
        button_sizer.Add(background_button, 0, wx.ALL, 5)

        vbox.Add(button_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        panel.SetSizer(vbox)
        self.Centre()
        self.start_download() #Start the download once the dialog is opened

    def update_elapsed_time(self, event):
        elapsed_seconds = int(time.time() - self.start_time)
        minutes, seconds = divmod(elapsed_seconds, 60)
        self.elapsed_time_label.SetLabel(f"Elapsed Time: {minutes:02}:{seconds:02}")

    def on_cancel(self, event):
        self.is_cancelled = True
        self.timer.Stop()
        self.EndModal(wx.ID_CANCEL)

    def on_background_download(self, event):
        self.is_background_download = True
        self.Hide()

    def start_download(self):
      def _download():
          try:
              def progress_callback(x, y):
                   # Check if the dialog still exists before calling GUI methods
                   if self and not self.IsBeingDeleted():
                       wx.CallAfter(self.update_progress, x, y)

              self.sftp_client.get(
                  self.remote_path,
                  self.local_path,
                  callback=progress_callback
              )
              if not self.is_cancelled:
                wx.CallAfter(self.show_notification)

          except Exception as e:
              if not self.is_cancelled:
                  wx.MessageBox(f"Error downloading {self.file_name}: {e}", "Error", wx.OK | wx.ICON_ERROR)
          finally:
              if not self.is_cancelled and not self.is_background_download:
                  wx.CallAfter(self.Close)

      self.Parent.executor.submit(_download)

    def update_progress(self, current, total):
        if not self.is_cancelled:
            progress = min(100, int((current / total) * 100))
            self.progress_bar.SetValue(progress)
            if progress == 100:
                self.timer.Stop()
                if not self.is_background_download:
                    self.EndModal(wx.ID_OK)

    def show_notification(self):
        """Shows a wxPython notification when download completes."""
        if self.is_background_download and self.local_path:
            try:
                notification = wx.adv.NotificationMessage(
                    title="Download Complete",
                    message=f"{self.file_name} has been downloaded.",
                    parent=self.GetParent(), # Associate with main frame or relevant parent
                    flags=wx.ICON_INFORMATION
                )

                # Generate a unique ID for the action
                action_id = wx.NewIdRef()
                self._action_id_map[action_id.GetId()] = self.local_path # Store path with ID

                # Add the action button
                if notification.AddAction(action_id.GetId(), "Show in folder"):
                    notification.Bind(wx.adv.EVT_NOTIFICATION_MESSAGE_ACTION, self.on_notification_action)

                notification.Bind(wx.adv.EVT_NOTIFICATION_MESSAGE_CLICK, self.on_notification_click)
                notification.Show()

            except Exception as e:
                wx.CallAfter(wx.MessageBox, f"Error showing notification: {e}", "Error", wx.OK | wx.ICON_ERROR, self.GetParent())

    def on_notification_action(self, event):
        """Handles clicks on notification actions."""
        action_id = event.GetId()
        local_file_path = self._action_id_map.get(action_id)

        if local_file_path:
            folder_path = os.path.dirname(local_file_path)
            try:
                subprocess.Popen(['explorer', os.path.normpath(folder_path)])
            except Exception as e:
                 wx.CallAfter(wx.MessageBox, f"Could not open folder:\n{folder_path}\nError: {e}", "Error", wx.OK | wx.ICON_ERROR, self.GetParent())
            del self._action_id_map[action_id]
        event.Skip() # Allow other potential handlers


class FolderDownloadDialog(wx.Dialog):
    def __init__(self, parent, title, total_files, total_folders, total_size):
        super().__init__(parent, title=title, size=(500, 350), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.total_files = total_files
        self.total_folders = total_folders
        self.total_size = total_size
        self.remaining_files = total_files
        self.remaining_folders = total_folders
        self.remaining_size = total_size
        self.downloaded_size = 0
        self.start_time = time.time()
        self.is_cancelled = False
        self._action_id_map = {}
        self.is_background_download = False
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.update_info, self.timer)
        self.timer.Start(1000)
        self.cancel_event = threading.Event()  # Event to signal cancellation

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.info_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE | wx.HSCROLL)
        vbox.Add(self.info_text, 1, wx.ALL | wx.EXPAND, 10)

        self.total_items_label = wx.StaticText(panel, label=f"Total: {self.total_files} Files, {self.total_folders} Folders")
        vbox.Add(self.total_items_label, 0, wx.ALL | wx.EXPAND, 10)

        self.remaining_items_label = wx.StaticText(panel, label=f"Remaining: {self.remaining_files} Files, {self.remaining_folders} Folders")
        vbox.Add(self.remaining_items_label, 0, wx.ALL | wx.EXPAND, 10)

        self.remaining_size_label = wx.StaticText(panel, label=f"Remaining Size: {self.format_size(self.remaining_size)}")
        vbox.Add(self.remaining_size_label, 0, wx.ALL | wx.EXPAND, 10)

        self.elapsed_time_label = wx.StaticText(panel, label="Elapsed Time: 00:00")
        vbox.Add(self.elapsed_time_label, 0, wx.ALL | wx.EXPAND, 10)

        self.progress_bar = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)
        vbox.Add(self.progress_bar, 0, wx.ALL | wx.EXPAND, 10)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        cancel_button = wx.Button(panel, label="Cancel")
        cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)

        background_button = wx.Button(panel, label="Download in Background")
        background_button.Bind(wx.EVT_BUTTON, self.on_background_download)
        button_sizer.Add(background_button, 0, wx.ALL, 5)
        vbox.Add(button_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        panel.SetSizer(vbox)
        self.Centre()

    def format_size(self, size_bytes):
        """Format file size to MB or KB."""
        if size_bytes < 1024 * 1024:
            size_kb = size_bytes / 1024
            return f"{size_kb:.2f} KB"
        else:
            size_mb = size_bytes / (1024 * 1024)
            return f"{size_mb:.2f} MB"

    def update_info(self, event=None):
        elapsed_seconds = int(time.time() - self.start_time)
        minutes, seconds = divmod(elapsed_seconds, 60)
        elapsed_time_str = f"Elapsed Time: {minutes:02}:{seconds:02}"
        self.elapsed_time_label.SetLabel(elapsed_time_str)

        info = f"Total: {self.total_files} Files, {self.total_folders} Folders\n"
        info += f"Remaining: {self.remaining_files} Files, {self.remaining_folders} Folders\n"
        info += f"Remaining Size: {self.format_size(self.remaining_size)}\n"
        info += f"Downloaded: {self.format_size(self.downloaded_size)} / {self.format_size(self.total_size)}\n"
        info += elapsed_time_str + "\n"
        self.info_text.SetValue(info)

    def on_cancel(self, event):
        self.is_cancelled = True
        self.cancel_event.set()
        self.timer.Stop()
        self.EndModal(wx.ID_CANCEL)

    def on_background_download(self, event):
        self.is_background_download = True
        self.Hide()

    def update_progress(self, files_done, folders_done, size_done, downloaded_size):
        if not self.is_cancelled:
            self.remaining_files = max(0, self.total_files - files_done)
            self.remaining_folders = max(0, self.total_folders - folders_done)
            self.remaining_size = max(0, self.total_size - size_done)
            self.downloaded_size = downloaded_size

            self.remaining_items_label.SetLabel(f"Remaining: {self.remaining_files} Files, {self.remaining_folders} Folders")
            self.remaining_size_label.SetLabel(f"Remaining Size: {self.format_size(self.remaining_size)}")
            progress = min(100, int((self.downloaded_size / self.total_size) * 100))
            self.progress_bar.SetValue(progress)
            self.update_info()

            if self.remaining_files == 0 and self.remaining_folders == 0:
                self.timer.Stop()
                if not self.is_background_download:
                    self.EndModal(wx.ID_OK)

    def show_notification(self, folder_name):
        if self.is_background_download:
            try:
                notification = wx.adv.NotificationMessage(
                    title="Download Complete",
                    message=f"Folder {folder_name} has been downloaded successfully.",
                    parent=self,
                    flags=wx.ICON_INFORMATION
                )
                notification.Show()
            except Exception as e:
                wx.MessageBox(f"Error showing notification: {e}", "Error", wx.OK | wx.ICON_ERROR)