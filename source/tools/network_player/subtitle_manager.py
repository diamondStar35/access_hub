import wx
import os
import sys
from .utils import run_yt_dlp_json
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
        if getattr(sys, 'frozen', False):
             project_root = os.path.dirname(sys.executable)
        else:
             project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.ffmpeg_dir = project_root
        self.yt_dlp_exe_path = os.path.join(project_root, 'yt-dlp.exe')

        # Verify ffmpeg.exe exists in the expected directory for clarity
        ffmpeg_exe_check = os.path.join(self.ffmpeg_dir, 'ffmpeg.exe')
        if not os.path.exists(ffmpeg_exe_check):
             print(f"Warning: ffmpeg.exe not found in the expected directory: {self.ffmpeg_dir}")


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
        """Fetches available subtitles, listing manual first, then unique automatic ones."""
        try:
            info_dict = run_yt_dlp_json(self.youtube_url, extra_args=['--write-subs', '--write-auto-subs'])
            if not info_dict:
                wx.CallAfter(self.loading_dialog.Destroy)
                return

            subtitles = info_dict.get('subtitles', {})
            automatic_captions = info_dict.get('automatic_captions', {})

            manual_subs_data = []
            auto_subs_data = []
            manual_codes = set()

            # Process manual subtitles first
            for lang_code, subs_list in subtitles.items():
                if subs_list:
                    lang_name = subs_list[0].get('name', lang_code)
                    display_name = f"{lang_name} ({lang_code})" # No marker
                    manual_subs_data.append((lang_code, display_name))
                    manual_codes.add(lang_code)

            # Process automatic captions, adding only if the language code wasn't in manual subs
            for lang_code, subs_list in automatic_captions.items():
                if subs_list and lang_code not in manual_codes:
                    lang_name = subs_list[0].get('name', lang_code)
                    display_name = f"{lang_name} ({lang_code})"
                    auto_subs_data.append((lang_code, display_name))

            # Sort each list alphabetically by display name
            manual_subs_data.sort(key=lambda item: item[1])
            auto_subs_data.sort(key=lambda item: item[1])

            # Combine the sorted lists: manual first, then auto
            combined_data = manual_subs_data + auto_subs_data
            if not combined_data:
                wx.CallAfter(self.loading_dialog.Destroy)
                wx.CallAfter(speak, "No subtitles found for this video.")
                return

            # Extract final lists for dialog and lookup based on the combined, sorted order
            self.sorted_lang_codes = [code for code, name in combined_data]
            dialog_data = [name for code, name in combined_data]
            if not dialog_data:
                 wx.CallAfter(self.loading_dialog.Destroy)
                 wx.CallAfter(speak, "No valid subtitle languages found to display.")
                 return

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
            self.selected_language = self.sorted_lang_codes[selected_index]
            self.executor.submit(self.download_selected_subtitle)
        dialog.Destroy()

    def download_selected_subtitle(self):
        """Downloads the selected subtitle as SRT using yt-dlp.exe."""
        if not self.selected_language:
            return

        wx.CallAfter(self.create_progress_dialog) # Show progress dialog

        config_dir = wx.StandardPaths.Get().GetUserConfigDir()
        subtitles_dir = os.path.join(config_dir, app_vars.app_name, "subtitles")
        os.makedirs(subtitles_dir, exist_ok=True)

        # Define the *exact* output path and filename for SRT
        # Using -o ensures the filename, -P sets the directory
        srt_output_path = os.path.join(subtitles_dir, 'subtitle.srt')
        # Use -P for path, -o for filename template (without extension)
        output_template = os.path.join(subtitles_dir, 'subtitle') # yt-dlp adds .lang.ext


        command = [
            self.yt_dlp_exe_path,
            '--no-warnings',
            '--sub-format', 'best',
            '--write-subs',
            '--write-auto-subs',
            '--sub-langs', self.selected_language,
            '--convert-subs', 'srt',
            '--skip-download',
            '--ffmpeg-location', self.ffmpeg_dir,
            '-P', subtitles_dir,
             '-o', 'subtitle.%(ext)s',
            self.youtube_url
        ]

        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', startupinfo=startupinfo)
            stdout, stderr = process.communicate(timeout=120) # Add timeout
            if process.returncode == 0:
                 expected_srt_filename = f'subtitle.{self.selected_language}.srt'
                 expected_srt_path = os.path.join(subtitles_dir, expected_srt_filename)
                 final_srt_path = os.path.join(subtitles_dir, 'subtitle.srt')

                 if os.path.exists(expected_srt_path):
                     try:
                         if os.path.exists(final_srt_path):
                             os.remove(final_srt_path)
                         os.rename(expected_srt_path, final_srt_path)
                         self.subtitle_filename = "subtitle.srt"
                         wx.CallAfter(speak, "Subtitle downloaded successfully.")
                     except OSError as rename_err:
                         wx.CallAfter(speak, "Subtitle downloaded, but failed to rename.")
                         self.subtitle_filename = expected_srt_filename
                 else:
                     # This case is less likely if returncode is 0, but check anyway
                     print(f"yt-dlp finished successfully, but expected subtitle file not found: {expected_srt_path}")
                     print(f"stdout: {stdout}")
                     print(f"stderr: {stderr}")
                     wx.CallAfter(speak, "Subtitle download finished, but the file could not be located.")
                     self.subtitle_filename = None
            else:
                wx.CallAfter(speak, f"Error downloading subtitle: yt-dlp failed. Check logs for details.")
                self.subtitle_filename = None
        except subprocess.TimeoutExpired:
            process.kill()
            wx.CallAfter(speak, "Subtitle download timed out.")
            self.subtitle_filename = None
        except Exception as e:
            wx.CallAfter(speak, f"Error downloading subtitle: {e}")
            self.subtitle_filename = None
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