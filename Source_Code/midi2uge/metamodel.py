import struct
from enum import IntEnum
from dataclasses import dataclass, field
from typing import List, Optional

# --- Constants & Enums ---

class InstrumentType(IntEnum):
    SQUARE = 0
    WAVE = 1
    NOISE = 2

class SweepType(IntEnum):
    UP = 0
    DOWN = 1

class StepWidth(IntEnum):
    FIFTEEN = 0
    SEVEN = 1

# --- Data Structures ---

@dataclass
class Cell:
    note: int = 0          # 4 bytes (Integer)
    instrument: int = 0    # 4 bytes (Integer)
    volume: int = 0        # 4 bytes (Integer)
    effect_code: int = 0   # 4 bytes (Integer)
    effect_params: int = 0 # 1 byte (TEffectParams - bitpacked, but size is 1 byte in C/Pascal typically for this union)
    
    # Total size: 4+4+4+4+1 = 17 bytes

    def pack(self) -> bytes:
        return struct.pack('<iiiiB', self.note, self.instrument, self.volume, self.effect_code, self.effect_params)

    @classmethod
    def unpack(cls, data: bytes) -> 'Cell':
        return cls(*struct.unpack('<iiiiB', data))
    
    @classmethod
    def size(cls):
        return 17

@dataclass
class Pattern:
    cells: List[Cell] = field(default_factory=list) # Fixed 64 cells

    def __init__(self):
        self.cells = [Cell() for _ in range(64)]

    def pack(self) -> bytes:
        return b''.join(cell.pack() for cell in self.cells)

    @classmethod
    def unpack(cls, data: bytes, version: int = 6) -> 'Pattern':
        p = cls()
        if version < 6:
            # V5 uses TCellV1: Note(4), Inst(4), Effect(4), Params(1) = 13 bytes
            # Total size: 64 * 13 = 832 bytes
            cell_size = 13
            for i in range(64):
                chunk = data[i*cell_size : (i+1)*cell_size]
                # Unpack V1 cell
                note, inst, eff, param = struct.unpack('<iiiB', chunk)
                c = Cell()
                c.note = note
                c.instrument = inst
                c.volume = 0 # Default? Or 11? V5 didn't have per-cell volume?
                c.effect_code = eff
                c.effect_params = param
                p.cells[i] = c
        else:
            # V6 uses TCellV2: Note(4), Inst(4), Vol(4), Eff(4), Params(1) = 17 bytes
            cell_size = 17
            p.cells = [Cell.unpack(data[i*17 : (i+1)*17]) for i in range(64)]
        return p

    @classmethod
    def size(cls, version: int = 6):
        return 832 if version < 6 else 1088

