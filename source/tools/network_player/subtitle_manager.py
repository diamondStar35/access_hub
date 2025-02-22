import wx
import os
import yt_dlp
from speech import speak
import app_vars
import concurrent.futures
import subprocess

class SubtitleManager:
    def __init__(self, parent, youtube_url):
        self.parent = parent
        self.youtube_url = youtube_url
        self.selected_language = None
        self.subtitles_info = None
        self.subtitle_filename = None
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        # Get the project root and ffmpeg path
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.ffmpeg_path = os.path.join(project_root, 'ffmpeg.exe')

    def download_subtitles(self):
        """Starts the subtitle download process."""
        config_dir = wx.StandardPaths.Get().GetUserConfigDir()
        subtitles_dir = os.path.join(config_dir, app_vars.app_name, "subtitles")
        self.clear_subtitles_directory(subtitles_dir)
        self.loading_dialog = wx.ProgressDialog(
            "Fetching Subtitles",
            "Please wait...",
            parent=self.parent,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
        )
        self.executor.submit(self.fetch_subtitles)

    def clear_subtitles_directory(self, subtitles_dir):
        """Clears all files in the subtitles directory."""
        if os.path.exists(subtitles_dir):
            for filename in os.listdir(subtitles_dir):
                file_path = os.path.join(subtitles_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except Exception as e:
                    print(f"Error deleting file {file_path}: {e}")

    def fetch_subtitles(self):
        """Fetches available subtitles using yt-dlp."""
        ydl_opts = {
            'quiet': True,
            'writesubtitles': True,
            'skip_download': True,
            'listsubtitles': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(self.youtube_url, download=False)

                if not info_dict:
                    raise Exception("Could not fetch video information.")

                subtitles = info_dict.get('subtitles', {})
                automatic_captions = info_dict.get('automatic_captions', {})
                self.subtitles_info = {**automatic_captions, **subtitles}

                if not self.subtitles_info:
                    wx.CallAfter(self.loading_dialog.Destroy)
                    wx.CallAfter(speak, "No subtitles found for this video.")
                    return

                self.lang_code_name_map = {}
                for lang_code, sub_info in self.subtitles_info.items():
                    lang_name = sub_info[0].get('name', lang_code)
                    self.lang_code_name_map[lang_code] = lang_name

                dialog_data = [f"{name} ({code})" for code, name in self.lang_code_name_map.items()]
                wx.CallAfter(self.show_language_selection_dialog, dialog_data)
        except Exception as e:
            wx.CallAfter(self.loading_dialog.Destroy)
            wx.CallAfter(speak, f"Error fetching subtitles: {e}")

    def show_language_selection_dialog(self, dialog_data):
        """Displays a dialog to select the subtitle language."""
        self.loading_dialog.Destroy()

        dialog = wx.SingleChoiceDialog(
            self.parent,
            "Select Subtitle Language",
            "Subtitle Language",
            dialog_data
        )

        if dialog.ShowModal() == wx.ID_OK:
            selected_index = dialog.GetSelection()
            self.selected_language = list(self.lang_code_name_map.keys())[selected_index]
            self.executor.submit(self.download_selected_subtitle)
        dialog.Destroy()

    def download_selected_subtitle(self):
        """Downloads the selected subtitle to the 'subtitles' folder in the config directory."""
        if not self.selected_language:
            return

        wx.CallAfter(self.create_progress_dialog)
        config_dir = wx.StandardPaths.Get().GetUserConfigDir()
        subtitles_dir = os.path.join(config_dir, app_vars.app_name, "subtitles")
        os.makedirs(subtitles_dir, exist_ok=True)
        # Define the output template for subtitle download
        subtitle_output_template = os.path.join(subtitles_dir, 'subtitle.%(ext)s')

        ydl_opts = {
            'quiet': True,
            'writeautomaticsub': True,
            'writesubtitles': True,
            'skip_download': True,
            'subtitleslangs': [self.selected_language],
            'subtitlesformat': 'best',
            'outtmpl': subtitle_output_template,
            'no_warnings': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(self.youtube_url, download=False)
                ydl.process_info(info_dict)

                # Find the downloaded subtitle file
            for filename in os.listdir(subtitles_dir):
                if filename.startswith("subtitle") and filename.endswith(".vtt"):
                    self.subtitle_filename = filename
                    break

            if self.subtitle_filename:
                wx.CallAfter(speak, "Subtitle downloaded successfully. Converting...")
                self.convert_to_srt(subtitles_dir)
            else:
                wx.CallAfter(self.loading_dialog.Destroy)
                wx.CallAfter(speak, "Subtitle download may have failed. Check the subtitles folder.")

        except yt_dlp.utils.DownloadError as e:
            wx.CallAfter(self.loading_dialog.Destroy)
            wx.CallAfter(speak, f"Download error: {e}")
        except Exception as e:
            wx.CallAfter(self.loading_dialog.Destroy)
            wx.CallAfter(speak, f"Error downloading subtitle: {e}")

    def convert_to_srt(self, subtitles_dir):
        """Converts the downloaded VTT subtitle to SRT format using FFmpeg."""
        vtt_subtitle_path = os.path.join(subtitles_dir, self.subtitle_filename)
        srt_subtitle_path = os.path.join(subtitles_dir, "subtitle.srt")

        try:
            subprocess.run([
                self.ffmpeg_path,
                "-i",
                vtt_subtitle_path,
                srt_subtitle_path
            ], check=True, capture_output=True)

            # Delete the original VTT file
            os.remove(vtt_subtitle_path)
            self.subtitle_filename = "subtitle.srt"
            wx.CallAfter(speak, "Subtitle converted successfully.")

        except subprocess.CalledProcessError as e:
            wx.CallAfter(speak, f"Error converting subtitle to SRT: {e}")
        except Exception as e:
            wx.CallAfter(speak, f"An unexpected error occurred during conversion: {e}")
        finally:
            wx.CallAfter(self.loading_dialog.Destroy)

    def create_progress_dialog(self):
        """Creates the progress dialog for the download operation."""
        self.loading_dialog = wx.ProgressDialog(
            "Downloading Subtitle",
            "Please wait...",
            parent=self.parent,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
        )