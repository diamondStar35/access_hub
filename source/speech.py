import accessible_output3.outputs
speaker=accessible_output3.outputs.auto.Auto()

def speak(text, interrupt=True):
    speaker.speak(text, interrupt=interrupt)