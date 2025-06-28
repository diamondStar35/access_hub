import wx
import wx.adv
import wx.lib.newevent
import app_guard
from app_guard import AppGuard, AppGuardError, IPCMsg
import os, sys, subprocess, re, platform, shutil
import app_vars
from gui.settings import SettingsDialog, GeneralSettingsPanel, AISettingsPanel, load_app_config, get_settings_path
from gui.dialogs import AccessTaskBarIcon, ContactDialog, AboutDialog
from tools.text_utils.text_utils import TextUtilitiesApp
from tools.text_utils.json_viewer import JsonViewer
from tools.text_utils.xml_viewer import XMLViewer
from tools.shutdown_control import ShutdownControl
from tools.network_player.network_player import NetworkPlayerFrame
from tools.network_player.settings import YoutubeSettings
from tools.password_doctor import PasswordDoctorDialog
from tools.task_scheduler.task_scheduler import TaskScheduler
from tools.eleven_labs.eleven_labs import ElevenLabs
from tools.accessible_terminal.session_viewer import SessionViewer
from tools.speed_test import SpeedTest
from tools.online_tts.online_tts import OnlineTTS
from tools.file_utils.file_tools import FileTools
from tools.gemini.chat import GeminiChat
from tools.updater import Updater
from speech import speak
import random
import time
import speech_recognition as sr
import threading
import concurrent.futures
import keyboard
import winsound
import ctypes
from ctypes import wintypes
import pyaudio
import io
import wave


# Constants for IPC
APP_GUARD_HANDLE_NAME = f"{app_vars.app_name.replace(' ', '_')}_AppGuardInstance"
IPC_MSG_OPEN_FILE = f"{APP_GUARD_HANDLE_NAME}_OpenFile"

# Load user32.dll and functions
user32 = ctypes.WinDLL('user32', use_last_error=True)
GetForegroundWindow = user32.GetForegroundWindow
GetForegroundWindow.restype = wintypes.HWND
GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
GetWindowThreadProcessId.restype = wintypes.DWORD
GetKeyboardLayout = user32.GetKeyboardLayout
GetKeyboardLayout.argtypes = [wintypes.DWORD]
GetKeyboardLayout.restype = wintypes.HKL

# Load kernel32.dll for LCID conversion
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
LCIDToLocaleName = kernel32.LCIDToLocaleName
LCIDToLocaleName.argtypes = [wintypes.DWORD, wintypes.LPWSTR, wintypes.INT, wintypes.DWORD]
LCIDToLocaleName.restype = wintypes.INT

def get_keyboard_language():
    hwnd = GetForegroundWindow()  # Get the handle of the foreground window
    thread_id = GetWindowThreadProcessId(hwnd, None)  # Get thread ID of the foreground window
    layout = GetKeyboardLayout(thread_id)  # Get the keyboard layout handle (HKL)
    # Extract language ID from HKL
    language_id = layout & 0xFFFF
    # Convert LCID to a readable name
    buffer = ctypes.create_unicode_buffer(85)  # Buffer for LCIDToLocaleName
    if LCIDToLocaleName(language_id, buffer, len(buffer), 0):
        return buffer.value  # Return the readable language
    else:
        return f"Language ID: {language_id} (0x{language_id:X})"  # Fallback: Show ID


