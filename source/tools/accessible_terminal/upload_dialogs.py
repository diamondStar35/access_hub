import wx
import time
import threading
import os

class UploadDialog(wx.Dialog):
    def __init__(self, parent, title, file_size):
        super().__init__(parent, title=title, size=(500, 3500), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.file_size = file_size
        self.start_time = time.time()
        self.is_cancelled = False
        self.is_background_upload = False
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.update_info, self.timer)
        self.timer.Start(1000)
        self.cancel_event = threading.Event()  # Event to signal cancellation

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.info_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE | wx.HSCROLL)
        vbox.Add(self.info_text, 1, wx.ALL | wx.EXPAND, 10)

        file_size_label = wx.StaticText(panel, label=f"File Size: {self.format_size(self.file_size)}")
        vbox.Add(file_size_label, 0, wx.ALL | wx.EXPAND, 10)

        self.remaining_size_label = wx.StaticText(panel, label=f"Remaining: {self.format_size(self.file_size)}")
        vbox.Add(self.remaining_size_label, 0, wx.ALL | wx.EXPAND, 10)

        self.elapsed_time_label = wx.StaticText(panel, label="Elapsed Time: 00:00")
        vbox.Add(self.elapsed_time_label, 0, wx.ALL | wx.EXPAND, 10)

        self.progress_bar = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)
        vbox.Add(self.progress_bar, 0, wx.ALL | wx.EXPAND, 10)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        cancel_button = wx.Button(panel, label="Cancel")
        cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)

        background_button = wx.Button(panel, label="Upload in Background")
        background_button.Bind(wx.EVT_BUTTON, self.on_background_upload)
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

        info = f"File Size: {self.format_size(self.file_size)}\n"
        info += f"Remaining: {self.remaining_size_label.GetLabel().replace('Remaining: ', '')}\n"
        info += elapsed_time_str + "\n"
        info += f"Progress: {self.progress_bar.GetValue()}%\n"
        self.info_text.SetValue(info)

    def on_cancel(self, event):
        self.is_cancelled = True
        self.cancel_event.set()
        self.timer.Stop()
        self.EndModal(wx.ID_CANCEL)

    def on_background_upload(self, event):
        self.is_background_upload = True
        self.Hide()

    def update_progress(self, current, total):
        if not self.is_cancelled:
            progress = min(100, int((current / total) * 100))
            self.progress_bar.SetValue(progress)
            remaining = total - current
            self.remaining_size_label.SetLabel(f"Remaining: {self.format_size(remaining)}")
            self.update_info()

            if progress == 100:
                self.timer.Stop()
                if not self.is_background_upload:
                  self.EndModal(wx.ID_OK)

    def show_notification(self, file_name):
        if self.is_background_upload:
            try:
                notification = wx.adv.NotificationMessage(
                    title="Upload Complete",
                    message=f"{file_name} has been uploaded successfully.",
                    parent=self,
                    flags=wx.ICON_INFORMATION
                )
                notification.Show()
            except Exception as e:
                wx.MessageBox(f"Error showing notification: {e}", "Error", wx.OK | wx.ICON_ERROR)

class FolderUploadDialog(wx.Dialog):
    def __init__(self, parent, title, total_files, total_folders, total_size):
        super().__init__(parent, title=title, size=(500, 350), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.total_files = total_files
        self.total_folders = total_folders
        self.total_size = total_size
        self.remaining_files = total_files
        self.remaining_folders = total_folders
        self.remaining_size = total_size
        self.start_time = time.time()
        self.is_cancelled = False
        self.is_background_upload = False
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.update_info, self.timer)
        self.timer.Start(1000)
        self.cancel_event = threading.Event()

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

        background_button = wx.Button(panel, label="Upload in Background")
        background_button.Bind(wx.EVT_BUTTON, self.on_background_upload)
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
        info += elapsed_time_str + "\n"
        self.info_text.SetValue(info)

    def on_cancel(self, event):
        self.is_cancelled = True
        self.cancel_event.set()
        self.timer.Stop()
        self.EndModal(wx.ID_CANCEL)

    def on_background_upload(self, event):
        self.is_background_upload = True
        self.Hide()

    def update_progress(self, files_done, folders_done, size_done, file_progress=0):
        if not self.is_cancelled:
            self.remaining_files = max(0, self.total_files - files_done)
            self.remaining_folders = max(0, self.total_folders - folders_done)
            self.remaining_size = max(0, self.total_size - size_done)

            self.remaining_items_label.SetLabel(f"Remaining: {self.remaining_files} Files, {self.remaining_folders} Folders")
            self.remaining_size_label.SetLabel(f"Remaining Size: {self.format_size(self.remaining_size)}")
            self.update_info()

            if self.remaining_files == 0 and self.remaining_folders == 0:
                self.timer.Stop()
                if not self.is_background_upload:
                    self.EndModal(wx.ID_OK)
            self.progress_bar.SetValue(file_progress)

    def update_file_progress(self, current, total):
        if not self.is_cancelled:
            progress = min(100, int((current / total) * 100))
            self.progress_bar.SetValue(progress)

    def show_notification(self, folder_name):
        if self.is_background_upload:
            try:
                notification = wx.adv.NotificationMessage(
                    title="Upload Complete",
                    message=f"Folder {folder_name} has been uploaded successfully.",
                    parent=self,
                    flags=wx.ICON_INFORMATION
                )
                notification.Show()
            except Exception as e:
                wx.MessageBox(f"Error showing notification: {e}", "Error", wx.OK | wx.ICON_ERROR)