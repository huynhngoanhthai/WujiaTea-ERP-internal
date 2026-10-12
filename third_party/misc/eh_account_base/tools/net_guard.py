# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Shared SSRF guard for server-initiated outbound HTTP.

Any feature that lets a user configure a URL the SERVER then fetches
(report webhooks, callback endpoints, custom providers) is an SSRF vector:
the request originates from inside the trust boundary, so a URL pointing at
``169.254.169.254`` (cloud instance metadata), ``127.0.0.1`` / ``localhost``
(internal-only admin routes), or an RFC 1918 address (10/8, 172.16/12,
192.168/16) reaches services the user could never reach directly. The
classic payload steals the instance's IAM credentials from the metadata
service.

``assert_safe_url`` refuses non-http(s) schemes, resolves the hostname, and
rejects the request when ANY resolved address is loopback / private /
link-local / multicast / reserved / unspecified (each individually
opt-in-able, off by default). Resolving the name — not just checking a
literal — closes the "``evil.example.com`` -> A record 169.254.169.254"
bypass that a literal-only check misses.

Proxy egress: when Odoo reaches the internet through an outbound HTTP(S)
proxy, the PROXY resolves the destination name, not this host, so a local
``getaddrinfo`` may fail (proxy-only egress / split-horizon DNS) for a host
``urllib.request.urlopen`` would reach fine. A resolution FAILURE is
therefore not treated as a hard block when a proxy is in effect for the
target: the scheme, metadata-hostname and literal-IP checks still run, the
name is deferred to the same proxy-aware resolver ``urlopen`` will use, and
only genuinely unresolvable-with-no-proxy names are refused. A resolution
that SUCCEEDS is still validated in full, so a name that locally resolves to
an internal address stays blocked whether or not a proxy is configured.

