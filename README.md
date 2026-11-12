# S3 Viewer

Desktop-Programm für Ubuntu, um Buckets einer OpenStack- oder anderen S3-Umgebung zu durchsuchen, Dateien anzusehen und sie zwischen dem Rechner und dem Bucket zu bewegen.

![Dunkle und helle Oberfläche](<misc/Dark and light mode comparison.png>)

## Start

```bash
./start.sh
```

Beim ersten Start legt das Skript eine virtuelle Umgebung an und installiert die Abhängigkeiten. Zusätzlich lässt sich das Programm per Doppelklick auf `S3 Viewer.desktop` oder über den Eintrag im Anwendungsmenü starten.

## Funktionen

- Verbindung zu einem S3-Endpunkt mit Zugriffsschlüssel und geheimem Schlüssel, wahlweise mit Pfad-Stil, TLS-Prüfung und Signatur `s3v4` oder `s3` (SigV2).
- Region aus einer Liste wählen oder selbst eintragen.
- Verbindungsformular nach oben einklappen. Eingeklappt bleiben Verbinden und Trennen als Symbole, ausgeklappt erscheinen Speichern, Entfernen, Verbinden und Trennen mit Beschriftung.
- Benannte Verbindungen in `~/.s3-viewer` speichern und wieder laden. Der geheime Schlüssel liegt nur dort, nicht im Git-Repository und nicht in den automatisch gemerkten Fenstereinstellungen.
- Oberfläche auf Deutsch oder Englisch und zwischen hellem und dunklem Erscheinungsbild umschalten.
- Buckets auflisten und den Namen filtern. Direkt einen Bucket öffnen, wenn die Rechte keine Liste erlauben.
- Ordner durchsuchen, mit Brotkrumen und Zurück-nach-oben. Dateien und Ordner nach Namen filtern und mehrere Einträge auswählen.
- Dateivorschau für Text, CSV, JSON, YAML, XML, HTML, SVG und NDJSON. CSV erscheint als Tabelle. Strukturierte Texte werden farblich hervorgehoben, Text und Tabelle zeigen Zeilennummern.
- Textbasierte Dateien in der Vorschau ändern und zurück in den Bucket schreiben.
- Grobe Vorschau für TIFF-Bilder, auch wenn mehrere Kanäle enthalten sind.
- Markierte Dateien und ganze Ordner herunterladen. Unten zeigt eine Leiste den Fortschritt; ein Download lässt sich abbrechen.
- Dateien und ganze Ordner hochladen. Unterordner bleiben erhalten. Eine Überschreibwarnung erscheint nur, wenn der Name im Ziel schon vorhanden ist.
- Im geöffneten Ordner einen neuen leeren Ordner anlegen.

## Verbindung

- **Endpunkt:** S3-API-Adresse, zum Beispiel `https://s3.cloud.example.com`
- **Zugriffsschlüssel und geheimer Schlüssel:** S3- bzw. EC2-Credentials aus OpenStack, nicht das Login-Passwort
- **Region:** bei OpenStack oft `RegionOne`, bei vielen S3-Schnittstellen `us-east-1`. Der Name geht in die Signatur ein.
- **Pfad-Stil:** für OpenStack eingeschaltet lassen
- **TLS-Zertifikat prüfen:** bei einem selbstsignierten Zertifikat ausschalten
- **Signatur:** wenn die Anmeldung an der Signatur scheitert, `s3 (SigV2)` versuchen
- **Bucket:** nur ausfüllen, wenn die Rechte keine Bucket-Liste erlauben

Endpunkt, Zugriffsschlüssel und die Optionen werden lokal in `~/.config/s3viewer/S3Viewer.conf` gemerkt. Der geheime Schlüssel nicht. Eine mit Namen gespeicherte Verbindung inklusive geheimem Schlüssel liegt in `~/.s3-viewer/connections.json`.
