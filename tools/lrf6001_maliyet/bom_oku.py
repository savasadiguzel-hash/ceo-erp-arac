import sys, re, json, openpyxl
sys.stdout.reconfigure(encoding="utf-8")
wb = openpyxl.load_workbook(sys.argv[1], data_only=True)
ws = wb["Urun BOM"]
ana = []; bolum = None
for i, r in enumerate(ws.iter_rows(min_row=7, values_only=True), 7):
    a = r[0]
    if isinstance(a, str) and a.strip() and r[1] is None and r[3] is None:
        bolum = a.strip(); continue
    if isinstance(a, (int, float)):
        konf = str(r[3]).strip() if r[3] is not None else None
        ana.append(dict(satir=i, bolum=bolum, sira=a, adet=r[1], eski=r[2], konf=konf, tanim=(r[4] or "").strip()))
kart = {}
for ws in wb.worksheets[1:]:
    hdr = None; rows = []
    for i, r in enumerate(ws.iter_rows(values_only=True), 1):
        if r and r[0] == "Comment": hdr = True; continue
        if hdr and r[0]:
            rows.append(dict(satir=i, mpn=str(r[0]).strip(), desc=(r[1] or ""), adet=r[3]))
    kart[ws.title] = rows
json.dump(dict(ana=ana, kart=kart), open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, default=str, indent=0)
for x in ana: print(x["bolum"][:10], x["sira"], x["adet"], x["eski"], "|", x["konf"], "|", x["tanim"][:45])
for k, v in kart.items():
    mp = {}
    for x in v: mp[x["mpn"]] = mp.get(x["mpn"], 0) + (x["adet"] or 0)
    print(k, "satır", len(v), "farklı MPN", len(mp), "toplam adet", sum(mp.values()), "adetsiz", sum(1 for x in v if not x["adet"]))
