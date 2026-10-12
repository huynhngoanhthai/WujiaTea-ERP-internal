# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Unit tests for the shared SSRF guard (tools/net_guard.assert_safe_url).

The guard protects any server-initiated fetch of a user-supplied URL
(report webhooks, custom providers). IP-literal hosts need no DNS, so
those cases are hermetic; the name-resolution and proxy-egress cases patch
socket.getaddrinfo / getproxies so no real lookup happens in CI.

``assert_safe_url`` is a pure module function, not an ORM-guarded write, so
the exploit path it refuses is refused for every caller regardless of Odoo
user - there is no privileged bypass to run under with_user.
"""

import socket
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.eh_account_base.tools.net_guard import (
    UnsafeUrlError, assert_safe_url,
)

# Where getproxies / proxy_bypass are bound for patching (imported into the
# module namespace).
_NG = 'odoo.addons.eh_account_base.tools.net_guard'


def _addrinfo(ip, port=443, family=2):
    # Mimic one socket.getaddrinfo tuple: (family, type, proto, canon, sa).
    return [(family, 1, 6, '', (ip, port))]


@tagged('eh_account_base', 'post_install', '-at_install')
class TestNetGuard(TransactionCase):

    # ---- blocked: scheme ----

    def test_rejects_file_scheme(self):
        with self.assertRaises(UnsafeUrlError):
            assert_safe_url('file:///etc/passwd')

    def test_rejects_gopher_scheme(self):
        with self.assertRaises(UnsafeUrlError):
            assert_safe_url('gopher://127.0.0.1:6379/_flushall')

    def test_rejects_empty(self):
        with self.assertRaises(UnsafeUrlError):
            assert_safe_url('')
        with self.assertRaises(UnsafeUrlError):
            assert_safe_url(None)

    # ---- blocked: IP literals (no DNS needed) ----

    def test_rejects_cloud_metadata_ip(self):
        with self.assertRaises(UnsafeUrlError):
            assert_safe_url('http://169.254.169.254/latest/meta-data/')

    def test_rejects_loopback_ip(self):
        with self.assertRaises(UnsafeUrlError):
            assert_safe_url('http://127.0.0.1:8069/web/session')

    def test_rejects_private_ip(self):
        for host in ('10.1.2.3', '192.168.0.1', '172.16.9.9'):
            with self.assertRaises(UnsafeUrlError):
                assert_safe_url('http://%s/hook' % host)

    def test_rejects_ipv6_loopback(self):
        with self.assertRaises(UnsafeUrlError):
            assert_safe_url('http://[::1]:8069/')

    def test_rejects_metadata_hostname(self):
        with self.assertRaises(UnsafeUrlError):
            assert_safe_url('http://metadata.google.internal/')

    # ---- blocked: hostname that RESOLVES to an internal address ----

    def test_rejects_hostname_resolving_to_metadata(self):
        with patch('socket.getaddrinfo',
                   return_value=_addrinfo('169.254.169.254')):
            with self.assertRaises(UnsafeUrlError):
                assert_safe_url('https://totally-benign.example.com/hook')

    def test_rejects_hostname_resolving_to_private(self):
        with patch('socket.getaddrinfo', return_value=_addrinfo('10.0.0.5')):
            with self.assertRaises(UnsafeUrlError):
                assert_safe_url('https://rebind.example.com/hook')

    def test_rejects_ipv4_mapped_ipv6_private(self):
        # ::ffff:10.0.0.1 must be judged on the mapped v4 address.
        with patch('socket.getaddrinfo',
                   return_value=_addrinfo('::ffff:10.0.0.1', family=10)):
            with self.assertRaises(UnsafeUrlError):
                assert_safe_url('https://mapped.example.com/hook')

    # ---- allowed: public host ----

    def test_allows_public_host(self):
        with patch('socket.getaddrinfo', return_value=_addrinfo('93.184.216.34')):
            parsed = assert_safe_url('https://hooks.slack.com/services/T/B/X')
        self.assertEqual(parsed.scheme, 'https')
        self.assertEqual(parsed.hostname, 'hooks.slack.com')

    # ---- opt-ins ----

    def test_allow_loopback_opt_in(self):
        # A local LLM provider explicitly permits loopback.
        parsed = assert_safe_url('http://127.0.0.1:11434/v1/chat',
                                 allow_loopback=True)
        self.assertEqual(parsed.hostname, '127.0.0.1')

    def test_allow_loopback_does_not_allow_private_networks(self):
        with self.assertRaises(UnsafeUrlError):
            assert_safe_url(
                'http://10.0.0.5/v1/chat',
                allow_loopback=True,
            )

    def test_allow_private_opt_in(self):
        with patch('socket.getaddrinfo', return_value=_addrinfo('10.0.0.5')):
            parsed = assert_safe_url('http://onprem.lan/v1',
                                     allow_private=True)
        self.assertEqual(parsed.hostname, 'onprem.lan')

    def test_link_local_still_blocked_even_with_private_opt_in(self):
        # allow_private must NOT re-open the cloud metadata range.
        with self.assertRaises(UnsafeUrlError):
            assert_safe_url('http://169.254.169.254/', allow_private=True,
                            allow_loopback=True)

    # ---- proxy egress: unresolvable public host is deferred, not blocked ----

    def test_proxy_defers_unresolvable_public_host(self):
        # LEGITIMATE PATH: proxy-only egress cannot resolve a public webhook
        # host locally (getaddrinfo -> gaierror), but a proxy is configured for
        # https, so the proxy-aware urlopen would reach it. The guard must NOT
        # hard-block; it defers the real connect decision to urlopen.
        gai_fail = socket.gaierror(-2, 'Name or service not known')
        with patch('socket.getaddrinfo', side_effect=gai_fail), \
                patch(_NG + '.getproxies',
                      return_value={'https': 'http://egress-proxy:3128'}), \
                patch(_NG + '.proxy_bypass', return_value=False):
            parsed = assert_safe_url('https://hooks.slack.com/services/T/B/X')
        self.assertEqual(parsed.hostname, 'hooks.slack.com')

    def test_no_proxy_unresolvable_host_still_refused(self):
        # ORIGINAL BEHAVIOUR PRESERVED: with no proxy, an unresolvable name is
        # still refused - it cannot be proven safe and urlopen could not reach
        # it either.
        gai_fail = socket.gaierror(-2, 'Name or service not known')
        with patch('socket.getaddrinfo', side_effect=gai_fail), \
                patch(_NG + '.getproxies', return_value={}):
            with self.assertRaises(UnsafeUrlError):
                assert_safe_url('https://hooks.slack.com/services/T/B/X')

    def test_proxy_does_not_open_internal_ip_literal(self):
        # HOLE STAYS CLOSED under a proxy: an internal / metadata IP literal is
        # still refused, because a proxy would forward the request to it just
        # the same. A literal must be judged WITHOUT any DNS call - a stubbed
        # getaddrinfo that would explode proves the literal path never resolves.
        boom = patch('socket.getaddrinfo',
                     side_effect=AssertionError('literal must not hit DNS'))
        with boom, \
                patch(_NG + '.getproxies',
                      return_value={'http': 'http://egress-proxy:3128'}), \
                patch(_NG + '.proxy_bypass', return_value=False):
            for url in ('http://169.254.169.254/latest/meta-data/',
                        'http://127.0.0.1:8069/web/session',
                        'http://10.1.2.3/hook',
                        'http://[::1]:8069/'):
                with self.assertRaises(UnsafeUrlError):
                    assert_safe_url(url)

    def test_proxy_does_not_open_hostname_resolving_internal(self):
        # HOLE STAYS CLOSED under a proxy: if local DNS DOES resolve (split
        # horizon) to an internal address, a successful resolution is validated
        # in full and the internal target is still refused.
        with patch('socket.getaddrinfo',
                   return_value=_addrinfo('169.254.169.254')), \
                patch(_NG + '.getproxies',
                      return_value={'https': 'http://egress-proxy:3128'}), \
                patch(_NG + '.proxy_bypass', return_value=False):
            with self.assertRaises(UnsafeUrlError):
                assert_safe_url('https://evil.example.com/hook')

    def test_no_proxy_scheme_mismatch_unresolvable_still_refused(self):
        # A proxy configured only for http does not proxy an https target, so
        # the https deferral must NOT fire - the unresolvable host is refused,
        # matching what urlopen (which also would not proxy it) would do.
        gai_fail = socket.gaierror(-2, 'Name or service not known')
        with patch('socket.getaddrinfo', side_effect=gai_fail), \
                patch(_NG + '.getproxies',
                      return_value={'http': 'http://egress-proxy:3128'}), \
                patch(_NG + '.proxy_bypass', return_value=False):
            with self.assertRaises(UnsafeUrlError):
                assert_safe_url('https://hooks.slack.com/services/T/B/X')

    def test_proxy_bypass_host_unresolvable_still_refused(self):
        # A host matched by no_proxy is NOT proxied (proxy_bypass -> True), so
        # the deferral is disabled and an unresolvable bypassed host is refused.
        gai_fail = socket.gaierror(-2, 'Name or service not known')
        with patch('socket.getaddrinfo', side_effect=gai_fail), \
                patch(_NG + '.getproxies',
                      return_value={'https': 'http://egress-proxy:3128'}), \
                patch(_NG + '.proxy_bypass', return_value=True):
            with self.assertRaises(UnsafeUrlError):
                assert_safe_url('https://internal.corp/hook')
