import time
import os
import threading
import wx
import subprocess

class ShutdownControl(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Shutdown control")
        self.SetBackgroundColour(wx.Colour(240, 240, 240))  # Light gray

        self.panel = wx.Panel(self)
        self.panel.SetBackgroundColour(wx.Colour(230, 230, 230)) # Slightly darker gray

        self.hours_label = wx.StaticText(self.panel, label="Enter hours:")
        self.hours_text = wx.TextCtrl(self.panel)
        self.hours_text.SetBackgroundColour(wx.Colour(250, 250, 250))
        self.hours_text.SetForegroundColour(wx.Colour(30, 30, 30))

        self.minutes_label = wx.StaticText(self.panel, label="Enter minutes:")
        self.minutes_text = wx.TextCtrl(self.panel)
        self.minutes_text.SetBackgroundColour(wx.Colour(250, 250, 250))
        self.minutes_text.SetForegroundColour(wx.Colour(30, 30, 30))

        self.start_button = wx.Button(self.panel, label="Shutdown")
        self.start_button.SetBackgroundColour(wx.Colour(200, 100, 100))  # Muted red
        self.start_button.SetForegroundColour(wx.Colour(255, 255, 255))
        self.start_button.Bind(wx.EVT_BUTTON, self.on_start)
        
        self.restart_button = wx.Button(self.panel, label="Restart")
        self.restart_button.SetBackgroundColour(wx.Colour(200, 100, 100))  # Muted red
        self.restart_button.SetForegroundColour(wx.Colour(255, 255, 255))
        self.restart_button.Bind(wx.EVT_BUTTON, self.on_restart)
        
        self.hibernate_button = wx.Button(self.panel, label="Hibernate")
        self.hibernate_button.SetBackgroundColour(wx.Colour(200, 100, 100))  # Muted red
        self.hibernate_button.SetForegroundColour(wx.Colour(255, 255, 255))
        self.hibernate_button.Bind(wx.EVT_BUTTON, self.on_hibernate)
        
        self.sleep_button = wx.Button(self.panel, label="Fast startup")
        self.sleep_button.Bind(wx.EVT_BUTTON, self.on_sleep)
        
        self.cancel_button = wx.Button(self.panel, label="Cancel")
        self.cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)
        
        self.exit_button = wx.Button(self.panel, label="Exit")
        self.exit_button.Bind(wx.EVT_BUTTON, self.on_exit)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.hours_label, 0, wx.ALL, 5)
        sizer.Add(self.hours_text, 0, wx.ALL, 5)
        sizer.Add(self.minutes_label, 0, wx.ALL, 5)
        sizer.Add(self.minutes_text, 0, wx.ALL, 5)
        sizer.Add(self.start_button, 0, wx.ALL, 5)
        sizer.Add(self.restart_button, 0, wx.ALL, 5)
        sizer.Add(self.hibernate_button, 0, wx.ALL, 5)
        sizer.Add(self.sleep_button, 0, wx.ALL, 5)
        sizer.Add(self.cancel_button, 0, wx.ALL, 5)
        sizer.Add(self.exit_button, 0, wx.ALL, 5)
        
        self.panel.SetSizer(sizer)
        
        self.process = None  # Hold a reference to the subprocess
        
    def get_seconds(self):
        hours = self.hours_text.GetValue()
        minutes = self.minutes_text.GetValue()

        if hours:
            try:
                hours = int(hours)
            except ValueError:
                wx.MessageBox("Invalid input for hours. Please enter a valid number.", "Error", wx.OK | wx.ICON_ERROR)
                return
        else:
            hours = 0

        if minutes:
            try:
                minutes = int(minutes)
            except ValueError:
                wx.MessageBox("Invalid input for minutes. Please enter a valid number.", "Error", wx.OK | wx.ICON_ERROR)
                return
        else:
            minutes = 0

        minutes += hours * 60
        seconds = minutes * 60
        return seconds
        
    def execute_command(self, command):
        self.process = subprocess.Popen(command, shell=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    def on_start(self, event):
        hours = self.hours_text.GetValue()
        minutes = self.minutes_text.GetValue()
        seconds = self.get_seconds()
        if hours:
            try:
                hours = int(hours)
            except ValueError:
                wx.MessageBox("Invalid input for hours. Please enter a valid number.", "Error", wx.OK | wx.ICON_ERROR)
                return
        else:
            hours = 0
        
        if minutes:
            try:
                minutes = int(minutes)
            except ValueError:
                wx.MessageBox("Invalid input for minutes. Please enter a valid number.", "Error", wx.OK | wx.ICON_ERROR)
                return
        else:
            minutes = 0
        if minutes == 0 and hours == 0:
            dlg = wx.MessageDialog(self.panel, "Warning: You did not enter a time. If you press 'Yes', the current command will be executed immediately. Are you sure you want to continue?", "Confirmation", wx.YES_NO | wx.ICON_WARNING)
            result = dlg.ShowModal()
            dlg.Destroy()
            if result != wx.ID_YES:
                return

        minutes += hours * 60
        seconds = minutes * 60
        
        command = f"shutdown /s /t {seconds}"
        self.execute_command(command)
        wx.MessageBox(f"Shutdown command initiated for {minutes} minutes.", "Shutdown", wx.OK | wx.ICON_INFORMATION)
    
    def on_restart(self, event):
        hours = self.hours_text.GetValue()
        minutes = self.minutes_text.GetValue()
        seconds = self.get_seconds()
        if hours:
            try:
                hours = int(hours)
            except ValueError:
                wx.MessageBox("Invalid input for hours. Please enter a valid number.", "Error", wx.OK | wx.ICON_ERROR)
                return
        else:
            hours = 0
        
        if minutes:
            try:
                minutes = int(minutes)
            except ValueError:
                wx.MessageBox("Invalid input for minutes. Please enter a valid number.", "Error", wx.OK | wx.ICON_ERROR)
                return
        else:
            minutes = 0
        if minutes == 0 and hours == 0:
            dlg = wx.MessageDialog(self.panel, "Warning: You did not enter a time. If you press 'Yes', the current command will be executed immediately. Are you sure you want to continue?", "Confirmation", wx.YES_NO | wx.ICON_WARNING)
            result = dlg.ShowModal()
            dlg.Destroy()
            if result != wx.ID_YES:
                return

        minutes += hours * 60
        seconds = minutes * 60        
        
        command = f"shutdown /r /t {seconds}"
        self.execute_command(command)
        wx.MessageBox(f"Your computer will restart in  {minutes} minutes.", "Restart", wx.OK | wx.ICON_INFORMATION)
    
    def on_hibernate(self, event):
        hours = self.hours_text.GetValue()
        minutes = self.minutes_text.GetValue()
        if hours:
            try:
                hours = int(hours)
            except ValueError:
                wx.MessageBox("Invalid input for hours. Please enter a valid number.", "Error", wx.OK | wx.ICON_ERROR)
                return
        else:
            hours = 0

        if minutes:
            try:
                minutes = int(minutes)
            except ValueError:
                wx.MessageBox("Invalid input for minutes. Please enter a valid number.", "Error", wx.OK | wx.ICON_ERROR)
                return
        else:
            minutes = 0
        if minutes == 0 and hours == 0:
            dlg = wx.MessageDialog(self.panel, "Warning: You did not enter a time. If you press 'Yes', the current command will be executed immediately. Are you sure you want to continue?", "Confirmation", wx.YES_NO | wx.ICON_WARNING)
            result = dlg.ShowModal()
            dlg.Destroy()
            if result != wx.ID_YES:
                return

        minutes += hours * 60
        seconds = minutes * 60

        self.Hide()  # hide the application window

        def hibernate():
            time.sleep(seconds)  # delay before hibernating
            os.system("shutdown /h")  # execute the command

        threading.Thread(target=hibernate).start()

        wx.MessageBox(f"Hibernate command initiated for {minutes} minutes.", "Hibernate", wx.OK | wx.ICON_INFORMATION)

    def on_sleep(self, event):
        hours = self.hours_text.GetValue()
        minutes = self.minutes_text.GetValue()
        seconds = self.get_seconds()
        if hours:
            try:
                hours = int(hours)
            except ValueError:
                wx.MessageBox("Invalid input for hours. Please enter a valid number.", "Error", wx.OK | wx.ICON_ERROR)
                return
        else:
            hours = 0
        
        if minutes:
            try:
                minutes = int(minutes)
            except ValueError:
                wx.MessageBox("Invalid input for minutes. Please enter a valid number.", "Error", wx.OK | wx.ICON_ERROR)
                return
        else:
            minutes = 0
        if minutes == 0 and hours == 0:
            dlg = wx.MessageDialog(self.panel, "Warning: You did not enter a time. If you press 'Yes', the current command will be executed immediately. Are you sure you want to continue?", "Confirmation", wx.YES_NO | wx.ICON_WARNING)
            result = dlg.ShowModal()
            dlg.Destroy()
            if result != wx.ID_YES:
                return

        minutes += hours * 60
        seconds = minutes * 60
        
        command = f"shutdown /s /hybrid /t {seconds}"
        self.execute_command(command)
        wx.MessageBox(f"fast startup mode command initiated for {minutes} minutes.", "Fast startup", wx.OK | wx.ICON_INFORMATION)
    
    def on_cancel(self, event):
        subprocess.call("shutdown /a", shell=True)
        self.process = None
        wx.MessageBox("Shutdown command canceled.", "Cancel", wx.OK | wx.ICON_INFORMATION)
    
    def on_exit(self, event):
        self.Close(True)
