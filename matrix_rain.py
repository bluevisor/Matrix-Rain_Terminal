#!/usr/bin/env python3
import curses
import random
import time
import sys

# --- Configuration ---
MIN_STREAM_LENGTH = 7       # Minimum characters in a stream
MAX_STREAM_LENGTH = 38      # Maximum characters in a stream
STREAM_SPEED_MIN = 1        # Fastest speed (lower value = faster, updates every N frames)
STREAM_SPEED_MAX = 15       # Slowest speed (higher value = slower)
FRAME_DELAY = 0.03          # Seconds between frames (~33 FPS). Adjusted for potentially faster feel.
STREAM_DENSITY = 0.6        # Chance (0 to 1) for a column to have an active stream
FADE_LENGTH = 5             # Number of characters at the tail to apply fading logic. Increased slightly.
HEAD_CHAR_BRIGHTNESS = curses.A_BOLD # Attribute for the head character (already set to A_BOLD)
SECOND_CHAR_BRIGHTNESS = curses.A_BOLD # Attribute for the second character

# Using Half-width Katakana characters + numbers + symbols (adjust as desired)
# CHAR_SET = list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ.:=*+-<>")
# Alternative: Katakana only
CHAR_SET = [chr(i) for i in range(0xFF61, 0xFF9F)]
# CHAR_SET.extend([str(i) for i in range(10)])


class RainStream:
    """Represents a single falling stream of characters."""
    def __init__(self, col, height, width):
        self.col = col
        self.height = height
        self.width = width
        # Ensure stream length config is valid relative to screen height
        self.max_len = min(MAX_STREAM_LENGTH, height - 1)
        self.min_len = min(MIN_STREAM_LENGTH, self.max_len)
        if self.min_len <= 2: # Need at least 3 for head/second/body distinction
            self.min_len = 3
        if self.max_len < self.min_len:
             self.max_len = self.min_len

        self._reset()

    def _get_random_char(self):
        """Returns a random character from the defined set."""
        return random.choice(CHAR_SET)

    def _reset(self):
        """Resets the stream to start again from the top."""
        if self.min_len >= self.max_len:
             self.length = self.min_len
        else:
            self.length = random.randint(self.min_len, self.max_len)

        # Start position: Ensure it can appear smoothly from top
        self.y = random.randint(-self.length, -1) # Start above screen

        # Speed: Lower value = faster updates
        self.speed = random.randint(STREAM_SPEED_MIN, STREAM_SPEED_MAX)
        # Initialize characters (ensure list isn't longer than self.length initially)
        self.chars = [self._get_random_char() for _ in range(random.randint(1, self.length))] # Start with partial stream?
        # self.chars = [self._get_random_char() for _ in range(self.length)] # Start with full stream?

        self.update_counter = 0 # Used with speed to control update frequency

    def update(self, current_height):
        """Updates the stream's position and characters."""
        # Update height in case of resize
        self.height = current_height
        self.max_len = min(MAX_STREAM_LENGTH, self.height - 1)


        self.update_counter += 1
        if self.update_counter >= self.speed: # Use >= for speeds > 1
            self.y += 1
            self.update_counter = 0 # Reset counter after move

            # Check if stream's head has moved completely off the bottom
            if self.y >= self.height + self.length: # Check based on where tail *would* be
                self._reset()
                return # Don't need to update chars if resetting

            # Add new head character
            new_char = self._get_random_char()
            self.chars.insert(0, new_char) # Add to the front (head)

            # Remove tail character *only* if the stream has reached its target length
            if len(self.chars) > self.length:
                 self.chars.pop() # Remove from the back (tail)

        # Randomly change some characters (glitch effect) - Apply even if not moving this frame
        # Exclude the head and potentially the second character from glitching?
        change_start_index = 2 # Start glitching from the 3rd character
        if len(self.chars) > change_start_index:
            for i in range(change_start_index, len(self.chars)):
                # Increase probability slightly for faster glitching if desired
                if random.random() < 0.05: # 5% chance per char per frame
                    self.chars[i] = self._get_random_char()


    def draw(self, screen):
        """Draws the stream on the curses screen with fading tail and bright second char."""
        last_drawn_y = -1 # Keep track of the last y position drawn by this stream
        stream_len = len(self.chars)

        for i, char in enumerate(self.chars):
            current_y = self.y - i

            # Ensure the character is within screen bounds vertically
            if 0 <= current_y < self.height:
                try:
                    attributes = 0 # Start with no attributes

                    if i == 0: # Head character
                        attributes = curses.color_pair(2) | HEAD_CHAR_BRIGHTNESS # White + Bold
                    elif i == 1 and stream_len > 1: # Second character
                        attributes = curses.color_pair(1) | SECOND_CHAR_BRIGHTNESS # Green + Bold
                    else:
                        # Body and Fading Tail Logic
                        # Determine if in fading tail section (last FADE_LENGTH chars)
                        # Ensure FADE_LENGTH is not longer than the stream allows (minus head/second)
                        effective_fade_len = min(FADE_LENGTH, max(1, stream_len - 2))

                        # Index from the end of the stream (0 = last char, 1 = second last, ...)
                        index_from_end = stream_len - 1 - i

                        if index_from_end < effective_fade_len:
                            # Character is within the fading zone
                            # Make the latter half of the fade zone use A_DIM
                            # Example: FADE_LENGTH=5. Indices from end: 0,1,2,3,4
                            # We want 0, 1, 2 (approx half) to be dim.
                            if index_from_end < effective_fade_len / 2.0:
                                attributes = curses.color_pair(1) | curses.A_DIM # Dim Green
                            else:
                                attributes = curses.color_pair(1) # Normal Green (start of fade)
                        else:
                             # Body character (not head, not second, not fading)
                            attributes = curses.color_pair(1) # Normal Green

                    # Add the character
                    screen.addstr(current_y, self.col, char, attributes)
                    last_drawn_y = current_y # Update last drawn position

                except curses.error:
                    # Handle potential error if trying to write outside bounds
                    pass # Silently ignore, common near corners

        # Erase the character that was at the tail position in the *previous* frame
        # This happens only when the stream has reached its full length and is moving
        if len(self.chars) >= self.length: # Check if tail is being popped
            tail_erase_y = self.y - self.length # Position where the last char *was*
            # Ensure erase position is valid and below the current head
            if 0 <= tail_erase_y < self.height and tail_erase_y < self.y:
                 try:
                     screen.addstr(tail_erase_y, self.col, ' ')
                 except curses.error:
                     pass