Residual: a name re-resolved between this check and the socket connect
(DNS rebinding) is not pinned here; callers needing that guarantee must
connect to a validated IP with an explicit Host header. For the practical
vector (metadata IP literal, or a hostname that resolves to an internal
address) this check is sufficient and is the layer the webhook path relies
on.
"""

import ipaddress
import socket
from urllib.parse import urlsplit
from urllib.request import getproxies, proxy_bypass

# Hostnames that front a metadata service without going through a numeric
# link-local literal. GCP's resolves to 169.254.169.254 (already blocked by
# the IP check once resolved) but is listed so a resolver override or hosts
# entry cannot slip it past.
_METADATA_HOSTNAMES = frozenset({
    'metadata.google.internal',
    'metadata',
})


class UnsafeUrlError(ValueError):
    """Raised when a server-fetched URL targets a forbidden host."""


def _parse_literal_ip(host):
    """Return an :class:`ipaddress` object if *host* is a numeric IP literal.

    A literal needs no DNS, so it can be judged directly and must ALWAYS be
    judged - a proxy would still forward a request aimed at ``169.254.169.254``
    or an RFC 1918 literal, so the internal-IP block stays in force even on the
    proxy path. Returns ``None`` when *host* is a name that requires
    resolution.
    """
    candidate = host
    # urlsplit strips the brackets from an IPv6 host, but be defensive.
    if candidate.startswith('[') and candidate.endswith(']'):
        candidate = candidate[1:-1]
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        return None


def _proxy_in_effect(scheme, host):
    """Best-effort: would ``urllib.request.urlopen`` route *host* via a proxy?

    Mirrors the resolver urlopen itself uses (``getproxies`` = environment +
    platform config, honouring ``no_proxy`` via ``proxy_bypass``) so this
    guard and the real request agree on whether egress is proxied. This only
    gates the resolution-FAILURE fallback below, so a wrong answer never opens
    an internal host: it merely decides whether an unresolvable public name is
    deferred to the proxy-aware urlopen or refused here.
    """
    try:
        proxies = getproxies()
    except Exception:  # pragma: no cover - platform proxy lookup is defensive
        return False
    if not proxies.get(scheme):
        return False
    try:
        if proxy_bypass(host):
            return False
    except Exception:  # pragma: no cover - proxy_bypass is platform-dependent
        pass
    return True


def _addr_forbidden(ip, *, allow_loopback, allow_private):
    """Return a reason string when this IP is forbidden, else ''."""
    if ip.is_multicast:
        return "a multicast address"
    if ip.is_unspecified:
        return "the unspecified address"
    if ip.is_reserved:
        return "a reserved address"
    if ip.is_link_local:
        # 169.254.0.0/16 and fe80::/10 - the cloud metadata range.
        return "a link-local address (cloud metadata range)"
    if ip.is_loopback and not allow_loopback:
        return "a loopback address"
    if ip.is_private and not ip.is_loopback and not allow_private:
        # is_private is a superset that also covers loopback/link-local; we
        # reach here only for RFC 1918 / ULA space. Loopback has its own
        # independent opt-in above; enabling it must never enable all private
        # network destinations as a side effect.
        return "a private (internal network) address"
    return ''


def assert_safe_url(url, *, allow_loopback=False, allow_private=False):
    """Validate a server-fetched URL or raise :class:`UnsafeUrlError`.

    :param url: the URL the server is about to request.
    :param allow_loopback: permit 127.0.0.0/8 and ::1 (e.g. a co-located
        local LLM). Off by default.
    :param allow_private: permit RFC 1918 / ULA space (e.g. an on-prem
        provider on the LAN). Off by default. Loopback stays blocked unless
        ``allow_loopback`` is also set.
    :returns: the parsed :class:`urllib.parse.SplitResult` for reuse.
    """
    if not url or not isinstance(url, str):
        raise UnsafeUrlError("A URL is required.")
    parsed = urlsplit(url.strip())
    if parsed.scheme not in ('http', 'https'):
        raise UnsafeUrlError(
            "URL scheme %r is not allowed; only http and https may be "
            "fetched by the server." % (parsed.scheme or '',))
    host = parsed.hostname
    if not host:
        raise UnsafeUrlError("URL has no host.")
    if host.lower() in _METADATA_HOSTNAMES:
        raise UnsafeUrlError(
            "URL host %r targets the cloud metadata service." % host)

    # A numeric IP literal is judged directly - no DNS, and it must be checked
    # whether or not egress is proxied (a proxy would still forward a request
    # aimed at an internal literal).
    literal_ip = _parse_literal_ip(host)
    if literal_ip is not None:
        if literal_ip.version == 6 and literal_ip.ipv4_mapped:
            literal_ip = literal_ip.ipv4_mapped
        reason = _addr_forbidden(
            literal_ip, allow_loopback=allow_loopback,
            allow_private=allow_private)
        if reason:
            raise UnsafeUrlError(
                "URL host %r is %s, which the server refuses to fetch."
                % (host, reason))
        return parsed

    # Resolve the name to every address it maps to and validate them all, so
    # a hostname that resolves to an internal address is rejected too.
    try:
        infos = socket.getaddrinfo(host, parsed.port or None,
                                   proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        # Local resolution failed. When Odoo egresses through a proxy the proxy
        # (not this host) resolves the name, so a local lookup failure is not
        # proof the host is unreachable or internal - urlopen would still reach
        # it through the proxy. Defer to that proxy-aware path rather than
        # hard-blocking a possibly-legitimate public host. Scheme, metadata and
        # literal-IP checks above have already run; a name cannot smuggle an
        # internal-IP literal past them. With no proxy configured, an
        # unresolvable name stays refused exactly as before.
        if _proxy_in_effect(parsed.scheme, host):
            return parsed
        raise UnsafeUrlError(
            "URL host %r could not be resolved: %s" % (host, exc)) from exc

    seen = set()
    for info in infos:
        addr = info[4][0]
        if addr in seen:
            continue
        seen.add(addr)
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            raise UnsafeUrlError(
                "URL host %r resolved to an unparseable address %r."
                % (host, addr))
        # Unwrap IPv4-mapped IPv6 (::ffff:10.0.0.1) so the mapped v4 address
        # is judged on its own merits rather than as a routable v6 address.
        if ip.version == 6 and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        reason = _addr_forbidden(
            ip, allow_loopback=allow_loopback, allow_private=allow_private)
        if reason:
            raise UnsafeUrlError(
                "URL host %r resolves to %s (%s), which the server refuses "
                "to fetch." % (host, addr, reason))
    return parsed
