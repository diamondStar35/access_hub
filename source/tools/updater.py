import wx
import requests
import os
import app_vars
import concurrent.futures
from packaging import version
import random
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
        self.total_size = file_size

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.file_label = wx.StaticText(panel, label=f"File: {file_name}")
        vbox.Add(self.file_label, 0, wx.ALL | wx.ALIGN_LEFT, 10)

        self.size_label = wx.StaticText(panel, label=f"Size: {self.format_size(file_size)}")
        vbox.Add(self.size_label, 0, wx.ALL | wx.ALIGN_LEFT, 10)

        self.remaining_label = wx.StaticText(panel, label="Remaining: -")
        vbox.Add(self.remaining_label, 0, wx.ALL | wx.ALIGN_LEFT, 10)

        self.progress_bar = wx.Gauge(panel, range=100, size=(350, 25))
        vbox.Add(self.progress_bar, 0, wx.ALL | wx.CENTER, 10)

        self.cancel_button = wx.Button(panel, label="Cancel")
        self.cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)
        vbox.Add(self.cancel_button, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(vbox)
        self.download_canceled = False

    def on_cancel(self, event):
        self.download_canceled = True
        self.EndModal(wx.ID_CANCEL)

    def update_progress(self, bytes_downloaded):
        remaining = self.total_size - bytes_downloaded
        self.remaining_label.SetLabel(f"Remaining: {self.format_size(remaining)}")

        # Calculate percentage and update the gauge
        if self.total_size > 0:
            percent = int((bytes_downloaded / self.total_size) * 100)
            self.progress_bar.SetValue(percent)
        else:
            self.progress_bar.Pulse()
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
        self.download_executor = None
        self.download_future = None


    def check_for_updates(self, silent_no_update=True):
        """Checks for updates in a separate thread."""
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(self._check_version)
            future.add_done_callback(lambda f: self._handle_update_result(f, silent_no_update))

    def _check_version(self):
        """Retrieves version information from the server and compares versions."""
        try:
            version_url = self.server_url + "/version.txt"
            response_ver = requests.get(version_url, timeout=10)
            response_ver.raise_for_status()
            server_version_str = response_ver.text.strip()

            try:
                current_v = version.parse(self.current_version)
                server_v = version.parse(server_version_str)
            except version.InvalidVersion as e:
                 error_msg = f"Invalid version format encountered: {e}"
                 return {'update_available': False, 'current_newer': False, 'error': error_msg}

            if server_v > current_v:
                download_url_path = self.server_url + "/download.txt"
                response_dl = requests.get(download_url_path, timeout=10)
                response_dl.raise_for_status()
                download_url = response_dl.text.strip()
                self.new_version = server_version_str
                self.download_url = download_url
                return {'update_available': True, 'current_newer': False, 'new_version': server_version_str, 'download_url': download_url, 'error': None}
            elif server_v < current_v:
                # Indicate current is newer, no update needed
                return {'update_available': False, 'current_newer': True, 'error': None}
            else:
                # Versions are identical, no update needed
                return {'update_available': False, 'current_newer': False, 'error': None}

        except requests.exceptions.Timeout:
             error_msg = "Connection timed out while checking for updates."
             return {'update_available': False, 'current_newer': False, 'error': error_msg}
        except requests.exceptions.RequestException as e:
            error_msg = f"Error checking for updates: {e}"
            return {'update_available': False, 'current_newer': False, 'error': error_msg}
        except Exception as e:
             error_msg = f"An unexpected error occurred during update check: {e}"
             return {'update_available': False, 'current_newer': False, 'error': error_msg}

    def _handle_update_result(self, future, silent_no_update):
        """Handles the result of the version check."""
        try:
            result = future.result()
            if result['error']:
                if not silent_no_update:
                    wx.CallAfter(wx.MessageBox, f"Failed to check for updates:\n{result['error']}", "Update Check Error", wx.OK | wx.ICON_ERROR)
                return

            if result['update_available']:
                wx.CallAfter(self._prompt_update)
            elif result['current_newer']:
                if not silent_no_update:
                    funny_messages = [
                        f"Whoa there, time traveler! You're already running version {self.current_version}, which is newer than the server's latest. Did you borrow a DeLorean?",
                        f"It seems you're from the future! Your version {self.current_version} is ahead of the curve. No update needed... yet!",
                        f"Are you a beta tester? Your version {self.current_version} is newer than what we have! Keep up the good work!",
                        f"Congratulations! You've achieved hyperspeed! Your version {self.current_version} is ahead of the official release. Slow down, Maverick!"
                    ]
                    wx.CallAfter(wx.MessageBox,
                                  random.choice(funny_messages),
                                  "Ahead of Time!",
                                  wx.OK | wx.ICON_INFORMATION)
            else:
                if not silent_no_update:
                     wx.CallAfter(wx.MessageBox,
                                  f"{app_vars.app_name} is already up to date (Version: {self.current_version}).",
                                  "No Updates Available",
                                  wx.OK | wx.ICON_INFORMATION)

        except concurrent.futures.CancelledError:
             print("Update check future was cancelled.") # Should not normally happen
        except Exception as e:
            if not silent_no_update:
                wx.CallAfter(wx.MessageBox, f"An error occurred after checking for updates: {e}", "Update Processing Error", wx.OK | wx.ICON_ERROR)

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
            self.download_future = self.download_executor.submit(self._perform_download, response, file_path, total_size)
            self.download_future.add_done_callback(lambda f: self._on_download_complete(f, file_path))

        except requests.exceptions.RequestException as e:
            print(f"Error downloading update: {e}")
            wx.CallAfter(wx.MessageBox, f"Failed to download update: {e}", "Error", wx.OK | wx.ICON_ERROR)
            if self.download_dialog:
                self.download_dialog.EndModal(wx.ID_CANCEL)

    def _perform_download(self, response, file_path, total_size):
        """Performs the actual download in chunks. Runs in executor thread."""
        bytes_downloaded = 0
        download_handle = None

        try:
            with open(file_path, "wb") as file:
                download_handle = file
                for chunk in response.iter_content(chunk_size=4096):
                    if self.download_dialog and self.download_dialog.download_canceled:
                        response.close()
                        return {'success': False, 'cancelled': True, 'error': None}
                    if chunk:
                        file.write(chunk)
                        bytes_downloaded += len(chunk)
                        if self.download_dialog:
                            wx.CallAfter(self.download_dialog.update_progress, bytes_downloaded)

            # After loop, verify if download completed fully if size was known
            if total_size > 0 and bytes_downloaded < total_size:
                 raise IOError(f"Download incomplete: Expected {total_size} bytes, got {bytes_downloaded}")

            return {'success': True, 'cancelled': False, 'error': None, 'bytes_downloaded': bytes_downloaded}

        except Exception as e:
            response.close()
            if os.path.exists(file_path):
                 try:
                     os.remove(file_path)
                 except OSError as ose:
                     print(f"Could not remove incomplete file {file_path}: {ose}")
            if self.download_dialog:
                 wx.CallAfter(self.download_dialog.EndModal, wx.ID_CANCEL)
            return {'success': False, 'cancelled': False, 'error': e}

    def _show_download_dialog(self, file_name, total_size):
        """Shows the download progress dialog."""
        self.download_dialog = DownloadDialog(None, file_name, total_size)
        self.download_dialog.ShowModal()

    def _on_download_complete(self, future, file_path):
        """Handles download completion, cancellation, or error. Runs on main thread via callback."""
        if self.download_dialog:
            wx.CallAfter(self.download_dialog.Destroy)
            self.download_dialog = None

        try:
            result = future.result()
            if result['success']:
                wx.CallAfter(self._install_update, file_path)
            elif result['cancelled']:
                wx.CallAfter(wx.MessageBox, "Update download was canceled.", "Download Canceled", wx.OK | wx.ICON_WARNING)
            else:
                # Download failed due to an error
                error = result.get('error', 'Unknown download error')
                wx.CallAfter(wx.MessageBox, f"Update download failed.\n\nError: {error}", "Download Error", wx.OK | wx.ICON_ERROR)

        except concurrent.futures.CancelledError:
             # This might happen if the executor is shut down prematurely
             wx.CallAfter(wx.MessageBox, "Update download was unexpectedly cancelled.", "Download Error", wx.OK | wx.ICON_WARNING)
             if os.path.exists(file_path): os.remove(file_path)
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"An error occurred processing the download result: {e}", "Update Error", wx.OK | wx.ICON_ERROR)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError as ose:
                    print(f"Could not remove file {file_path} after error: {ose}")
        finally:
            if self.download_executor:
                self.download_executor.shutdown(wait=False)
                self.download_executor = None
            self.download_future = None

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