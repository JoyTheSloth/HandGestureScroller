import cv2
import mediapipe as mp
import time

class HandTracker:
    def __init__(self, mode=False, max_hands=2, detection_con=0.7, track_con=0.5):
        self.mode = mode
        self.max_hands = max_hands
        self.detection_con = detection_con
        self.track_con = track_con
        
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=self.mode,
            max_num_hands=self.max_hands,
            min_detection_confidence=self.detection_con,
            min_tracking_confidence=self.track_con
        )
        self.mp_draw = mp.solutions.drawing_utils

    def find_hands(self, img, draw=True):
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self.results = self.hands.process(img_rgb)
        
        if self.results.multi_hand_landmarks:
            for hand_lms in self.results.multi_hand_landmarks:
                if draw:
                    self.mp_draw.draw_landmarks(img, hand_lms, self.mp_hands.HAND_CONNECTIONS)
        return img

    def find_all_positions(self, img):
        # Returns a list of separate landmark lists for each detected hand
        all_hands_list = []
        if self.results.multi_hand_landmarks:
            for my_hand in self.results.multi_hand_landmarks:
                lm_list = []
                for id, lm in enumerate(my_hand.landmark):
                    h, w, c = img.shape
                    cx, cy = int(lm.x * w), int(lm.y * h)
                    lm_list.append([id, cx, cy])
                all_hands_list.append(lm_list)
        return all_hands_list

class GestureProcessor:
    def __init__(self, threshold=30, cooldown=1.0):
        self.threshold = threshold
        self.cooldown = cooldown
        self.last_gesture_time = 0
        self.prev_y = None
        
        # State: "SCROLL" or "VOLUME"
        self.state = "SCROLL" 
        self.volume_level = 0.5 # 0.0 to 1.0
        self.last_vol_change_time = 0

    def get_fingers_up(self, lm_list):
        # Tips: Thumb=4, Index=8, Middle=12, Ring=16, Pinky=20
        fingers = []
        
        # Thumb (Approximation based on x relative to knuckle) - tricky, skipping for simple check
        # Use only 4 long fingers for reliability? 
        # Requirement: "3 fingers first". Usually Index, Middle, Ring.
        
        # Index
        if lm_list[8][2] < lm_list[6][2]: fingers.append(1)
        else: fingers.append(0)
        
        # Middle
        if lm_list[12][2] < lm_list[10][2]: fingers.append(1)
        else: fingers.append(0)
        
        # Ring
        if lm_list[16][2] < lm_list[14][2]: fingers.append(1)
        else: fingers.append(0)
        
        # Pinky
        if lm_list[20][2] < lm_list[18][2]: fingers.append(1)
        else: fingers.append(0)
        
        return fingers # [Index, Middle, Ring, Pinky]

    def is_pinching(self, lm_list):
        # Pinch: Distance between Thumb Tip (4) and Index Tip (8) is small
        x1, y1 = lm_list[4][1], lm_list[4][2]
        x2, y2 = lm_list[8][1], lm_list[8][2]
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        return length < 40 # Threshold for pinch

    def process_gestures(self, all_hands_list, img_width):
        current_time = time.time()
        status_text = f"MODE: {self.state}"
        gesture_action = None
        
        # --- STATE: SCROLL (Default) ---
        if self.state == "SCROLL":
            # Check for Mode Switch Trigger: 3 Fingers Up (Index, Middle, Ring) on ANY hand
            triggered = False
            for lm_list in all_hands_list:
                fingers = self.get_fingers_up(lm_list)
                # Check for [1, 1, 1, 0] -> Index, Middle, Ring UP, Pinky DOWN
                if fingers == [1, 1, 1, 0]:
                     self.state = "VOLUME"
                     self.last_gesture_time = current_time
                     return "MODE_VOL", "MODE: VOLUME ACTIVE"
            
            # Normal Scroll Logic (on first hand detected)
            if all_hands_list:
                lm_list = all_hands_list[0] # Use primary hand
                # Basic specific scroll logic reusing prev code
                _, _, cy = lm_list[9] 
                
                # Check cooldown specifically for scroll
                if current_time - self.last_gesture_time > self.cooldown:
                    if self.prev_y is not None:
                        dy = cy - self.prev_y
                        if dy < -self.threshold:
                            self.last_gesture_time = current_time
                            self.prev_y = cy
                            return "NEXT", "SCROLL DOWN (NEXT)"
                        elif dy > self.threshold:
                            self.last_gesture_time = current_time
                            self.prev_y = cy
                            return "PREVIOUS", "SCROLL UP (PREV)"
                    self.prev_y = cy
                else:
                    status_text = "COOLDOWN..."
            else:
                self.prev_y = None
                status_text = "NO HAND"

        # --- STATE: VOLUME ---
        elif self.state == "VOLUME":
            status_text = "MODE: VOLUME (PINCH 2 HANDS)"
            
            # Check for Exit Condition (Timeout logic or specific gesture? Let's use 3 fingers again to toggle off or just 5 sec timeout?)
            # Requirement: "Pinch and move". 
            
            # Logic: Need 2 hands. Both pinching.
            if len(all_hands_list) == 2:
                h1 = all_hands_list[0]
                h2 = all_hands_list[1]
                
                if self.is_pinching(h1) and self.is_pinching(h2):
                    # Calculate midpoint of both hands to determine "slider" position
                    h1_x = h1[9][1]
                    h2_x = h2[9][1]
                    avg_x = (h1_x + h2_x) / 2
                    
                    # Define Active Zone (e.g., 20% to 80% of screen width)
                    # This prevents hands from going out of frame
                    margin = img_width * 0.2
                    active_width = img_width - (2 * margin)
                    
                    # Normalize to relative position in active zone
                    rel_x = avg_x - margin
                    vol_per = rel_x / active_width
                    vol_per = max(0.0, min(1.0, vol_per)) # Clamp 0.0 to 1.0
                    
                    # Smoothing (Exponential Moving Average)
                    # New Value = Current * alpha + target * (1-alpha)
                    # Lower alpha = smoother/slower, Higher = responsive
                    self.volume_level = (self.volume_level * 0.8) + (vol_per * 0.2)
                    
                    status_text = f"VOL: {int(self.volume_level*100)}%"
                    return "SET_VOLUME", (status_text, self.volume_level)
            
            # Auto-exit if idle specifically for Volume? 
            # Let's keep it simple: Toggle off if no hands for 2 seconds
            if not all_hands_list:
                 if current_time - self.last_gesture_time > 2.0:
                     self.state = "SCROLL"
                     return "MODE_SCROLL", "MODE: SCROLL REVERT"
            else:
                # Keep alive if hands are present
                self.last_gesture_time = current_time

        return gesture_action, status_text
