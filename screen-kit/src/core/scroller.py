from pynput.mouse import Controller

class Scroller:
    def __init__(self):
        self.mouse = Controller()
        
    def scroll(self, dy):
        """
        Emits a vertical scroll event.
        dy: positive for scrolling up, negative for scrolling down.
        """
        # On macOS, dy typically needs to be scaled down slightly for smooth scrolling
        # compared to raw pixel deltas.
        print(f"[Scroller] Emitting scroll event: dy={dy}")
        self.mouse.scroll(0, dy)
