import wx
import requests
import os
import app_vars
import concurrent.futures
from speech import speak
import subprocess
import shutil
import ctypes


class UpdateDialog(wx.Dialog):
    def __init__(self, parent, current_version, server_version):
        super().__init__(parent, title="Update Available", size=(400, 200))

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        vbox.Add(wx.StaticText(panel, label=f"A new version of {app_vars.app_name} is available!"), 0, wx.ALL | wx.CENTER, 10)
        vbox.Add(wx.StaticText(panel, label=f"Current Version: {current_version}."), 0, wx.ALL | wx.CENTER, 5)
        vbox.Add(wx.StaticText(panel, label=f"Available Version: {server_version}."), 0, wx.ALL | wx.CENTER, 5)
        vbox.Add(wx.StaticText(panel, label="Would you like to update now?"), 0, wx.ALL | wx.CENTER, 10)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        yes_button = wx.Button(panel, label="Yes")
        yes_button.Bind(wx.EVT_BUTTON, self.on_yes)
        hbox.Add(yes_button, 0, wx.ALL | wx.CENTER, 5)

        no_button = wx.Button(panel, label="No")
        no_button.Bind(wx.EVT_BUTTON, self.on_no)
        hbox.Add(no_button, 0, wx.ALL | wx.CENTER, 5)

        vbox.Add(hbox, 0, wx.ALL | wx.CENTER, 10)
        panel.SetSizer(vbox)

    def on_yes(self, event):
        self.EndModal(wx.ID_YES)

    def on_no(self, event):
        self.EndModal(wx.ID_NO)