def main(screen):
    """Main function to run the Matrix rain effect."""
    # --- Curses Setup ---
    curses.curs_set(0) # Hide the cursor
    screen.nodelay(True) # Make getch non-blocking
    screen.timeout(int(FRAME_DELAY * 1000)) # Set timeout for getch

    curses.start_color()
    if curses.has_colors():
        try:
            curses.use_default_colors()
            bg_color = -1
        except curses.error:
             bg_color = curses.COLOR_BLACK

        # Pair 1: Green text, default/black background (Body, Dim Tail, Second Char)
        curses.init_pair(1, curses.COLOR_GREEN, bg_color)
        # Pair 2: White text, default/black background (Bright Head)
        curses.init_pair(2, curses.COLOR_WHITE, bg_color)
    else:
        print("Terminal does not support colors. Exiting.")
        return

    # --- Initialization ---
    height, width = screen.getmaxyx()
    streams = []

    def create_streams(w, h):
        new_streams = []
        if h <= 2: return [] # Not enough height for effect
        for col in range(w):
            if random.random() < STREAM_DENSITY:
                new_streams.append(RainStream(col, h, w))
        return new_streams

    streams = create_streams(width, height)

    if not streams and (width > 0 and height > 2):
        print("Density might be too low, or terminal too narrow. No streams created.")
        # Optionally wait or exit
        time.sleep(2)
        # return

    # --- Main Loop ---
    frame_count = 0 # For potential future use (e.g., performance timing)
    while True:
        try:
            # --- Input Handling ---
            key = screen.getch()
            if key == ord('q') or key == 27: # Quit on 'q' or ESC
                break
            elif key == curses.KEY_RESIZE:
                 # Handle resize event more robustly
                 new_height, new_width = screen.getmaxyx()
                 if new_height != height or new_width != width:
                     # Check if new size is viable
                     if new_height <= 2 or new_width <= 0:
                          screen.clear()
                          msg = "Terminal too small!"
                          try: screen.addstr(0,0, msg)
                          except: pass
                          screen.refresh()
                          time.sleep(1)
                          # Keep checking size in a loop? Or just exit? For now, just update vars.
                          height, width = new_height, new_width
                          streams = [] # Clear streams if too small
                     else:
                          height, width = new_height, new_width
                          screen.clear() # Clear screen before recreating streams
                          screen.refresh() # Apply clear immediately
                          streams = create_streams(width, height) # Recreate streams for new size
                 continue # Skip rest of loop iteration to avoid drawing with old/bad state

            # --- Update and Draw ---
            screen.erase() # Clear buffer for this frame

            active_streams_exist = False
            for stream in streams:
                stream.update(height) # Pass current height for dynamic adjustment
                stream.draw(screen)
                active_streams_exist = True

            if not active_streams_exist and width > 0 and height > 2:
                # Handle case where density was low and no streams were initially created
                 try: screen.addstr(height // 2, width // 2 - 10, "Waiting for streams...")
                 except: pass
                 # Optionally create one stream if none exist after a delay?
                 if frame_count > 50 and not streams: # Wait ~1.5s
                     streams = create_streams(width, height)

            screen.refresh() # Update the physical screen with changes
            frame_count += 1

        except curses.error as e:
             # Gracefully exit on common curses errors (often resize related)
             curses.endwin()
             print(f"\nA curses error occurred: {e}")
             print("Terminal might have been resized rapidly or become too small.")
             print("Please restart the script.")
             sys.exit(1)
        except KeyboardInterrupt:
             break # Allow Ctrl+C to exit gracefully

# --- Run the application ---
if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except Exception as e:
        # Catch any other unexpected errors during setup or teardown
        print(f"\nAn unexpected error occurred: {e}")
        # Ensure terminal state is restored even if wrapper failed early
        try: curses.endwin()
        except: pass
    finally:
        print("Matrix rain stopped.")