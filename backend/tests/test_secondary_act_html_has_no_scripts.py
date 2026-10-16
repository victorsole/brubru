"""Act bodies carry no script, style or on* handler (16 Oct 2026: 40 acts did)."""
from api.v1._body import strip_active_html


def test_active_markup_is_removed_and_the_text_kept():
    html = ('<div onclick="track()"><script>var x=1;</script><style>p{}</style>'
            '<p class="oj-normal">Article 1</p></div>')
    assert strip_active_html(html) == '<div><p class="oj-normal">Article 1</p></div>'
    assert strip_active_html(None) is None
