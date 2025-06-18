import wx
import wx.lib.newevent
import os
import sys
import shutil
import re
import threading
import subprocess
import time

# Constants
MEDIA_EXTENSIONS = [
    ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus",
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mpg", ".mpeg"
]

AUDIO_FORMATS = {
    "MP3 (MPEG Audio Layer III)": "mp3",
    "WAV (Waveform Audio File Format)": "wav",
    "FLAC (Free Lossless Audio Codec)": "flac",
    "OGG (Ogg Vorbis)": "ogg",
    "M4A (MPEG-4 Audio)": "m4a",
    "AAC (Advanced Audio Coding)": "aac",
    "Opus": "opus"
}

AUDIO_CODECS = {
    "mp3": "libmp3lame",
    "wav": "pcm_s16le",
    "flac": "flac",
    "ogg": "libvorbis",
    "m4a": "aac",
    "aac": "aac",
    "opus": "libopus"
}

BITRATES = ["64k", "96k", "128k", "160k", "192k", "256k", "320k"]
SAMPLE_RATES = ["22050", "32000", "44100", "48000", "96000"]
OPUS_SUPPORTED_SAMPLE_RATES = ["48000", "24000", "16000", "12000", "8000"]
CHANNELS = {"Stereo": "2", "Mono": "1"}

# Custom events for thread communication
ConversionUpdateEvent, EVT_CONVERSION_UPDATE = wx.lib.newevent.NewEvent()
ConversionDoneEvent, EVT_CONVERSION_DONE = wx.lib.newevent.NewEvent()