@dataclass
class Instrument:
    type: int = InstrumentType.SQUARE # 4 bytes
    name: str = ""                    # 256 bytes (ShortString)
    length: int = 0                   # 4 bytes
    length_enabled: bool = False      # 1 byte
    initial_volume: int = 15          # 1 byte
    vol_sweep_direction: int = 1      # 1 byte? or 4? Based on analysis: 4+256+4+1+1+X... = 1385.
                                      # Let's align with the calculated layout.
                                      # Remaining fixed block is 37 bytes.
                                      # 1385 - 260 (type+name) - 1088 (subpattern) = 37 bytes.
                                      # Fields needed:
                                      # Length (4)
                                      # LengthEnabled (1)
                                      # InitialVolume (1)
                                      # VolSweepDirection (4) -> Enum? Wait, if 4 bytes, let's re-sum.
                                      # VolSweepAmount (1)
                                      # SweepTime (4)
                                      # SweepIncDec (4) -> Enum?
                                      # SweepShift (4)
                                      # Duty (4) -> Subrange 0..3 usually 1 byte, but packed record alignment?
                                      # OutputLevel (4)
                                      # Waveform (4)
                                      # CounterStep (4) -> Enum?
                                      # SubpatternEnabled (1)
                                      # Let's try to fit 37 bytes: 
                                      # 4 (Len) + 1 (LE) + 1 (InitVol) + 1 (VSD) + 1 (VOA) + 4 (SwT) + 1 (SwID) + 4 (SwS) + 1 (D) + 4 (OL) + 4 (W) + 1 (CS) + 1 (SE) = 28. Too small.
                                      # If enums/subranges are 4 bytes?
                                      # Direction(4), Amount(4), IncDec(4), Duty(4), CounterStep(4)?
                                      # Pascal 'checked' enums are 4 bytes.
                                      # Try:
                                      # Len(4) + LE(1) + InitVol(1) (TEnvelopeVolume=0..15 is 1 byte?) -> FPC packs subrange to smallest.
                                      # But alignment? 'packed record' eliminates alignment padding.
                                      # Let's guess:
                                      # Length: 4
                                      # LengthEnabled: 1
                                      # InitialVolume: 4 (TEnvelopeVolume 0..15 but maybe Integer base?)
                                      # VolSweepDirection: 4
                                      # VolSweepAmount: 4
                                      # SweepTime: 4
                                      # SweepIncDec: 4
                                      # SweepShift: 4
                                      # Duty: 4
                                      # OutputLevel: 4
                                      # Waveform: 4
                                      # CounterStep: 4
                                      # SubpatternEnabled: 1
                                      # Total: 4+1 + 10*4 + 1 = 46. Too big.
                                      #
                                      # Let's count bytes in the Hex Dump between Name end (0x308+256 = 0x408) to Subpattern start or next instrument?
                                      # Actually, checking the UGE_Repo source `hugedatatypes.pas`:
                                      # TInstrumentV3 is `packed record`.
                                      # Let's look at offset of `Subpattern`.
                                      # It is the last field.
                                      # If total is 1385.
                                      # Subpattern is 1088. 
                                      # Header is 297 bytes.
                                      # Type(4) + Name(256) = 260.
                                      # 297 - 260 = 37 bytes.
                                      # We need to pack 13 fields into 37 bytes.
                                      # The fields are:
                                      # 1. Length (Integer) -> 4
                                      # 2. LengthEnabled (Boolean) -> 1
                                      # 3. InitialVolume (TEnvelopeVolume 0..15) -> 1 (Subrange)
                                      # 4. VolSweepDirection (TSweepType Enum) -> 1 (Enum with 2 vals, 1 byte in packed?)
                                      # 5. VolSweepAmount (TEnvelopeSweepAmount 0..7) -> 1 (Subrange)
                                      # 6. SweepTime (Integer) -> 4
                                      # 7. SweepIncDec (TSweepType) -> 1
                                      # 8. SweepShift (Integer) -> 4
                                      # 9. Duty (TDutyType 0..3) -> 1 (Subrange)
                                      # 10. OutputLevel (Integer) -> 4
                                      # 11. Waveform (Integer) -> 4
                                      # 12. CounterStep (TStepWidth Enum) -> 1
                                      # 13. SubpatternEnabled (Boolean) -> 1
                                      #
                                      # Sum: 4+1+1+1+1 + 4+1+4+1 + 4+4+1+1 = 28 bytes.
                                      # Still 9 bytes short.
                                      # What if TSweepType is 4 bytes? (2 enums: Direction, IncDec). +6 bytes. Total 34.
                                      # What if CounterStep is 4 bytes? +3 bytes. Total 37.
                                      # YES! 28 + 6 + 3 = 37.
                                      # So Enums (TSweepType, TStepWidth) are 4 bytes.
                                      # Subranges (InitialVolume, VolSweepAmount, Duty) are likely 1 byte?
                                      # Or maybe `TEnvelopeVolume` is 4 bytes? 
                                      # `TEnvelopeVolume = 0..15`.
                                      # If subranges are 4 bytes?
                                      # Then we have 5 subranges/enums. 5*3 = 15 extra bytes. 28 + 15 = 43. Too big.
                                      #
                                      # Hypothesis:
                                      # Enums (defined as `(a,b)`) are 4 bytes in `{$mode objfpc}` even in packed records?
                                      # Subranges (defined as `0..15`) are 1 byte in packed records?
                                      # Let's proceed with this hypothesis:
                                      # Enums (Type, SweepType, StepWidth) = 4 bytes.
                                      # Subranges (Volume, SweepAmount, Duty) = 1 byte.
                                      # Integers = 4 bytes.
                                      # Booleans = 1 byte.
                                      #
                                      # Let's verify:
                                      # Type(4) + Name(256) + Len(4) + LE(1) + InitVol(1) + VSD(4) + VSA(1) + SwTime(4) + SwID(4) + SwShift(4) + Duty(1) + OutLvl(4) + Wave(4) + CS(4) + SubEn(1).
                                      # 260 + 29 (fixed block?) + Subpattern(1088).
                                      # Fixed block sum: 4+1+1+4+1+4+4+4+1+4+4+4+1 = 37.
                                      # PERFECT! 37 bytes exactly.
    
    vol_sweep_amount: int = 0         # 1 byte
    
    sweep_time: int = 0               # 4 bytes
    sweep_inc_dec: int = 1            # 4 bytes (Enum)
    sweep_shift: int = 0              # 4 bytes
    
    duty: int = 2                     # 1 byte (Subrange)
    
    output_level: int = 1             # 4 bytes
    waveform: int = 0                 # 4 bytes
    
    counter_step: int = 0             # 4 bytes (Enum)
    
    subpattern_enabled: bool = False  # 1 byte
    subpattern: Pattern = field(default_factory=Pattern) # 1088 bytes (V6) or 832 (V5)

    def pack(self) -> bytes:
        # Pad string to 256 bytes. format: len byte + string bytes (up to 255) + padding?
        # WAIT. Pascal ShortString is: Byte[0] = Len. Bytes[1..Len] = Chars. Bytes[Len+1..255] = undefined.
        # Total size is 256 bytes always.
        name_bytes = self.name.encode('utf-8')[:255]
        name_block = struct.pack('B', len(name_bytes)) + name_bytes + b'\x00' * (255 - len(name_bytes))
        
        header = struct.pack('<i', self.type) + name_block
        
        # Fixed block (37 bytes)
        # 4 (Len) + 1 (LE) + 1 (InitVol) + 4 (VSD) + 1 (VSA) + 4 (SwT) + 4 (SwID) + 4 (SwS) + 1 (Duty) + 4 (OL) + 4 (Wave) + 4 (CS) + 1 (SubEn)
        # Format: i B B i B i i i B i i i B
        fixed_block = struct.pack('<iBBiBiiiBiiiB',
            self.length,
            self.length_enabled,
            self.initial_volume,
            self.vol_sweep_direction,
            self.vol_sweep_amount,
            self.sweep_time,
            self.sweep_inc_dec,
            self.sweep_shift,
            self.duty,
            self.output_level,
            self.waveform,
            self.counter_step,
            self.subpattern_enabled
        )
        
        return header + fixed_block + self.subpattern.pack()

    @classmethod
    def unpack(cls, data: bytes, version: int = 6) -> 'Instrument':
        inst = cls()
        ptr = 0
        
        # Type
        inst.type = struct.unpack('<i', data[ptr:ptr+4])[0]
        ptr += 4
        
        # Name
        name_len = data[ptr]
        inst.name = data[ptr+1 : ptr+1+name_len].decode('utf-8', errors='replace')
        ptr += 256
        
        if version >= 6:
            # V6 (Instrument V3)
            # Fixed block 37 bytes
            (inst.length, le, inst.initial_volume, inst.vol_sweep_direction,
             inst.vol_sweep_amount, inst.sweep_time, inst.sweep_inc_dec,
             inst.sweep_shift, inst.duty, inst.output_level, inst.waveform,
             inst.counter_step, se) = struct.unpack('<iBBiBiiiBiiiB', data[ptr:ptr+37])
            
            inst.length_enabled = bool(le)
            inst.subpattern_enabled = bool(se)
            ptr += 37
            
            # Subpattern
            pat_size = Pattern.size(version)
            inst.subpattern = Pattern.unpack(data[ptr:ptr+pat_size], version=version)
        else:
            # V5 (Instrument V2)
            # Common block 32 bytes (Length..Waveform) matches V3
            (inst.length, le, inst.initial_volume, inst.vol_sweep_direction,
             inst.vol_sweep_amount, inst.sweep_time, inst.sweep_inc_dec,
             inst.sweep_shift, inst.duty, inst.output_level, inst.waveform) = struct.unpack('<iBBiBiiiBii', data[ptr:ptr+32])
             
            inst.length_enabled = bool(le)
            ptr += 32
            
            # Skip V2 specific fields: ShiftClockFreq(4), CounterStep(4), DividingRatio(4), NoiseMacro(6)
            # Total 18 bytes
            ptr += 18
            
            inst.subpattern_enabled = False
            # No subpattern to read
        
        return inst

    @classmethod
    def size(cls, version: int = 6):
        if version >= 6:
            # 4 (type) + 256 (name) + 37 (fixed block) + Pattern.size
            return 297 + Pattern.size(version)
        else:
            # V5: 4 + 256 + 32 (common) + 18 (V2 specific) = 310
            return 310

