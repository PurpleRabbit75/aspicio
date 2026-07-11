#!/bin/python3

import sys, os
import curses
import subprocess
import threading
import time

# How often the background thread refreshes the node/topic list.
# The original code re-ran "ros2 node list" + "ros2 topic list" on
# EVERY render frame (i.e. every keypress, plus every idle timeout).
# Those are full CLI subprocess launches with DDS discovery overhead,
# so this was the single biggest cost in the program. A slow poll on
# a background thread keeps the list "fresh enough" for a TUI without
# ever blocking a keystroke.
LIST_REFRESH_INTERVAL = 2.0

# Timeout for a single "ros2 topic echo -n 1 <topic>" call.
ECHO_TIMEOUT = 1.0

# stdscr.getch() timeout. Rendering is now cheap (no subprocess calls
# happen in the render path), so this can be short: it just controls
# how quickly the UI notices background-thread updates and redraws.
INPUT_TIMEOUT_MS = 150


class RosListCache:
    """
    Owns the periodic "ros2 node list" / "ros2 topic list" polling.
    Runs on its own thread so the UI never blocks waiting on it.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._array = ["### NODES ###", "### TOPICS ###"]
        self._topics_index = 1  # index of "### TOPICS ###" in _array
        self._stop = False

    def start(self):
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def stop(self):
        self._stop = True

    def _loop(self):
        while not self._stop:
            try:
                self._refresh_once()
            except Exception:
                # Never let a transient ros2 CLI failure kill the poller.
                pass
            time.sleep(LIST_REFRESH_INTERVAL)

    def _refresh_once(self):
        nodes = subprocess.run(
            ["ros2", "node", "list"], capture_output=True, text=True
        ).stdout.split("\n")
        topics = subprocess.run(
            ["ros2", "topic", "list"], capture_output=True, text=True
        ).stdout.split("\n")

        # NOTE: the original inserted the literal 2-char string "\n" as
        # a standalone array element (["\n", "### TOPICS ###"]), which
        # rendered as a stray non-blank row. Use "" for an actual blank line.
        array = ["### NODES ###"] + nodes + ["", "### TOPICS ###"] + topics
        topics_index = array.index("### TOPICS ###")

        with self._lock:
            self._array = array
            self._topics_index = topics_index

    def get(self):
        """Returns (ros_data_array, topics_index) as an atomic snapshot."""
        with self._lock:
            return self._array, self._topics_index


class RosDetailCache:
    """
    Owns "ros2 <type> info <item>" and "ros2 topic echo -n 1 <item>" for
    whichever item is currently selected. Only re-fetches when the
    selected item actually changes, and does the fetch on a background
    thread so the (potentially 1s-blocking) echo call never freezes
    keystroke handling. While a fetch is in flight the last-known text
    (or a "Loading..." placeholder) is shown instead of blocking.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._current_item = None
        self._info_text = "Selected element not found"
        self._echo_text = "Selected element not found"

    def request(self, item, item_type):
        """
        Call every frame with the currently selected item. Kicks off a
        background fetch the first time an item is selected (or when
        selection changes) and always returns immediately with the
        best data currently available.
        """
        with self._lock:
            if item == self._current_item:
                return self._info_text, self._echo_text

            self._current_item = item
            self._info_text = "Loading..."
            self._echo_text = "Loading..."

        threading.Thread(
            target=self._fetch, args=(item, item_type), daemon=True
        ).start()
        return "Loading...", "Loading..."

    def _fetch(self, item, item_type):
        info_text = subprocess.run(
            ["ros2", item_type, "info", item], capture_output=True, text=True
        ).stdout

        if item_type == "topic":
            try:
                echo_text = subprocess.run(
                    ["ros2", "topic", "echo", "-n", "1", item],
                    capture_output=True,
                    text=True,
                    timeout=ECHO_TIMEOUT,
                ).stdout
            except subprocess.TimeoutExpired:
                echo_text = "No topic messages received within 1 second."
        else:
            echo_text = "Echo not applicable to selected element."

        with self._lock:
            # Only commit the result if the selection hasn't moved on
            # to something else while we were fetching.
            if self._current_item == item:
                self._info_text = info_text
                self._echo_text = echo_text

    def clear(self):
        with self._lock:
            self._current_item = None
            self._info_text = "Selected element not found"
            self._echo_text = "Selected element not found"


