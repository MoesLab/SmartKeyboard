import math
import struct
import unittest
from speech_spectrum import bands,FREQUENCIES


class SpectrumTests(unittest.TestCase):
    def test_silence_and_short_input_do_not_invent_activity(self):
        for pcm in (b'',b'\0',b'\0\0'*1024):self.assertEqual(bands(pcm),[0]*24)

    def test_known_tone_appears_in_matching_frequency_band(self):
        for index in (5,12,19):
            frequency=FREQUENCIES[index]
            pcm=b''.join(struct.pack('<h',round(15000*math.sin(2*math.pi*frequency*i/16000))) for i in range(1024))
            values=bands(pcm)
            self.assertEqual(len(values),24)
            self.assertLessEqual(abs(values.index(max(values))-index),1)
            self.assertGreater(max(values),75)
            self.assertTrue(all(0<=value<=100 for value in values))

    def test_dc_offset_is_removed(self):
        self.assertEqual(bands(struct.pack('<h',10000)*1024),[0]*24)


if __name__=='__main__':unittest.main()
