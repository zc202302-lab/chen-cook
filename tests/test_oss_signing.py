"""Exercise the real SDK signer; block every HTTP send before network access."""
import os
import tempfile
import unittest
from unittest.mock import patch
import oss2
from cooklib import oss


class BlockedHTTP(Exception):pass


class OSSSigningTest(unittest.TestCase):
    def test_listing_head_and_range_use_v4_with_qingdao_scope(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,COOK_DATA_DIR=folder):
            oss.save_settings('test-library','test-access-id','test-access-secret')
            bucket=oss.bucket_client()
            with patch('oss2.http.Session.do_request',side_effect=BlockedHTTP) as send:
                operations=[lambda:bucket.list_objects(prefix='ebooks/'),
                            lambda:bucket.head_object('ebooks/test.pdf'),
                            lambda:bucket.get_object('ebooks/test.pdf',byte_range=(0,4))]
                for operation in operations:
                    with self.assertRaises(BlockedHTTP):operation()
                    request=send.call_args.args[0]
                    headers={k.lower():v for k,v in request.headers.items()}
                    authorization=headers['authorization']
                    self.assertTrue(authorization.startswith('OSS4-HMAC-SHA256 '))
                    self.assertIn('/cn-qingdao/oss/aliyun_v4_request',authorization)
                    self.assertIn('x-oss-date',headers)
                self.assertEqual(send.call_count,3)
                self.assertEqual(headers['range'],'bytes=0-4')
