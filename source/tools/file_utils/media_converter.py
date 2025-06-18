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

# A list of just the video extensions for easy checking
VIDEO_EXTENSIONS = [".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv"]

CONVERSION_FORMATS = {
    # Audio
    "MP3 (MPEG Audio Layer III)": "mp3",
    "WAV (Waveform Audio File Format)": "wav",
    "FLAC (Free Lossless Audio Codec)": "flac",
    "OGG (Ogg Vorbis)": "ogg",
    "M4A (MPEG-4 Audio)": "m4a",
    "AAC (Advanced Audio Coding)": "aac",
    "Opus": "opus",
    # Video
    "MP4 (MPEG-4 Video)": "mp4",
    "MKV (Matroska Video)": "mkv",
    "MOV (QuickTime Movie)": "mov"
}

CODECS = {
    # Audio
    "mp3": ("libmp3lame", "aac"),
    "wav": ("pcm_s16le", "pcm_s16le"),
    "flac": ("flac", "flac"),
    "ogg": ("libvorbis", "libvorbis"),
    "m4a": ("aac", "aac"),
    "aac": ("aac", "aac"),
    "opus": ("libopus", "libopus"),
    # Video
    "mp4": ("libx264", "aac"),
    "mkv": ("libx264", "aac"),
    "mov": ("libx264", "aac")
}

VIDEO_RESOLUTIONS = {
    "480p (854x480)": "854:480",
    "720p (1280x720)": "1280:720",
    "1080p (1920x1080)": "1920:1080",
    "1440p (2560x1440)": "2560:1440",
    "4K (3840x2160)": "3840:2160",
}

ENCODER_PRESETS = {
    "Ultrafast (Lowest Quality, Fastest)": "ultrafast",
    "Veryfast": "veryfast",
    "Faster": "faster",
    "Fast": "fast",
    "Medium (Default Quality/Speed)": "medium",
    "Slow": "slow",
    "Slower": "slower",
    "Veryslow (Highest Quality, Slowest)": "veryslow"
}

FRAME_RATES = ["24", "25", "30", "50", "60"]
BITRATES = ["64k", "96k", "128k", "160k", "192k", "256k", "320k"]
SAMPLE_RATES = ["22050", "32000", "44100", "48000", "96000"]
OPUS_SUPPORTED_SAMPLE_RATES = ["48000", "24000", "16000", "12000", "8000"]
CHANNELS = {"Stereo": "2", "Mono": "1"}

# Custom events for thread communication
ConversionUpdateEvent, EVT_CONVERSION_UPDATE = wx.lib.newevent.NewEvent()
ConversionDoneEvent, EVT_CONVERSION_DONE = wx.lib.newevent.NewEvent()