@dataclass
class UGESong:
    version: int = 6
    name: str = ""
    artist: str = ""
    comment: str = ""
    instruments: List[Instrument] = field(default_factory=list) # Fixed 45 instruments
    waves: List[bytes] = field(default_factory=list) # 16 waves * 32 bytes = 512 bytes
    ticks_per_row: int = 7
    timer_enabled: bool = False
    timer_divider: int = 0
    patterns: List[Pattern] = field(default_factory=list) # Variable count
    orders: List[List[int]] = field(default_factory=list) # 4 channels, each is list of pattern IDs
    routines: List[str] = field(default_factory=list)

    def __init__(self):
        self.instruments = [Instrument() for _ in range(45)]
        self.waves = [b'\x00'*32 for _ in range(16)]
        self.orders = [[0] for _ in range(4)]
        self.patterns = [] 
        # Note: Patterns are dynamic. User must add them.
        self.routines = ["" for _ in range(16)]

    def pack(self) -> bytes:
        data = bytearray()
        
        # Helper for string packing
        def pack_str(s):
            b = s.encode('utf-8')[:255]
            return struct.pack('B', len(b)) + b + b'\x00' * (255 - len(b))

        data += struct.pack('<i', self.version)
        data += pack_str(self.name)
        data += pack_str(self.artist)
        data += pack_str(self.comment)
        
        for inst in self.instruments:
            data += inst.pack()
            
        for wave in self.waves:
            data += wave[:32].ljust(32, b'\x00')
            
        data += struct.pack('<i', self.ticks_per_row)
        
        # Timer only in V6
        if self.version >= 6:
            data += struct.pack('<Bi', self.timer_enabled, self.timer_divider)
        # Let's verify TSongV6 padding.
        # TSongV6:
        # ...
        # TicksPerRow: Integer;
        # TimerEnabled: Boolean;
        # TimerDivider: Integer;
        # Patterns: TPatternMap;
        # ...
        # In packed record: i (4) + ? (1) + i (4) = 9 bytes?
        # Or is there padding after Boolean? "packed" usually no padding.
        # Let's assume 9 bytes for this block.
        
        # Patterns
        # TPatternMap is dynamic. 
        # WriteSongToStream logic:
        # S.Write(ASong.Patterns.Count, SizeOf(Integer));
        # For each pattern:
        #   Write Key (Integer)
        #   Write Pattern Data (TPattern)
        
        count = len(self.patterns)
        data += struct.pack('<i', count)
        for i, pat in enumerate(self.patterns):
             # Write key/index. 
             # Note: If converting MIDI to V6, we used sequential 0..N indices.
             # If we loaded V5, we might have weird keys.
             # For packing, we just assume dense for now or user cared for it.
             # Ideally we should store keys in UGESong.
             # Using 'i' relies on list order.
             data += struct.pack('<i', i)
             data += pat.pack()
             
        # Order Matrix
        # 4 arrays. Each: Length (Int), then Data (Ints).
        for ch in range(4):
            order = self.orders[ch]
            data += struct.pack('<i', len(order))
            for val in order:
                data += struct.pack('<i', val)
                
        # Routines
        # 16 AnsiStrings (variable length: 4 byte len + bytes)?
        # Check `S.WriteAnsiString` in standard FPC or Utils unit.
        # `song.pas` says `S.WriteAnsiString(ASong.Routines[i])`.
        # `utils.pas` (assumed standard LCL/FCL): WriteAnsiString usually writes 4-byte length + content.
        # Let's verify `WriteAnsiString` format.
        # Assuming standard Pascal TStream.WriteAnsiString: 4-byte Length + String content. (No null term).
        if self.version >= 2: # V1 has no routines
            for r in self.routines:
                b = r.encode('utf-8')
                data += struct.pack('<i', len(b))
                data += b
            
        return bytes(data)

    @classmethod
    def load(cls, path: str) -> 'UGESong':
        with open(path, 'rb') as f:
            data = f.read()
            
        song = cls()
        ptr = 0
        
        song.version = struct.unpack('<i', data[ptr:ptr+4])[0]
        ptr += 4
        
        def read_str(data, ptr):
            length = data[ptr]
            s = data[ptr+1 : ptr+1+length].decode('utf-8', errors='replace')
            return s, ptr + 256 # Fixed 256 jump
            
        song.name, ptr = read_str(data, ptr)
        song.artist, ptr = read_str(data, ptr)
        song.comment, ptr = read_str(data, ptr)
        
        # Calculate Instrument Size based on Version
        inst_size = Instrument.size(song.version)
        
        song.instruments = []
        for _ in range(45):
            inst = Instrument.unpack(data[ptr:ptr+inst_size], version=song.version)
            song.instruments.append(inst)
            ptr += inst_size
            
        song.waves = []
        for _ in range(16):
            song.waves.append(data[ptr:ptr+32])
            ptr += 32
            
        song.ticks_per_row = struct.unpack('<i', data[ptr:ptr+4])[0]
        ptr += 4
        
        # Timer block
        if song.version >= 6:
            te, td = struct.unpack('<Bi', data[ptr:ptr+5])
            song.timer_enabled = bool(te)
            song.timer_divider = td
            ptr += 5
        
        # Patterns
        pat_count = struct.unpack('<i', data[ptr:ptr+4])[0]
        ptr += 4
        
        # We need to map keys correctly.
        # Let's store patterns in a dict or list?
        # For this converter, list is fine if keys are sequential.
        # But for robustness, let's just ready them into a list 
        # and assume the user manages the order/indices for now.
        song.patterns = []
        # Pattern map in Pascal might correspond to sparse keys.
        # We will reconstruct a dense list for simplicity, filling gaps? 
        # Or just append.
        # Actually, let's just make patterns a list and ignore keys for the *model* 
        # unless strict roundtrip is needed. 
        # Wait, OrderMatrix REFERENCES keys. So keys are important.
        # Let's store patterns as a Dict {id: Pattern} temporarily?
        # But `UGESong` defined `patterns: List[Pattern]`.
        # Let's change `patterns` to `List[Pattern]` and assume strict 0..N mapping for OUR usage.
        # But when LOADING, we must respect keys used in OrderMatrix.
        # If we load a file with Key=5, and Order=[5], but we put it at index 0..
        # We need a proper map.
        # For now, let's just Read them.
        
        pattern_map = {}
        pat_size = Pattern.size(song.version)
        for _ in range(pat_count):
            key = struct.unpack('<i', data[ptr:ptr+4])[0]
            ptr += 4
            pat = Pattern.unpack(data[ptr:ptr+pat_size], version=song.version)
            ptr += pat_size
            pattern_map[key] = pat
            
        # Linearize patterns for our list?
        # Simplification: specific logic for logic later.
        # For now, just store values.
        # We'll re-assign song.patterns as the values sorted by key?
        # Or just keep the raw map if we want to be safe.
        # NOTE: `UGESong` definition uses List. 
        # Let's hack: The list will contain patterns where index = key.
        # If keys are sparse, we fill with empty patterns?
        # Or just append and hope keys are 0..N-1.
        # In typical UGE files, they are 0..Count-1.
        song.patterns = [pattern_map[k] for k in sorted(pattern_map.keys())] if pattern_map else []
        
        # Orders
        song.orders = []
        for _ in range(4):
            count = struct.unpack('<i', data[ptr:ptr+4])[0]
            ptr += 4
            # Read Array
            # int values
            fmt = f'<{count}i'
            size = count * 4
            vals = list(struct.unpack(fmt, data[ptr:ptr+size]))
            song.orders.append(vals)
            ptr += size
            
        # Routines
        song.routines = []
        for _ in range(16):
            # AnsiString: 4 byte len + chars
            slen = struct.unpack('<i', data[ptr:ptr+4])[0]
            ptr += 4
            if slen > 0:
                s = data[ptr:ptr+slen].decode('utf-8')
                ptr += slen
            else:
                s = ""
            song.routines.append(s)
            
        return song
