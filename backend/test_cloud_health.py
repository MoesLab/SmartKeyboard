import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
from cloud_health import CloudHealth,probe_direct


class CloudHealthTests(unittest.TestCase):
    def test_probe_is_get_only_and_never_uploads_audio(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)/'config';folder.mkdir();(folder/'openai-api-key').write_text('sk-test')
            connection=Mock();response=Mock(status=200);connection.getresponse.return_value=response
            with patch('cloud_health.http.client.HTTPSConnection',return_value=connection):
                self.assertEqual(probe_direct(root)['state'],'online')
            self.assertEqual(connection.request.call_args.args,('GET','/v1/models/gpt-transcribe'))
            self.assertNotIn('body',connection.request.call_args.kwargs)
            connection.close.assert_called_once()

    def test_disabled_or_gateway_route_does_not_claim_online(self):
        with patch('cloud_health.probe_direct') as probe:
            self.assertEqual(CloudHealth('/app',lambda:None).snapshot()['state'],'offline')
            self.assertEqual(CloudHealth('/app',lambda:'zima').snapshot()['state'],'unknown')
            probe.assert_not_called()

    def test_cached_and_nonblocking_and_failure_sanitized(self):
        health=CloudHealth('/app',lambda:'direct')
        with patch('cloud_health.threading.Thread') as thread:
            self.assertEqual(health.snapshot()['state'],'checking')
            self.assertEqual(health.snapshot()['state'],'checking')
            self.assertEqual(thread.call_count,1)
            with patch('cloud_health.probe_direct',side_effect=OSError('private secret detail')):health._check()
            state=health.snapshot();self.assertEqual(state['state'],'offline')
            self.assertNotIn('secret',state['message']);self.assertEqual(thread.call_count,1)


if __name__=='__main__':unittest.main()
