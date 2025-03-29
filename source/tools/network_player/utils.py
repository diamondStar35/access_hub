import wx
import subprocess
import json
import os
import sys

def run_yt_dlp_json(url, format_selector=None, extra_args=None):
    """
    Runs yt-dlp.exe to get video info as JSON.

    Args:
        url (str): The YouTube video URL.
        format_selector (str, optional): yt-dlp format selection string (e.g., 'bv*+ba/b').
        extra_args (list, optional): List of additional command-line arguments.

    Returns:
        dict: Parsed JSON output from yt-dlp.
        None: If an error occurs.
    """
    if getattr(sys, 'frozen', False):
        project_root = os.path.dirname(sys.executable)
    else:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    yt_dlp_exe_path = os.path.join(project_root, 'yt-dlp.exe')

    if not os.path.exists(yt_dlp_exe_path):
        print(f"Error: yt-dlp.exe not found at {yt_dlp_exe_path}")
        wx.CallAfter(wx.MessageBox, f"Error: yt-dlp.exe not found at expected location:\n{yt_dlp_exe_path}", "Dependency Error", wx.OK | wx.ICON_ERROR)
        return None

    command = [
        yt_dlp_exe_path,
        '--dump-single-json', # Get info for the URL as a single JSON line
        '--no-playlist',
        '--quiet',
    ]

    if format_selector:
        command.extend(['-f', format_selector])
    if extra_args:
        command.extend(extra_args)
    command.append(url)

    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=subprocess.SW_HIDE))
        stdout, stderr = process.communicate(timeout=60)

        if process.returncode != 0:
            wx.CallAfter(wx.MessageBox, f"yt-dlp failed with error:\n{stderr}", "yt-dlp Error", wx.OK | wx.ICON_ERROR)
            return None

        if not stdout:
             wx.CallAfter(wx.MessageBox, "yt-dlp did not return video information.", "yt-dlp Error", wx.OK | wx.ICON_ERROR)
             return None

        try:
            return json.loads(stdout)
        except json.JSONDecodeError as json_err:
            wx.CallAfter(wx.MessageBox, f"Failed to parse video information from yt-dlp.\nError: {json_err}", "Parsing Error", wx.OK | wx.ICON_ERROR)
            return None
    except FileNotFoundError:
        print(f"Error: Command not found - {yt_dlp_exe_path}")
        wx.CallAfter(wx.MessageBox, f"Error: Could not execute yt-dlp.exe. Ensure it exists at:\n{yt_dlp_exe_path}", "Execution Error", wx.OK | wx.ICON_ERROR)
        return None
    except subprocess.TimeoutExpired:
        print("yt-dlp command timed out.")
        process.kill()
        wx.CallAfter(wx.MessageBox, "Fetching video information timed out.", "Timeout Error", wx.OK | wx.ICON_WARNING)
        return None
    except Exception as e:
        print(f"An unexpected error occurred running yt-dlp: {e}")
        wx.CallAfter(wx.MessageBox, f"An unexpected error occurred while getting video info:\n{e}", "Error", wx.OK | wx.ICON_ERROR)
        return None
