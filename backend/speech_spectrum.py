"""Small speech-band Goertzel analysis of mono 16kHz s16le PCM, no dependencies."""
import math
import struct

FREQUENCIES=tuple(80*(3800/80)**(index/23) for index in range(24))
COEFFICIENTS=tuple(2*math.cos(2*math.pi*frequency/8000) for frequency in FREQUENCIES)


def bands(pcm):
    # Analyse at most 64ms, downsampled to 8kHz. All display bands are below 4kHz.
    tail=pcm[-2048:];tail=tail[:len(tail)//2*2]
    values=[value[0]/32768 for value in struct.iter_unpack('<h',tail)][::2]
    count=len(values)
    if count<32:return [0]*24
    mean=sum(values)/count
    window=[0.5-0.5*math.cos(2*math.pi*i/(count-1)) for i in range(count)]
    samples=[(value-mean)*weight for value,weight in zip(values,window)]
    scale=2/sum(window)
    result=[]
    for coefficient in COEFFICIENTS:
        previous=older=0.0
        for sample in samples:
            current=sample+coefficient*previous-older
            older,previous=previous,current
        magnitude=math.sqrt(max(0,previous*previous+older*older-coefficient*previous*older))*scale
        db=20*math.log10(max(magnitude,1e-10))
        result.append(round(max(0,min(100,(db+65)/65*100))))
    return result
