# HA Recipe Manager

HA Recipe Manager ist eine Home-Assistant-Custom-Integration für Kochrezepte, Zutatenchecks und die Home-Assistant-Einkaufsliste.

## Funktionen

- Rezepte mit Zutaten, Portionen, Kategorien, Quelle und Anleitung speichern
- Rezept vor dem Einkauf auswählen und vorhandene Zutaten abhaken
- Nicht abgehakte Zutaten automatisch per `shopping_list.add_item` auf die Home-Assistant-Einkaufsliste setzen
- Eigenes Sidebar-Panel unter `/recipes`
- Dashboard-Karte `custom:ha-recipe-guide-card` für Küchen-Displays
- Automatische Aktualisierung bereits geöffneter Panels und Dashboard-Karten
- Lokale Speicherung in Home Assistant `.storage`

## Installation als Home-Assistant-App (empfohlen)

Dieser Weg benoetigt kein HACS. Das GitHub-Repository enthaelt die einmalig ausgefuehrte App `Get HA Recipe Manager`, die die eigentliche Integration installiert oder aktualisiert. Apps werden von Home Assistant OS und dem Supervisor unterstuetzt.

1. Dieses Projekt in ein öffentliches GitHub-Repository hochladen.
2. In Home Assistant `Einstellungen > Apps > App installieren` öffnen.
3. Über das Menü oben rechts `Repositories` öffnen.
4. Die vollständige GitHub-Repository-URL eintragen und hinzufügen.
5. `Get HA Recipe Manager` auswählen und installieren.
6. Die App einmal starten und das Protokoll auf die Erfolgsmeldung prüfen.
7. Home Assistant neu starten.
8. Unter `Einstellungen > Geräte & Dienste > Integration hinzufügen` nach `HA Recipe Manager` suchen und die Integration hinzufügen.
9. Sicherstellen, dass die Home-Assistant-Integration `Einkaufsliste` ebenfalls eingerichtet ist.

Die Installer-App kopiert ein mit SHA-256 geprüftes Paket nach `/config/custom_components/ha_recipe_manager` und beendet sich anschließend. Sie muss nicht dauerhaft laufen. Neue Versionen erscheinen als App-Update; nach dem Update wird die App erneut einmal gestartet.

Die genaue Upload- und Installationsreihenfolge steht in [UPLOAD_CHECKLIST.md](UPLOAD_CHECKLIST.md).

## Alternative Installation über ein HACS Custom Repository

Dasselbe Repository bleibt zusätzlich als HACS Custom Repository verwendbar. Eine Aufnahme in den öffentlichen HACS-Katalog ist nicht erforderlich.

1. In Home Assistant `HACS > Integrationen` öffnen.
2. Über das Menü oben rechts `Benutzerdefinierte Repositories` öffnen.
3. Die vollständige GitHub-Repository-URL eintragen.
4. Als Kategorie `Integration` auswählen und das Repository hinzufügen.
5. `HA Recipe Manager` herunterladen und Home Assistant neu starten.
6. Die Integration unter `Einstellungen > Geräte & Dienste` hinzufügen.

Vor dem ersten Hochladen müssen in `custom_components/ha_recipe_manager/manifest.json` die Platzhalter für `codeowners`, `documentation` und `issue_tracker` durch den tatsächlichen GitHub-Benutzernamen und die Repository-URL ersetzt werden. Die mitgelieferte GitHub Action prüft Installer, HACS und hassfest automatisch.

## Manuelle Installation ohne HACS

Entpacke `dist/ha_recipe_manager.zip` in dein Home-Assistant-Konfigurationsverzeichnis oder kopiere den Ordner `custom_components/ha_recipe_manager` dorthin:

```text
<home-assistant-config>/custom_components/ha_recipe_manager
```

Danach Home Assistant neu starten und die Integration über die UI hinzufügen.

## Bedienung

Nach der Einrichtung erscheint in der Sidebar der Eintrag `Rezepte`.

1. Rezept anlegen.
2. Zutaten mit Menge, Einheit, Name und optionaler Notiz eintragen.
3. Rezept vor dem Einkauf auswählen.
4. Zutaten abhaken, die bereits zu Hause vorhanden sind.
5. `Fehlende auf Einkaufsliste` klicken.

Die Integration fügt dann alle nicht abgehakten Zutaten zur Home-Assistant-Einkaufsliste hinzu.

## Dashboard-Karte

Die Integration liefert zusätzlich eine Lovelace-Karte für die Rezeptanleitung aus.

Füge diese Ressource unter `Einstellungen > Dashboards > Ressourcen` hinzu:

```yaml
url: /ha_recipe_manager_static/recipe-guide-card.js
type: module
```

Beispielkarte mit Rezeptauswahl:

```yaml
type: custom:ha-recipe-guide-card
title: Küchenrezept
show_ingredients: true
```

Beispielkarte für ein festes Rezept:

```yaml
type: custom:ha-recipe-guide-card
recipe_id: REZEPT_ID_HIER_EINTRAGEN
show_ingredients: true
```

Die Rezept-ID lässt sich im Rezept-Panel über die Schaltfläche mit dem ID-Symbol kopieren. Ohne `recipe_id` zeigt die Karte eine Rezeptauswahl an.

## Automationen und Service

Die Integration registriert die Aktion:

```yaml
action: ha_recipe_manager.add_missing_to_shopping_list
data:
  recipe_id: REZEPT_ID
  checked_ingredient_ids:
    - ZUTATEN_ID
```

Das Sidebar-Panel nutzt denselben Mechanismus automatisch.

## Entwicklung

Lokale Prüfungen:

```powershell
.\scripts\build-release.ps1
python -m unittest discover -s tests -v
python -m py_compile custom_components/ha_recipe_manager/models.py custom_components/ha_recipe_manager/store.py custom_components/ha_recipe_manager/shopping.py custom_components/ha_recipe_manager/websocket.py custom_components/ha_recipe_manager/__init__.py custom_components/ha_recipe_manager/config_flow.py
node --check custom_components/ha_recipe_manager/frontend/ha-recipe-manager-panel.js
node --check custom_components/ha_recipe_manager/frontend/recipe-guide-card.js
```
