import tempfile
from pathlib import Path
import unittest

from calibrated_ops.hosted import configuration,gateway_config


class HostedConfigurationTests(unittest.TestCase):
    def env(self):
        return dict(CALIBRATED_PUBLIC_ORIGIN='https://example.onrender.com',
                    CALIBRATED_PASSWORD='synthetic-test-password-only',
                    CALIBRATED_DATABASE=str(Path(tempfile.gettempdir())/'calibratedops-qa.sqlite3'))

    def test_requires_https_origin_and_secret_before_startup(self):
        for origin in ('','http://example.com','https://example.com/','https://a.com/path',
                       'https://a.com?secret=x','https://user:pass@a.com','https://a.com\nadmin off'):
            with self.subTest(origin=origin),self.assertRaises(ValueError):
                configuration(dict(self.env(),CALIBRATED_PUBLIC_ORIGIN=origin))
        for password in ('','short','x'*73,'long-enough-password\n'):
            with self.assertRaises(ValueError):configuration(dict(self.env(),CALIBRATED_PASSWORD=password))

    def test_render_origin_fallback_and_loopback_test_exception(self):
        env=self.env();env['RENDER_EXTERNAL_URL']=env.pop('CALIBRATED_PUBLIC_ORIGIN')
        self.assertEqual(configuration(env)['origin'],'https://example.onrender.com')
        self.assertEqual(configuration(dict(self.env(),CALIBRATED_PUBLIC_ORIGIN='http://127.0.0.1:18888',
                                            CALIBRATED_LOCAL_TEST='1'))['hostname'],'127.0.0.1')
        with self.assertRaises(ValueError):
            configuration(dict(self.env(),CALIBRATED_PUBLIC_ORIGIN='http://public.example',CALIBRATED_LOCAL_TEST='1'))

    def test_gateway_has_no_public_backend_or_plaintext_password(self):
        config=configuration(self.env())
        text=gateway_config(config,'$2a$14$'+'A'*53)
        self.assertIn('admin off',text)
        self.assertIn('basic_auth',text)
        self.assertIn('header_up -Authorization',text)
        self.assertIn('127.0.0.1:8767',text)
        self.assertNotIn(config['password'],text)
        with self.assertRaises(ValueError):gateway_config(config,'bad-hash\nmalicious config')

    def test_rejects_relative_database_and_port_collision(self):
        with self.assertRaises(ValueError):configuration(dict(self.env(),CALIBRATED_DATABASE='runs/data.sqlite3'))
        for port in ('80','8767','65536'):
            with self.assertRaises(ValueError):configuration(dict(self.env(),PORT=port))

    def test_public_demo_has_no_password_challenge(self):
        env=self.env();env.pop('CALIBRATED_PASSWORD')
        config=configuration(dict(env,CALIBRATED_PUBLIC_DEMO='1',CALIBRATED_DEMO='1'))
        self.assertTrue(config['public_demo'])
        self.assertNotIn('basic_auth',gateway_config(config))
        self.assertIn('Invalid host',gateway_config(config))

    def test_public_access_cannot_disable_private_workspace_authentication(self):
        with self.assertRaises(ValueError):configuration(dict(self.env(),CALIBRATED_PUBLIC_DEMO='1'))
        with self.assertRaises(ValueError):
            env=self.env();env.pop('CALIBRATED_PASSWORD');configuration(env)
