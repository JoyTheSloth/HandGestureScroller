import tkinter as tk
from gui import GestureApp

def main():
    root = tk.Tk()
    root.title("Gesture Scroll Controller")
    root.geometry("800x600")
    root.configure(bg='#121212')
    
    # Initialize the application
    app = GestureApp(root)
    app.pack(fill=tk.BOTH, expand=True)
    
    # Set exit handler
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    
    root.mainloop()

if __name__ == "__main__":
    main()
