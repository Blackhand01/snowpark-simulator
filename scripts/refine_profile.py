"""Deterministic monotone piste profile. No Blender, assets or file writes."""
import math


def solve(t):
    target,drop=t['surface_length_m'],t['drop_m']
    assert 0<drop<target
    def parameters(length):
        mean=drop/length;amplitude=t['profile_max_grade']-mean
        assert amplitude>0 and abs((t['rail_sector_grade']-mean)/amplitude)<1
        return mean,amplitude,math.acos((t['rail_sector_grade']-mean)/amplitude)
    def arc(length):
        mean,amp,phase=parameters(length);n=4096
        return length/n*sum(math.sqrt(1+(mean+amp*math.cos(2*math.pi*((i+.5)/n-.5)+phase))**2) for i in range(n))
    low,high=math.sqrt(target*target-drop*drop)-.5,target-.1
    for _ in range(60):
        mid=(low+high)/2
        if arc(mid)>target:high=mid
        else:low=mid
    length=(low+high)/2;mean,amplitude,phase=parameters(length)
    return dict(horizontal_length_m=length,mean_grade=mean,amplitude=amplitude,phase=phase,surface_length_m=arc(length))


def elevation(y,p):
    k=2*math.pi/p['horizontal_length_m']
    return p['mean_grade']*y+p['amplitude']/k*(math.sin(k*y+p['phase'])-math.sin(p['phase']))


def grade(y,p):
    return p['mean_grade']+p['amplitude']*math.cos(2*math.pi*y/p['horizontal_length_m']+p['phase'])


def height(x,y,t,p):
    # Ripple vanishes at both ends and never overwhelms the downhill grade.
    return elevation(y,p)+t['cross_grade']*x+t['ripple_m']*math.sin(2*math.pi*x/12)*math.sin(2*math.pi*y/p['horizontal_length_m'])


def longitudinal_grade(x,y,t,p):
    return grade(y,p)+t['ripple_m']*math.sin(2*math.pi*x/12)*2*math.pi/p['horizontal_length_m']*math.cos(2*math.pi*y/p['horizontal_length_m'])
