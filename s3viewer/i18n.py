"""Deutsch und Englisch für die Oberfläche."""

from __future__ import annotations

_language = "de"

STRINGS: dict[str, dict[str, str]] = {
    "buckets": {"de": "Buckets", "en": "Buckets"},
    "files": {"de": "Dateien", "en": "Files"},
    "connection": {"de": "Verbindung", "en": "Connection"},
    "preview": {"de": "Dateivorschau", "en": "Preview"},
    "filter_buckets": {"de": "Bucket-Name filtern", "en": "Filter bucket name"},
    "filter_buckets_tip": {
        "de": "Zeigt nur Buckets, deren Name diesen Text enthält.",
        "en": "Shows only buckets whose name contains this text.",
    },
    "filter_files": {"de": "Dateiname filtern", "en": "Filter file name"},
    "filter_files_tip": {
        "de": "Zeigt nur Dateien und Ordner, deren Name diesen Text enthält.",
        "en": "Shows only files and folders whose name contains this text.",
    },
    "up": {"de": "Nach oben", "en": "Up"},
    "refresh": {"de": "Aktualisieren", "en": "Refresh"},
    "download": {"de": "Herunterladen", "en": "Download"},
    "download_tip": {
        "de": "Speichert die markierten Dateien. Mehrere mit Strg+Klick oder Umschalt+Klick auswählen. Ein markierter Ordner wird mit seinem Inhalt gespeichert.",
        "en": "Saves the selected files. Ctrl+click or Shift+click selects more than one. A selected folder is saved with its contents.",
    },
    "upload": {"de": "Hochladen", "en": "Upload"},
    "upload_tip": {
        "de": "Lädt Dateien in den geöffneten Bucket und Ordner hoch.",
        "en": "Uploads files into the open bucket and folder.",
    },
    "upload_folder": {"de": "Ordner hochladen", "en": "Upload folder"},
    "upload_folder_tip": {
        "de": "Lädt einen Ordner mit allen Unterordnern in den geöffneten Bucket und Ordner hoch.",
        "en": "Uploads a folder and its subfolders into the open bucket and folder.",
    },
    "new_folder": {"de": "Neuer Ordner", "en": "New folder"},
    "new_folder_tip": {
        "de": "Legt im geöffneten Bucket und Ordner einen neuen Ordner an.",
        "en": "Creates a new folder in the open bucket and folder.",
    },
    "new_folder_title": {"de": "Neuer Ordner", "en": "New folder"},
    "new_folder_label": {"de": "Name", "en": "Name"},
    "new_folder_invalid": {
        "de": "Der Ordnername darf nicht leer sein und keine Schrägstriche enthalten.",
        "en": "The folder name must not be empty or contain slashes.",
    },
    "new_folder_exists": {"de": "Der Ordner „{name}“ ist schon da.", "en": "The folder “{name}” already exists."},
    "new_folder_created": {"de": "Ordner „{name}“ angelegt", "en": "Created folder “{name}”"},
    "delete": {"de": "Löschen", "en": "Delete"},
    "delete_tip": {
        "de": "Löscht die markierten Dateien und Ordner. Ein Ordner wird mit seinem Inhalt gelöscht. Mehrere mit Strg+Klick oder Umschalt+Klick auswählen.",
        "en": "Deletes the selected files and folders. A folder is deleted with its contents. Ctrl+click or Shift+click selects more than one.",
    },
    "delete_title": {"de": "Löschen", "en": "Delete"},
    "delete_body": {
        "de": "Diese Einträge werden unwiderruflich gelöscht:\n{names}",
        "en": "These items will be permanently deleted:\n{names}",
    },
    "delete_folders": {
        "de": "\nOrdner werden zusammen mit allem Inhalt gelöscht.",
        "en": "\nFolders are deleted together with everything inside.",
    },
    "deleted_one": {"de": "1 Objekt gelöscht", "en": "1 object deleted"},
    "deleted_many": {"de": "{count} Objekte gelöscht", "en": "{count} objects deleted"},
    "transfer_delete": {"de": "Löschen", "en": "Delete"},
    "save_profile": {"de": "Speichern", "en": "Save"},
    "save_profile_tip": {
        "de": "Endpunkt und Zugangsdaten unter einem Namen in ~/.s3-viewer speichern",
        "en": "Save endpoint and credentials under a name in ~/.s3-viewer",
    },
    "delete_profile": {"de": "Entfernen", "en": "Remove"},
    "delete_profile_tip": {
        "de": "Die ausgewählte gespeicherte Verbindung löschen",
        "en": "Delete the selected saved connection",
    },
    "connect": {"de": "Verbinden", "en": "Connect"},
    "connecting": {"de": "Verbinde…", "en": "Connecting…"},
    "disconnect": {"de": "Trennen", "en": "Disconnect"},
    "show_secret": {"de": "Zeigen", "en": "Show"},
    "hide_secret": {"de": "Verbergen", "en": "Hide"},
    "fold_collapse": {"de": "Verbindung nach oben einklappen", "en": "Collapse the connection panel"},
    "fold_expand": {"de": "Verbindung ausklappen", "en": "Expand the connection panel"},
    "language": {"de": "Sprache: Deutsch. Klick schaltet auf Englisch.", "en": "Language: English. Click switches to German."},
    "dark_mode": {"de": "Dunkelmodus", "en": "Dark mode"},
    "light_mode": {"de": "Heller Modus", "en": "Light mode"},
    "endpoint": {"de": "Endpunkt", "en": "Endpoint"},
    "region": {"de": "Region", "en": "Region"},
    "access_key": {"de": "Zugriffsschlüssel", "en": "Access key"},
    "secret_key": {"de": "Geheimer Schlüssel", "en": "Secret key"},
    "bucket": {"de": "Bucket", "en": "Bucket"},
    "signature": {"de": "Signatur", "en": "Signature"},
    "path_style": {"de": "Pfad-Stil", "en": "Path style"},
    "verify_tls": {"de": "TLS-Zertifikat prüfen", "en": "Verify TLS certificate"},
    "endpoint_ph": {"de": "https://s3.cloud.example.com", "en": "https://s3.cloud.example.com"},
    "access_ph": {"de": "S3 Access Key", "en": "S3 access key"},
    "secret_ph": {"de": "S3 Secret Key", "en": "S3 secret key"},
    "bucket_ph": {"de": "optional", "en": "optional"},
    "endpoint_tip": {
        "de": "S3-API-Adresse der OpenStack-Umgebung, inklusive https://",
        "en": "S3 API address of the OpenStack environment, including https://",
    },
    "region_tip": {
        "de": "Region aus der Liste wählen oder eintragen. Der Name geht in die Signatur ein. Bei OpenStack oft RegionOne, sonst häufig us-east-1.",
        "en": "Choose a region from the list or type one. The name is part of the signature. On OpenStack often RegionOne, otherwise usually us-east-1.",
    },
    "secret_tip": {
        "de": "Wird nur im Speicher gehalten und nicht gespeichert.",
        "en": "Kept in memory only and not saved, unless you save a named connection.",
    },
    "bucket_tip": {
        "de": "Nur nötig, wenn die Rechte keine Bucket-Liste erlauben.",
        "en": "Only needed when the credentials cannot list buckets.",
    },
    "signature_tip": {
        "de": "Ältere OpenStack-Installationen brauchen manchmal SigV2.",
        "en": "Older OpenStack installations sometimes need SigV2.",
    },
    "path_tip": {
        "de": "Für OpenStack aktiv lassen. Der Bucket steht dann im URL-Pfad und nicht in der Domain.",
        "en": "Leave this on for OpenStack. The bucket is then in the URL path, not the domain.",
    },
    "verify_tip": {
        "de": "Ausschalten, wenn der Endpunkt ein selbstsigniertes Zertifikat verwendet.",
        "en": "Turn off when the endpoint uses a self-signed certificate.",
    },
    "hint": {
        "de": "Der Endpunkt ist die S3-API-Adresse, nicht die Keystone-URL. Zugangsdaten sind die S3-Schlüssel (EC2 Credentials), nicht das Login-Passwort. Der geheime Schlüssel wird nicht gespeichert.",
        "en": "The endpoint is the S3 API address, not the Keystone URL. Credentials are the S3 keys (EC2 credentials), not the login password. The secret key is not stored unless you save a named connection.",
    },
    "saved_connection": {"de": "Gespeicherte Verbindung", "en": "Saved connection"},
    "profile_tip": {
        "de": "Gespeicherte Verbindung aus ~/.s3-viewer laden",
        "en": "Load a saved connection from ~/.s3-viewer",
    },
    "col_name": {"de": "Name", "en": "Name"},
    "col_size": {"de": "Größe", "en": "Size"},
    "col_modified": {"de": "Geändert", "en": "Modified"},
    "files_placeholder": {
        "de": "Nach der Verbindung links einen Bucket wählen.\nOrdner öffnen sich per Klick. Textdateien, CSV, JSON, YAML und XML\nerscheinen in der Dateivorschau.",
        "en": "After connecting, choose a bucket on the left.\nFolders open with a click. Text files, CSV, JSON, YAML and XML\nappear in the preview.",
    },
    "preview_idle": {
        "de": "Wähle eine Textdatei, CSV, JSON, YAML oder XML aus.\nDer Inhalt erscheint hier.",
        "en": "Choose a text file, CSV, JSON, YAML or XML.\nThe contents appear here.",
    },
    "preview_named": {"de": "Dateivorschau — {name}", "en": "Preview — {name}"},
    "copy": {"de": "Text kopieren", "en": "Copy text"},
    "save_edits": {"de": "Änderungen speichern", "en": "Save changes"},
    "save_edits_tip": {
        "de": "Schreibt den geänderten Text zurück in den Bucket und ersetzt die Datei.",
        "en": "Writes the edited text back to the bucket and replaces the file.",
    },
    "download_file": {"de": "Diese Datei speichern", "en": "Save this file"},
    "download_file_tip": {
        "de": "Speichert die Datei, die in der Vorschau geöffnet ist.",
        "en": "Saves the file that is open in the preview.",
    },
    "download_cancelled": {"de": "Download abgebrochen", "en": "Download cancelled"},
    "download_cancelling": {"de": "Breche Download ab…", "en": "Cancelling download…"},
    "cancel_download": {"de": "Abbrechen", "en": "Cancel"},
    "transfer_download": {"de": "Download", "en": "Download"},
    "transfer_upload": {"de": "Upload", "en": "Upload"},
    "not_connected": {"de": "Nicht verbunden", "en": "Not connected"},
    "parent_folder": {"de": "Übergeordneter Ordner", "en": "Parent folder"},
    "open_folder": {"de": "Klick öffnet den Ordner.", "en": "Click opens the folder."},
    "loading_preview": {"de": "Lade Vorschau…", "en": "Loading preview…"},
    "loading_folder": {"de": "Lade Ordner…", "en": "Loading folder…"},
    "folder_empty": {"de": "Dieser Ordner ist leer.", "en": "This folder is empty."},
    "bucket_empty": {"de": "Dieser Bucket ist leer.", "en": "This bucket is empty."},
    "folder_failed": {"de": "Ordner konnte nicht geladen werden", "en": "Could not load the folder"},
    "counts": {"de": "{folders} Ordner, {files} Dateien", "en": "{folders} folders, {files} files"},
    "list_capped": {"de": ". Anzeige auf {limit} Einträge begrenzt.", "en": ". Showing at most {limit} entries."},
    "buckets_refreshed": {"de": "Buckets aktualisiert", "en": "Buckets refreshed"},
    "no_buckets": {"de": "Verbunden. Keine Buckets sichtbar.", "en": "Connected. No buckets visible."},
    "bucket_count": {"de": "Verbunden. {count} Buckets.", "en": "Connected. {count} buckets."},
    "no_bucket_list": {
        "de": "Die Verbindung steht, aber es wurden keine Buckets gelistet. Trag den Bucket-Namen ein und verbinde erneut, falls die Liste gesperrt ist.",
        "en": "Connected, but no buckets were listed. Enter the bucket name and connect again if listing is denied.",
    },
    "created": {"de": "Erstellt {when}", "en": "Created {when}"},
    "copied": {"de": "Vorschau in die Zwischenablage kopiert", "en": "Preview copied to the clipboard"},
    "writing": {"de": "Schreibe {name}…", "en": "Writing {name}…"},
    "written": {"de": "In den Bucket geschrieben: {key}", "en": "Written to the bucket: {key}"},
    "discard_title": {"de": "Ungespeicherte Änderungen", "en": "Unsaved changes"},
    "discard_body": {
        "de": "Der Text wurde geändert und noch nicht in den Bucket geschrieben. Änderungen verwerfen?",
        "en": "The text was changed and has not been written to the bucket. Discard the changes?",
    },
    "save_one": {"de": "Datei speichern", "en": "Save file"},
    "saving": {"de": "Speichere {name}…", "en": "Saving {name}…"},
    "saved_at": {"de": "Gespeichert: {path}", "en": "Saved: {path}"},
    "saving_files": {"de": "Speichere Dateien…", "en": "Saving files…"},
    "no_files_saved": {"de": "Keine Dateien gespeichert", "en": "No files saved"},
    "no_files_to_save": {"de": "Keine Dateien zum Speichern.", "en": "No files to save."},
    "choose_upload_files": {"de": "Dateien zum Hochladen auswählen", "en": "Choose files to upload"},
    "choose_upload_folder": {"de": "Ordner zum Hochladen auswählen", "en": "Choose a folder to upload"},
    "choose_download_dir": {"de": "Ordner zum Speichern wählen", "en": "Choose a folder to save into"},
    "uploading": {"de": "Lade {count} {noun} nach {destination} hoch…", "en": "Uploading {count} {noun} to {destination}…"},
    "noun_file": {"de": "Datei", "en": "file"},
    "noun_files": {"de": "Dateien", "en": "files"},
    "checking_files": {"de": "Prüfe vorhandene Dateien…", "en": "Checking existing files…"},
    "replace_title": {"de": "Dateien ersetzen", "en": "Replace files"},
    "replace_body": {
        "de": "Diese Dateien gibt es schon und sie werden ersetzt:\n{names}",
        "en": "These files already exist and will be replaced:\n{names}",
    },
    "replace_more": {"de": "\n… und {count} weitere", "en": "\n… and {count} more"},
    "save_connection_title": {"de": "Verbindung speichern", "en": "Save connection"},
    "save_connection_label": {"de": "Name", "en": "Name"},
    "replace_connection_title": {"de": "Verbindung ersetzen", "en": "Replace connection"},
    "replace_connection_body": {
        "de": "„{name}“ ist schon gespeichert. Überschreiben?",
        "en": "“{name}” is already saved. Overwrite it?",
    },
    "saved_connection_status": {"de": "Verbindung gespeichert in {path}", "en": "Connection saved in {path}"},
    "remove_connection_title": {"de": "Verbindung entfernen", "en": "Remove connection"},
    "remove_connection_body": {"de": "„{name}“ aus ~/.s3-viewer entfernen?", "en": "Remove “{name}” from ~/.s3-viewer?"},
    "removed_connection": {"de": "„{name}“ entfernt", "en": "Removed “{name}”"},
    "summary_empty": {"de": "Endpunkt und Zugangsdaten", "en": "Endpoint and credentials"},
    "fallback_profile": {"de": "Verbindung", "en": "Connection"},
    "err_endpoint_missing": {"de": "Der Endpunkt fehlt.", "en": "The endpoint is missing."},
    "err_endpoint_url": {"de": "Der Endpunkt muss eine http- oder https-URL sein.", "en": "The endpoint must be an http or https URL."},
    "err_keys_required": {
        "de": "Zugriffsschlüssel und geheimer Schlüssel werden benötigt.",
        "en": "Access key and secret key are required.",
    },
    "err_signature": {"de": "Unbekannte Signaturversion.", "en": "Unknown signature version."},
    "err_bucket_name": {
        "de": "Der Bucket-Name darf keine Leerzeichen oder Schrägstriche enthalten.",
        "en": "The bucket name must not contain spaces or slashes.",
    },
    "err_timeout": {"de": "Der Endpunkt hat nicht rechtzeitig geantwortet.", "en": "The endpoint did not respond in time."},
    "err_credentials": {"de": "Die Zugangsdaten sind unvollständig.", "en": "The credentials are incomplete."},
    "err_invalid_connection": {"de": "Die Verbindungsdaten sind unvollständig oder ungültig.", "en": "The connection details are incomplete or invalid."},
    "err_unreachable": {
        "de": "Der Endpunkt ist nicht erreichbar. Prüfe die URL, den Port und das Netzwerk.",
        "en": "The endpoint is unreachable. Check the URL, the port and the network.",
    },
    "err_tls": {
        "de": "TLS-Zertifikat konnte nicht geprüft werden. Bei einem selbstsignierten Zertifikat die Option „TLS-Zertifikat prüfen“ ausschalten.",
        "en": "The TLS certificate could not be verified. For a self-signed certificate, turn off “Verify TLS certificate”.",
    },
    "err_access_key": {"de": "Der Zugriffsschlüssel wurde abgelehnt.", "en": "The access key was rejected."},
    "err_sig_mismatch": {
        "de": "Die Signatur passt nicht. Prüfe den geheimen Schlüssel, die Region und die Signaturversion (s3v4 oder s3).",
        "en": "The signature does not match. Check the secret key, the region and the signature version (s3v4 or s3).",
    },
    "err_access_denied": {"de": "Kein Zugriff auf diese Ressource.", "en": "Access to this resource was denied."},
    "err_access_disabled": {"de": "Der Zugriff ist für diesen Account deaktiviert.", "en": "Access is disabled for this account."},
    "err_no_bucket": {"de": "Der Bucket wurde nicht gefunden.", "en": "The bucket was not found."},
    "err_no_key": {"de": "Die Datei wurde nicht gefunden.", "en": "The file was not found."},
    "err_bad_bucket": {"de": "Der Bucket-Name ist ungültig.", "en": "The bucket name is invalid."},
    "err_auth_header": {"de": "Die Anmeldung wurde abgelehnt. Oft stimmt die Region nicht.", "en": "Sign-in was rejected. The region is often wrong."},
    "err_redirect": {"de": "Der Endpunkt leitet woanders hin. Prüfe Region und Endpunkt-URL.", "en": "The endpoint redirects elsewhere. Check the region and endpoint URL."},
    "err_clock": {"de": "Die Uhrzeit dieses Rechners weicht zu stark ab.", "en": "This computer's clock is too far off."},
    "err_argument": {
        "de": "Der Endpunkt hat die Anfrage abgelehnt. Bei OpenStack Pfad-Stil und Signaturversion prüfen.",
        "en": "The endpoint rejected the request. For OpenStack, check path style and signature version.",
    },
    "err_not_implemented": {"de": "Der Endpunkt unterstützt diese Operation nicht ({code}).", "en": "The endpoint does not support this operation ({code})."},
    "err_forbidden": {"de": "Kein Zugriff ({code}).", "en": "Access denied ({code})."},
    "err_failed": {"de": "Die Anfrage ist fehlgeschlagen ({code}).", "en": "The request failed ({code})."},
    "err_with_code": {"de": "{message} ({code})", "en": "{message} ({code})"},
    "direct_bucket_notice": {
        "de": "Die Bucket-Liste ist mit diesen Rechten nicht abrufbar. Der eingetragene Bucket wurde direkt geöffnet.",
        "en": "The bucket list is not available with these permissions. The entered bucket was opened directly.",
    },
    "no_text_preview": {
        "de": "Für diesen Dateityp gibt es keine Textvorschau. Die Datei kann heruntergeladen werden.",
        "en": "There is no text preview for this file type. The file can be downloaded.",
    },
    "empty_file": {"de": "Die Datei ist leer.", "en": "The file is empty."},
    "preview_truncated": {"de": "Die Vorschau zeigt nur den Anfang der Datei (1 MB).", "en": "The preview shows only the start of the file (1 MB)."},
    "json_raw": {"de": "JSON konnte nicht formatiert werden und wird roh angezeigt.", "en": "JSON could not be formatted and is shown raw."},
    "xml_raw": {"de": "XML konnte nicht formatiert werden und wird roh angezeigt.", "en": "XML could not be formatted and is shown raw."},
    "table_too_wide": {
        "de": "Die Datei wird als Text gezeigt, weil sie zu viele Spalten für die Tabelle hat.",
        "en": "The file is shown as text because it has too many columns for the table.",
    },
    "table_limited": {"de": "Die Tabelle zeigt die ersten 2000 Zeilen.", "en": "The table shows the first 2000 rows."},
    "column": {"de": "Spalte {index}", "en": "Column {index}"},
    "tiff_rough": {
        "de": "Grobe Vorschau, längste Seite höchstens {edge} Pixel. Original {width}×{height}.",
        "en": "Coarse preview, longest side at most {edge} pixels. Original {width}×{height}.",
    },
    "tiff_page": {"de": " Seite 1 von {pages}.", "en": " Page 1 of {pages}."},
    "tiff_channels_one": {"de": "1 Kanal", "en": "1 channel"},
    "tiff_channels_many": {"de": "{count} Kanäle", "en": "{count} channels"},
    "tiff_first_three": {"de": ", Vorschau aus den ersten drei", "en": ", preview of the first three"},
    "tiff_both": {"de": ", Vorschau aus beiden", "en": ", preview of both"},
    "tiff_stack": {
        "de": "Grobe Vorschau, längste Seite höchstens {edge} Pixel. Original {width}×{height}, {channels}, {dtype}.",
        "en": "Coarse preview, longest side at most {edge} pixels. Original {width}×{height}, {channels}, {dtype}.",
    },
    "tiff_shape": {"de": "TIFF-Form {shape} wird nicht als Bild angezeigt.", "en": "TIFF shape {shape} cannot be shown as an image."},
    "tiff_failed": {
        "de": "Die TIFF-Vorschau konnte nicht erzeugt werden. Die Datei kann heruntergeladen werden.",
        "en": "The TIFF preview could not be created. The file can be downloaded.",
    },
    "tiff_too_big_known": {
        "de": "Die TIFF-Datei ist etwa {amount} MB groß. Für eine schnelle Vorschau werden höchstens {limit} MB geladen. Die Datei kann heruntergeladen werden.",
        "en": "The TIFF file is about {amount} MB. A quick preview loads at most {limit} MB. The file can be downloaded.",
    },
    "tiff_too_big": {
        "de": "Die TIFF-Datei ist größer als {limit} MB. Für eine schnelle Vorschau wird sie nicht vollständig geladen. Die Datei kann heruntergeladen werden.",
        "en": "The TIFF file is larger than {limit} MB. A quick preview does not load all of it. The file can be downloaded.",
    },
    "no_tiff": {"de": "Keine TIFF-Vorschau.", "en": "No TIFF preview."},
    "no_preview": {"de": "Keine Vorschau.", "en": "No preview."},
    "upload_bad_path": {"de": "„{path}“ kann so nicht hochgeladen werden.", "en": "“{path}” cannot be uploaded like this."},
    "upload_duplicate": {"de": "Mehrere ausgewählte Dateien heißen „{name}“.", "en": "Several selected files are named “{name}”."},
    "upload_none": {"de": "Keine Dateien ausgewählt.", "en": "No files selected."},
    "not_a_folder": {"de": "Das ist kein Ordner.", "en": "That is not a folder."},
    "bad_folder": {"de": "Dieser Ordner kann so nicht hochgeladen werden.", "en": "This folder cannot be uploaded like this."},
    "folder_empty_local": {"de": "Der Ordner enthält keine Dateien.", "en": "The folder contains no files."},
    "uploaded_one": {"de": "1 Datei hochgeladen nach {destination}", "en": "1 file uploaded to {destination}"},
    "uploaded_many": {"de": "{count} Dateien hochgeladen nach {destination}", "en": "{count} files uploaded to {destination}"},
    "saved_one": {"de": "1 Datei gespeichert in {directory}", "en": "1 file saved in {directory}"},
    "saved_many": {"de": "{count} Dateien gespeichert in {directory}", "en": "{count} files saved in {directory}"},
    "saved_capped": {"de": ". Es wurden höchstens {limit} Dateien berücksichtigt.", "en": ". At most {limit} files were included."},
    "bad_filename": {"de": "Ungültiger Dateiname: {name}", "en": "Invalid file name: {name}"},
    "empty_filename": {"de": "Leerer Dateiname.", "en": "Empty file name."},
    "profile_missing": {"de": "Die Verbindung „{name}“ ist nicht gespeichert.", "en": "The connection “{name}” is not saved."},
    "profile_incomplete": {"de": "Die Verbindung „{name}“ ist unvollständig.", "en": "The connection “{name}” is incomplete."},
    "profile_needs_name": {"de": "Die Verbindung braucht einen Namen.", "en": "The connection needs a name."},
    "profile_bad_name": {
        "de": "Der Name darf keine Schrägstriche enthalten und höchstens 80 Zeichen lang sein.",
        "en": "The name must not contain slashes and can be at most 80 characters.",
    },
    "profile_unreadable": {
        "de": "Die gespeicherten Verbindungen konnten nicht gelesen werden.",
        "en": "The saved connections could not be read.",
    },
}


def language() -> str:
    return _language


def set_language(code: str) -> None:
    global _language
    _language = "en" if code == "en" else "de"


def tr(message_id: str, **values: object) -> str:
    entry = STRINGS.get(message_id) or {}
    text = entry.get(_language) or entry.get("de") or message_id
    if values:
        return text.format(**values)
    return text