def is_video_file(filepath):
    """Checks if a file has a video extension."""
    return os.path.splitext(filepath)[1].lower() in VIDEO_EXTENSIONS

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
        is_video_output = 'output_filepath' in self.settings

        for i, (original_path, _) in enumerate(self.files_to_convert):
            if not self._running:
                break

            base_name = os.path.basename(original_path)            
            if is_video_output:
                output_path = self.settings['output_filepath']
                # If multiple files were passed to thread for video (should not happen due to on_start_conversion logic)
                # this would overwrite the same output_path. The logic in on_start_conversion ensures only one file for video.
            else: # Audio output
                file_name_part, _ = os.path.splitext(base_name)
                new_file_name = f"{file_name_part}.{self.settings['format']}"
                output_path = os.path.join(self.settings['output_dir'], new_file_name)

            if os.path.exists(output_path) and not self.settings['overwrite']:
                # For video, this check is also done in on_start_conversion, but keep for safety
                errors.append(f"Skipped '{base_name}': Target file '{os.path.basename(output_path)}' already exists.")
                skipped_count += 1
                wx.CallAfter(wx.PostEvent, self.parent, ConversionUpdateEvent(
                    total_files=total_files,
                    current_file_index=i + 1,
                    current_file_name=base_name,
                    percentage=100 # Skipped, so 100% of this "file's progress"
                ))
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
                print(f"Could not get duration for {base_name}: {e}")

            command = [
                self.ffmpeg_path, '-hide_banner', '-progress', 'pipe:1', '-nostats',
            ]

            if is_video_output:
                video_codec, audio_codec_for_video = self.settings['codec']
                command.extend([
                    '-loop', '1', '-framerate', self.settings['fps'], '-i', self.settings['image_path'],
                    '-i', original_path,
                    '-c:v', video_codec,
                    '-preset', self.settings['encoder_preset'], # Add preset
                    '-tune', 'stillimage',
                    '-c:a', audio_codec_for_video,
                ])
                if audio_codec_for_video != 'libopus' and self.settings.get('bitrate'):
                    command.extend(['-b:a', self.settings['bitrate']])
                command.extend([
                    '-vf', f"scale={self.settings['resolution']}",
                    '-pix_fmt', 'yuv420p',
                    '-shortest'
                ])
            else: 
                audio_codec, _ = self.settings['codec']
                command.extend([
                    '-i', original_path,
                    '-vn', 
                    '-c:a', audio_codec,
                    '-ar', self.settings['sample_rate'],
                    '-ac', self.settings['channels'],
                ])
                if self.settings['format'] != 'opus':
                     command.extend(['-b:a', self.settings['bitrate']])

            if self.settings['overwrite']:
                command.append('-y')
            else:
                command.append('-n')
            
            if self.settings['copy_metadata']:
                # For audio-to-video, metadata should come from the audio input (index 1 in ffmpeg command)
                # For audio-to-audio, metadata comes from the audio input (index 0 in ffmpeg command)
                input_index_for_metadata = '1' if is_video_output else '0'
                command.extend(['-map_metadata', input_index_for_metadata, '-c:s', 'copy'])            
            command.append(output_path)
            
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW)
            error_details = []
            while self._running:
                line = process.stdout.readline()
                if not line:
                    break
                
                if duration_seconds == 0: # Try to parse duration from ffmpeg output if ffprobe failed
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

                if "error" in line.lower() or "invalid" in line.lower() or "failed" in line.lower() :
                    error_details.append(line.strip())

            if not self._running:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                process.wait()
                if os.path.exists(output_path): # Clean up partially created file
                    try: os.remove(output_path)
                    except OSError: pass
                break # Exit the loop over files

            return_code = process.wait()
            if return_code == 0:
                converted_count += 1
            else:
                error_message = f"Failed to convert '{base_name}'."
                if error_details:
                    relevant_errors = "\n".join(error_details[-3:])
                    error_message += f"\nDetails: {relevant_errors}"
                else:
                    error_message += f" (ffmpeg exit code: {return_code})"
                errors.append(error_message)
        
        final_update_data = {
            'total_files': total_files,
            'current_file_index': total_files,
            'current_file_name': "Finalizing...",
            'percentage': 100
        }
        wx.CallAfter(wx.PostEvent, self.parent, ConversionUpdateEvent(**final_update_data))
        wx.CallAfter(wx.PostEvent, self.parent, ConversionDoneEvent(converted=converted_count, skipped=skipped_count, total=total_files, errors=errors))


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

        self.audio_settings_fgs = wx.FlexGridSizer(4, 2, 5, 10)
        self.audio_settings_fgs.AddGrowableCol(1, 1)
        self.audio_settings_fgs.Add(wx.StaticText(self.panel, label="Output Format:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
        self.format_combo = wx.ComboBox(self.panel, choices=list(CONVERSION_FORMATS.keys()), style=wx.CB_READONLY)
        self.audio_settings_fgs.Add(self.format_combo, 1, wx.EXPAND)
        self.audio_settings_fgs.Add(wx.StaticText(self.panel, label="Audio Quality (Bitrate):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
        self.bitrate_combo = wx.ComboBox(self.panel, choices=BITRATES, style=wx.CB_READONLY)
        self.audio_settings_fgs.Add(self.bitrate_combo, 1, wx.EXPAND)
        self.audio_settings_fgs.Add(wx.StaticText(self.panel, label="Sample Rate (Hz):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
        self.samplerate_combo = wx.ComboBox(self.panel, choices=SAMPLE_RATES, style=wx.CB_READONLY)
        self.audio_settings_fgs.Add(self.samplerate_combo, 1, wx.EXPAND)
        self.audio_settings_fgs.Add(wx.StaticText(self.panel, label="Channels:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
        self.channels_combo = wx.ComboBox(self.panel, choices=list(CHANNELS.keys()), style=wx.CB_READONLY)
        self.audio_settings_fgs.Add(self.channels_combo, 1, wx.EXPAND)
        main_sizer.Add(self.audio_settings_fgs, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        video_box = wx.StaticBox(self.panel, label="Video Settings")
        self.video_settings_sizer = wx.StaticBoxSizer(video_box, wx.VERTICAL)
        video_fgs = wx.FlexGridSizer(4, 2, 5, 10)
        video_fgs.AddGrowableCol(1, 1)
        video_fgs.Add(wx.StaticText(self.panel, label="Static Image:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
        image_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.image_path_text = wx.TextCtrl(self.panel, style=wx.TE_READONLY | wx.TE_MULTILINE | wx.HSCROLL)
        image_sizer.Add(self.image_path_text, 1, wx.EXPAND)
        self.browse_image_btn = wx.Button(self.panel, label="Browse...")
        image_sizer.Add(self.browse_image_btn, 0, wx.LEFT, 5)
        video_fgs.Add(image_sizer, 1, wx.EXPAND)
        video_fgs.Add(wx.StaticText(self.panel, label="Resolution:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
        self.resolution_combo = wx.ComboBox(self.panel, choices=list(VIDEO_RESOLUTIONS.keys()), style=wx.CB_READONLY)
        video_fgs.Add(self.resolution_combo, 1, wx.EXPAND)
        video_fgs.Add(wx.StaticText(self.panel, label="Frame Rate (FPS):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
        self.fps_combo = wx.ComboBox(self.panel, choices=FRAME_RATES, style=wx.CB_READONLY)
        video_fgs.Add(self.fps_combo, 1, wx.EXPAND)
        video_fgs.Add(wx.StaticText(self.panel, label="Encoder Speed/Quality:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
        self.encoder_preset_combo = wx.ComboBox(self.panel, choices=list(ENCODER_PRESETS.keys()), style=wx.CB_READONLY)
        video_fgs.Add(self.encoder_preset_combo, 1, wx.EXPAND)
        self.video_settings_sizer.Add(video_fgs, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(self.video_settings_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.video_filename_sizer = wx.FlexGridSizer(1, 2, 5, 10)
        self.video_filename_sizer.AddGrowableCol(1, 1)
        self.video_filename_sizer.Add(wx.StaticText(self.panel, label="Output Filename:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
        self.output_filename_text = wx.TextCtrl(self.panel)
        self.video_filename_sizer.Add(self.output_filename_text, 1, wx.EXPAND)
        main_sizer.Add(self.video_filename_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        common_fgs = wx.FlexGridSizer(2, 2, 5, 10)
        common_fgs.AddGrowableCol(1, 1)
        common_fgs.Add(wx.StaticText(self.panel, label="Output Folder:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
        output_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.output_path_text = wx.TextCtrl(self.panel, style=wx.TE_READONLY | wx.TE_MULTILINE | wx.HSCROLL)
        output_sizer.Add(self.output_path_text, 1, wx.EXPAND)
        self.browse_output_btn = wx.Button(self.panel, label="Browse...")
        output_sizer.Add(self.browse_output_btn, 0, wx.LEFT, 5)
        common_fgs.Add(output_sizer, 1, wx.EXPAND)
        common_fgs.AddSpacer(0)
        
        extra_options_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.copy_metadata_cb = wx.CheckBox(self.panel, label="Copy metadata")
        self.copy_metadata_cb.SetValue(True)
        extra_options_sizer.Add(self.copy_metadata_cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self.overwrite_cb = wx.CheckBox(self.panel, label="Overwrite existing files")
        extra_options_sizer.Add(self.overwrite_cb, 0, wx.ALIGN_CENTER_VERTICAL)
        common_fgs.Add(extra_options_sizer, 1, wx.EXPAND)
        main_sizer.Add(common_fgs, 0, wx.EXPAND | wx.ALL, 10)

        action_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.start_btn = wx.Button(self.panel, label="Start Conversion")
        self.close_btn = wx.Button(self.panel, label="Close")
        action_btn_sizer.Add(self.start_btn, 0, wx.ALL, 10)
        action_btn_sizer.Add(self.close_btn, 0, wx.ALL, 10)
        main_sizer.Add(action_btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.panel.SetSizer(main_sizer)
        self.Layout()
        self.Centre()

        # Set defaults
        self.format_combo.SetSelection(0)
        self.resolution_combo.SetValue("1080p (1920x1080)")
        self.fps_combo.SetValue("30")
        self.encoder_preset_combo.SetValue("Medium (Default Quality/Speed)")
        self.on_format_change(None)

        # Bind events
        self.add_files_btn.Bind(wx.EVT_BUTTON, self.on_add_files)
        self.add_folder_btn.Bind(wx.EVT_BUTTON, self.on_add_folder)
        self.remove_item_btn.Bind(wx.EVT_BUTTON, self.on_remove_item)
        self.browse_output_btn.Bind(wx.EVT_BUTTON, self.on_browse_output)
        self.browse_image_btn.Bind(wx.EVT_BUTTON, self.on_browse_image)
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
        selected_format_ext = CONVERSION_FORMATS.get(selected_format_key)

        if selected_format_ext is None:
            if event: event.Skip()
            return

        is_video = f".{selected_format_ext}" in VIDEO_EXTENSIONS
        is_opus = selected_format_ext == 'opus'

        panel_main_sizer = self.panel.GetSizer()
        panel_main_sizer.Show(self.video_settings_sizer, show=is_video, recursive=True)
        panel_main_sizer.Show(self.video_filename_sizer, show=is_video, recursive=True)
        self.bitrate_combo.Enable(not is_opus) # Bitrate is always enabled unless Opus

        if is_video:
            self.samplerate_combo.Enable(False)
            self.channels_combo.Enable(False)
            if self.files_to_convert:
                first_file_basename = self.files_to_convert[0][1]
                name_part, _ = os.path.splitext(first_file_basename)
                self.output_filename_text.SetValue(f"{name_part}.{selected_format_ext}")
            else:
                self.output_filename_text.SetValue(f"output.{selected_format_ext}")

        else: # Is Audio
            self.samplerate_combo.Enable(True)
            self.channels_combo.Enable(True)
            self.output_filename_text.SetValue("") # Clear video filename field
            
            if is_opus:
                self.samplerate_combo.Set(OPUS_SUPPORTED_SAMPLE_RATES)
                self.samplerate_combo.SetValue("48000")
                self.bitrate_combo.SetToolTip("Bitrate is handled automatically by the Opus codec.")
            else:
                self.samplerate_combo.Set(SAMPLE_RATES)
                if self.samplerate_combo.GetValue() not in SAMPLE_RATES:
                    self.samplerate_combo.SetValue("44100")
                if self.bitrate_combo.GetValue() not in BITRATES:
                    self.bitrate_combo.SetValue("128k")
                if self.channels_combo.GetSelection() == -1:
                    self.channels_combo.SetSelection(0)
                self.bitrate_combo.SetToolTip("")

        self.panel.Layout()
        self.Layout()
        self.Fit()
        if event:
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

                # Update video filename if a video format is selected
                selected_format_key = self.format_combo.GetValue()
                selected_format_ext = CONVERSION_FORMATS.get(selected_format_key)
                if selected_format_ext and f".{selected_format_ext}" in VIDEO_EXTENSIONS:
                    name_part, _ = os.path.splitext(basename) # Use current file's name
                    self.output_filename_text.SetValue(f"{name_part}.{selected_format_ext}")

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

    def on_browse_image(self, event):
        wildcard = "Image Files (*.png;*.jpg;*.jpeg;*.bmp)|*.png;*.jpg;*.jpeg;*.bmp|All files (*.*)|*.*"
        with wx.FileDialog(self, "Select an image", wildcard=wildcard, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.image_path_text.SetValue(dialog.GetPath())

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

        format_key = self.format_combo.GetValue()
        format_ext = CONVERSION_FORMATS[format_key]
        is_video_output_format = f".{format_ext}" in VIDEO_EXTENSIONS
        
        files_for_thread = list(self.files_to_convert)
        output_filepath_for_video = None

        if is_video_output_format:
            image_path = self.image_path_text.GetValue()
            if not image_path or not os.path.exists(image_path):
                wx.MessageBox("Please select a valid static image for the video background.", "Image Missing", wx.OK | wx.ICON_ERROR)
                return

            output_filename_base = self.output_filename_text.GetValue().strip()
            if not output_filename_base:
                wx.MessageBox("Please enter an output filename for the video.", "Filename Missing", wx.OK | wx.ICON_ERROR)
                return

            name_part, ext_part = os.path.splitext(output_filename_base)
            if not ext_part or ext_part.lower() != f".{format_ext}".lower():
                actual_output_filename = f"{name_part}.{format_ext}"
                self.output_filename_text.SetValue(actual_output_filename) # Update UI
            else:
                actual_output_filename = output_filename_base
            
            output_filepath_for_video = os.path.join(output_dir, actual_output_filename)

            if os.path.exists(output_filepath_for_video) and not self.overwrite_cb.IsChecked():
                wx.MessageBox(f"Output file '{actual_output_filename}' already exists in the output folder. Enable 'Overwrite existing files' or choose a different name/folder.", "File Exists", wx.OK | wx.ICON_ERROR)
                return

            videos_in_input_list = [f for f, b in self.files_to_convert if is_video_file(f)]
            if videos_in_input_list:
                msg_dlg = wx.MessageDialog(self,
                                       f"You have added {len(videos_in_input_list)} video file(s) to the input list. "
                                       "This tool can only convert audio files to video when a video output format is selected.\n\n"
                                       "Do you want to remove the video files from the input list and continue with only the audio files?",
                                       "Video Input Detected for Audio-to-Video Conversion",
                                       wx.YES_NO | wx.ICON_WARNING)
                if msg_dlg.ShowModal() != wx.ID_YES:
                    msg_dlg.Destroy()
                    return
                msg_dlg.Destroy()
                
                self.files_to_convert = [(f, b) for f, b in self.files_to_convert if not is_video_file(f)]
                self.file_list_box.Clear()
                self.file_list_box.AppendItems([b for f,b in self.files_to_convert])
                files_for_thread = list(self.files_to_convert)
                if not files_for_thread:
                    wx.MessageBox("All files were removed. There are no audio files left to convert to video.", "No Audio Files", wx.OK | wx.ICON_INFORMATION)
                    return
            
            if len(files_for_thread) > 1:
                dlg = wx.MessageDialog(self, 
                                       "You have multiple audio files listed for video conversion. "
                                       "Only the first audio file in the list will be used to create the video.\n\n"
                                       "Do you want to continue?",
                                       "Multiple Files for Video Output",
                                       wx.YES_NO | wx.ICON_QUESTION)
                if dlg.ShowModal() != wx.ID_YES:
                    dlg.Destroy()
                    return
                dlg.Destroy()
                files_for_thread = [files_for_thread[0]]

        settings = {
            'format': format_ext,
            'codec': CODECS.get(format_ext, ('copy', 'copy')), # Default to copy if somehow not found
            'bitrate': self.bitrate_combo.GetValue(),
            'sample_rate': self.samplerate_combo.GetValue(),
            'channels': CHANNELS[self.channels_combo.GetValue()],
            'overwrite': self.overwrite_cb.IsChecked(),
            'copy_metadata': self.copy_metadata_cb.IsChecked(),
        }

        if is_video_output_format:
            settings['output_filepath'] = output_filepath_for_video
            settings['image_path'] = self.image_path_text.GetValue()
            settings['resolution'] = VIDEO_RESOLUTIONS.get(self.resolution_combo.GetValue())
            settings['fps'] = self.fps_combo.GetValue()
            settings['encoder_preset'] = ENCODER_PRESETS.get(self.encoder_preset_combo.GetValue(), "medium")
        else:
            settings['output_dir'] = output_dir

        self.Hide()
        self.progress_dialog = ConversionProgressDialog(self)
        self.progress_dialog.Show()
        self.conversion_thread = ConversionWorkerThread(self, files_for_thread, settings, self.ffmpeg_path, self.ffprobe_path)
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