class AccessHub(wx.Frame):
    def __init__(self, parent, title, launched_for_file=False):
        super(AccessHub, self).__init__(parent, title=title, size=(800, 600))
        self.launched_for_file = launched_for_file
        self.direct_file_viewer_frame = None
        self.tools_list = [
            ("Text Tools", "Manipulate and analyze text content.", self.on_text_utilities),
            ("Task Scheduler", "Schedule tasks to run automatically.", self.on_task_scheduler),
            ("Shutdown Control", "Schedule system shutdown, restart, or logoff.", self.on_shutdown_control),
            ("Password Doctor", "Analyze password strength and check for breaches.", self.on_password_doctor),
            ("Online player", "Play streams from YouTube or direct links.", self.on_network_player),
            ("ElevenLabs", "Generate speech using ElevenLabs AI.", self.on_elevenlabs),
            ("Accessible SSH Terminal", "Connect to SSH servers accessibly.", self.on_ssh_terminal),
            ("Internet Speed Test", "Measure your internet connection speed.", self.on_speed_test),
            ("Online Text to Speech", "Convert text to speech using online services.", self.on_online_tts),
            ("File Tools", "Access file management utilities.", self.on_file_tools),
            ("Gemini Chat", "Chat with Google's Gemini model.", self.on_gemini_chat),
        ]

        self.child_frames = [] # List to store child frames
        self.task_scheduler_instance = TaskScheduler(self)
        self.is_recording = False
        self.audio_frames = []
        self.p = pyaudio.PyAudio()
        self.recognizer = sr.Recognizer()
        self.recording_thread = None
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.config = load_app_config()

        # taskbar icon
        self.tbIcon = AccessTaskBarIcon(self)
        self.initialize_notifications()
        self.create_menu_bar()

        # Create a panel to hold the buttons
        panel = wx.Panel(self, wx.ID_ANY)

        # Create a sizer for flexible layout
        sizer = wx.BoxSizer(wx.VERTICAL)

        title_text = wx.StaticText(panel, label="Access Hub", style=wx.ALIGN_CENTER)
        title_text.SetFont(wx.Font(18, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        title_text.SetForegroundColour("#333333") # Dark gray text


        # Add some spacing
        sizer.AddSpacer(20)
        sizer.Add(title_text, 0, wx.ALL | wx.EXPAND, 10)
        sizer.AddSpacer(15)

        # Create the ListCtrl
        self.tool_list_ctrl = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VRULES | wx.LC_HRULES)
        self.tool_list_ctrl.SetFont(wx.Font(14, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        self.tool_list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_run_tool)

        # Add columns
        self.tool_list_ctrl.InsertColumn(0, "Tool Name", width=200)
        self.tool_list_ctrl.InsertColumn(1, "Description", width=450)

        # Populate the list
        for index, (name, description, handler) in enumerate(self.tools_list):
            # Get the current item count to determine the insertion index for appending
            current_item_count = self.tool_list_ctrl.GetItemCount()
            list_index = self.tool_list_ctrl.InsertItem(current_item_count, name)
            self.tool_list_ctrl.SetItem(list_index, 1, description)
            self.tool_list_ctrl.SetItemData(list_index, index)
        sizer.Add(self.tool_list_ctrl, 1, wx.ALL | wx.EXPAND, 10)

        run_button = wx.Button(panel, label="Run")
        run_button.Bind(wx.EVT_BUTTON, self.on_run_tool)
        sizer.Add(run_button, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(sizer)

        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND | wx.ALL, 0) # Add panel, allow expansion, no extra border here
        self.SetSizer(frame_sizer)

        # Finalize the layout
        self.Layout()
        self.Fit()   
        self.Centre()
        self.Show(True)
        self.start_hotkey_listener()
        check_updates = self.config.get('General', {}).get('check_for_updates', 'True')
        check_updates = check_updates.lower() == 'true'
        if check_updates:
            self.check_for_updates()


    def on_run_tool(self, event):
        """Handles running the tool selected in the list control."""
        selected_index = self.tool_list_ctrl.GetFirstSelected()
        if selected_index != -1:
            tool_data_index = self.tool_list_ctrl.GetItemData(selected_index)
            # Get the handler using the retrieved index
            _, _, handler = self.tools_list[tool_data_index]
            if callable(handler):
                handler(event)
            else:
                wx.MessageBox(f"Error: No valid action found for selected tool.", "Error", wx.OK | wx.ICON_ERROR)

    def initialize_notifications(self):
        """
        Sets up wx.adv.NotificationMessage integration based on platform.
        Should be called once after the TaskBarIcon is created.
        """
        try:
            if platform.system() == "Windows":
                if not wx.adv.NotificationMessage.MSWUseToasts():
                    print("Warning: Could not enable MSW Toast notifications.")
                wx.adv.NotificationMessage.UseTaskBarIcon(self.tbIcon)

        except Exception as e:
            print(f"Error initializing notification system: {e}")
            wx.MessageBox(f"Could not fully initialize native notifications: {e}", "Notification Warning", wx.OK | wx.ICON_WARNING)

    def create_menu_bar(self):
        menu_bar = wx.MenuBar()

        app_menu = wx.Menu()
        settings_item = app_menu.Append(wx.ID_ANY, "&Settings\talt+s", "Open the settings dialog")
        self.Bind(wx.EVT_MENU, self.on_settings, settings_item)

        updates_menu = wx.Menu()
        check_app_update_item = updates_menu.Append(wx.ID_ANY, "Check for &App Updates", "Check for updates to Access Hub")
        self.Bind(wx.EVT_MENU, lambda event: self.check_for_updates(silent_no_update=False), check_app_update_item)

        check_yt_dlp_update_item = updates_menu.Append(wx.ID_ANY, "Check for &yt-dlp Update", "Check for updates to yt-dlp")
        self.Bind(wx.EVT_MENU, self.on_check_yt_dlp_update, check_yt_dlp_update_item)
        app_menu.AppendSubMenu(updates_menu, "&Updates")

        open_config_dir_item = app_menu.Append(wx.ID_ANY, "&Open app configuration folder", "Open the folder containing application settings")
        self.Bind(wx.EVT_MENU, self.on_open_config_directory, open_config_dir_item)

        quit_item = app_menu.Append(wx.ID_EXIT, "&Quit", "Quit the application")
        self.Bind(wx.EVT_MENU, self.on_quit, quit_item)

        help_menu = wx.Menu()
        documentation_item = help_menu.Append(wx.ID_ANY, "&Documentation\tf1", "Open the documentation in your web browser")
        self.Bind(wx.EVT_MENU, self.on_documentation, documentation_item)

        about_item = help_menu.Append(wx.ID_ABOUT, "&About", "Information about this application")
        self.Bind(wx.EVT_MENU, self.on_about, about_item)

        recent_changes_item = help_menu.Append(wx.ID_ANY, "&Recent changes\tf2", "View recent changes")
        self.Bind(wx.EVT_MENU, self.on_recent_changes, recent_changes_item)

        contact_item = help_menu.Append(wx.ID_ANY, "&Contact Us", "Contact the developer")
        self.Bind(wx.EVT_MENU, self.on_contact_us, contact_item)

        menu_bar.Append(app_menu, "&App")
        menu_bar.Append(help_menu, "&Help")
        self.SetMenuBar(menu_bar)

    def start_hotkey_listener(self):
        """Start listening for global hotkey to toggle voice recording."""
        keyboard.add_hotkey("shift+ctrl+h", self.toggle_recording)

    def toggle_recording(self):
        """Toggle voice recording on/off."""
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        """Start recording audio."""
        self.is_recording = True
        self.audio_frames = []
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=24000,
            input=True,
            frames_per_buffer=1024
        )
        winsound.Beep(1000, 100)
        self.recording_thread = threading.Thread(target=self.record_audio)
        self.recording_thread.start()

    def record_audio(self):
        """Capture audio data in chunks."""
        while self.is_recording:
            try:
                data = self.stream.read(1024, exception_on_overflow=False)
                self.audio_frames.append(data)
            except Exception as e:
                print(f"Error during recording: {e}")
                break

    def stop_recording(self):
        """Stop recording and process the audio."""
        self.is_recording = False
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join()
        self.stream.stop_stream()
        self.stream.close()
        winsound.Beep(1500, 100)  # Beep to indicate recording stop
        threading.Thread(target=self.process_audio).start()

    def process_audio(self):
        """Process the recorded audio and perform speech recognition."""
        # Convert audio frames into a valid WAV format
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(1)  # Mono audio
            wf.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(24000)
            wf.writeframes(b''.join(self.audio_frames))

        buffer.seek(0)  # Rewind the buffer to the beginning

        try:
            with sr.AudioFile(buffer) as source:
                audio = self.recognizer.record(source)
                result = self.recognizer.recognize_google(audio, language=get_keyboard_language())
                wx.CallAfter(self.type_text, result)
        except sr.UnknownValueError as e:
                wx.CallAfter(speak, f"Could not understand what you're trying to say. Please try again.", interrupt=True)
        except sr.RequestError:
                wx.CallAfter(speak, "Speech recognition service is unavailable at the moment.", interrupt=True)

    def type_text(self, text):
        for char in text:
            keyboard.write(char)
            time.sleep(0.05)

    def get_yt_dlp_path(self):
        """Finds the path to yt-dlp.exe, checking multiple locations."""
        # Check next to script/executable first
        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        yt_dlp_exe_path = os.path.join(base_dir, 'yt-dlp.exe')
        if os.path.exists(yt_dlp_exe_path):
            return yt_dlp_exe_path

        # Check in AppData/Local (where yt-dlp --update might place it)
        appdata_local = os.getenv('LOCALAPPDATA')
        if appdata_local:
            alt_path = os.path.join(appdata_local, 'yt-dlp', 'yt-dlp.exe')
            if os.path.exists(alt_path):
                return alt_path

        # Check if it's in the system PATH
        path_exe = shutil.which('yt-dlp.exe')
        if path_exe:
            print("Info: yt-dlp.exe found in system PATH.")
            return path_exe
        return None

    def run_yt_dlp_command(self, args, timeout=120): # Default timeout
        """Runs a yt-dlp command with a timeout and returns output."""
        yt_dlp_path = self.get_yt_dlp_path()
        if not yt_dlp_path:
            return -3, "", "yt-dlp.exe not found." # Specific code for not found

        command = [yt_dlp_path] + args
        process = None
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                startupinfo=startupinfo
            )
            stdout, stderr = process.communicate(timeout=timeout)
            return process.returncode, stdout, stderr
        except FileNotFoundError:
            # Should be caught by get_yt_dlp_path, but handle defensively
            return -3, "", f"Error: Command not found - {yt_dlp_path}"
        except subprocess.TimeoutExpired:
            if process:
                process.kill()
                try:
                    # Attempt to grab final output after kill
                    stdout, stderr = process.communicate(timeout=5)
                except Exception:
                    stdout, stderr = "", ""
            else:
                stdout, stderr = "", ""
            # Return specific timeout code
            return -2, stdout, f"yt-dlp command timed out after {timeout} seconds.\n{stderr}"
        except Exception as e:
            stdout, stderr = "", ""
            if process:
                try:
                    stdout, stderr = process.communicate(timeout=5)
                except Exception:
                    pass
            return -1, stdout, f"An unexpected error occurred running yt-dlp: {e}\n{stderr}"

    def check_for_updates(self, silent_no_update=True):
        """Initiates the update check."""
        server_url = "http://raw.githubusercontent.com/diamondStar35/access_hub/main"
        # Get the AppData directory
        appdata_dir = os.path.join(wx.StandardPaths.Get().GetUserConfigDir(), app_vars.app_name)
        updates_dir = os.path.join(appdata_dir, "updates")
        # Remove the "updates" folder if it exists
        if os.path.exists(updates_dir):
            try:
                shutil.rmtree(updates_dir)
            except Exception as e:
                print(f"Error removing 'updates' folder: {e}")

        updater = Updater(server_url, app_vars.app_version)
        self.executor.submit(updater.check_for_updates, silent_no_update)

    def on_check_yt_dlp_update(self, event):
        yt_dlp_path = self.get_yt_dlp_path()
        if not yt_dlp_path:
            wx.MessageBox(
                f"yt-dlp.exe could not be found in the application directory.",
                "yt-dlp Not Found", wx.OK | wx.ICON_ERROR
            )
            return

        # Check if yt-dlp.exe is writable
        if not os.access(yt_dlp_path, os.W_OK):
             wx.MessageBox(
                f"Cannot write to yt-dlp.exe located at:\n{yt_dlp_path}\n\n"
                "The application may not have permission to update it. "
                "Try running Access Hub as administrator if you want to update.",
                "Permission Error", wx.OK | wx.ICON_WARNING, parent=self
             )
             return

        self.config = load_app_config()
        channel = self.config.get('YouTube', {}).get('yt_dlp_update_channel', 'stable')

        update_dialog = wx.ProgressDialog(
            "Updating yt-dlp",
            f"Preparing update check for '{channel}' channel...",
            maximum=100, # Will just pulse
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME
        )
        update_dialog.Show() # Show it immediately
        wx.Yield()

        update_thread = threading.Thread(target=self._perform_yt_dlp_update_action,
                                         args=(channel, update_dialog),
                                         daemon=True)
        update_thread.start()

    def _perform_yt_dlp_update_action(self, channel, update_dialog):
        """Worker function to run yt-dlp update commands."""
        initial_version = "Unknown"
        cancelled = False

        def safely_destroy_dialog(dialog):
            """Helper to destroy dialog safely from worker thread."""
            if dialog and dialog.IsShown():
                try:
                    dialog.Destroy()
                except (wx.wxAssertionError, RuntimeError) as err:
                    print(f"Ignoring error destroying progress dialog: {err}")

        try:
            # Check if cancelled before starting
            if update_dialog.WasCancelled():
                 print("yt-dlp update cancelled before starting.")
                 cancelled = True
                 final_code, final_out, final_err = -10, "", "Update cancelled by user."
                 return

            wx.CallAfter(update_dialog.Pulse, "Checking current yt-dlp version...")
            speak("Checking current yt-dlp version...")
            code_curr, out_curr, err_curr = self.run_yt_dlp_command(['--version'])
            if cancelled or update_dialog.WasCancelled(): return

            if code_curr == 0 and out_curr.strip():
                initial_version = out_curr.strip()
                display_version = initial_version
                if '@' in display_version:
                    parts = display_version.split('@')
                    if len(parts) > 1:
                        display_version = f"{parts[0]}@{parts[1][:15]}" # e.g., nightly@2025.03.31.2143
                wx.CallAfter(update_dialog.Pulse, f"Current: {display_version}. Fetching update info for '{channel}'...")
                speak(f"Current version: {display_version}. Initiating update...")
            elif code_curr == -2:
                wx.CallAfter(update_dialog.Pulse, f"Timeout getting current version. Proceeding with update check for '{channel}'...")
                print(f"yt-dlp version check timed out. Error: {err_curr}")
            elif code_curr == -3:
                # yt-dlp not found - show result and exit thread
                wx.CallAfter(self._show_yt_dlp_update_final_result, code_curr, out_curr, err_curr, initial_version, channel)
                return
            else:
                wx.CallAfter(update_dialog.Pulse, f"Could not get current version (Code: {code_curr}). Attempting update to '{channel}' anyway...")
                print(f"yt-dlp version check failed. Stderr: {err_curr}, Stdout: {out_curr}")

            if cancelled or update_dialog.WasCancelled():
                cancelled = True
                final_code, final_out, final_err = -10, "", "Update cancelled by user."
                return

            wx.CallAfter(update_dialog.Pulse, f"Running update process to channel (channel: {channel}). This may take some time...")
            update_command = ['--update-to', f'{channel}@latest']
            code, out, err = self.run_yt_dlp_command(update_command, timeout=300)
            final_code, final_out, final_err = code, out, err

        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"An unexpected error occurred during the update check: {e}", "Update Error", wx.OK | wx.ICON_ERROR, parent=self.frame) # Assuming self.frame exists, otherwise pass None or self
            final_code, final_out, final_err = -11, "", f"An unexpected error occurred during the update check: {e}" # Specific thread error code
        finally:
            wx.CallAfter(self._finalize_yt_dlp_update, update_dialog, final_code, final_out, final_err, initial_version, channel, cancelled)

    def _finalize_yt_dlp_update(self, dialog_to_destroy, returncode, stdout, stderr, old_version, channel, was_cancelled):
        """Runs on main thread. Destroys dialog THEN shows result message."""
        if dialog_to_destroy:
            try:
                dialog_to_destroy.Destroy()
            except (wx.wxAssertionError, RuntimeError) as err:
                 print(f"Ignoring error destroying progress dialog during finalization: {err}")

        if returncode == -11:
             wx.MessageBox(f"Update process failed due to an internal error.\n\nDetails: {stderr}", "Update Error", wx.OK | wx.ICON_ERROR, parent=self)
        else:
            self._show_yt_dlp_update_final_result(returncode, stdout, stderr, old_version, channel)

    def _show_yt_dlp_update_final_result(self, returncode, stdout, stderr, old_version, channel):
        """Displays the final result of the yt-dlp update check in a MessageBox."""
        new_version = old_version # Assume no change initially
        success = False
        message = ""
        icon = wx.ICON_ERROR # Default to error

        # Normalize outputs for reliable checks
        stdout_lower = stdout.strip().lower() if stdout else ""
        stderr_lower = stderr.strip().lower() if stderr else ""

        if returncode == 0:
            updated_match = re.search(r'updated yt-dlp to ([\w.@-]+)', stdout_lower)
            up_to_date_match = ("already up to date" in stdout_lower) or ("is up to date" in stdout_lower)

            if updated_match:
                success = True
                new_version = updated_match.group(1).strip() # Get reported version
                message = f"yt-dlp updated successfully to version '{new_version}' (from '{old_version}') on the '{channel}' channel."
                icon = wx.ICON_INFORMATION
            elif up_to_date_match:
                success = True
                current_ver_match = re.search(r'up to date \(([\w.@-]+)\)', stdout_lower)
                current_version = current_ver_match.group(1).strip() if current_ver_match else old_version
                message = f"yt-dlp is already up to date on the '{channel}' channel.\nCurrent Version: {current_version}"
                icon = wx.ICON_INFORMATION
            else:
                message = f"yt-dlp command finished successfully (Code: 0), but the output was unexpected. Update status uncertain.\n\nOutput:\n{stdout}\n\nError Output:\n{stderr}"
                icon = wx.ICON_WARNING

        elif returncode == -2: # Specific timeout code
            message = f"The yt-dlp update command timed out.\n\nLast Output:\n{stdout}\n\nError Output:\n{stderr}"
            icon = wx.ICON_ERROR
        elif returncode == -3: # Specific not found code
             message = f"Failed to run update: yt-dlp.exe could not be found.\nPlease ensure it is placed correctly or available in PATH."
             icon = wx.ICON_ERROR
        else:
            message = f"Failed to update yt-dlp on the '{channel}' channel (Exit Code: {returncode}).\n\nError Output:\n{stderr}\n\nStandard Output:\n{stdout}"
            # Append common hints based on error output
            if "urlopen error" in stderr_lower or "[winerror" in stderr_lower:
                message += "\n\n(This often indicates a network connection issue or firewall blocking the connection.)"
            elif "permissionerror" in stderr_lower or "access is denied" in stderr_lower:
                 message += "\n\n(This suggests Access Hub doesn't have permission to modify yt-dlp.exe. Try running as administrator.)"
            elif "error: externally-managed environment" in stderr_lower:
                 message += "\n\n(This usually means yt-dlp was installed via a system package manager like pipx or brew. Use the package manager to update it instead.)"

            icon = wx.ICON_ERROR

        title = "Info"
        if icon == wx.ICON_WARNING: title = "yt-dlp Update Status Uncertain"
        if icon == wx.ICON_ERROR: title = "yt-dlp Update Failed"
        wx.MessageBox(message, title, wx.OK | icon, self)


    def open_file_in_viewer(self, filepath):
        if not filepath or not os.path.exists(filepath):
            if self.launched_for_file:
                wx.MessageBox(f"File not found: {filepath}\nAccessHub will now exit.", "Error", wx.OK | wx.ICON_ERROR)
                wx.CallAfter(self.perform_app_exit)
            return

        _, ext = os.path.splitext(filepath.lower())
        viewer_frame = None
        if ext == ".json":
            viewer_frame = JsonViewer(self, title=f"JSON Viewer - {os.path.basename(filepath)}", filepath=filepath)
        elif ext == ".xml":
            viewer_frame = XMLViewer(self, title=f"XML Viewer - {os.path.basename(filepath)}", filepath=filepath)
        if viewer_frame:
            if self.launched_for_file:
                self.direct_file_viewer_frame = viewer_frame
            self.add_child_frame(viewer_frame)
            viewer_frame.Show()
        elif self.launched_for_file:
            wx.MessageBox(f"Unsupported file type: {ext}\nAccessHub will now exit.", "Cannot Open File", wx.OK | wx.ICON_WARNING, None)
            wx.CallAfter(self.perform_app_exit)

    def handle_ipc_open_file(self, ipc_msg_data: str):
        """Handles IPC message to open a file, received by the primary instance."""
        filepath = ipc_msg_data
        if filepath and os.path.exists(filepath) and os.path.isfile(filepath):
            if not self.IsShown():
                self.Show(True)
            self.Raise()
            self.open_file_in_viewer(filepath)
        else:
            wx.CallAfter(wx.MessageBox,
                          f"Received request to open an invalid or non-existent file: {filepath}",
                          "File Error", wx.OK | wx.ICON_ERROR, parent=self)

    def on_text_utilities(self, event):
        text_utils_app = TextUtilitiesApp(None, title="Text Utilities")
        self.add_child_frame(text_utils_app)
        self.manage_main_window_visibility(text_utils_app)
        text_utils_app.Show()

    def on_shutdown_control(self, event):
        shutdown_control = ShutdownControl()
        self.add_child_frame(shutdown_control)
        self.manage_main_window_visibility(shutdown_control)
        shutdown_control.Show()

    def on_password_doctor(self, event):
        password_doctor = PasswordDoctorDialog(self)
        self.add_child_frame(password_doctor)
        self.manage_main_window_visibility(password_doctor)
        password_doctor.Show()

    def on_network_player(self, event):
        self.network_player = NetworkPlayerFrame(self, "Online Player")
        self.add_child_frame(self.network_player)
        self.network_player.Bind(wx.EVT_CLOSE, self.network_player.OnClose)
        self.manage_main_window_visibility(self.network_player)

    def on_task_scheduler(self, event):
        self.task_scheduler_instance = TaskScheduler(self)
        self.task_scheduler_instance.Bind(wx.EVT_CLOSE, self.on_task_scheduler_close)
        self.add_child_frame(self.task_scheduler_instance)
        self.manage_main_window_visibility(self.task_scheduler_instance)
        self.task_scheduler_instance.Show()
        self.task_scheduler_instance.Raise()

    def on_task_scheduler_close(self, event):
        if self.task_scheduler_instance:
            self.task_scheduler_instance.Hide()
            event.Veto()

    def on_elevenlabs(self, event):
        elevenlabs = ElevenLabs(self)
        self.add_child_frame(elevenlabs)
        self.manage_main_window_visibility(elevenlabs)
        elevenlabs.Show()

    def on_ssh_terminal(self, event):
        accessible_terminal = SessionViewer(self, app_vars.app_name)
        self.add_child_frame(accessible_terminal)
        self.manage_main_window_visibility(accessible_terminal)
        accessible_terminal.Show()

    def on_speed_test(self, event):
        self.speed_test= SpeedTest(self, title="Internet Speed Test")
        self.add_child_frame(self.speed_test)
        self.speed_test.ShowModal()

    def on_online_tts(self, event):
        """Handles the Online TTS tool."""
        online_tts_frame = OnlineTTS(self, title="Online Text to Speech")
        self.add_child_frame(online_tts_frame)
        self.manage_main_window_visibility(online_tts_frame)
        online_tts_frame.Show()

    def on_file_tools(self, event):
        """Opens the File Tools selection frame."""
        file_tools_frame = FileTools(self, title="File Tools")
        self.add_child_frame(file_tools_frame)
        self.manage_main_window_visibility(file_tools_frame)
        file_tools_frame.Show()

    def on_gemini_chat(self, event):
        gemini_frame = GeminiChat(self)
        self.add_child_frame(gemini_frame)
        self.manage_main_window_visibility(gemini_frame)
        gemini_frame.Show()

    def on_settings(self, event):
        config_path = get_settings_path()
        settings_dialog = SettingsDialog(self, self.config, config_path)
        settings_dialog.add_category(GeneralSettingsPanel)
        settings_dialog.add_category(AISettingsPanel)
        settings_dialog.add_category(YoutubeSettings)
        settings_dialog.ShowModal()
        settings_dialog.Destroy()
        # Reload Config After Settings Dialog Closes ---
        self.config = load_app_config()

    def on_open_config_directory(self, event):
        """Opens the application's configuration directory in the file explorer."""
        try:
            config_base_dir = wx.StandardPaths.Get().GetUserConfigDir()
            app_config_dir = os.path.join(config_base_dir, app_vars.app_name)
            if not os.path.isdir(app_config_dir):
                os.makedirs(app_config_dir)
            wx.LaunchDefaultApplication(app_config_dir)
        except Exception as e:
            wx.MessageBox(f"Could not open configuration directory.\nError: {e}", "Error Opening Directory", wx.OK | wx.ICON_ERROR, self)

    def on_quit(self, event):
        """Handles the Quit menu item."""
        self.perform_app_exit()

    def on_documentation(self, event):
        """Opens the readme.html file in the default browser."""
        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        doc_path = os.path.join(base_dir, "readme.html")
        if os.path.exists(doc_path):
            try:
                wx.LaunchDefaultApplication(doc_path)
            except Exception as e:
                wx.MessageBox(f"Failed to open documentation: {e}", "Error", wx.OK | wx.ICON_ERROR)
        else:
            wx.MessageBox(f"Documentation file not found at:\n{doc_path}", "File Not Found", wx.OK | wx.ICON_WARNING)

    def on_recent_changes(self, event):
        """Opens the changelog.txt file with the default application."""
        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        changelog_path = os.path.join(base_dir, "changelog.txt")
        if os.path.exists(changelog_path):
             try:
                wx.LaunchDefaultApplication(changelog_path)
             except Exception as e:
                 wx.MessageBox(f"Failed to open changelog: {e}", "Error", wx.OK | wx.ICON_ERROR)
        else:
            wx.MessageBox(f"Changelog file not found at:\n{changelog_path}", "File Not Found", wx.OK | wx.ICON_WARNING)

    def on_about(self, event):
        about_dialog = AboutDialog(self, title=f"About {app_vars.app_name}")
        about_dialog.ShowModal()

    def on_contact_us(self, event):
        contact_dialog = ContactDialog(self, "Contact Us")
        contact_dialog.ShowModal()


    # frame tracking logic
    def add_child_frame(self, frame):
        self.child_frames.append(frame)
        frame.Bind(wx.EVT_CLOSE, lambda event, f=frame: self.on_child_close(event,f)) #Listen to child's close events

    def manage_main_window_visibility(self, child_frame, show_on_close=True):
        """Hides or shows the main window based on the settings.

        Args:
            child_frame: The child frame (tool) being opened.
            show_on_close: Whether to automatically show the main window
                           when the child frame is closed.
        """
        hide_on_open = self.config.get('General', {}).get('hide_on_open', 'True')
        hide_on_open = hide_on_open.lower() == 'true'

        if hide_on_open:
            self.Hide()

            if show_on_close:
                def delayed_show(event):
                    self.Show()
                    self.Raise()
                    event.Skip()
                child_frame.Bind(wx.EVT_CLOSE, delayed_show)

    def on_child_close(self, event, frame):
        try:
            if frame in self.child_frames:
                self.child_frames.remove(frame)
        except (ValueError, RunTimeError):
            pass  # Frame was already removed or destroyed

        if self.launched_for_file and frame == self.direct_file_viewer_frame:
            wx.CallAfter(self.perform_app_exit) # Schedule app exit
        event.Skip()

    def close_all_children(self):
        # Recursively close all child frames
        frames_to_close = self.child_frames.copy()  # Create a copy to avoid modification during iteration
        for frame in frames_to_close:
            try:
                frame.Close()
            except RuntimeError:
                pass

    def perform_app_exit(self):
        """Helper function to cleanly exit the application."""
        # Unregistering all keys before closing, and spicificly alt modifier to prevent weird issues with screen readers
        try:
            keyboard.release('left alt')
            keyboard.release('right alt')
            keyboard.unhook_all()
            keyboard.unhook_all_hotkeys()
        except Exception as e:
            print(f"Error unhooking keyboard: {e}")

        if self.task_scheduler_instance:
            try:
                self.task_scheduler_instance.Close(force=True)
            except wx.wxAssertionError:
                pass 
            except RuntimeError:
                pass

        self.close_all_children()
        if self.tbIcon:
            self.tbIcon.RemoveIcon()
            self.tbIcon.Destroy()
        AppGuard.release()
        wx.Exit()

    def OnClose(self, event):
        # Minimize to tray instead of closing, based on setting
        minimize_on_close = self.config.get('General', {}).get('minimize_on_close', True)
        if minimize_on_close == 'False': minimize_on_close = False

        if minimize_on_close:
            self.Hide()
            event.Veto()
        else:
            self.perform_app_exit()


