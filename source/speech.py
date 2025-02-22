import accessible_output2.outputs
speaker=accessible_output2.outputs.auto.Auto()

def speak(text, interrupt=True):
    speaker.speak(text, interrupt=interrupt)