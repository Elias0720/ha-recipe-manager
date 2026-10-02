# Changelog

## 0.3.0

- Gesamtkalorien pro Rezept per vorhandenem KI-Konversationsagenten schaetzen
- Standardagent: conversation.google_ai_conversation_2; in den Integrationseinstellungen aenderbar
- Kaloriensumme, Annahmen und Quellen lokal speichern; Gesamtkalorien manuell korrigieren oder entfernen
- Veraltete Werte nach Zutaten-, Mengen- oder Anleitungsaenderungen kennzeichnen
- Ergebnisse laufender Abfragen ueberschreiben keine neueren Zutaten oder manuellen Kalorienwerte
- Kaloriensumme auch auf der Dashboard-Karte anzeigen

## 0.2.0

- Ungefaehren Zeitaufwand in Minuten pro Rezept eintragen und anzeigen
- Eigener Ranking-Tab mit getrennten Listen fuer Geschmack und Kochaufwand
- Reihenfolgen per Ziehgriff, Pfeiltasten oder Auf-/Ab-Buttons aendern
- Rankings werden in Home Assistant gespeichert und mit anderen Panels synchronisiert
- Diagramm aus beiden Ranglisten mit Rezeptpunkten und linearer Trendlinie
- Bestehende Rezepte bleiben erhalten; neue Rezepte werden an beide Ranglisten angehaengt

## 0.1.4

- Lesbare Auswahl-, Hover- und Eingabefarben im Dark Mode
- Wochentagsfeld entfernt
- Gleiche Zutaten werden auf der Einkaufsliste zusammengefasst und Mengen addiert
- Zutaten ohne Mengenangabe werden als 2x Zwiebel oder 2x Sellerie gezaehlt
- Umrechnung kompatibler Einheiten wie g/kg, dag/g und ml/l
- Bereits erledigte Einkaeufe bleiben unveraendert; gleichzeitige Rezeptzugaben werden nacheinander verarbeitet

## 0.1.3

- Eingabefelder behalten Text und Fokus bei Home-Assistant- und Rezept-Aktualisierungen
- Rezepteingaben bleiben nach einem fehlgeschlagenen Speichern erhalten
- Primaere Buttons werden beim Hover dunkelgruen und behalten lesbaren Text
- Neue Panel-Datei wird durch eine versionierte URL ohne alten Browser-Cache geladen

## 0.1.2

- Hassfest-Abhaengigkeiten und Config-Entry-Schema korrigiert
- HACS-Brand-Icon in die Integration aufgenommen

## 0.1.1

- BusyBox-kompatible SHA-256-Pruefung im Installer

## 0.1.0

- Erste Version der Installer-App
- Installation und Aktualisierung der Integration aus einem geprueften lokalen Paket
- Wiederherstellung der vorherigen Version bei einem fehlgeschlagenen Austausch
