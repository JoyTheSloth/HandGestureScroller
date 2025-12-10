import tkinter as tk
from tkinter import ttk
import cv2
from PIL import Image, ImageTk
import threading
import pyautogui
from gesture_engine import HandTracker, GestureProcessor
import pythoncom

# Audio Imports
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

class GestureApp(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.configure(bg='#121212') # Dark background
        self.pack(fill=tk.BOTH, expand=True)
        self.create_widgets()
        
        # Camera and Logic setup
        self.cap = None
        self.is_running = False
        self.thread = None
        
        self.tracker = HandTracker(detection_con=0.7)
        self.processor = GestureProcessor(threshold=30, cooldown=1.0)
        
        # Audio Setup
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(
                IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self.volume = interface.QueryInterface(IAudioEndpointVolume)
            # self.volume.GetMute()
            # self.volume.GetMasterVolumeLevelScalar()
        except Exception as e:
            print(f"Audio Init Error: {e}")
            self.volume = None
        
    def create_widgets(self):
        # Styles
        style_font = ("Consolas", 12)
        bg_color = "#121212"
        fg_color = "#E0E0E0"
        accent_color = "#00FF41" # Matrix Green
        
        # Controls Frame
        self.controls_frame = tk.Frame(self, bg=bg_color)
        self.controls_frame.pack(side=tk.TOP, fill=tk.X, padx=20, pady=20)
        
        # Custom "Flat" Buttons
        self.btn_start = tk.Button(self.controls_frame, text="[ START SYSTEM ]", 
                                   command=self.start_detection,
                                   bg=bg_color, fg=accent_color, 
                                   font=("Consolas", 12, "bold"),
                                   relief=tk.FLAT, borderwidth=1,
                                   activebackground=accent_color, activeforeground=bg_color)
        self.btn_start.pack(side=tk.LEFT, padx=10)
        
        self.btn_stop = tk.Button(self.controls_frame, text="[ STOP ]", 
                                  command=self.stop_detection, 
                                  state=tk.DISABLED,
                                  bg=bg_color, fg="#FF4081", # Retro Pink for stop
                                  font=("Consolas", 12, "bold"),
                                  relief=tk.FLAT, borderwidth=1,
                                  activebackground="#FF4081", activeforeground=bg_color,
                                  disabledforeground="#555555")
        self.btn_stop.pack(side=tk.LEFT, padx=10)
        
        self.lbl_status = tk.Label(self.controls_frame, text="STATUS: IDLE", 
                                   bg=bg_color, fg=fg_color, font=("Consolas", 14))
        self.lbl_status.pack(side=tk.LEFT, padx=40)
        
        # Instructions Label
        self.lbl_instructions = tk.Label(self.controls_frame, 
                                         text="< TRIG: 3 FINGERS | PINCH: VOL >", 
                                         bg=bg_color, fg="#888888", font=("Consolas", 10))
        self.lbl_instructions.pack(side=tk.RIGHT, padx=10)
        
        # Video Frame with Border
        self.video_container = tk.Frame(self, bg=accent_color, padx=2, pady=2) # Acts as border
        self.video_container.pack(side=tk.TOP, padx=20, pady=10)
        
        self.video_label = tk.Label(self.video_container, bg="#000000")
        self.video_label.pack()
        
    def start_detection(self):
        if not self.is_running:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                print("Error: Could not open webcam.")
                return
                
            self.is_running = True
            self.btn_start.config(state=tk.DISABLED, cursor="arrow")
            self.btn_stop.config(state=tk.NORMAL, cursor="hand2")
            self.lbl_status.config(text="STATUS: SEARCHING...", fg="#00FF41")
            
            # Start background thread for video processing
            self.thread = threading.Thread(target=self.video_loop, daemon=True)
            self.thread.start()
            
    def stop_detection(self):
        self.is_running = False
        if self.cap:
            self.cap.release()
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.lbl_status.config(text="STATUS: HALTED", fg="#FF4081")
        # Clear video label
        self.video_label.config(image='')
        
    def on_close(self):
        self.stop_detection()
        self.master.destroy()

    def perform_action(self, gesture, value=None):
        def _action():
            if gesture == "NEXT":
                print("Action: Scrolling Next")
                pyautogui.press('pagedown')
            elif gesture == "PREVIOUS":
                print("Action: Scrolling Prev")
                pyautogui.press('pageup')
            elif gesture == "SET_VOLUME" and value is not None:
                # Value is 0.0 to 1.0
                try:
                    # Initialize COM for this thread
                    pythoncom.CoInitialize()
                    
                    # We need to get the interface instance INSIDE the thread (or marshal it)
                    # Ideally, create a new instance here for safety
                    devices = AudioUtilities.GetSpeakers()
                    interface = devices.Activate(
                        IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    volume_interface = interface.QueryInterface(IAudioEndpointVolume)
                    
                    volume_interface.SetMasterVolumeLevelScalar(value, None)
                    pythoncom.CoUninitialize()
                except Exception as e:
                    print(f"Vol Error: {e}")
        
        threading.Thread(target=_action, daemon=True).start()

    def video_loop(self):
        while self.is_running:
            ret, frame = self.cap.read()
            if ret:
                # 1. Flip frame for mirror view
                frame = cv2.flip(frame, 1)
                img_h, img_w, _ = frame.shape
                
                # 2. Hand Tracking
                frame = self.tracker.find_hands(frame) # Draws landmarks
                all_hands_list = self.tracker.find_all_positions(frame)
                
                # 3. Gesture Processing
                gesture, status_text = self.processor.process_gestures(all_hands_list, img_w)
                
                # 4. Handle Status & Action
                display_text = status_text
                
                # Check if it's a Volume Tuple response
                if isinstance(status_text, tuple):
                    display_text = status_text[0]
                    vol_level = status_text[1]
                    
                    # Perform Volume Action
                    self.perform_action("SET_VOLUME", vol_level)
                    
                    # Draw Volume Bar
                    bar_x, bar_y = 50, img_h - 50
                    bar_w, bar_h = img_w - 100, 20
                    
                    # Background Bar
                    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (50, 50, 50), -1)
                    # Fill Bar
                    fill_w = int(bar_w * vol_level)
                    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h), (0, 255, 65), -1)
                    cv2.putText(frame, f"VOL: {int(vol_level*100)}%", (bar_x, bar_y - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 65), 2)
                
                elif gesture:
                    self.perform_action(gesture)

                # Update Status Label (thread safe)
                self.master.after(0, lambda s=display_text: self.lbl_status.config(text=f"STATUS: {s.upper()}"))
                
                # 6. Convert to ImageTk
                cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
                img = Image.fromarray(cv2image)
                imgtk = ImageTk.PhotoImage(image=img)
                
                # 7. Update Video Panel
                self.master.after(0, self.update_video_widget, imgtk)
                
            else:
                break
        
        if self.cap:
            self.cap.release()

    def update_video_widget(self, imgtk):
        self.video_label.config(image=imgtk)
        self.video_label.image = imgtk
