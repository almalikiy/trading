

import sys
import pyautogui
import time

# Usage:
# python pyautogui_order.py buy [window_hint]
# python pyautogui_order.py sell [window_hint]
# python pyautogui_order.py close [window_hint]
# python pyautogui_order.py close_by_index index [window_hint]

def focus_mt5(window_hint):
    mt5_windows = [w for w in pyautogui.getAllWindows() if window_hint in w.title]
    if not mt5_windows:
        print(f'Window with hint "{window_hint}" not found!')
        sys.exit(1)
    mt5_windows[0].activate()
    time.sleep(0.5)

def do_buy(window_hint):
    focus_mt5(window_hint)
    pyautogui.moveTo(430, 256)
    pyautogui.click()
    print('Clicked BUY at (430, 256)')

def do_sell(window_hint):
    focus_mt5(window_hint)
    pyautogui.moveTo(149, 256)
    pyautogui.click()
    print('Clicked SELL at (149, 256)')

def do_close(window_hint):
    focus_mt5(window_hint)
    # Default: close trade #1
    pyautogui.moveTo(438, 1410)
    pyautogui.click(button='right')
    time.sleep(0.3)
    # Koordinat menu Close (asumsi: X=550, Y=850)
    pyautogui.moveTo(550, 850)
    pyautogui.click()
    print('Closed trade #1')

def do_close_by_index(index, window_hint):
    focus_mt5(window_hint)
    base_x = 438
    base_y = 1409
    row_height = 20
    y = base_y + index * row_height
    pyautogui.moveTo(base_x, y)
    pyautogui.click(button='right')
    time.sleep(0.3)
    pyautogui.moveTo(550, y + 50)
    pyautogui.click()
    print(f'Closed trade at index {index} (y={y})')

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pyautogui_order.py [buy|sell|close|close_by_index] [index] [window_hint]")
        sys.exit(1)
    action = sys.argv[1].lower()
    window_hint = sys.argv[-1] if len(sys.argv) > 2 and not sys.argv[2].isdigit() else 'FinexBisnisSolusi'
    if action == 'buy':
        do_buy(window_hint)
    elif action == 'sell':
        do_sell(window_hint)
    elif action == 'close':
        do_close(window_hint)
    elif action == 'close_by_index':
        if len(sys.argv) < 3 or not sys.argv[2].isdigit():
            print('close_by_index membutuhkan parameter index (0=trade #1)')
            sys.exit(1)
        index = int(sys.argv[2])
        do_close_by_index(index, window_hint)
    else:
        print('Unknown action')
        sys.exit(1)
