import os
import sys
import mido
import math
import argparse
from typing import List, Dict, Optional
from midi2uge.metamodel import UGESong, Pattern, Cell, Instrument, InstrumentType

def smart_convert(midi_path: str, output_path: str, template_path: Optional[str] = None):
    try:
        from mido.midifiles import meta
        if not hasattr(meta, '_key_signature_decode_patched'):
            class DefaultKeyDict(dict):
                def __getitem__(self, key):
                    return super().get(key, 'C')
            meta._key_signature_decode = DefaultKeyDict(meta._key_signature_decode)
            meta._key_signature_decode_patched = True
    except:
        pass

    mid = mido.MidiFile(midi_path)
    
    if template_path and os.path.exists(template_path):
        song = UGESong.load(template_path)
        song.patterns = []
        song.orders = [[], [], [], []]
    else:
        song = UGESong()
        _setup_default_instruments(song)
        
    song.ticks_per_row = 6 # Standard (approx 0.1s/row)
    rows_per_beat = 4
    ticks_per_beat = mid.ticks_per_beat
    
    # 1. Collect all events into a unified list
    all_drums = []
    all_melodic = []
    
    for i, track in enumerate(mid.tracks):
        abs_ticks = 0
        active_notes = {}
        for msg in track:
            abs_ticks += msg.time
            if msg.type == 'note_on' and msg.velocity > 0:
                row = int(round((abs_ticks / ticks_per_beat) * rows_per_beat))
                active_notes[msg.note] = {'start_row': row, 'velocity': msg.velocity}
            elif (msg.type == 'note_off') or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in active_notes:
                    start_info = active_notes.pop(msg.note)
                    event = {
                        'row': start_info['start_row'],
                        'note': msg.note,
                        'velocity': start_info['velocity']
                    }
                    channel = getattr(msg, 'channel', 0)
                    if channel == 9: # MIDI Drum Channel
                        all_drums.append(event)
                    else:
                        all_melodic.append(event)

    # 2. Smart Note-Level Allocation
    allocated_events = [[], [], [], []] # Duty1, Duty2, Wave, Noise
    
    for e in all_drums:
        allocated_events[3].append(e)
        
    melodic_by_row = {}
    for e in all_melodic:
        r = e['row']
        if r not in melodic_by_row:
            melodic_by_row[r] = []
        melodic_by_row[r].append(e)
        
    for r, evs in melodic_by_row.items():
        # Sort notes in this row highest to lowest
        evs.sort(key=lambda x: x['note'], reverse=True)
        unique_evs = []
        seen = set()
        for e in evs:
            if e['note'] not in seen:
                seen.add(e['note'])
                unique_evs.append(e)
                
        if len(unique_evs) == 0: continue
        elif len(unique_evs) == 1:
            allocated_events[0].append(unique_evs[0]) # Single note -> Duty 1 (Melody)
        elif len(unique_evs) == 2:
            allocated_events[0].append(unique_evs[0]) # Highest -> Duty 1
            allocated_events[2].append(unique_evs[-1]) # Lowest -> Wave (Bass)
        else:
            allocated_events[0].append(unique_evs[0]) # Highest -> Duty 1
            allocated_events[2].append(unique_evs[-1]) # Lowest -> Wave (Bass)
            allocated_events[1].append(unique_evs[1]) # 2nd Highest -> Duty 2 (Harmony)
            # Anything else drops due to 3 melodic track limit
            
    # 3. Determine song length
    max_row = 0
    for ch_events in allocated_events:
        if ch_events:
            last = max(e['row'] for e in ch_events)
            if last > max_row: max_row = last
            
    num_patterns = math.ceil((max_row + 1) / 64)
    if num_patterns == 0: num_patterns = 1
    
    # 4. Generate UGE Patterns
    current_pat_id = 0
    for block_idx in range(num_patterns):
        start_row = block_idx * 64
        end_row = start_row + 64
        
        for ch_idx in range(4):
            pat = Pattern()
            # Initialize with Rest (Note 90 means empty cell in Tracker view)
            for c in pat.cells:
                c.note = 90
                
            block_events = [e for e in allocated_events[ch_idx] if start_row <= e['row'] < end_row]
            by_row = {}
            for e in block_events:
                r = e['row'] % 64
                if r not in by_row: by_row[r] = []
                by_row[r].append(e)
                
            for r in range(64):
                cell = pat.cells[r]
                if r in by_row:
                    evs = by_row[r]
                    evs.sort(key=lambda x: x['note'], reverse=True)
                    winner = evs[0]
                    
                    final_note = winner['note'] - 24
                    if final_note < 0: final_note = 0
                    if final_note > 80: final_note = 80
                    
                    cell.note = final_note
                    cell.volume = 0
                    
                    # Core template instruments (matching converter_inst12)
                    if ch_idx == 3:
                         n = winner['note']
                         if n in [36, 35]: cell.instrument = 40
                         elif n in [38, 40]: cell.instrument = 36
                         elif n in [49, 57]: cell.instrument = 34
                         else: cell.instrument = 30
                    elif ch_idx == 2: cell.instrument = 8 # Wave
                    elif ch_idx == 0: cell.instrument = 1 # Duty 1
                    elif ch_idx == 1: cell.instrument = 2 # Duty 2
                    
            song.patterns.append(pat)
            song.orders[ch_idx].append(current_pat_id)
            current_pat_id += 1
            
    with open(output_path, 'wb') as f:
        f.write(song.pack())
    print(f"Smart Converted: {midi_path} -> {output_path}")

def _setup_default_instruments(song: UGESong):
    for i in range(15):
        song.instruments[i].type = InstrumentType.SQUARE
        song.instruments[i].name = f"Duty {i}"
    for i in range(15, 30):
        song.instruments[i].type = InstrumentType.WAVE
        song.instruments[i].name = f"Wave {i}"
    for i in range(30, 45):
        song.instruments[i].type = InstrumentType.NOISE
        song.instruments[i].name = f"Noise {i}"

import tkinter as tk
from tkinter import messagebox, filedialog

def show_message(title, msg, is_error=False):
    try:
        root = tk.Tk()
        root.withdraw()
        if is_error:
            messagebox.showerror(title, msg)
        else:
            messagebox.showinfo(title, msg)
        root.destroy()
    except:
        print(f"[{title}] {msg}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Convert MIDI to UGE")
    parser.add_argument("input", nargs='?', help="Input MIDI (.mid)")
    parser.add_argument("output", nargs='?', help="Output UGE (.uge)")
    parser.add_argument("--template", help="Template UGE")
    args = parser.parse_args()

    if getattr(sys, 'frozen', False):
        # We are running as an app bundle or pyinstaller executable
        bundle_dir = sys._MEIPASS
    else:
        # We are running in a normal Python environment
        bundle_dir = os.path.dirname(os.path.abspath(__file__))

    if not args.input:
        root = tk.Tk()
        root.withdraw()
        args.input = filedialog.askopenfilename(filetypes=[("MIDI Files", "*.mid")])
        root.destroy()
        if not args.input:
            sys.exit(0)

    if not args.output:
        base, _ = os.path.splitext(args.input)
        args.output = base + "_smart.uge"

    if not args.template:
        args.template = os.path.join(bundle_dir, "template.uge")
        if not os.path.exists(args.template):
            # Development fallback
            args.template = os.path.join(bundle_dir, "00-250301-scales.uge")

    try:
        smart_convert(args.input, args.output, args.template)
        show_message("Conversion Successful", f"Successfully generated:\n{os.path.basename(args.output)}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        show_message("Conversion Error", f"Failed to convert file:\n{str(e)}", is_error=True)