class DownloadDialog(wx.Dialog):
    def __init__(self, parent, file_name, file_size):
        super().__init__(parent, title="Downloading Update", size=(400, 250))

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.file_label = wx.StaticText(panel, label=f"File: {file_name}")
        vbox.Add(self.file_label, 0, wx.ALL | wx.ALIGN_LEFT, 10)

        self.size_label = wx.StaticText(panel, label=f"Size: {self.format_size(file_size)}")
        vbox.Add(self.size_label, 0, wx.ALL | wx.ALIGN_LEFT, 10)

        self.remaining_label = wx.StaticText(panel, label="Remaining: -")
        vbox.Add(self.remaining_label, 0, wx.ALL | wx.ALIGN_LEFT, 10)

        self.progress_bar = wx.Gauge(panel, range=file_size, size=(350, 25))
        vbox.Add(self.progress_bar, 0, wx.ALL | wx.CENTER, 10)

        self.cancel_button = wx.Button(panel, label="Cancel")
        self.cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)
        vbox.Add(self.cancel_button, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(vbox)
        self.download_canceled = False

    def on_cancel(self, event):
        self.download_canceled = True
        self.EndModal(wx.ID_CANCEL)

    def update_progress(self, bytes_downloaded, total_bytes):
        remaining = total_bytes - bytes_downloaded
        self.remaining_label.SetLabel(f"Remaining: {self.format_size(remaining)}")
        self.progress_bar.SetValue(bytes_downloaded)
        wx.Yield()

    def format_size(self, bytes):
        if bytes < 1024:
            return f"{bytes} B"
        elif bytes < 1024**2:
            return f"{bytes / 1024:.2f} KB"
        elif bytes < 1024**3:
            return f"{bytes / (1024**2):.2f} MB"
        else:
            return f"{bytes / (1024**3):.2f} GB"

class Updater:
    def __init__(self, server_url, current_version):
        self.server_url = server_url
        self.current_version = current_version
        self.download_url = None
        self.new_version = None
        self.download_dialog = None

    def check_for_updates(self):
        """Checks for updates in a separate thread."""
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(self._check_version)
            future.add_done_callback(self._handle_update_result)

    def _check_version(self):
        """Retrieves version information from the server."""
        try:
            response = requests.get(self.server_url + "/version.txt")
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            self.new_version = response.text.strip()
            if self.new_version != self.current_version:
              response = requests.get(self.server_url + "/download.txt")
              response.raise_for_status()
              self.download_url = response.text.strip()
            return self.new_version != self.current_version
        except requests.exceptions.RequestException as e:
            print(f"Error checking for updates: {e}")
            wx.MessageBox(f"Failed to check for updates: {e}", "Error", wx.OK | wx.ICON_ERROR)
            return False

    def _handle_update_result(self, future):
        """Handles the result of the version check."""
        try:
            update_available = future.result()
            if update_available:
                wx.CallAfter(self._prompt_update)
        except Exception as e:
            print(f"Error in update check: {e}")

    def _prompt_update(self):
        """Prompts the user to update."""
        dialog = UpdateDialog(None, self.current_version, self.new_version)
        result = dialog.ShowModal()
        dialog.Destroy()
        if result == wx.ID_YES:
            self._download_and_install()

    def _download_and_install(self):
        """Downloads the update and starts the installation."""
        try:
            # Get the AppData directory for the app
            appdata_dir = os.path.join(wx.StandardPaths.Get().GetUserConfigDir(), app_vars.app_name)
            updates_dir = os.path.join(appdata_dir, "updates")

            if not os.path.exists(updates_dir):
                os.makedirs(updates_dir)

            file_name = os.path.basename(self.download_url)
            file_path = os.path.join(updates_dir, file_name)
            response = requests.get(self.download_url, stream=True)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))

            wx.CallAfter(self._show_download_dialog, file_name, total_size)
            self.download_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            self.download_future = self.download_executor.submit(self._perform_download, response, file_path)
            self.download_future.add_done_callback(lambda f: self._on_download_complete(f, file_path))

        except requests.exceptions.RequestException as e:
            print(f"Error downloading update: {e}")
            wx.CallAfter(wx.MessageBox, f"Failed to download update: {e}", "Error", wx.OK | wx.ICON_ERROR)
            if self.download_dialog:
                self.download_dialog.EndModal(wx.ID_CANCEL)

    def _perform_download(self, response, file_path):
        """Performs the actual download in chunks."""
        bytes_downloaded = 0
        total_size = int(response.headers.get('content-length', 0))
        try:
            with open(file_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.download_dialog and self.download_dialog.download_canceled:
                        print("Download canceled by user.")
                        return
                    if chunk:
                        file.write(chunk)
                        bytes_downloaded += len(chunk)
                        if self.download_dialog:
                            wx.CallAfter(self.download_dialog.update_progress, bytes_downloaded, total_size)
        except Exception as e:
            print(f"An error occurred during download: {e}")
            wx.CallAfter(wx.MessageBox, f"An error occurred during download: {e}", "Error", wx.OK | wx.ICON_ERROR)
        finally:
            if self.download_executor:
                self.download_executor.shutdown(wait=False)
        return bytes_downloaded

    def _show_download_dialog(self, file_name, total_size):
        """Shows the download progress dialog."""
        self.download_dialog = DownloadDialog(None, file_name, total_size)
        self.download_dialog.ShowModal()

    def _on_download_complete(self, future, file_path):
        """Handles download completion or cancellation."""
        try:
            if self.download_dialog:
                self.download_dialog.Destroy()
            if future.result() and not (self.download_dialog and self.download_dialog.download_canceled):
                wx.CallAfter(self._install_update, file_path)
            else:
                os.remove(file_path)  # Delete incomplete file
                if not (self.download_dialog and self.download_dialog.download_canceled):
                    wx.CallAfter(wx.MessageBox, "Update download failed or was canceled.", "Download Error", wx.OK | wx.ICON_WARNING)
        except Exception as e:
            print(f"Error in download completion: {e}")

    def _install_update(self, file_path):
        """Starts the update installer."""
        wx.MessageBox("Update downloaded successfully!\n\nThe installer will now start.", "Update Complete", wx.OK | wx.ICON_INFORMATION)
        try:
            # Use ShellExecuteW to launch the installer with elevation
            ctypes.windll.shell32.ShellExecuteW(None, "runas", file_path, None, None, 1)
            wx.CallLater(2000, wx.Exit)
        except Exception as e:
            print(f"Error launching installer: {e}")
            wx.MessageBox(f"Failed to launch installer: {e}", "Error", wx.OK | wx.ICON_ERROR)