"""Patch validation tests; no Bluetooth hardware, module load or kernel build."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('sco_helper',Path(__file__).with_name('prepare-bluetooth-sco-test.py'))
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
HEADER='#define CONFIG_BLUEDROID 0\n#define SCO_NUM hdev->conn_hash.sco_num\n'
SOURCE='''static void check_sco_event(struct urb *urb)
{
    if (connected) {
        SCO_NUM++;
    } else {
        SCO_NUM--;
    }
}
static void reset(void) {
    SCO_NUM = 0;
}
static int send(void) {
    switch (type) {
    case HCI_SCODATA_PKT:
        print_sco(skb, 1);
        if (!data->isoc_tx_ep || !SCO_NUM) {
            kfree(skb);
            return -ENODEV;
        }
        urb = usb_alloc_urb(1, GFP_ATOMIC);
        if (!urb) {
            kfree(skb);
            return -ENOMEM;
        }
        hdev->stat.sco_tx++;
    }
}
'''


class PrepareTest(unittest.TestCase):
    def test_five_vendor_mutations_are_guarded(self):
        patched=helper.patch_source(SOURCE,HEADER)
        self.assertEqual(patched.count('#if CONFIG_BLUEDROID'),5)
        native=__import__('re').sub(r'#if CONFIG_BLUEDROID\n.*?#endif[^\n]*','',patched,flags=__import__('re').S)
        self.assertNotIn('SCO_NUM++;',native);self.assertNotIn('SCO_NUM--;',native)
        self.assertNotIn('SCO_NUM=0;',native);self.assertNotIn('kfree(skb);',native)
        self.assertIn('return -ENODEV;',native);self.assertIn('return -ENOMEM;',native)
        self.assertIn('!data->isoc_tx_ep || !SCO_NUM',native)

    def test_unrecognized_or_repatched_source_is_rejected(self):
        variants=[(SOURCE,HEADER.replace('CONFIG_BLUEDROID 0','CONFIG_BLUEDROID 1')),
                  (SOURCE,HEADER.replace('hdev->conn_hash.sco_num','another_counter')),
                  (SOURCE.replace('SCO_NUM++;',''),HEADER),
                  (SOURCE.replace('kfree(skb);','kfree_skb(skb);'),HEADER),
                  (helper.patch_source(SOURCE,HEADER),HEADER)]
        for source,header in variants:
            with self.assertRaises(ValueError):helper.patch_source(source,header)

    def test_prepare_keeps_original_and_skips_old_build_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);original=base/'original';original.mkdir()
            (original/'aic_btusb.c').write_text(SOURCE);(original/'aic_btusb.h').write_text(HEADER)
            (original/'aic_btusb.ko').write_text('old module');(original/'Makefile').write_text('# fixture')
            output=helper.prepare(original,base/'tests')
            self.assertEqual((original/'aic_btusb.c').read_text(),SOURCE)
            self.assertEqual((original/'aic_btusb.ko').read_text(),'old module')
            self.assertFalse((output/'aic_btusb.ko').exists())
            self.assertTrue((output/'smartkeyboard-sco-test.patch').exists())


if __name__=='__main__':unittest.main()
