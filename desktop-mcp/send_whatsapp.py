# -*- coding: utf-8 -*-
"""Send WhatsApp message - improved version"""
import time
import pyautogui
import pyperclip

pyautogui.FAILSAFE = True

def send_message(message):
    """Send a message to WhatsApp using keyboard shortcuts"""
    
    # Step 1: Open WhatsApp via Start menu
    print("Opening WhatsApp...")
    pyautogui.press('win')
    time.sleep(0.5)
    pyautogui.typewrite('WhatsApp', interval=0.05)
    time.sleep(1)
    pyautogui.press('enter')
    time.sleep(2)
    
    # Step 2: Use Tab to navigate to input field (WhatsApp shortcut)
    # Or just click in the general input area
    print("Focusing input...")
    
    # Get screen size
    screen_w, screen_h = pyautogui.size()
    
    # WhatsApp input is usually at bottom-right area
    # Assume WhatsApp takes right half of screen after opening
    input_x = int(screen_w * 0.75)  # 75% from left
    input_y = int(screen_h * 0.9)   # 90% from top (near bottom)
    
    print(f"Screen: {screen_w}x{screen_h}, clicking at ({input_x}, {input_y})")
    
    pyautogui.click(input_x, input_y)
    time.sleep(0.3)
    
    # Step 3: Type message using clipboard
    print(f"Typing: {message}")
    pyperclip.copy(message)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.3)
    
    # Step 4: Send
    pyautogui.press('enter')
    print("Message sent!")
    return True

if __name__ == "__main__":
    import sys
    msg = sys.argv[1] if len(sys.argv) > 1 else "\u4f60\u597d"  # "你好"
    send_message(msg)
