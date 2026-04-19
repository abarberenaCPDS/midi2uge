# MIDI to UGE Smart Converter

A brilliant tool that intelligently maps polyphonic `.mid` files directly into `.uge` format for GB Studio and hUGETracker! 

Unlike older scripts that naively dump notes into a single channel, this converter dynamically analyzes your MIDI file row-by-row and correctly separates the chords out to avoid mono-channel overlaps:
- **Melody** (Highest Pitch) -> Tracks to **Duty 1**
- **Bass** (Lowest Pitch) -> Tracks to **Wave**
- **Harmony** (Middle Pitch) -> Tracks to **Duty 2**
- **Drums** (MIDI channel 10) -> Tracks to **Noise**

All empty space is correctly initialized to Rests (Note 90) preventing GB Studio "ghost notes", giving you clean, beautifully formatted patterns!

---

## 🍎 For Mac Users (Easiest)

If you are on macOS:
1. Extract the `MIDI2UGE.app` file.
2. Simply **Drag and Drop** any `.mid` file directly onto the `MIDI2UGE` application icon!
3. The app will process it silently in the background and pop up a success message. Your new `_smart.uge` file will automatically appear right next to your original MIDI file!

*(You can also just double-click the app to open a visual file selector!)*

---

## 🪟 For Windows/Linux Users (Command Line)

If you are not on macOS, or prefer full CLI control, you can use the raw Python source script provided in the `Source_Code` folder.

1. **Install Python 3.8+**
2. **Install the required dependencies:**
   Open a terminal in the `Source_Code` folder and run:
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the Script:**
   ```bash
   python smart_convert.py "path/to/your/song.mid" "output_song.uge" --template template.uge
   ```

*(A default `template.uge` containing basic Game Boy instrument banks is already included in the folder for you!)*
# midi2uge
