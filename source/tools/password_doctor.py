import wx
from passwordmeter import test
from pwnedpasswords import check
import random

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
