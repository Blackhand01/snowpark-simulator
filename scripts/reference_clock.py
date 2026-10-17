"""Monotone retiming of an approved motion onto observed video timestamps."""
import bisect
import math
from statistics import median


def anchors(timing):
    return [(e['pts']/timing['time_base_den'], e['approved_time_s'])
            for e in timing['events'] if e.get('anchor', True)]


def approved_time(t, timing):
    """Monotone cubic Hermite clock; exact at anchors, continuous velocity."""
    pairs = anchors(timing)
    x, y = zip(*pairs)
    assert all(a < b for a, b in zip(x, x[1:]))
    assert all(a < b for a, b in zip(y, y[1:]))
    h = [b-a for a, b in zip(x, x[1:])]
    d = [(b-a)/hh for a, b, hh in zip(y, y[1:], h)]
    slopes = [d[0]]
    for i in range(1, len(x)-1):
        w1, w2 = 2*h[i]+h[i-1], h[i]+2*h[i-1]
        slopes.append((w1+w2)/(w1/d[i-1]+w2/d[i]))
    slopes.append(d[-1])
    if t <= x[0]: return y[0]
    if t >= x[-1]: return y[-1]
    i = bisect.bisect_right(x, t)-1
    u = (t-x[i])/h[i]
    return ((2*u**3-3*u*u+1)*y[i]+(u**3-2*u*u+u)*h[i]*slopes[i]
            +(-2*u**3+3*u*u)*y[i+1]+(u**3-u*u)*h[i]*slopes[i+1])


def pts_filter(pts):
    """Exact presentation ticks from frame index, including VFR deviations."""
    assert pts[0] == 0 and all(a < b for a, b in zip(pts, pts[1:]))
    step = int(median(b-a for a, b in zip(pts, pts[1:])))
    terms = [f'{step}*N']
    for i in range(1, len(pts)):
        delta = pts[i]-pts[i-1]-step
        if delta:
            terms.append(f'{delta:+d}*gte(N,{i})')
    return ''.join(terms), step


def validate(timing, c):
    den = timing['time_base_den']; pts = timing['frame_pts']
    assert type(den) is int and den > 0
    assert pts[0] == 0 and all(type(p) is int for p in pts)
    assert all(a < b for a, b in zip(pts, pts[1:]))
    assert timing['duration_ticks'] > pts[-1]
    assert math.isclose(c['motion']['duration_s'], timing['duration_ticks']/den)
    assert timing['video_sha256'] == c['source']['reference_sha256']
    assert timing['approved_blend_sha256'] == c['source']['sha256']
    for e in timing['events']:
        if 'frame_index' in e:
            assert pts[e['frame_index']] == e['pts']
        if e['name'] in c['rail_slide']:
            assert math.isclose(c['rail_slide'][e['name']], e['pts']/den)
    pairs = anchors(timing)
    assert pairs[0] == (0., 0.)
    assert all(a[0] < b[0] and a[1] < b[1] for a, b in zip(pairs, pairs[1:]))
