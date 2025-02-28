import os
# global variables
app_name="Access Hub"
app_version="0.0.1b"
developer="Nolan Maher (Diamond star)"
website="https://github.com/diamondStar35/access_hub"
telegram="https://t.me/diamondStar35"
whatsapp="https://wa.me/201067573360"
mail="ramymaherali55@gmail.com"
# This is made to check if we run the app from the source folder or the root of the project
if os.path.exists("icon.ico"):
    icon_path="icon.ico"
else:
    icon_path = "source/icon.ico"