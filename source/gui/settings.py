import wx
from configobj import ConfigObj
import os
import app_vars

def get_settings_path():
    """Gets the path to the main application config file."""
    config_dir = os.path.join(wx.StandardPaths.Get().GetUserConfigDir(), app_vars.app_name)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    return os.path.join(config_dir, "settings.ini")

def get_file_path(filename="history.json"):
    """A general function to get the path for a specific file within the config directory."""
    config_dir = os.path.join(wx.StandardPaths.Get().GetUserConfigDir(), app_vars.app_name)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    return os.path.join(config_dir, filename)

def load_app_config():
    """Loads the main application config file or creates it if it doesn't exist."""
    config_path = get_settings_path()
    config = ConfigObj(config_path)
    if 'General' not in config:
        config['General'] = {}
    if 'YouTube' not in config:
         config['YouTube'] = {}
    return config


class SettingsPanel(wx.Panel):
    """Base class for all settings panels."""
    category_name = "Default"

    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        self.sizer = wx.BoxSizer(wx.VERTICAL)

        self.create_controls()
        self.load_settings()
        self.SetSizer(self.sizer)

    def create_controls(self):
        """Creates the controls for the panel.  Override in subclasses."""
        pass

    def load_settings(self):
        """Loads settings from the config file. Override in subclasses."""
        pass

    def save_settings(self):
        """Saves settings to the config file. Override in subclasses."""
        pass

    def on_setting_change(self, event=None):
         """Generic handler to save settings when a control value changes."""
         self.save_settings()


class SettingsDialog(wx.Dialog):
    def __init__(self, parent, config, config_path, title="Settings"):
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.panels = {}
        self.parent = parent
        self.config = config
        self.config_path = config_path

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.listbook_label = wx.StaticText(self, label="Categories:")
        main_sizer.Add(self.listbook_label, 0, wx.LEFT | wx.TOP, 10)

        self.listbook = wx.Listbook(self, wx.ID_ANY, style=wx.LB_LEFT)
        main_sizer.Add(self.listbook, 1, wx.EXPAND | wx.ALL, 5)

        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(self, wx.ID_OK)
        ok_button.Bind(wx.EVT_BUTTON, self.on_ok)
        cancel_button = wx.Button(self, wx.ID_CANCEL)
        button_sizer.AddButton(ok_button)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()
        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(main_sizer)
        self.listbook.Bind(wx.EVT_LISTBOOK_PAGE_CHANGED, self.on_page_changed)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def add_category(self, panel_class):
        """Adds a category and its panel to the dialog using the panel class.

        Args:
            panel_class (class): The class of the panel to add (must inherit from SettingsPanel).
        """
        if not issubclass(panel_class, SettingsPanel):
            raise TypeError("panel_class must be a subclass of SettingsPanel")

        # Check if the panel already exists.
        category_name = panel_class.category_name
        if category_name in self.panels:
            panel = self.panels[category_name]
            self.listbook.SetSelection(self.listbook.FindPage(panel))
            return

        panel = panel_class(self.listbook, self.config)  # Instantiate the panel
        self.panels[category_name] = panel
        panel.Reparent(self.listbook)  # Reparent to the listbook
        self.listbook.AddPage(panel, category_name)
        panel.load_settings()

        # Set accessibility information
        panel.SetAccessible(SettingsAccessibility(panel, category_name))
        self.listbook.SetSelection(0)
        self.listbook.SetFocus()

    def on_ok(self, event):
        """Saves settings and closes the dialog."""
        for panel in self.panels.values():
            panel.save_settings()
        try:
            self.config.write()
            self.EndModal(wx.ID_OK)
        except Exception as e:
            wx.MessageBox(f"Error saving settings: {e}", "Save Error", wx.OK | wx.ICON_ERROR)

    def on_page_changed(self, event):
        event.Skip()

    def on_close(self, event):
        self.Destroy()


class SettingsAccessibility(wx.Accessible):
    def __init__(self, panel, category_name):
        super().__init__()
        self.panel = panel
        self.category_name = category_name

    def GetName(self, childId=0):
        return (wx.ACC_OK, self.category_name)

    def GetRole(self, childId):
        return (wx.ACC_OK, wx.ROLE_SYSTEM_PROPERTYPAGE)

class GeneralSettingsPanel(SettingsPanel):
    category_name = "General"

    def create_controls(self):
        self.minimize_checkbox = wx.CheckBox(self, label="Minimize to tray on close")
        self.sizer.Add(self.minimize_checkbox, 0, wx.ALL, 5)
        self.minimize_checkbox.Bind(wx.EVT_CHECKBOX, self.on_setting_change)

        self.hide_main_window_checkbox = wx.CheckBox(self, label="Hide the main window when opening tools")
        self.sizer.Add(self.hide_main_window_checkbox, 0, wx.ALL, 5)
        self.hide_main_window_checkbox.Bind(wx.EVT_CHECKBOX, self.on_setting_change)

        self.check_updates_checkbox = wx.CheckBox(self, label="Check for updates at startup")
        self.sizer.Add(self.check_updates_checkbox, 0, wx.ALL, 5)
        self.check_updates_checkbox.Bind(wx.EVT_CHECKBOX, self.on_setting_change)

    def load_settings(self):
        """Loads the settings and converts to boolean."""
        minimize_on_close = self.config.get('General', {}).get('minimize_on_close', 'True')
        # Convert string to boolean
        if minimize_on_close.lower() == 'true':
            minimize_on_close = True
        elif minimize_on_close.lower() == 'false':
            minimize_on_close = False
        else:
            minimize_on_close = True  # Default if somehow invalid
        self.minimize_checkbox.SetValue(minimize_on_close)

        hide_on_open = self.config.get('General', {}).get('hide_on_open', 'True')
        hide_on_open = hide_on_open.lower() == 'true'
        self.hide_main_window_checkbox.SetValue(hide_on_open)

        check_updates = self.config.get('General', {}).get('check_for_updates', 'True')
        check_updates = check_updates.lower() == 'true'
        self.check_updates_checkbox.SetValue(check_updates)

    def save_settings(self):
        self.config['General']['minimize_on_close'] = self.minimize_checkbox.GetValue()
        self.config['General']['hide_on_open'] = self.hide_main_window_checkbox.GetValue()
        self.config['General']['check_for_updates'] = self.check_updates_checkbox.GetValue()

    def on_setting_change(self, event):
        self.save_settings() # Save the settings when any option is changed.