class ConversionProgressDialog(wx.Dialog):
    def __init__(self, parent, title="Converting..."):
        super(ConversionProgressDialog, self).__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE)
        self.panel = wx.Panel(self)
        self.SetSize((450, 250))
        self.cancelled = False

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.info_label = wx.StaticText(self.panel, label="Initializing...")
        main_sizer.Add(self.info_label, 0, wx.ALL | wx.EXPAND, 10)

        self.file_label = wx.StaticText(self.panel, label="")
        main_sizer.Add(self.file_label, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)

        self.progress_gauge = wx.Gauge(self.panel, range=100, style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        main_sizer.Add(self.progress_gauge, 0, wx.ALL | wx.EXPAND, 10)

        self.cancel_button = wx.Button(self.panel, wx.ID_CANCEL, "Cancel")
        main_sizer.Add(self.cancel_button, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.panel.SetSizer(main_sizer)
        self.Layout()
        self.Centre()

        self.cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def on_cancel(self, event):
        self.cancelled = True
        self.info_label.SetLabel("Cancelling, please wait...")
        self.cancel_button.Disable()

    def on_close(self, event):
        self.on_cancel(event)

    def update_progress(self, event):
        total = getattr(event, 'total_files', 0)
        current_index = getattr(event, 'current_file_index', 0)
        file_name = getattr(event, 'current_file_name', '')
        percentage = getattr(event, 'percentage', 0)

        info_text = f"Processing file {current_index} of {total}..."
        self.info_label.SetLabel(info_text)
        self.file_label.SetLabel(f"Current: {file_name}")
        self.progress_gauge.SetValue(percentage)


class ConversionWorkerThread(threading.Thread):
    def __init__(self, parent, files, settings, ffmpeg_path, ffprobe_path):
        super(ConversionWorkerThread, self).__init__()
        self.parent = parent
        self.files_to_convert = files
        self.settings = settings
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self._running = True
        self.progress_regex = re.compile(r"out_time_us=(\d+)")
        self.duration_regex = re.compile(r"Duration: (\d{2}):(\d{2}):(\d{2})\.(\d{2})")


    def stop(self):
        self._running = False

    def run(self):
        total_files = len(self.files_to_convert)
        converted_count = 0
        skipped_count = 0
        errors = []

        for i, (original_path, _) in enumerate(self.files_to_convert):
            if not self._running:
                break

            base_name = os.path.basename(original_path)
            file_name_part, _ = os.path.splitext(base_name)
            new_file_name = f"{file_name_part}.{self.settings['format']}"
            output_path = os.path.join(self.settings['output_dir'], new_file_name)

            if os.path.exists(output_path) and not self.settings['overwrite']:
                errors.append(f"Skipped '{base_name}': Target file already exists.")
                skipped_count += 1
                continue

            update_data = {
                'total_files': total_files,
                'current_file_index': i + 1,
                'current_file_name': base_name,
                'percentage': 0
            }
            wx.CallAfter(wx.PostEvent, self.parent, ConversionUpdateEvent(**update_data))

            duration_seconds = 0
            try:
                ffprobe_cmd = [self.ffprobe_path, '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', original_path]
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                duration_str = subprocess.check_output(ffprobe_cmd, text=True, startupinfo=startupinfo, creationflags=subprocess.CREATE_NO_WINDOW).strip()
                if duration_str and duration_str.lower() != 'n/a':
                    duration_seconds = float(duration_str)
            except Exception as e:
                print(f"Could not get duration for {base_name} via ffprobe: {e}")

            command = [
                self.ffmpeg_path, '-hide_banner', '-progress', 'pipe:1', '-nostats',
                '-i', original_path,
                '-vn',
                '-c:a', self.settings['codec'],
                '-ar', self.settings['sample_rate'],
                '-ac', self.settings['channels'],
            ]
            if self.settings['format'] != 'opus':
                 command.extend(['-b:a', self.settings['bitrate']])

            if self.settings['overwrite']:
                command.append('-y')
            else:
                command.append('-n')

            if self.settings['copy_metadata']:
                command.extend(['-map_metadata', '0'])
            command.append(output_path)

            process = subprocess.Popen(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                text=True, 
                encoding='utf-8', 
                errors='replace', 
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            error_details = []
            while self._running:
                line = process.stdout.readline()
                if not line:
                    break
                
                if duration_seconds == 0:
                    match = self.duration_regex.search(line)
                    if match:
                        h, m, s, cs = map(int, match.groups())
                        duration_seconds = h * 3600 + m * 60 + s + cs / 100.0
                
                if duration_seconds > 0:
                    match = self.progress_regex.search(line)
                    if match:
                        current_us = int(match.group(1))
                        current_seconds = current_us / 1000000.0
                        percentage = int((current_seconds / duration_seconds) * 100)
                        update_data['percentage'] = min(100, percentage)
                        wx.CallAfter(wx.PostEvent, self.parent, ConversionUpdateEvent(**update_data))

                if "progress=end" in line:
                    break

                if "error" in line.lower() or "invalid" in line.lower():
                    error_details.append(line.strip())

            if not self._running:
                process.terminate()
                process.wait()
                if os.path.exists(output_path):
                    try: os.remove(output_path)
                    except OSError: pass
                break

            return_code = process.wait()

            if return_code == 0:
                converted_count += 1
            else:
                error_message = f"Failed to convert '{base_name}'."
                if error_details:
                    error_message += f"\nDetails: {error_details[-1]}"
                errors.append(error_message)

        wx.CallAfter(wx.PostEvent, self.parent, ConversionDoneEvent(
            converted=converted_count,
            skipped=skipped_count,
            total=total_files,
            errors=errors))


class MediaConverter(wx.Frame):
    def __init__(self, parent, title):
        super(MediaConverter, self).__init__(parent, title=title, size=(700, 650))
        self.panel = wx.Panel(self)
        self.files_to_convert = []
        self.conversion_thread = None
        self.progress_dialog = None

        self.ffmpeg_path = None
        self.ffprobe_path = None
        if not self.find_media_executables():
            wx.MessageBox("ffmpeg.exe and/or ffprobe.exe not found. This tool cannot function without them.", "Error", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.Close)
            return

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        list_label = wx.StaticText(self.panel, label="Files to Convert:")
        main_sizer.Add(list_label, 0, wx.LEFT | wx.TOP | wx.RIGHT, 5)
        self.file_list_box = wx.ListBox(self.panel, style=wx.LB_SINGLE)
        main_sizer.Add(self.file_list_box, 1, wx.EXPAND | wx.ALL, 5)

        list_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.add_files_btn = wx.Button(self.panel, label="Add Files")
        self.add_folder_btn = wx.Button(self.panel, label="Add Folder")
        self.remove_item_btn = wx.Button(self.panel, label="Remove Selected")
        list_btn_sizer.Add(self.add_files_btn, 0, wx.ALL, 5)
        list_btn_sizer.Add(self.add_folder_btn, 0, wx.ALL, 5)
        list_btn_sizer.Add(self.remove_item_btn, 0, wx.ALL, 5)
        main_sizer.Add(list_btn_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 5)

        options_fgs = wx.FlexGridSizer(6, 2, 5, 10)
        options_fgs.AddGrowableCol(1, 1)

        options_fgs.Add(wx.StaticText(self.panel, label="Output Format:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
        self.format_combo = wx.ComboBox(self.panel, choices=list(AUDIO_FORMATS.keys()), style=wx.CB_READONLY)
        options_fgs.Add(self.format_combo, 1, wx.EXPAND)

        options_fgs.Add(wx.StaticText(self.panel, label="Audio Quality (Bitrate):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
        self.bitrate_combo = wx.ComboBox(self.panel, choices=BITRATES, style=wx.CB_READONLY)
        options_fgs.Add(self.bitrate_combo, 1, wx.EXPAND)

        options_fgs.Add(wx.StaticText(self.panel, label="Sample Rate (Hz):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
        self.samplerate_combo = wx.ComboBox(self.panel, choices=SAMPLE_RATES, style=wx.CB_READONLY)
        options_fgs.Add(self.samplerate_combo, 1, wx.EXPAND)

        options_fgs.Add(wx.StaticText(self.panel, label="Channels:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
        self.channels_combo = wx.ComboBox(self.panel, choices=list(CHANNELS.keys()), style=wx.CB_READONLY)
        options_fgs.Add(self.channels_combo, 1, wx.EXPAND)

        options_fgs.Add(wx.StaticText(self.panel, label="Output Folder:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
        output_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.output_path_text = wx.TextCtrl(self.panel, style=wx.TE_READONLY)
        output_sizer.Add(self.output_path_text, 1, wx.EXPAND)
        self.browse_output_btn = wx.Button(self.panel, label="Browse...")
        output_sizer.Add(self.browse_output_btn, 0, wx.LEFT, 5)
        options_fgs.Add(output_sizer, 1, wx.EXPAND)

        options_fgs.AddSpacer(0)
        extra_options_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.copy_metadata_cb = wx.CheckBox(self.panel, label="Copy metadata")
        self.copy_metadata_cb.SetValue(True)
        extra_options_sizer.Add(self.copy_metadata_cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self.overwrite_cb = wx.CheckBox(self.panel, label="Overwrite existing files")
        self.overwrite_cb.SetValue(False)
        extra_options_sizer.Add(self.overwrite_cb, 0, wx.ALIGN_CENTER_VERTICAL)
        options_fgs.Add(extra_options_sizer, 1, wx.EXPAND)
        main_sizer.Add(options_fgs, 0, wx.EXPAND | wx.ALL, 10)

        action_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.start_btn = wx.Button(self.panel, label="Start Conversion")
        self.close_btn = wx.Button(self.panel, label="Close")
        action_btn_sizer.Add(self.start_btn, 0, wx.ALL, 10)
        action_btn_sizer.Add(self.close_btn, 0, wx.ALL, 10)
        main_sizer.Add(action_btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.panel.SetSizer(main_sizer)
        self.Layout()
        self.Centre()

        self.format_combo.SetSelection(0)
        self.bitrate_combo.SetValue("128k")
        self.samplerate_combo.SetValue("44100")
        self.channels_combo.SetSelection(0)

        self.add_files_btn.Bind(wx.EVT_BUTTON, self.on_add_files)
        self.add_folder_btn.Bind(wx.EVT_BUTTON, self.on_add_folder)
        self.remove_item_btn.Bind(wx.EVT_BUTTON, self.on_remove_item)
        self.browse_output_btn.Bind(wx.EVT_BUTTON, self.on_browse_output)
        self.start_btn.Bind(wx.EVT_BUTTON, self.on_start_conversion)
        self.close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        self.format_combo.Bind(wx.EVT_COMBOBOX, self.on_format_change)
        self.Bind(wx.EVT_CLOSE, self.on_frame_close)
        self.Bind(EVT_CONVERSION_UPDATE, self.on_conversion_update)
        self.Bind(EVT_CONVERSION_DONE, self.on_conversion_done)


    def find_media_executables(self):
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        
        local_ffmpeg = os.path.join(base_dir, 'ffmpeg.exe')
        local_ffprobe = os.path.join(base_dir, 'ffprobe.exe')

        if os.path.exists(local_ffmpeg):
            self.ffmpeg_path = local_ffmpeg
        else:
            self.ffmpeg_path = shutil.which('ffmpeg')

        if os.path.exists(local_ffprobe):
            self.ffprobe_path = local_ffprobe
        else:
            self.ffprobe_path = shutil.which('ffprobe')
        return self.ffmpeg_path and self.ffprobe_path

    def on_format_change(self, event):
        selected_format_key = self.format_combo.GetValue()
        is_opus = AUDIO_FORMATS.get(selected_format_key) == 'opus'

        if is_opus:
            self.samplerate_combo.Set(OPUS_SUPPORTED_SAMPLE_RATES)
            self.samplerate_combo.SetValue("48000")
            self.bitrate_combo.Enable(False)
            self.bitrate_combo.SetToolTip("Bitrate is handled automatically by the Opus codec for best quality.")
        else:
            self.samplerate_combo.Set(SAMPLE_RATES)
            self.samplerate_combo.SetValue("44100")
            self.bitrate_combo.Enable(True)
            self.bitrate_combo.SetToolTip("")
        event.Skip()

    def _add_file_to_list(self, filepath):
        _, ext = os.path.splitext(filepath)
        if ext.lower() in MEDIA_EXTENSIONS:
            if not any(f[0] == filepath for f in self.files_to_convert):
                basename = os.path.basename(filepath)
                self.files_to_convert.append((filepath, basename))
                self.file_list_box.Append(basename)
                if not self.output_path_text.GetValue():
                    self.output_path_text.SetValue(os.path.dirname(filepath))

    def on_add_files(self, event):
        wildcard = "Media Files|" + ";".join("*" + ext for ext in MEDIA_EXTENSIONS) + "|All files (*.*)|*.*"
        with wx.FileDialog(self, "Select media files", wildcard=wildcard,
                           style=wx.FD_OPEN | wx.FD_MULTIPLE | wx.FD_FILE_MUST_EXIST) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return
            for path in file_dialog.GetPaths():
                self._add_file_to_list(path)

    def on_add_folder(self, event):
        with wx.DirDialog(self, "Choose a folder", style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dir_dialog:
            if dir_dialog.ShowModal() == wx.ID_CANCEL:
                return
            folder_path = dir_dialog.GetPath()
            if not self.output_path_text.GetValue():
                self.output_path_text.SetValue(folder_path)
            
            for root, _, files in os.walk(folder_path):
                for f_name in files:
                    self._add_file_to_list(os.path.join(root, f_name))

    def on_remove_item(self, event):
        selected_index = self.file_list_box.GetSelection()
        if selected_index != wx.NOT_FOUND:
            self.file_list_box.Delete(selected_index)
            del self.files_to_convert[selected_index]

    def on_browse_output(self, event):
        with wx.DirDialog(self, "Choose an output folder", style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dir_dialog:
            if dir_dialog.ShowModal() == wx.ID_OK:
                self.output_path_text.SetValue(dir_dialog.GetPath())

    def on_start_conversion(self, event):
        if not self.files_to_convert:
            wx.MessageBox("Please add files to convert.", "No Files", wx.OK | wx.ICON_WARNING)
            return
        
        output_dir = self.output_path_text.GetValue()
        if not output_dir or not os.path.isdir(output_dir):
            wx.MessageBox("Please select a valid output folder.", "Output Error", wx.OK | wx.ICON_ERROR)
            return

        format_ext = AUDIO_FORMATS[self.format_combo.GetValue()]
        settings = {
            'output_dir': output_dir,
            'format': format_ext,
            'codec': AUDIO_CODECS.get(format_ext, 'copy'),
            'bitrate': self.bitrate_combo.GetValue(),
            'sample_rate': self.samplerate_combo.GetValue(),
            'channels': CHANNELS[self.channels_combo.GetValue()],
            'copy_metadata': self.copy_metadata_cb.IsChecked(),
            'overwrite': self.overwrite_cb.IsChecked()
        }

        self.Hide()
        self.progress_dialog = ConversionProgressDialog(self)
        self.progress_dialog.Show()
        self.conversion_thread = ConversionWorkerThread(self, self.files_to_convert, settings, self.ffmpeg_path, self.ffprobe_path)
        self.conversion_thread.start()

    def on_conversion_update(self, event):
        if self.progress_dialog:
            if self.progress_dialog.cancelled:
                if self.conversion_thread and self.conversion_thread.is_alive():
                    self.conversion_thread.stop()
            else:
                self.progress_dialog.update_progress(event)

    def on_conversion_done(self, event):
        if self.progress_dialog:
            self.progress_dialog.Destroy()
            self.progress_dialog = None

        msg = f"Conversion finished.\n\nSuccessfully converted: {event.converted} file(s)."
        if event.skipped > 0:
            msg += f"\nSkipped: {event.skipped} file(s)."
        
        total_processed = event.converted + event.skipped
        msg += f"\nTotal processed: {total_processed}/{event.total} file(s)."        
        if event.errors:
            msg += "\n\nErrors encountered:\n" + "\n".join(event.errors)
        
        wx.MessageBox(msg, "Conversion Complete", wx.OK | wx.ICON_INFORMATION)
        self.files_to_convert.clear()
        self.file_list_box.Clear()
        self.Show()
        self.Raise()

    def on_frame_close(self, event):
        if self.conversion_thread and self.conversion_thread.is_alive():
            self.conversion_thread.stop()
            self.conversion_thread.join(timeout=5)
        
        parent = self.GetParent()
        if parent and hasattr(parent, 'on_child_tool_close'):
             parent.on_child_tool_close(self)
        self.Destroy()
