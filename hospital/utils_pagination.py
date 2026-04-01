"""
Pagination: build the full HTML in Python so the template only does {{ pagination_html|safe }}.
No include, no loops, no variable resolution — avoids string_if_invalid "INVALID" on server.
"""
import html
from django.core.paginator import EmptyPage


def get_pagination_html(request, page_obj, max_visible=25):
    """
    Return the complete <nav>...</nav> HTML for pagination, or '' if not applicable.
    Template uses: {% if pagination_html %}{{ pagination_html|safe }}{% endif %}
    Never raises EmptyPage: all paginator calls are guarded.
    """
    try:
        if not page_obj or not hasattr(page_obj, 'paginator'):
            return ''
        paginator = page_obj.paginator
        num_pages = paginator.num_pages
        if num_pages <= 0:
            return ''
        current = page_obj.number
        get_copy = request.GET.copy() if request else {}
        max_visible = min(max(1, int(max_visible)), 25)
        raw = _pagination_window(current, num_pages, max_visible)

        li_parts = []
        # "Page X of Y" badge
        li_parts.append(
            '<li class="page-item">'
            '<span class="page-link pagination-page-of" style="background: linear-gradient(135deg, var(--primary, #6366f1) 0%, var(--secondary, #8b5cf6) 100%); color: #fff; border: none; border-radius: 10px; margin: 0 4px; font-weight: 600; pointer-events: none;">'
            'Page {} of {}'
            '</span></li>'.format(current, num_pages)
        )
        # Page number links and ellipsis
        for num, is_ellipsis in raw:
            if is_ellipsis:
                li_parts.append('<li class="page-item disabled"><span class="page-link pagination-ellipsis">…</span></li>')
            else:
                get_copy['page'] = num
                qs = html.escape(get_copy.urlencode())
                if num == current:
                    li_parts.append(
                        '<li class="page-item active">'
                        '<span class="page-link pagination-num" style="border-radius: 8px; min-width: 38px; text-align: center;">{}</span>'
                        '</li>'.format(num)
                    )
                else:
                    li_parts.append(
                        '<li class="page-item">'
                        '<a class="page-link pagination-num" href="?{}" style="border-radius: 8px; min-width: 38px; text-align: center;">{}</a>'
                        '</li>'.format(qs, num)
                    )
        # Next: only call next_page_number() when has_next(); catch EmptyPage defensively
        try:
            if page_obj.has_next():
                next_qs = request.GET.copy() if request else {}
                next_qs['page'] = page_obj.next_page_number()
                next_qs_esc = html.escape(next_qs.urlencode())
                li_parts.append('<li class="page-item"><a class="page-link pagination-next" href="?{}" style="border-radius: 8px; font-weight: 600;">Next</a></li>'.format(next_qs_esc))
            else:
                li_parts.append('<li class="page-item disabled"><span class="page-link pagination-next" style="border-radius: 8px;">Next</span></li>')
        except EmptyPage:
            li_parts.append('<li class="page-item disabled"><span class="page-link pagination-next" style="border-radius: 8px;">Next</span></li>')
        # Last
        last_qs = request.GET.copy() if request else {}
        last_qs['page'] = paginator.num_pages
        last_qs_esc = html.escape(last_qs.urlencode())
        if page_obj.has_next():
            li_parts.append('<li class="page-item"><a class="page-link pagination-last" href="?{}" style="border-radius: 8px; font-weight: 600;">Last</a></li>'.format(last_qs_esc))
        else:
            li_parts.append('<li class="page-item disabled"><span class="page-link pagination-last" style="border-radius: 8px;">Last</span></li>')

        return (
            '<nav aria-label="Page navigation" class="mt-4">'
            '<ul class="pagination justify-content-center flex-wrap align-items-center gap-1 mb-0">'
            + ''.join(li_parts) +
            '</ul></nav>'
        )
    except EmptyPage:
        return ''
    except Exception:
        return ''


def _pagination_window(current, num_pages, max_visible):
    """Return list of (page_num, is_ellipsis)."""
    if num_pages <= 0:
        return []
    if num_pages <= max_visible:
        return [(i, False) for i in range(1, num_pages + 1)]
    half = max(max_visible - 4, 3)
    start = max(2, current - half // 2)
    end = min(num_pages - 1, start + half - 1)
    if end - start + 1 < half:
        start = max(2, end - half + 1)
    result = [(1, False)]
    if start > 2:
        result.append((None, True))
    for i in range(start, end + 1):
        result.append((i, False))
    if end < num_pages - 1:
        result.append((None, True))
    if num_pages > 1:
        result.append((num_pages, False))
    return result