def draw_menu(stdscr):
    k = -1
    cursor_x = 0
    cursor_y = 0

    # One-time full clear at startup is fine; per-frame clears use
    # erase() instead (see main_loop) so curses can diff efficiently.
    stdscr.clear()
    stdscr.refresh()
    stdscr.timeout(INPUT_TIMEOUT_MS)

    curses.start_color()
    curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)

    list_cache = RosListCache()
    list_cache.start()
    detail_cache = RosDetailCache()

    def get_item_type(topics_index, i):
        # Was previously recomputed with two ros_data_array.index(...)
        # calls per item per frame; topics_index is now precomputed
        # once per list refresh instead.
        return "node" if i < topics_index else "topic"

    def get_info_window_x(ros_data_array):
        return 5 + max(len(i) for i in ros_data_array)

    def draw_box(stdscr, content_lines, x, y, title, addstr):
        top_left = chr(9484)
        top_right = chr(9488)
        bottom_left = chr(9492)
        bottom_right = chr(9496)
        vertical = chr(9474)
        horizontal = chr(9472)

        box_width = max(len(line) for line in content_lines) + 2 if content_lines else 2
        box_height = len(content_lines)

        horizontal_line = horizontal * (box_width - 2)
        addstr(y - 1, x - 1, top_left + horizontal_line + top_right)
        addstr(y + box_height, x - 1, bottom_left + horizontal_line + bottom_right)

        for i in range(box_height):
            addstr(y + i, x - 1, vertical)
            addstr(y + i, x + box_width - 2, vertical)

        addstr(y - 2, x - 1, f"### {title} ###")

    def get_echo_window_x(ros_data_array, info_lines):
        return max(
            67,
            5 + max(len(i) for i in ros_data_array) + max(len(i) for i in info_lines) + 1,
        )

    def main_loop(k, cursor_x, cursor_y):
        # erase() marks cells for redraw without forcing a full
        # touchwin() the way clear() does — curses can then diff
        # against the previous frame instead of repainting everything.
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        addstr = stdscr.addstr

        if k == curses.KEY_DOWN:
            cursor_y += 1
        elif k == curses.KEY_UP:
            cursor_y -= 1
        elif k == curses.KEY_RIGHT:
            cursor_x += 1
        elif k == curses.KEY_LEFT:
            cursor_x -= 1

        cursor_x = max(0, min(width - 1, cursor_x))
        cursor_y = max(0, min(height - 1, cursor_y))

        # Cheap: reads a cached snapshot, no subprocess call here.
        ros_data_array, topics_index = list_cache.get()
        start_ros_data_x = 0
        start_ros_data_y = 0

        statusbarstr = f"Press 'q' to exit | Pos: {cursor_x}, {cursor_y}"
        statusbarstr = statusbarstr + " " * (width - len(statusbarstr) - 1)
        stdscr.attron(curses.color_pair(3))
        addstr(height - 1, 0, statusbarstr)
        stdscr.attroff(curses.color_pair(3))

        info_text = "Selected element not found"
        echo_text = "Selected element not found"
        selected_index = None

        for i, line in enumerate(ros_data_array):
            global_y = i + start_ros_data_y + 1
            if global_y >= height - 1:
                break
            if cursor_y == global_y:
                selected_index = i
                stdscr.attron(curses.color_pair(3))
                addstr(global_y, start_ros_data_x, line[: width - 1])
                stdscr.attroff(curses.color_pair(3))
            else:
                addstr(global_y, start_ros_data_x, line[: width - 1])

        if selected_index is not None and 0 <= selected_index < len(ros_data_array):
            item = ros_data_array[selected_index]
            if item.startswith("/") and item in ros_data_array:
                item_type = get_item_type(topics_index, selected_index)
                # Non-blocking: returns cached/"Loading..." text
                # immediately, kicks off a background fetch only if
                # the selection changed since the last frame.
                info_text, echo_text = detail_cache.request(item, item_type)
        else:
            detail_cache.clear()

        # Split each text once and reuse everywhere, instead of the
        # original's 2-3 independent .split("\n") calls per text.
        info_lines = info_text.split("\n")
        echo_lines = echo_text.split("\n")

        info_window_x = get_info_window_x(ros_data_array)
        info_window_y = 3
        max_info_width = width - info_window_x - 2
        max_lines_allowed = (height - 1) - info_window_y
        for j, line in enumerate(info_lines[:max_lines_allowed]):
            addstr(info_window_y + j, info_window_x, line[:max_info_width])
        draw_box(stdscr, info_lines, info_window_x, info_window_y, "INFO", addstr)

        echo_window_x = get_echo_window_x(ros_data_array, info_lines)
        echo_window_y = 3
        max_echo_width = width - echo_window_x - 2
        max_lines_allowed = (height - 1) - echo_window_y
        for j, line in enumerate(echo_lines[:max_lines_allowed]):
            addstr(echo_window_y + j, echo_window_x, line[:max_echo_width])
        draw_box(stdscr, echo_lines, echo_window_x, echo_window_y, "ECHO", addstr)

        stdscr.move(cursor_y, cursor_x)

        return cursor_x, cursor_y

    cursor_x, cursor_y = main_loop(k, cursor_x, cursor_y)

    while True:
        k = stdscr.getch()
        if k == ord('q'):
            break
        cursor_x, cursor_y = main_loop(k, cursor_x, cursor_y)
        curses.doupdate()
        stdscr.noutrefresh()

    list_cache.stop()


def main():
    curses.wrapper(draw_menu)


if __name__ == "__main__":
    main()
