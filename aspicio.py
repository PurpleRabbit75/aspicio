#!/bin/python3

import sys,os
import curses
import subprocess
import time

time_0 = time.time()

def draw_menu(stdscr):
    k = -1
    cursor_x = 0
    cursor_y = 0

    # Clear and refresh the screen for a blank canvas
    stdscr.clear()
    stdscr.refresh()

    # Wait for input up to 1000ms (1s) — returns -1 on timeout
    stdscr.timeout(1000)

    # Start colors in curses
    curses.start_color()
    curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)

    

    # k is the last character pressed
    def main_loop(k, cursor_x, cursor_y):

        # Initialization
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        # Move cursor
        if k == curses.KEY_DOWN:
            cursor_y = cursor_y + 1
        elif k == curses.KEY_UP:
            cursor_y = cursor_y - 1
        elif k == curses.KEY_RIGHT:
            cursor_x = cursor_x + 1
        elif k == curses.KEY_LEFT:
            cursor_x = cursor_x - 1

        # Define cursor boundaries
        cursor_x = max(0, cursor_x)
        cursor_x = min(width-1, cursor_x)

        cursor_y = max(0, cursor_y)
        cursor_y = min(height-1, cursor_y)

        # Functions

        def construct_ros_data_array():
            ros_data_array = ["### NODES ###"]
            ros_data_array = ros_data_array + subprocess.run(["ros2", "node", "list"], capture_output = True, text=True).stdout.split("\n")
            ros_data_array = ros_data_array + ["\n", "### TOPICS ###"]
            ros_data_array = ros_data_array + subprocess.run(["ros2", "topic", "list"], capture_output = True, text=True).stdout.split("\n")
            return ros_data_array

        def ros_data_y_to_global_y(ros_data_y):
            return ros_data_y + 1
        
        def select_item(i):
            stdscr.attron(curses.color_pair(3))
            stdscr.addstr(global_y, start_ros_data_x, ros_data_array[i][:width-1])
            stdscr.attroff(curses.color_pair(3))
            return get_info_window(ros_data_array, i), get_echo_window(ros_data_array, i)
        
        def print_item(i):
            stdscr.addstr(global_y, start_ros_data_x, ros_data_array[i][:width-1])
        
        def get_item_type(ros_data_array, i):
            nodes, topics = ros_data_array[0:ros_data_array.index("### TOPICS ###")], ros_data_array[ros_data_array.index("### TOPICS ###")+1:]
            if i < len(nodes):
                return "node"
            else:
                return "topic"
        

        def get_info_window_x(ros_data_array):
            return 5 + max([len(i) for i in ros_data_array])
        
        def get_info_window(ros_data_array, i):
            if (i < len(ros_data_array)):
                item = ros_data_array[i]
                if (item.startswith("/")):
                    if (item in ros_data_array):
                        item_type = get_item_type(ros_data_array, i)
                        info_window = subprocess.run(["ros2", item_type, "info", item], capture_output = True, text=True).stdout
                        return info_window

            return "Selected element not found"
        
        def draw_info_window_box(info_window, info_window_x, info_window_y):

            top_left = curses.ACS_ULCORNER
            top_right = curses.ACS_URCORNER
            bottom_left = curses.ACS_LLCORNER
            bottom_right = curses.ACS_LRCORNER
            vertical = curses.ACS_VLINE
            horizontal = curses.ACS_HLINE

            info_window_width = max([len(i) for i in info_window.split("\n")]) + 1
            info_window_height = len(info_window.split("\n"))

            stdscr.addch(info_window_y - 1, info_window_x - 1, top_left)
            stdscr.addch(info_window_y - 1, info_window_x + info_window_width + 1, top_right)
            stdscr.addch(info_window_y + info_window_height, info_window_x - 1, bottom_left)
            stdscr.addch(info_window_y + info_window_height, info_window_x + info_window_width + 1, bottom_right)
            for i in range(info_window_height):
                stdscr.addch(info_window_y + i, info_window_x - 1, vertical)
                stdscr.addch(info_window_y + i, info_window_x + info_window_width + 1, vertical)
            for i in range(info_window_width):
                stdscr.addch(info_window_y - 1, info_window_x + i, horizontal)
                stdscr.addch(info_window_y + info_window_height, info_window_x + i, horizontal)
            
            stdscr.addstr(info_window_y - 2, info_window_x - 1, "### INFO ###")
        

        def get_echo_window_x(ros_data_array, info_window):
            return max(67, 5 + max([len(i) for i in ros_data_array]) + max([len(i) for i in info_window.split("\n")]) + 1)
        
        def get_echo_window(ros_data_array, i):
            if (i < len(ros_data_array)):
                item = ros_data_array[i]
                if (item.startswith("/")):
                    if (item in ros_data_array):
                        item_type = get_item_type(ros_data_array, i)
                        echo_window = subprocess.run(["ros2", item_type, "echo", item], capture_output = True, text=True).stdout
                        return echo_window

            return "Selected element not found"
        
        def draw_echo_window_box(echo_window, echo_window_x, echo_window_y):

            top_left = curses.ACS_ULCORNER
            top_right = curses.ACS_URCORNER
            bottom_left = curses.ACS_LLCORNER
            bottom_right = curses.ACS_LRCORNER
            vertical = curses.ACS_VLINE
            horizontal = curses.ACS_HLINE

            echo_window_width = max([len(i) for i in echo_window.split("\n")]) + 1
            echo_window_height = len(echo_window.split("\n"))

            stdscr.addch(echo_window_y - 1, echo_window_x - 1, top_left)
            stdscr.addch(echo_window_y - 1, echo_window_x + echo_window_width + 1, top_right)
            stdscr.addch(echo_window_y + echo_window_height, echo_window_x - 1, bottom_left)
            stdscr.addch(echo_window_y + echo_window_height, echo_window_x + echo_window_width + 1, bottom_right)
            for i in range(echo_window_height):
                stdscr.addch(echo_window_y + i, echo_window_x - 1, vertical)
                stdscr.addch(echo_window_y + i, echo_window_x + echo_window_width + 1, vertical)
            for i in range(echo_window_width):
                stdscr.addch(echo_window_y - 1, echo_window_x + i, horizontal)
                stdscr.addch(echo_window_y + echo_window_height, echo_window_x + i, horizontal)
            
            stdscr.addstr(echo_window_y - 2, echo_window_x - 1, "### ECHO ###")



        

        # Declaration of strings
        statusbarstr = f"Press 'q' to exit | Pos: {cursor_x}, {cursor_y}"

        ros_data_array = construct_ros_data_array()

        start_ros_data_x = 0
        start_ros_data_y = 0

        # Render status bar
        stdscr.attron(curses.color_pair(3))
        stdscr.addstr(height-1, 0, statusbarstr)
        stdscr.addstr(height-1, len(statusbarstr), " " * (width - len(statusbarstr) - 1))
        stdscr.attroff(curses.color_pair(3))

        # Render ROS node/topic data
        info_window, echo_window = "Selected element not found", "Selected element not found"
        for i in range(len(ros_data_array)):
            ros_data_y = i + start_ros_data_y
            global_y = ros_data_y_to_global_y(ros_data_y)
    
            if (global_y < height - 1):
                if (cursor_y == global_y):
                    info_window, echo_window = select_item(i)
                else:
                    print_item(i)
        
        # Render info window
        info_window_x = get_info_window_x(ros_data_array)
        info_window_y = 3
        info_lines = info_window.splitlines()
        max_info_width = width - info_window_x - 2
        for j, line in enumerate(info_lines):
            if info_window_y + j >= height - 1:
                break
            stdscr.addstr(info_window_y + j, info_window_x, line[:max_info_width])
        draw_info_window_box(info_window, info_window_x, info_window_y)

        # Render echo window
        echo_window_x = get_echo_window_x(ros_data_array, info_window)
        echo_window_y = 3
        echo_lines = echo_window.splitlines()
        max_echo_width = width - echo_window_x - 2
        for j, line in enumerate(echo_lines):
            if echo_window_y + j >= height - 1:
                break
            stdscr.addstr(echo_window_y + j, echo_window_x, line[:max_echo_width])
        draw_echo_window_box(echo_window, echo_window_x, echo_window_y)

        stdscr.move(cursor_y, cursor_x)

        # Refresh the screen
        stdscr.refresh()

        return cursor_x, cursor_y

    
    # Initial render
    cursor_x, cursor_y = main_loop(k, cursor_x, cursor_y)

    # Loop: wake on keypress or every 1s (timeout). Exit on 'q'.
    while True:
        k = stdscr.getch()
        if k == ord('q'):
            break
        cursor_x, cursor_y = main_loop(k, cursor_x, cursor_y)


def main():
    curses.wrapper(draw_menu)

if __name__ == "__main__":
    main()
