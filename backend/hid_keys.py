"""USB HID keyboard usage encoding shared by the BLE report transport.

Reports are eight bytes (modifier, reserved, six key usages). GATT Report
Reference supplies report ID 1; the ID is not prepended to the characteristic.
"""
import struct

REPORT_MAP = bytes.fromhex(
    '05 01 09 06 a1 01 85 01 05 07 19 e0 29 e7 15 00 25 01 '
    '75 01 95 08 81 02 95 01 75 08 81 01 95 05 75 01 05 08 '
    '19 01 29 05 91 02 95 01 75 03 91 01 95 06 75 08 15 00 '
    '25 65 05 07 19 00 29 65 81 00 c0')
RELEASE = bytes(8)
SPECIAL = {'enter':40, 'tab':43, 'space':44, 'escape':41, 'backspace':42,
           'delete':76, 'home':74, 'end':77, 'arrowright':79, 'arrowleft':80,
           'arrowdown':81, 'arrowup':82}
SPECIAL.update({'f'+str(i):57+i for i in range(1,13)})
MODIFIERS = {'ctrl':1, 'control':1, 'shift':2, 'alt':4, 'meta':8, 'super':8, 'win':8}
PLAIN = "1234567890-=[]\\;\x27`,./"
SHIFT = '!@#$%^&*()_+{}|:"~<>?'
USAGES = list(range(30,40)) + [45,46,47,48,49,51,52,53,54,55,56]
ASCII = {chr(97+i):(0,4+i) for i in range(26)}
ASCII.update({chr(65+i):(2,4+i) for i in range(26)})
ASCII.update({c:(0,k) for c,k in zip(PLAIN,USAGES)})
ASCII.update({c:(2,k) for c,k in zip(SHIFT,USAGES)})
ASCII.update({' ':(0,44), '\n':(0,40), '\t':(0,43)})
TYPOGRAPHIC = str.maketrans({'‘':"'",'’':"'",'“':'"','”':'"','–':'-','—':'-','…':'...','\u00a0':' '})

def report(modifier, key):
    return struct.pack('8B',modifier,0,key,0,0,0,0,0)

def encode_text(text):
    if not isinstance(text,str) or not text or len(text)>1000:
        raise ValueError('Send 1–1000 characters at a time.')
    normalized=text.replace('\r\n','\n').replace('\r','\n').translate(TYPOGRAPHIC)
    line=1;column=1
    for character in text:
        mapped=character.translate(TYPOGRAPHIC).replace(chr(13),chr(10))
        if any(c not in ASCII for c in mapped):
            point='U+%04X'%ord(character)
            raise ValueError('Unsupported '+repr(character)+' ('+point+') at line '+str(line)+', column '+str(column)+'. Nothing sent. Current Bluetooth encoding supports US-layout text only.')
        if character==chr(10):line+=1;column=1
        elif character!=chr(13):column+=1
    return [packet for c in normalized for packet in (report(*ASCII[c]),RELEASE)]

def encode_shortcuts(shortcuts):
    if not isinstance(shortcuts,list) or not 1<=len(shortcuts)<=100:
        raise ValueError('Use 1–100 shortcut actions.')
    result=[]
    for shortcut in shortcuts:
        if not isinstance(shortcut,str): raise ValueError('Shortcut must be text.')
        parts=shortcut.lower().split('+'); key=parts.pop().strip(); modifier=0
        for part in parts:
            if part.strip() not in MODIFIERS: raise ValueError('Unknown modifier: '+part)
            modifier |= MODIFIERS[part.strip()]
        if key in SPECIAL: usage=SPECIAL[key]
        elif len(key)==1 and key in ASCII:
            shift,usage=ASCII[key]; modifier |= shift
        else: raise ValueError('Unknown key: '+key)
        result.extend((report(modifier,usage),RELEASE))
    return result
