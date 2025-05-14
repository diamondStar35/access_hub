import wx
from speech import speak
import paramiko
import os
import time
import threading
import re


class AccessibleTerminal(wx.Frame):
    def __init__(self, parent, server_host, server_port, username, password, session_name, key_file_path=None):
        super(AccessibleTerminal, self).__init__(parent, title=f"SSH Terminal - {username}@{server_host}", size=(800, 600))
        self.session_name = session_name
        self.server_host = server_host
        self.server_port = server_port
        self.username = username
        self.password = password
        self.key_file_path = key_file_path
        self.ssh_client = None
        self.channel = None
        self.is_connected = False
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')  # ANSI escape regex

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        entry_label = wx.StaticText(panel, label="Entry:")
        vbox.Add(entry_label, 0, wx.ALL | wx.ALIGN_LEFT, 5)

        self.entry_text = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.entry_text.Bind(wx.EVT_TEXT_ENTER, self.on_command_enter)
        vbox.Add(self.entry_text, 0, wx.ALL | wx.EXPAND, 5)

        output_label = wx.StaticText(panel, label="Output:")
        vbox.Add(output_label, 0, wx.ALL | wx.ALIGN_LEFT, 5)

        self.output_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        vbox.Add(self.output_text, 1, wx.ALL | wx.EXPAND, 5)

        panel.SetSizer(vbox)
        self.Centre()
        self.Show(True)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        threading.Thread(target=self.connect_ssh, daemon=True).start()


    def connect_ssh(self):
        try:
            self.display_output("Connecting to SSH server...\n")
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            if self.key_file_path:
                 # Check if key file exists before attempting connection
                 if not os.path.exists(self.key_file_path):
                      error_msg = f"SSH Key File not found: {self.key_file_path}"
                      self.display_output(f"\nConnection failed: {error_msg}\n")
                      speak(error_msg, interrupt=True)
                      self.is_connected = False
                      return

                 self.ssh_client.connect(self.server_host, port=self.server_port, username=self.username, key_filename=self.key_file_path)
            else:
                 self.ssh_client.connect(self.server_host, port=self.server_port, username=self.username, password=self.password)
            self.channel = self.ssh_client.get_transport().open_session()
            self.channel.get_pty()
            self.channel.invoke_shell()

            self.is_connected = True
            self.display_output("Connected to SSH server.\n")
            speak("Connected to SSH server.", interrupt=True)
            threading.Thread(target=self.receive_output, daemon=True).start()

        except FileNotFoundError as e:
            error_msg = f"Connection failed: Key file not found: {e}"
            self.display_output(f"\n{error_msg}\n")
            speak(error_msg, interrupt=True)
            self.is_connected = False
            wx.CallAfter(self.Destroy)

        except paramiko.AuthenticationException:
            error_msg = "Connection failed: Authentication failed. Check username, password, or key file."
            self.display_output(f"\n{error_msg}\n")
            speak(error_msg, interrupt=True)
            self.is_connected = False
            wx.CallAfter(self.Destroy)

        except paramiko.SSHException as e:
            error_msg = f"Connection failed: SSH error: {e}"
            self.display_output(f"\n{error_msg}\n")
            speak(error_msg, interrupt=True)
            self.is_connected = False
            wx.CallAfter(self.Destroy)

        except Exception as e:
            error_msg = f"Connection failed: An unexpected error occurred: {e}"
            self.display_output(f"\n{error_msg}\n")
            speak(error_msg, interrupt=True)
            self.is_connected = False
            wx.CallAfter(self.Destroy)

    def on_command_enter(self, event):
        command = self.entry_text.GetValue()
        self.entry_text.Clear()
        if not self.is_connected or not self.channel or not self.channel.active:
            self.display_output("Not connected to SSH server or connection closed.\n")
            speak("Not connected to SSH server or connection closed.", interrupt=True)
            self.entry_text.Disable()
            return

        self.display_output(f">> {command}\n")
        try:
            self.channel.send(command + "\n")
        except Exception as e:
           self.display_output(f"\nError sending command: {e}\n")
           speak(f"Error sending command: {e}", interrupt=True)
           self.is_connected=False
           self.entry_text.Disable()

    def receive_output(self):
        while self.is_connected and self.channel and self.channel.active:
            if self.channel.recv_ready():
                try:
                    output = self.channel.recv(4096).decode("utf-8", errors="ignore")
                    if output:
                        cleaned_output = self.ansi_escape.sub('', output)
                        self.display_output(cleaned_output)
                        for line in cleaned_output.splitlines():
                           if line.strip(): # Speak only if line is not blank
                              speak(line, interrupt=False)
                except EOFError:
                        self.display_output("\nConnection closed by remote host.\n")
                        speak("Connection closed by remote host.", interrupt=True)
                        self.is_connected=False
                        wx.CallAfter(self.entry_text.Disable)
                        wx.CallAfter(self.Destroy)
                        break
                except Exception as e:
                    self.display_output(f"\nError receiving data from server: {e}\n")
                    speak(f"Error receiving data from server: {e}", interrupt=True)
                    self.is_connected=False
                    wx.CallAfter(self.entry_text.Disable)
                    wx.CallAfter(self.Destroy)

            else:
                time.sleep(0.1)  # Reduce CPU usage

    def display_output(self, text):
        wx.CallAfter(self.output_text.AppendText, text)

    def on_close(self):
       if self.is_connected:
            dlg = wx.MessageDialog(self, "Do you want to disconnect from the current SSH session?", "Disconnect", wx.YES_NO | wx.ICON_QUESTION)
            result = dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_YES:
               self.disconnect_ssh()
               return True  # Confirmed disconnect
            else:
               return False
       else:
           return True

    def disconnect_ssh(self):
        if self.channel:
          try:
              self.channel.close()
              speak("SSH Channel Closed.", interrupt=True)
          except Exception as e:
               speak(f"Error closing channel: {e}", interrupt=True)

        if self.ssh_client:
            try:
                 self.ssh_client.close()
                 speak("SSH connection closed.", interrupt=True)
            except Exception as e:
                 speak(f"Error closing connection: {e}", interrupt=True)
        self.is_connected = False

    def OnClose(self, event):
        if self.is_connected:  # Only ask if it is connected
            if self.on_close():
                event.Skip()
            else:
                event.Veto()
        else:
            event.Skip()

