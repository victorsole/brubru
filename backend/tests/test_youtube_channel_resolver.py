"""The YouTube resolver must read a page's OWN identity, never the first channelId.

Regression for 2 Sep 2026: on the European Parliament's own channel page the first
`"channelId"` in the serialised JSON belongs to the European Commission (related
channels are emitted before the page's metadata). The old resolver took it, 19 EU
handles collapsed onto the Commission's channel, and every Commission video was
stored 19 times as an "original" statement by a different institution.
"""
from services.social.post_fetcher import _own_channel_id, _own_handle

EP = "UCvU4p_w08osQsrNi_I4ZtDA"
EC = "UCMPaviJxybo1RTdzvYcU91A"

# Shape of a real channel page: a related channel's channelId comes first, the
# canonical link and channelMetadataRenderer (the page's own identity) later.
PAGE = (
    '<html><head>'
    f'<link rel="canonical" href="https://www.youtube.com/channel/{EP}">'
    '</head><body><script>'
    f'{{"relatedChannels":[{{"channelId":"{EC}","title":"European Commission"}}],'
    f'"metadata":{{"channelMetadataRenderer":{{"title":"European Parliament","externalId":"{EP}",'
    '"vanityChannelUrl":"http://www.youtube.com/@europeanparliament"}},'
    '"featured":[{"canonicalBaseUrl":"/@EuropeanCommission",'
    '"vanityChannelUrl":"http://www.youtube.com/@EuropeanCommission"}]}'
    '</script></body></html>'
)


def test_own_channel_id_is_the_canonical_link_not_the_first_channel_id():
    assert _own_channel_id(PAGE) == EP


def test_own_channel_id_falls_back_to_metadata_external_id():
    no_canonical = PAGE.replace(f'<link rel="canonical" href="https://www.youtube.com/channel/{EP}">', '')
    assert _own_channel_id(no_canonical) == EP


def test_own_handle_is_the_first_vanity_url_not_a_featured_channel():
    assert _own_handle(PAGE) == "europeanparliament"


def test_unknown_page_resolves_to_nothing():
    assert _own_channel_id('<html><script>{"channelId":"' + EC + '"}</script></html>') is None
    assert _own_handle("<html></html>") is None
