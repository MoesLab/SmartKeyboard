"""A short headset-only ready cue after live microphone data, excluded from capture."""
import io
import math
import os
import select
import struct
import subprocess
import time
import wave
from audio_preferences import HEADSET


def ready_tone():
    rate=16000;frames=[]
    for index in range(int(rate*0.21)):
        moment=index/rate
        if moment<0.09:local=moment;frequency=880
        elif moment>=0.12:local=moment-0.12;frequency=1320
        else:frames.append(b'\0\0');continue
        envelope=max(0,min(1,local/0.006,(0.09-local)/0.006))
        frames.append(struct.pack('<h',round(32767*0.12*envelope*math.sin(2*math.pi*frequency*local))))
    output=io.BytesIO()
    with wave.open(output,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(rate);wav.writeframes(b''.join(frames))
    return output.getvalue()


def prepare_headset(microphone,source,stopping):
    if source!=HEADSET:return None
    deadline=time.monotonic()+3
    while not stopping():
        if time.monotonic()>=deadline:raise ValueError('Headset microphone did not become ready.')
        readable,_,_=select.select([microphone.stdout],[],[],0.05)
        if readable:
            if not os.read(microphone.stdout.fileno(),6400):raise ValueError('Headset microphone closed before ready.')
            break
        if microphone.poll() is not None:raise ValueError('Headset microphone unavailable.')
    if stopping():return None
    playback=None
    try:
        playback=subprocess.Popen(['paplay','--device=bluez_sink.C0_86_B3_F2_E8_96.headset_head_unit'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        playback.stdin.write(ready_tone());playback.stdin.close()
        deadline=time.monotonic()+1.5
        # Drain and discard microphone samples while the cue plays. They never
        # enter the recognizer or upload recording. User speaks after the cue.
        while playback.poll() is None:
            if stopping() or time.monotonic()>deadline:return False
            readable,_,_=select.select([microphone.stdout],[],[],0.02)
            if readable and not os.read(microphone.stdout.fileno(),6400):raise ValueError('Microphone closed during ready cue.')
        return playback.returncode==0
    except (OSError,subprocess.SubprocessError):
        return False  # Cue failure must not prevent otherwise usable dictation.
    finally:
        if playback is not None:
            if playback.stdin and not playback.stdin.closed:
                try:playback.stdin.close()
                except OSError:pass
            if playback.poll() is None:
                playback.terminate()
                try:playback.wait(timeout=0.5)
                except subprocess.TimeoutExpired:playback.kill();playback.wait(timeout=0.5)
