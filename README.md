# S3 Viewer

Desktop-Programm für Ubuntu, um Buckets einer OpenStack- oder anderen S3-Umgebung zu durchsuchen.

## Start

```bash
./start.sh
```

Beim ersten Start legt das Skript eine virtuelle Umgebung an und installiert die Abhängigkeiten.

## Verbindung

- **Endpunkt:** S3-API-Adresse, zum Beispiel `https://s3.cloud.example.com`
- **Zugriffsschlüssel und geheimer Schlüssel:** S3- bzw. EC2-Credentials aus OpenStack, nicht das Login-Passwort
- **Region:** bei OpenStack oft der Region-Name, zum Beispiel `RegionOne`
- **Pfad-Stil:** für OpenStack eingeschaltet lassen
- **TLS-Zertifikat prüfen:** bei einem selbstsignierten Zertifikat ausschalten
- **Signatur:** wenn die Anmeldung an der Signatur scheitert, `s3 (SigV2)` versuchen
- **Bucket:** nur ausfüllen, wenn die Rechte keine Bucket-Liste erlauben

Endpunkt, Zugriffsschlüssel und die Optionen werden lokal in `~/.config/s3viewer/S3Viewer.conf` gemerkt. Der geheime Schlüssel nicht.

Ein Klick öffnet einen Bucket oder Ordner. Ein Klick auf eine Text-, CSV-, JSON- oder XML-Datei zeigt den Inhalt in der Dateivorschau. Die Vorschau lässt sich aus dem Fenster herausziehen.