if __name__ == "__main__":
    app = wx.App(False) 
    app.SetAppName(app_vars.app_name)
    app.SetVendorName(app_vars.developer)
    filepath_to_open = None
    launched_for_file_arg = False
    if len(sys.argv) > 1:
        file_path_arg = sys.argv[1]
        if os.path.exists(file_path_arg) and os.path.isfile(file_path_arg):
            filepath_to_open = os.path.abspath(file_path_arg)
            launched_for_file_arg = True

    def on_appguard_secondary_quit_callback():
        # This callback is required by AppGuard.init.
        # It's called for secondary instances if quit_immediate=True.
        # Since we use quit_immediate=False and handle exit manually, it's mostly a placeholder.
        pass

    try:
        AppGuard.init(app_handle=APP_GUARD_HANDLE_NAME,
                      on_quit_callback=on_appguard_secondary_quit_callback,
                      quit_immediate=False) # We manage secondary instance manually
    except AppGuardError as e:
        wx.MessageBox(f"Failed to initialize application instance management: {e}\nApplication will now exit.",
                      "Initialization Error", wx.OK | wx.ICON_ERROR)
        sys.exit(1)
    except Exception as e:
        wx.MessageBox(f"An unexpected error occurred during application initialization: {e}\nApplication will now exit.",
                      "Critical Initialization Error", wx.OK | wx.ICON_ERROR)
        sys.exit(1)

    if not AppGuard.is_primary_instance():
        # This is a secondary Instance ---
        try:
            app_guard.AG_focus_window(app_vars.app_name)
        except Exception as e:
            # This is not critical, but good to know if it fails.
            print(f"Note: Could not focus primary instance's window: {e}")

        if filepath_to_open:
            try:
                # Send the file path to the primary instance.
                AppGuard.send_msg_request(IPC_MSG_OPEN_FILE, filepath_to_open)
            except Exception as e:
                wx.MessageBox(f"Could not send file '{os.path.basename(filepath_to_open)}' to the running AccessHub instance: {e}",
                              "Error", wx.OK | wx.ICON_WARNING)
        
        AppGuard.release() # Release AppGuard resources for this secondary instance.
        sys.exit(0)

    # --- This is the Primary Instance ---
    # Create an AppGuard object instance for calling its instance methods
    ag_instance = AppGuard()
    frame = AccessHub(None, title=app_vars.app_name, launched_for_file=launched_for_file_arg)

    # Register IPC message handler for opening files.
    # This allows the primary instance to receive messages from secondary instances.
    try:
        # The callback 'frame.handle_ipc_open_file' will be called when a message
        # with IPC_MSG_OPEN_FILE is received. The string data sent will be passed to it.
        open_file_ipc_msg_struct: IPCMsg = ag_instance.create_ipc_msg(
            msg_handle=IPC_MSG_OPEN_FILE,
            callback=frame.handle_ipc_open_file
        )
        ag_instance.register_msg(open_file_ipc_msg_struct)
    except Exception as e:
        wx.MessageBox(f"Failed to register IPC message handler for opening files: {e}\n"
                      "Opening files from new instances may not work.",
                      "Registration Error", wx.OK | wx.ICON_WARNING, parent=frame)

    if filepath_to_open:
        wx.CallAfter(frame.open_file_in_viewer, filepath_to_open)
        if launched_for_file_arg:
            frame.Show(False)
        else:
            frame.Show(True)
    else:
        frame.Show(True)

    frame.Bind(wx.EVT_CLOSE, frame.OnClose)
    app.MainLoop()
