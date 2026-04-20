#!/usr/bin/env python3
"""Applies mobile-friendly fixes to src/App.jsx"""

with open("src/App.jsx") as f:
    c = f.read()

fixes = 0

# Fix 1: filter row - horizontal scroll instead of wrap
old1 = 'gap:8,flexWrap:"wrap"}}>\n                <IntownToggle/><div style={{width:1,height:18,background:"#2A2E42"}}/><StatusPills/>'
new1 = 'gap:8,overflowX:"auto",paddingBottom:4,WebkitOverflowScrolling:"touch"}}>\n                <IntownToggle/><div style={{width:1,height:18,flexShrink:0,background:"#2A2E42"}}/><StatusPills/>'
if old1 in c:
    c = c.replace(old1, new1)
    fixes += 1
    print("Fix 1 applied: filter row horizontal scroll")
else:
    print("Fix 1 NOT found - searching for alternatives...")
    # Try to find what's actually there
    idx = c.find("IntownToggle/><div style={{width:1")
    if idx > -1:
        print("  Found at:", repr(c[idx-100:idx+50]))

# Fix 2: status pills no shrink
old2 = 'padding:"5px 12px",transition:"all .15s"}}>{s}</button>'
new2 = 'padding:"5px 12px",transition:"all .15s",flexShrink:0,whiteSpace:"nowrap"}}>{s}</button>'
if old2 in c:
    c = c.replace(old2, new2)
    fixes += 1
    print("Fix 2 applied: status pills no shrink")
else:
    print("Fix 2 NOT found")

# Fix 3: intown toggle no shrink - find the exact string
old3 = 'fontSize:12,fontWeight:600,transition:"all .15s"}}>'
new3 = 'fontSize:12,fontWeight:600,transition:"all .15s",flexShrink:0,whiteSpace:"nowrap"}}>'
if old3 in c:
    c = c.replace(old3, new3)
    fixes += 1
    print("Fix 3 applied: intown toggle no shrink")
else:
    print("Fix 3 NOT found")

# Fix 4: metadata dots - use a simple join
old4 = '{app.neighborhood} \u00b7 {app.type}{app.zoning?` \u00b7 ${app.zoning}`:""} \u00b7 {formatDate(app.submitted)}'
new4 = '{[app.neighborhood,app.type,app.zoning,formatDate(app.submitted)].filter(Boolean).join(" \u00b7 ")}'
if old4 in c:
    c = c.replace(old4, new4)
    fixes += 1
    print("Fix 4 applied: metadata dots")
else:
    # Try alternate format
    old4b = "{app.neighborhood} · {app.type}{app.zoning?` · ${app.zoning}`:\"\"} · {formatDate(app.submitted)}"
    if old4b in c:
        c = c.replace(old4b, new4)
        fixes += 1
        print("Fix 4b applied: metadata dots")
    else:
        print("Fix 4 NOT found - looking for neighborhood line...")
        idx = c.find("app.neighborhood}")
        if idx > -1:
            print("  Found at:", repr(c[idx:idx+100]))

with open("src/App.jsx", "w") as f:
    f.write(c)

print(f"\n{fixes} fixes applied to src/App.jsx")
