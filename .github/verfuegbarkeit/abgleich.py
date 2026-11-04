# Freie Tage fuer die Website - laeuft alle 30 Minuten bei GitHub (Anjas Wunsch vom 04.11.2026:
# die Website soll Sperren aus ihrem Kalender ohne Claude-Fenster sehen).
#
# Quellen:
#   - Anjas Google Kalender ueber die GEHEIMEN iCal-Adressen (GitHub-Secrets KALENDER_PRIVAT,
#     KALENDER_GESCHAEFT). Die Adressen stehen nirgends im Repo.
#   - .github/verfuegbarkeit/gebucht.json (gebuchte Hochzeiten, schreibt Claude).
# Regeln (Anja, 04.11.2026): Titel beginnt mit "Urlaub" oder "Nicht verfuegbar" = gesperrt.
#   1 gebuchte Braut = eineBraut, 2 = voll. Nur Daten, keine Namen, keine Gruende.
# Sicherung: Ist ein Kalender nicht lesbar, wird NICHTS geschrieben - lieber eine alte Liste
#   (die Website faellt nach 30 Tagen selbst auf WhatsApp zurueck) als eine leere, falsche.
# Aufruf ohne Argumente (GitHub) oder zum Testen: python abgleich.py datei1.ics [datei2.ics ...]
import os, sys, re, json, datetime, urllib.request
from zoneinfo import ZoneInfo
import icalendar, recurring_ical_events

HIER = os.path.dirname(os.path.abspath(__file__))
ZIEL = os.path.join(HIER, '..', '..', 'verfuegbarkeit.json')
TZ = ZoneInfo('Europe/Amsterdam')
heute = datetime.datetime.now(TZ).date()
bis = heute + datetime.timedelta(days=730)
TITEL = re.compile(r'(urlaub|nicht verf(ü|ue|u)gbar)(?!\w)')

def quellen():
    if len(sys.argv) > 1:
        for p in sys.argv[1:]:
            yield p, open(p, 'rb').read()
        return
    gefunden = False
    for name in ('KALENDER_PRIVAT', 'KALENDER_GESCHAEFT'):
        url = (os.environ.get(name) or '').strip()
        if not url:
            print(f'{name}: nicht hinterlegt, uebersprungen')
            continue
        gefunden = True
        req = urllib.request.Request(url, headers={'User-Agent': 'bridal-glam-verfuegbarkeit'})
        daten = urllib.request.urlopen(req, timeout=60).read()   # Fehler -> Abbruch, nichts wird geschrieben
        if b'BEGIN:VCALENDAR' not in daten[:500]:
            sys.exit(f'{name}: Antwort ist kein Kalender - nichts geschrieben')
        yield name, daten
    if not gefunden:
        sys.exit('Kein Kalender hinterlegt - nichts geschrieben')

def tag(x):
    if isinstance(x, datetime.datetime):
        return (x.astimezone(TZ) if x.tzinfo else x).date(), x
    return x, None

gesperrt = set()
for name, daten in quellen():
    kal = icalendar.Calendar.from_ical(daten)
    n = 0
    for e in recurring_ical_events.of(kal).between(heute, bis + datetime.timedelta(days=1)):
        titel = str(e.get('SUMMARY', '')).strip().lower()
        if not TITEL.match(titel) or str(e.get('STATUS', '')).upper() == 'CANCELLED':
            continue
        a, _ = tag(e.decoded('DTSTART'))
        ende = e.decoded('DTEND') if e.get('DTEND') else e.decoded('DTSTART')
        z, zeit = tag(ende)
        if zeit is None:
            z = z - datetime.timedelta(days=1) if z > a else a     # ganztaegig: Ende exklusiv
        elif zeit.astimezone(TZ).time() == datetime.time(0, 0) and z > a:
            z -= datetime.timedelta(days=1)                         # endet um Mitternacht
        d = a
        while d <= z:
            if heute <= d <= bis:
                gesperrt.add(d)
            d += datetime.timedelta(days=1)
        n += 1
    print(f'{name}: {n} Sperr-Termine')

geb = json.load(open(os.path.join(HIER, 'gebucht.json'))).get('tage', {})
zahl = {datetime.date.fromisoformat(k): int(v) for k, v in geb.items()
        if datetime.date.fromisoformat(k) >= heute}
voll = sorted(gesperrt | {d for d, n in zahl.items() if n >= 2})
eine = sorted(d for d, n in zahl.items() if n == 1 and d not in voll)
neu = {'stand': heute.isoformat(), 'eineBraut': [d.isoformat() for d in eine],
       'voll': [d.isoformat() for d in voll]}

try:
    alt = json.load(open(ZIEL))
except Exception:
    alt = {}
gleich = {k: v for k, v in alt.items() if k != 'stand'} == {k: v for k, v in neu.items() if k != 'stand'}
if gleich and alt.get('stand') == neu['stand']:
    print('Unveraendert, nichts zu tun.')
else:
    open(ZIEL, 'w').write(json.dumps(neu, ensure_ascii=False) + '\n')
    print('Neu geschrieben:', len(voll), 'volle Tage,', len(eine), 'mit einer Braut',
          '(nur Datum aufgefrischt)' if gleich else '')
