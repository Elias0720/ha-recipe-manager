# GitHub-Upload

## Einmalige Vorbereitung

1. Erstelle die Pakete neu:

   ```powershell
   .\scripts\build-release.ps1
   ```

2. Fuehre die lokalen Pruefungen aus:

   ```powershell
   python -m unittest discover -s tests -v
   node --check custom_components/ha_recipe_manager/frontend/ha-recipe-manager-panel.js
   node --check custom_components/ha_recipe_manager/frontend/recipe-guide-card.js
   ```

3. Erstelle auf GitHub ein oeffentliches Repository mit dem Namen `ha-recipe-manager`. Fuege dort keine automatisch erzeugte README, `.gitignore` oder Lizenz hinzu, da diese Dateien bereits lokal vorhanden sind.

## Erster Push

```powershell
git add .
git commit -m "Initial release of HA Recipe Manager"
git remote add origin https://github.com/Elias0720/ha-recipe-manager.git
git push -u origin main
```

## Repository in Home Assistant hinzufuegen

1. Oeffne **Einstellungen > Apps > App installieren**.
2. Oeffne oben rechts das Drei-Punkte-Menue und waehle **Repositories**.
3. Fuege `https://github.com/Elias0720/ha-recipe-manager` hinzu.
4. Installiere **Get HA Recipe Manager**.
5. Starte die App einmal und kontrolliere ihr Protokoll.
6. Starte Home Assistant neu.
7. Fuege **HA Recipe Manager** unter **Einstellungen > Geraete & Dienste** hinzu.
