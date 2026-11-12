import unittest
from hid_keys import RELEASE, REPORT_MAP, encode_text, encode_shortcuts

class Reports(unittest.TestCase):
    def test_typing_releases_every_key(self):
        packets=encode_text('aA!\n')
        self.assertEqual([list(p[:3]) for p in packets[::2]],[[0,0,4],[2,0,4],[2,0,30],[0,0,40]])
        self.assertTrue(all(p==RELEASE for p in packets[1::2]))
        self.assertTrue(all(len(p)==8 for p in packets))

    def test_all_printable_us_characters(self):
        text=''.join(chr(i) for i in range(32,127))
        self.assertEqual(len(encode_text(text)),len(text)*2)

    def test_shortcuts_are_not_text(self):
        packets=encode_shortcuts(['Ctrl+C','Ctrl+Shift+T','Meta+E','Alt+Tab'])
        self.assertEqual([list(p[:3]) for p in packets[::2]],[[1,0,6],[3,0,23],[8,0,8],[4,0,43]])
        self.assertTrue(all(p==RELEASE for p in packets[1::2]))

    def test_reject_before_partial_send(self):
        for text in ('valid then Ω','😀','', 'x'*1001):
            with self.assertRaises(ValueError): encode_text(text)
        for keys in (['Ctrl+C','invalid+oops'],[],['Ctrl+Alt+']):
            with self.assertRaises(ValueError): encode_shortcuts(keys)

    def test_editor_punctuation(self):
        self.assertEqual(encode_text('“Hi”—it’s…'),encode_text('"Hi"-it\'s...'))
        self.assertEqual(encode_text('a\r\nb'),encode_text('a\nb'))

    def test_report_reference_id_present(self):
        self.assertIn(bytes([0x85,0x01]),REPORT_MAP)

if __name__=='__main__': unittest.main()
