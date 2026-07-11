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
    # curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
    # curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)

    

    # k is the last character pressed
    def main_loop(k, cursor_x, cursor_y):

        # Initialization
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        addstr = stdscr.addstr

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
            addstr(global_y, start_ros_data_x, ros_data_array[i][:width-1])
            stdscr.attroff(curses.color_pair(3))
            return get_info_window(ros_data_array, i), get_echo_window(ros_data_array, i)
        
        def print_item(i):
            addstr(global_y, start_ros_data_x, ros_data_array[i][:width-1])
        
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
        
        def draw_box(contents, x, y, title):

            top_left = chr(9484)
            top_right = chr(9488)
            bottom_left = chr(9492)
            bottom_right = chr(9496)
            vertical = chr(9474)
            horizontal = chr(9472)

            content_lines = contents.split("\n")
            width = max(len(line) for line in content_lines) + 2
            height = len(content_lines)

            horizontal_line = horizontal * (width - 2)
            addstr(y - 1, x - 1, top_left + horizontal_line + top_right)
            addstr(y + height, x - 1, bottom_left + horizontal_line + bottom_right)

            for i in range(height):
                addstr(y + i, x - 1, vertical)
                addstr(y + i, x + width - 2, vertical)

            addstr(y - 2, x - 1, f"### {title} ###")
        

        def get_echo_window_x(ros_data_array, info_window):
            return max(67, 5 + max([len(i) for i in ros_data_array]) + max([len(i) for i in info_window.split("\n")]) + 1)
        
        def get_echo_window(ros_data_array, i):
            if (i < len(ros_data_array)):
                item = ros_data_array[i]
                if (item.startswith("/")):
                    if (item in ros_data_array):
                        item_type = get_item_type(ros_data_array, i)
                        if item_type == "topic":
                            try:
                                echo_window = subprocess.run(
                                    ["ros2", item_type, "echo", "-n", "1", item],
                                    capture_output=True,
                                    text=True,
                                    timeout=1,
                                ).stdout
                            except subprocess.TimeoutExpired:
                                echo_window = "No topic messages received within 1 second."
                        else:
                            echo_window = "Echo not applicable to selected element."
                        return echo_window

            return "Selected element not found"
        

        
        ros_data_array = construct_ros_data_array()
        start_ros_data_x = 0
        start_ros_data_y = 0

        # Render status bar
        statusbarstr = f"Press 'q' to exit | Pos: {cursor_x}, {cursor_y}"
        statusbarstr = statusbarstr + " " * (width - len(statusbarstr) - 1)
        stdscr.attron(curses.color_pair(3))
        addstr(height-1, 0, statusbarstr)
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
        max_info_width = width - info_window_x - 2
        max_lines_allowed = (height - 1) - info_window_y
        for j, line in enumerate(info_window.split("\n")[:max_lines_allowed]):
            addstr(info_window_y + j, info_window_x, line[:max_info_width])
        draw_box(info_window, info_window_x, info_window_y, "INFO")

        # Render echo window
        echo_window_x = get_echo_window_x(ros_data_array, info_window)
        echo_window_y = 3
        max_echo_width = width - echo_window_x - 2
        max_lines_allowed = (height - 1) - echo_window_y
        for j, line in enumerate(echo_window.split("\n")[:max_lines_allowed]):
            addstr(echo_window_y + j, echo_window_x, line[:max_echo_width])
        draw_box(echo_window, echo_window_x, echo_window_y, "ECHO")
        

        stdscr.move(cursor_y, cursor_x)

    

        return cursor_x, cursor_y

    
    # Initial render
    cursor_x, cursor_y = main_loop(k, cursor_x, cursor_y)

    # Loop: wake on keypress or every 1s (timeout). Exit on 'q'.
    while True:
        k = stdscr.getch()
        if k == ord('q'):
            break
        cursor_x, cursor_y = main_loop(k, cursor_x, cursor_y)
        curses.doupdate()  # Refresh the screen after all updates have been made
        stdscr.noutrefresh()


def main():
    curses.wrapper(draw_menu)

if __name__ == "__main__":
    main()
