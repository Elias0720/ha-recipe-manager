# HA Recipe Manager

HA Recipe Manager ist eine Home-Assistant-Custom-Integration für Kochrezepte, Zutatenchecks und die Home-Assistant-Einkaufsliste.

## Funktionen

- Rezepte mit Zutaten, Portionen, Kategorien, Quelle und Anleitung speichern
- Rezept vor dem Einkauf auswählen und vorhandene Zutaten abhaken
- Nicht abgehakte Zutaten automatisch per `shopping_list.add_item` auf die Home-Assistant-Einkaufsliste setzen
- Gleiche offene Zutaten zusammenführen: `200g Karotten` + `300 g Karotten` = `500 g Karotten`, `Zwiebel` + `Zwiebel` = `2x Zwiebel`
- Lesbare Auswahl und Eingabefelder im hellen und dunklen Home-Assistant-Theme
- Ungefähren Zeitaufwand in Minuten pro Rezept speichern und anzeigen
- Gesamtkalorien pro Rezept mit einem vorhandenen KI-Konversationsagenten schätzen und lokal speichern
- Eigener Ranking-Tab: Rezepte unabhängig nach Geschmack und Kochaufwand sortieren
- Diagramm aus beiden Ranglisten mit linearer Trendlinie
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
Bereits vorhandene offene Einträge werden dabei aktualisiert. Mengen mit kompatiblen
Einheiten (z. B. g/kg, dag/g und ml/l) werden addiert; ohne Mengenangabe zählt jede
Zugabe als ein Stück. Groß-/Kleinschreibung, zusätzliche Leerzeichen und übliche
Namensvarianten wie Zwiebel/Zwiebeln werden erkannt. Verschiedene Zutaten,
abweichende Notizen, unvereinbare Einheiten und unklare Mengen wie „nach Bedarf“
bleiben getrennt. Erledigte Einträge werden nicht mitgezählt.

Beim Anlegen und Bearbeiten kannst du optional den **Zeitaufwand (ca. Minuten)**
eintragen. Er erscheint am Rezept, in der Rezeptliste und auf der Dashboard-Karte.

Im Tab **Ranking** enthält jede der beiden Listen alle Rezepte. Bei **Geschmack**
steht das leckerste Rezept oben, bei **Kochaufwand** das Rezept mit dem geringsten
Aufwand. Ziehe den Griff eines Rezepts nach oben oder unten; alternativ helfen
die Auf-/Ab-Buttons oder die Pfeiltasten am fokussierten Griff. Die Reihenfolge
wird automatisch in Home Assistant gespeichert. Neue Rezepte erscheinen am Ende
beider Listen; beim Löschen eines Rezepts verschwindet es auch aus den Rankings.

Das Diagramm verwendet die beiden persönlichen Rangplätze. Wenig Aufwand liegt
links, guter Geschmack oben. Die Zeitangabe bleibt unabhängig vom Aufwandsranking.
Ab zwei Rezepten erscheint eine lineare Trendlinie. Ein Klick auf einen Rezeptpunkt
öffnet das Rezept; unter **Alle Rezeptwerte** stehen die Werte als Tabelle.

## Gesamtkalorien mit Gemini

Die Schaltfläche **Gesamtkalorien schätzen** wertet alle Zutaten des gespeicherten
Rezepts aus. Die Summe wird **nicht durch die Portionen geteilt**. Einkaufs-Häkchen
haben keinen Einfluss. Ein Aufruf erfolgt nur beim Klicken; das Öffnen eines
Rezepts löst keine KI-Abfrage aus.

Voraussetzung ist ein vorhandener Home-Assistant-Konversationsagent. Der
Standard ist `conversation.google_ai_conversation_2`. Unter
`Einstellungen > Geräte & Dienste > HA Recipe Manager > Konfigurieren` lässt
sich ein anderer Konversationsagent auswählen. Ein zusätzlicher API-Schlüssel
in HA Recipe Manager ist nicht nötig.

Für Gemini mit kostenloser Google-Suche (Stand 2. Oktober 2026):

1. In Google AI Studio ein Projekt im kostenlosen Tarif ohne aktive Abrechnung verwenden.
2. Beim Google-Konversationsagenten die empfohlenen Modelleinstellungen ausschalten und `gemini-2.5-flash` wählen.
3. HA-Steuerung ausschalten und das Google-Suchwerkzeug aktivieren.
4. Bei leeren oder abgeschnittenen Antworten die maximalen Antworttokens erhöhen, z. B. auf 4000.

Die Tarife sind modellabhängig: `gemini-3.1-flash-lite` bietet kostenlose
Textabfragen, aber keine Google-Suche im kostenlosen API-Tarif. Aktuelle
Kontingente stehen in der [Google-Preisliste](https://ai.google.dev/gemini-api/docs/pricing).
Die Zutaten, Mengen, Notizen und die Anleitung werden an den gewählten Anbieter
übermittelt. Im kostenlosen Google-Tarif können Inhalte zur Produktverbesserung
verwendet werden.

Gesamtkalorien, Annahmen und die von der KI angegebenen Quellen werden lokal
gespeichert und sind anschließend ohne Internet lesbar. Die Werte bleiben
ungefähre Schätzungen, besonders bei fehlenden Mengen, Stückgrößen oder
unklarem Garzustand. Quellenlinks stammen aus der KI-Antwort.

Im Rezept-Editor kann die Summe unter **Gesamtkalorien (ca. kcal)** korrigiert oder
durch Leeren des Feldes entfernt werden. Nach Änderungen an Zutaten, Mengen,
Notizen oder Anleitung wird ein bestehender Wert als veraltet markiert. Ein
neuer KI-Aufruf oder eine manuelle Bestätigung aktualisiert ihn. Geänderte
Portionen, Namen, Kategorien und Zeiten machen die Gesamtsumme nicht ungültig.
Fehlgeschlagene Abfragen behalten den bisherigen Wert. Während einer Abfrage
geänderte Zutaten oder manuelle Kalorienwerte werden nicht überschrieben.

## Dashboard-Karte

Die Integration liefert zusätzlich eine Lovelace-Karte für die Rezeptanleitung aus.

Füge diese Ressource unter `Einstellungen > Dashboards > Ressourcen` hinzu:

```yaml
url: /ha_recipe_manager_static/recipe-guide-card.js?v=0.3.0
type: module
```

Bei einer bereits eingebundenen Dashboard-Karte die Ressourcen-URL auf diese
Version aktualisieren, damit auch die Gesamtkalorien geladen werden.

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
python -m compileall -q custom_components/ha_recipe_manager
node --check custom_components/ha_recipe_manager/frontend/ha-recipe-manager-panel.js
node --check custom_components/ha_recipe_manager/frontend/recipe-guide-card.js
```

Die Browser-Regressionsprüfung benötigt das Node-Paket `playwright` und Chromium:

```powershell
node tests/test_frontend.cjs
node tests/test_rankings.cjs
```

Für ein vorhandenes Chrome oder Edge kann `HA_RECIPE_BROWSER_PATH` auf den Pfad
der Browser-Datei gesetzt werden. Die Prüfung simuliert Home-Assistant- und
Rezept-Aktualisierungen während der Eingabe sowie fehlgeschlagenes Speichern
und kontrolliert die Hover-Farbe im Browser.
