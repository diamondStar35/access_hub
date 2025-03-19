import wx
import wx.adv
import os
import sys
import shutil
import webbrowser
import app_vars
from gui.settings import SettingsDialog, GeneralSettingsPanel
from tools.text_utils import TextUtilitiesApp
from tools.shutdown_control import ShutdownControl
from tools.network_player.media_player import DirectLinkPlayer, EVT_VLC_READY
from tools.network_player.youtube_search import YoutubeSearchDialog
from tools.network_player.youtube_streamer import YoutubeStreamer
from tools.network_player.settings import YoutubeSettings
from tools.task_scheduler import TaskScheduler
from tools.eleven_labs.eleven_labs import ElevenLabs, ElevenLabsSettings
from tools.accessible_terminal.session_viewer import SessionViewer
from tools.speed_test import SpeedTest
from tools.online_tts.online_tts import OnlineTTS
from tools.updater import Updater
from speech import speak
from passwordmeter import test
from pwnedpasswords import check
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
    def __init__(self, parent, title):
        super(AccessHub, self).__init__(parent, title=title, size=(800, 600))
        self.child_frames = [] # List to store child frames
        self.task_scheduler = None
        self.is_recording = False
        self.audio_frames = []
        self.p = pyaudio.PyAudio()
        self.recognizer = sr.Recognizer()
        self.recording_thread = None
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.settings_dialog = SettingsDialog(self)  # Instantiate settings dialog for config access
        self.settings_dialog.add_category(GeneralSettingsPanel)
        config_path = self.settings_dialog.get_config_path()
        self.config = self.settings_dialog.load_config()

        # taskbar icon
        self.tbIcon = AccessTaskBarIcon(self)
        self.create_menu_bar()

        # Set a pleasing background color
        self.SetBackgroundColour(wx.Colour(240, 240, 240))  # Light gray background

        # Create a panel to hold the buttons
        panel = wx.Panel(self, wx.ID_ANY)
        panel.SetBackgroundColour(wx.Colour(230, 230, 230)) # Slightly darker gray for contrast

        # Create a sizer for flexible layout
        sizer = wx.BoxSizer(wx.VERTICAL)

        title_text = wx.StaticText(panel, label="Access Hub", style=wx.ALIGN_CENTER)
        title_text.SetFont(wx.Font(18, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        title_text.SetForegroundColour("#333333") # Dark gray text


        # Add some spacing
        sizer.AddSpacer(20)
        sizer.Add(title_text, 0, wx.ALL | wx.EXPAND, 10)
        sizer.AddSpacer(20)

        # Create buttons dynamically
        tools = {
            "Text Tools": self.on_text_utilities,
            "Task Scheduler": self.on_task_scheduler,
            "Shutdown Control": self.on_shutdown_control,
            "Password Doctor": self.on_password_doctor,
            "Network player": self.on_network_player,
            "ElevenLabs": self.on_elevenlabs,
            "Accessible SSH Terminal": self.on_ssh_terminal,
            "Internet Speed Test": self.on_speed_test,
            "Online Text to Speech": self.on_online_tts,
        }

        for tool_name, handler in tools.items():
            button = wx.Button(panel, label=tool_name)
            button.Bind(wx.EVT_BUTTON, handler)
            sizer.Add(button, 0, wx.ALL | wx.EXPAND, 5)

        panel.SetSizer(sizer)

        # Finalize the layout
        sizer.Fit(panel)
        self.Centre()
        self.Show(True)
        self.start_hotkey_listener()
        check_updates = self.config.get('General', {}).get('check_for_updates', 'True')
        check_updates = check_updates.lower() == 'true'
        if check_updates:
            self.check_for_updates()


    def create_menu_bar(self):
        menu_bar = wx.MenuBar()

        app_menu = wx.Menu()
        settings_item = app_menu.Append(wx.ID_ANY, "&Settings", "Open the settings dialog")
        self.Bind(wx.EVT_MENU, self.on_settings, settings_item)
        quit_item = app_menu.Append(wx.ID_EXIT, "&Quit", "Quit the application")
        self.Bind(wx.EVT_MENU, self.on_quit, quit_item)

        help_menu = wx.Menu()
        about_item = help_menu.Append(wx.ID_ABOUT, "&About", "Information about this application")
        self.Bind(wx.EVT_MENU, self.on_about, about_item)

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

    def check_for_updates(self):
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
        self.executor.submit(updater.check_for_updates)

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
        self.network_player = NetworkPlayerFrame(self, "Network Player")
        self.add_child_frame(self.network_player)
        self.network_player.Bind(wx.EVT_CLOSE, self.network_player.OnClose)
        self.manage_main_window_visibility(self.network_player)

    def on_task_scheduler(self, event):
        if self.task_scheduler is None:  # Create only if it doesn't exist
            self.task_scheduler = TaskScheduler(self)
            self.task_scheduler.Bind(wx.EVT_CLOSE, self.on_task_scheduler_close)
            self.add_child_frame(self.task_scheduler)
        self.manage_main_window_visibility(self.task_scheduler)
        self.task_scheduler.Show()
        self.task_scheduler.Raise()

    def on_task_scheduler_close(self, event):
        if self.task_scheduler:
            self.task_scheduler.Hide()
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

    def on_settings(self, event):
        settings_dialog = SettingsDialog(self)
        settings_dialog.add_category(GeneralSettingsPanel)
        settings_dialog.add_category(ElevenLabsSettings)
        settings_dialog.add_category(YoutubeSettings)
        settings_dialog.ShowModal()
        settings_dialog.Destroy()
        # Reload Config After Settings Dialog Closes ---
        self.config = self.settings_dialog.load_config()

    def on_quit(self, event):
        """Handles the Quit menu item."""
        self.close_all_children()
        wx.Exit()

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
        event.Skip()

    def close_all_children(self):
        # Recursively close all child frames
        frames_to_close = self.child_frames.copy()  # Create a copy to avoid modification during iteration
        for frame in frames_to_close:
            try:
                frame.Close()
            except RuntimeError:
                pass

    def OnClose(self, event):
        # Minimize to tray instead of closing, based on setting
        minimize_on_close = self.config.get('General', {}).get('minimize_on_close', True)
        if minimize_on_close == 'False': minimize_on_close = False

        if minimize_on_close:
            self.Hide()
            event.Veto()
        else:
            self.close_all_children()
            wx.Exit()


class AccessTaskBarIcon(wx.adv.TaskBarIcon):
    def __init__(self, frame):
        super(AccessTaskBarIcon, self).__init__()
        self.frame = frame
        icon = wx.Icon(app_vars.icon)
        self.SetIcon(icon, "Access Hub") # Tooltip
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.on_left_down) # Restore on left click


    def CreatePopupMenu(self):
        menu = wx.Menu()
        restore_item = menu.Append(wx.ID_ANY, "Restore")
        menu.Bind(wx.EVT_MENU, self.on_restore, restore_item)
        exit_item = menu.Append(wx.ID_EXIT, "Exit")
        menu.Bind(wx.EVT_MENU, self.on_exit, exit_item)
        return menu

    def on_left_down(self, event):
        self.on_restore(event)

    def on_restore(self, event):
        self.frame.Show()
        self.frame.Raise()

    def on_exit(self, event):
        self.frame.close_all_children()
        wx.Exit()


class PasswordDoctorDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Password Doctor", size=(400, 250))
        self.SetBackgroundColour(wx.Colour("#f5f5f5"))  # Light gray background

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.password_label = wx.StaticText(panel, label="Enter Password:")
        vbox.Add(self.password_label, 0, wx.ALL | wx.ALIGN_LEFT, 10)

        self.password_text = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
        self.password_text.Bind(wx.EVT_TEXT, self.on_password_change)
        vbox.Add(self.password_text, 0, wx.ALL | wx.EXPAND, 10)

        self.feedback_label = wx.StaticText(panel, label="")  # Initially empty
        vbox.Add(self.feedback_label, 0, wx.ALL | wx.ALIGN_LEFT, 10)

        # Label for strength
        self.strength_label = wx.StaticText(panel, label="Strength: Unknown")  # Strength label
        vbox.Add(self.strength_label, 0, wx.ALL | wx.ALIGN_LEFT, 10)

        self.progress_bar = wx.Gauge(panel, range=100, size=(200, 25), style=wx.GA_HORIZONTAL)
        vbox.Add(self.progress_bar, 0, wx.ALL| wx.ALIGN_CENTER, 10)

        breach_check_button = wx.Button(panel, label="Check Breaches")
        breach_check_button.Bind(wx.EVT_BUTTON, self.on_check_breaches)
        vbox.Add(breach_check_button, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        close_button = wx.Button(panel, label="Close")
        close_button.Bind(wx.EVT_BUTTON, self.on_close)
        vbox.Add(close_button, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        panel.SetSizer(vbox)

        self.funny_messages = {
            (0, 30): ["Password's so weak, even a kitten could hack it!", "This password is basically made of tissue paper.", "You're asking to be hacked!"],
            (31, 50): ["Not bad, but hackers are still smirking.", "It's like a lukewarm cup of coffee: not strong enough."],
            (51, 75): ["Getting there! This password is average at best.", "Nice try, but it's not Fort Knox material yet."],
            (76, 90): ["Now we're talking! Hackers are sweating a little.", "Almost a masterpiece—add more spice!", "Decent, but don’t brag."],
            (91, 100): ["This password laughs at hackers!", "You’ve built the Great Wall of Passwords. Bravo!"],
        }


    def on_password_change(self, event):
        password = self.password_text.GetValue()
        strength, _ = test(password)

        # Calculate progress value (0-100 based on strength)
        progress_value = int(strength * 100)
        self.progress_bar.SetValue(progress_value)

        # Set strength label
        if progress_value < 30:
            strength_text = "Very Weak"
        elif progress_value < 50:
            strength_text = "Weak"
        elif progress_value < 75:
            strength_text = "Moderate"
        elif progress_value < 90:
            strength_text = "Strong"
        else:
            strength_text = "Very Strong"
        self.strength_label.SetLabel(f"Strength: {strength_text}")

        # Get and display a funny message
        funny_message = self.get_funny_message(progress_value)
        self.feedback_label.SetLabel(f"{funny_message}")
        speak(f"{strength_text}. {funny_message}")

    def get_funny_message(self, progress_value):
        """Select a funny message based on the progress value."""
        for range_limits, messages in self.funny_messages.items():
            if range_limits[0] <= progress_value <= range_limits[1]:
                return random.choice(messages)

    def on_check_breaches(self, event):
        password = self.password_text.GetValue()
        if not password:
            wx.MessageBox("Please enter a password to check!", "No Password", wx.OK | wx.ICON_WARNING)
            return

        # Check if the password has been compromised
        breached = check(password)
        message = (
            "This password is so famous, it made the breach hall of fame! Change it, Unless you like surprises!"
            if breached
            else "This password is a fortress. No breaches found. Keep it up!"
        )

        wx.MessageBox(message, "Breach Check Result", wx.OK | wx.ICON_INFORMATION)
        speak(message)

    def on_close(self, event):
        self.Destroy()


class NetworkPlayerFrame(wx.Frame):
    def __init__(self, parent, title):
        super(NetworkPlayerFrame, self).__init__(parent, title=title, size=(400, 200))
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        youtube_button = wx.Button(panel, label="Search in YouTube")
        youtube_button.Bind(wx.EVT_BUTTON, self.on_youtube_search)  # Not implemented yet
        vbox.Add(youtube_button, 0, wx.ALL | wx.CENTER, 10)

        youtube_link_button = wx.Button(panel, label="Play a youtube link")
        youtube_link_button.Bind(wx.EVT_BUTTON, self.on_youtube_link)
        vbox.Add(youtube_link_button, 0, wx.ALL | wx.CENTER, 10)

        direct_link_button = wx.Button(panel, label="Play a direct Link")
        direct_link_button.Bind(wx.EVT_BUTTON, self.on_direct_link)
        vbox.Add(direct_link_button, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(vbox)
        self.Centre()
        self.Show(True)


    def on_youtube_search(self, event):
        searchdlg = YoutubeSearchDialog(self, self)
        searchdlg.ShowModal()
        searchdlg.Destroy()

    def on_direct_link(self, event):
        dlg = wx.TextEntryDialog(self, "Enter the direct link:", "Play stream from a direct link")
        if dlg.ShowModal() == wx.ID_OK:
            link = dlg.GetValue()
            self.play_video(link)
        dlg.Destroy()

    def on_youtube_link(self, event):
        streamerdlg = YoutubeStreamer(self)
        streamerdlg.ShowModal()
        streamerdlg.Destroy()

    def play_video(self, link):
        self.player = DirectLinkPlayer(self, "Direct link Player", link)
        self.player.Bind(EVT_VLC_READY, self.player.onVlcReady)
        self.player.Bind(wx.EVT_CLOSE, self.player.OnClose)

    def OnClose(self, event):
        if hasattr(self, 'player') and self.player:
            self.player.Close()
        event.Skip()


class ContactDialog(wx.Dialog):
    def __init__(self, parent, title):
        super().__init__(parent, title=title, size=(350, 250))

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        developer_label = wx.StaticText(panel, label=f"Developer: {app_vars.developer}")
        vbox.Add(developer_label, 0, wx.ALL | wx.CENTER, 10)

        buttons_info = [
            ("App Home Page", app_vars.website),
            ("Telegram", app_vars.telegram),
            ("WhatsApp", app_vars.whatsapp),
            ("Email", f"mailto:{app_vars.mail}")
        ]

        for label, url in buttons_info:
            button = wx.Button(panel, label=label)
            button.Bind(wx.EVT_BUTTON, lambda event, link=url: self.on_open_url(event, link))
            vbox.Add(button, 0, wx.ALL | wx.CENTER, 5)

        panel.SetSizer(vbox)
        self.Centre()

    def on_open_url(self, event, url):
        webbrowser.open(url)


class AboutDialog(wx.Dialog):
    def __init__(self, parent, title):
        super().__init__(parent, title=title, size=(600, 800))
        self.SetBackgroundColour(wx.Colour("#f5f5f5"))

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        name_label = wx.StaticText(panel, label=app_vars.app_name)
        name_label.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        version_label = wx.StaticText(panel, label=f"Version {app_vars.app_version}")
        main_sizer.Add(name_label, 0, wx.ALL | wx.CENTER, 10)
        main_sizer.Add(version_label, 0, wx.ALL | wx.CENTER, 5)
        main_sizer.AddSpacer(30)

        app_info = (
            f"{app_vars.app_name} is a collection of accessible tools designed to enhance your computing experience.\n"
            "It provides a user-friendly interface to access various utilities like text manipulation, task scheduling, "
            "system control, and more.\n\n"
            f"Version: {app_vars.app_version}\n"
            "Copyright: (C) 2025 Diamond Star\n"
            f"Developer: {app_vars.developer}\n"
            f"Website: {app_vars.website}"
            # "License: Add your license information here"
        )
        info_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE | wx.HSCROLL)
        info_text.SetValue(app_info)
        main_sizer.Add(info_text, 1, wx.EXPAND | wx.ALL, 10)

        hyperlink = wx.adv.HyperlinkCtrl(panel, -1, "Visit Website", app_vars.website)
        main_sizer.Add(hyperlink, 0, wx.ALL | wx.CENTER, 5)

        contact_button = wx.Button(panel, label="Contact Us")
        contact_button.Bind(wx.EVT_BUTTON, self.on_contact_us)
        main_sizer.Add(contact_button, 0, wx.ALL | wx.CENTER, 5)

        ok_button = wx.Button(panel, id=wx.ID_OK, label="OK")
        main_sizer.Add(ok_button, 0, wx.ALL | wx.CENTER, 5)

        panel.SetSizer(main_sizer)
        self.Centre()

    def on_contact_us(self, event):
        self.EndModal(wx.ID_CANCEL)
        contact_dialog = ContactDialog(self.GetParent(), "Contact Us")
        contact_dialog.ShowModal()


if __name__ == "__main__":
    app = wx.App()
    # Single instance check
    instance_checker = wx.SingleInstanceChecker("AccessHubLock")
    if instance_checker.IsAnotherRunning():
        wx.MessageBox("Another instance of Access Hub is already running.", "Instance Running", wx.OK | wx.ICON_WARNING)
        wx.Exit()
    frame = AccessHub(None, app_vars.app_name)
    frame.Bind(wx.EVT_CLOSE, frame.OnClose)
    app.MainLoop()