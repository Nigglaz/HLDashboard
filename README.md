# Harborline - Flask-Prototyp

Lokale Liegeplatzplanung fuer sieben Schiffe, sieben Haefen und die Dienste NE2 und NE4.

## Start

Aus diesem Ordner:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Browser: http://127.0.0.1:5055. Ein anderer Port ist ueber die Umgebungsvariable `PORT` einstellbar.

## Planung

- Oben einen Dienst auswaehlen; links erscheinen ausschliesslich dessen Schiffe. Das ausgewaehlte Schiff ist rot, andere Schiffe bleiben zum Vergleich im Kalender sichtbar.
- NE2-Schiffe haben unterschiedliche Blautoene, NE4-Schiffe Gruenblautoene. Angezeigt werden nur die Haefen der ausgewaehlten Hafenfolge, in deren Reihenfolge.
- Einen Aufenthalt ziehen, um ihn stundenweise zu verschieben. Vertikales Ziehen wechselt den Liegeplatz innerhalb desselben Hafens.
- Den rechten Balkenrand ziehen, um die Abfahrt zu aendern.
- Mit "Folgeaufenthalte mitnehmen" werden anschliessende Aufenthalte um denselben Betrag verschoben.
- Einen Balken anklicken: verschiebbares Detailfenster mit Zeiten, Liegeplatz und Transitdauer.
- Die eingetragene Transitdauer ist ein Planungswert. "Ankunft aus Transit neu berechnen" setzt die Ankunft entsprechend und erhaelt die Liegedauer. Die Plausibilitaetspruefung verwendet unabhaengig davon Entfernung / Maximalgeschwindigkeit, nicht den eingetragenen Planungswert.
- Transitzeiten lassen sich auch direkt zwischen den Hafenbloecken bearbeiten. Der Haken berechnet die naechste Ankunft neu und erhaelt die Liegedauer; das Mitnehmen weiterer Aufenthalte folgt dem Schalter oben.
- Hafenueberschriften klappen die Liegeplaetze ein und aus. In der Transitzeile steht vor dem Transit ein grauer Kasten mit Schiffsname und Liegezeit. Er bleibt auch bei eingeklappten Haefen sichtbar; es gibt keine gesonderten Liegezeitzeilen pro Hafen. Unter "Liegeplaetze & Ansicht" lassen sich alle Haefen einklappen oder einzelne Liegeplaetze ausblenden. Eine benannte Ansicht speichert diese Einstellungen, Schiff, Reisedatum, Anfang, Ende, Zoom und Scrollposition auf dem Server. Die zuletzt gewaehlte Ansicht wird im selben Browser wieder geladen.
- Mausrad: horizontal durch die Zeit scrollen. Strg/Mac-Command + Mausrad: am Mauszeiger zoomen. Umschalt + Mausrad: vertikal scrollen. Der Zoomregler funktioniert ebenfalls.
- "Reise ab" waehlt eine Reise anhand ihres nominellen Startdatums; zwischen zwei Starts wird die vorherige Runde gewaehlt. Vor dem ersten Start einer neuen Proforma wird deren erste gueltige Runde angeboten. Ohne tatsaechlichen Reiseabschnitt wird die datumsabhaengig gueltige Proforma verwendet. Der Standardzyklus ist 14 Wochen: Busan startet erneut am 24.04.2027. Der Kalender umfasst standardmaessig sechs Kalendermonate und zeigt darin auch die weiteren Runden. "Ab" und "Bis" lassen sich unabhaengig anpassen; "Bis" ist inklusive. Der Zoom reicht bis 1200 Pixel pro Tag; ab 240 Pixeln erscheinen Uhrzeiten im 3-Stunden-Abstand.
- Gelb: ungespeicherter Entwurf. Gestrichelter Umriss: bisherige Belegung, stets mit Schiffsname im Balken.
- "Proforma vergleichen" blendet fuer alle Schiffe des ausgewaehlten Dienstes die Proforma-Positionen als gestrichelte Rahmen ein. Rahmen und gestrichelte Verbindungslinien tragen die jeweilige Schiffsfarbe; das ausgewaehlte Schiff ist rot. Ueber der Linie steht die Abweichung der Ankunft gegenueber der fuer das Reisedatum gueltigen Proforma, z. B. "+24 h Verzoegerung", "6 h frueher" oder "0 h Abweichung". Bestehende Reisen bleiben unveraendert. Der Vergleichsschalter wird mit benannten Ansichten gespeichert.
- Es gibt nur den aktuellen Plan und offene Aenderungen (Pending). "Plan fuer dieses Schiff uebernehmen" speichert ausschliesslich das ausgewaehlte Schiff. Andere offene Schiffsentwuerfe bleiben erhalten. Die Einzeluebernahme wird gegen die gespeicherten Plaene der anderen Schiffe geprueft, nicht gegen deren ungespeicherte Aenderungen. Dadurch kann eine abhaengige Verschiebung erfordern, zuerst das andere Schiff zu uebernehmen.
- Rueckgaengig/Wiederholen, Verwerfen und JSON-Export stehen zur Verfuegung. "Verwerfen" betrifft nur das ausgewaehlte Schiff. Lokale Entwuerfe bleiben im selben Browser nach Neuladen erhalten.

## Daten

`data/ports.json`, `data/services.json` und `data/views.json` enthalten Haefen, Dienste und Ansichten. `data/schedules.json` verweist auf genau eine aktuelle Datei je Schiff, beispielsweise `data/ships/busan.json`. Beim Uebernehmen wird nur die aktuelle Datei dieses Schiffs atomar ersetzt; es entstehen keine neuen Planversionsdateien. Bereits vorhandene Sicherungen aus dem frueheren Prototyp werden nicht geloescht, aber auch nicht mehr als aktive Plaene verwendet. Die Anwendung ist fuer eine einzelne lokale Serverinstanz ausgelegt.

Die interne `revision` ist ausschliesslich ein technischer Schutz gegen gleichzeitiges Ueberschreiben. Sie ist kein auswaehlbarer Planstand und erscheint nicht in der Oberflaeche. Der fruehere Text "Planstand 06" bedeutete lediglich, dass der technische Speicherzaehler bei sechs stand. Pending wird getrennt im lokalen Browser gehalten.

Eine Schiffsdatei enthaelt `id`, `name`, `serviceId`, `proformas` und `voyages`. Jede Proforma hat `id`, `name`, `validFrom`, `repeatWeeks` und `stops`. Das Startdatum einer Reise entscheidet, welche Proforma-Version verwendet wird; die jeweils neueste Version mit passendem Geltungsbeginn gewinnt. Die erste Ankunft der Vorlage ist der Anker ihres Zyklus. Unterschiedliche Jahres- oder Saisonproformas koennen dadurch unterschiedliche Anker und Intervalle haben.

`voyages` enthaelt nur explizit gespeicherte tatsaechliche Reisen, indiziert nach dem nominellen Startdatum. Jede Reise speichert die vollstaendige Hafenfolge und ihre `proformaId`. Fehlt ein Eintrag, berechnet die Anwendung die Reise aus der Vorlage. Erst eine Aenderung in der Liegeplatzplanung legt einen Reiseabschnitt an. Proforma-Aenderungen wirken auf den Fallback, aber nicht auf vorhandene tatsaechliche Reisen. "Auf Proforma zuruecksetzen" entfernt einen tatsaechlichen Reiseabschnitt als Entwurf; erst "Plan fuer dieses Schiff uebernehmen" speichert das Entfernen.

Beim Wechsel vom alten Format wird `data/schedules.legacy.json` als Sicherung erzeugt. Bereits bearbeitete Reisen und alte 15-Wochen-Ausnahmen werden als explizite Reiseabschnitte erhalten; sie koennen daher vom neuen 14-Wochen-Fallback abweichen.

## Proformas

Der Reiter "Proformas" ist ausschliesslich eine schreibgeschuetzte Ansicht. Dienst, Schiff und vorhandene Vorlage lassen sich auswaehlen; Name, Geltungsbeginn, Zyklus, Liegeplaetze und Transitzeiten koennen nicht bearbeitet werden. Auch die API weist Proforma-Aenderungen ab. Der spaetere Excel-Import ist noch nicht implementiert. Zwischen der Planungs- und Proforma-Ansicht kann gewechselt werden, ohne offene Schiffsentwuerfe zu verwerfen.

## Nautische Transitpruefung

Entfernungen stehen direkt an den Haefen in `data/ports.json`, Geschwindigkeiten in der jeweiligen Schiffsdatei, beispielsweise `data/ships/busan.json`. Die separate Navigationsdatei wurde bei der Migration entfernt. Anfangswerte: alle Hafenpaare **100 sm**, Schiffe standardmaessig **20 kn**. Die Mindestfahrzeit ist somit zunaechst **5 Stunden**. Die Entfernungen sind Platzhalter, keine echten nautischen Strecken.

Beim Hafeneintrag mit `id: "rotterdam"` aendert `distancesNm.hamburg` die Entfernung nach Hamburg. Jedes Paar steht nur einmal und gilt in beiden Richtungen. Nicht konfigurierte Paare verwenden 100 sm. An jeder Schiffsdatei steht `maxSpeedKnots`, beispielsweise `20` fuer die Busan Express. Eine bereits konfigurierte individuelle Geschwindigkeit wird aus den alten Navigationsdaten uebernommen; andernfalls gilt 20 kn.

Die verfuegbare Zeit wird aus Abfahrt des vorherigen Hafens und Ankunft im naechsten Hafen berechnet. Hinweise enthalten die verfuegbaren Stunden, die erforderlichen Stunden und die Rechnung in sm / kn. `transitMinutes` bleibt ein Planungswert. Neue bzw. verschaerfte Unterschreitungen werden beim Uebernehmen abgewiesen; bekannte Unterschreitungen blockieren keine unabhaengigen Aenderungen. Vorhandene Fahrplanzeiten werden bei einer Aenderung der Entfernung oder Geschwindigkeit nicht automatisch verschoben.

Alle Zeitangaben sind gemeinsame **UTC-Planzeit**, ohne saisonale oder lokale Umrechnung. Die gelieferten Uhrzeiten werden unveraendert als Planzeit verwendet. Busan Express startet am 16.01.2027; Berlin, Gdansk, Rotterdam, Hamburg und Genova Express folgen jeweils sieben Tage spaeter.

Mathilde Maersks Proforma verwendet die korrigierten NE4-Zeiten: London 16.01. 14:00 bis 18.01. 04:00; Bremerhaven 20.01. 06:00 bis 21.01. 22:00; Hamburg 22.01. 15:00 bis 24.01. 18:00; Rotterdam **26.01. 11:00 bis 27.01. 12:00**; Algeciras 01.02. 20:00 bis 02.02. 14:00. Bereits individuell bearbeitete tatsaechliche Fahrplaene bleiben bei der Migration erhalten.

Der Server prueft Transitzeiten, Liegeplaetze, neue Doppelbelegungen und sich ueberlappende Reisen. Die Kollisionspruefung generiert alle Runden vom fruehesten gespeicherten Datum minus zwei Jahren bis zum spaetesten Datum plus zwei Jahren. Sie ist keine Zusage, dass sich beliebige Dienstzyklen in unendlicher Zukunft nie ueberschneiden.

Die eingetragenen Transitzeiten der Beispieldaten sind aus den gelieferten Abfahrts- und Ankunftszeiten abgeleitet. Sie bleiben als Planungswerte erhalten und werden nicht automatisch aus einer Verschiebung zurueckgerechnet. Die nautische Mindestfahrzeit wird dagegen stets aus der separaten Entfernungs- und Geschwindigkeitskonfiguration berechnet.

## Dynamisches Laden

Der Server liest Hafen-, Dienst- und Schiffsdateien bei jeder Anfrage neu ein. Der Browser fragt alle fuenf Sekunden und bei Rueckkehr zum Fenster nach Aenderungen. Ohne offenen Entwurf oder aktive Eingabe wird die Ansicht automatisch aktualisiert; Zoom, Zeitraum und Scrollposition bleiben erhalten. Ein Neustart ist fuer gueltige Datenaenderungen nicht erforderlich.

Bei offenen Entwuerfen, einem geoeffneten Aufenthaltsfenster oder aktiven Eingaben wird die automatische Uebernahme zurueckgehalten. Bei erkannten externen Aenderungen erscheint ein Hinweis. Entwuerfe werden nicht stillschweigend ueberschrieben; sie koennen exportiert oder verworfen werden. Eine Datenpruefsumme verhindert, dass ein alter Entwurf inzwischen manuell geaenderte JSON-Dateien ueberschreibt. Nach dem Verwerfen werden die aktuellen Dateien wieder automatisch geladen.

Neue Schiffe werden aus `data/ships/*.json` erkannt, nicht aus den alten Sicherungs-Unterordnern. Eine bestehende Schiffsdatei kann als Vorlage kopiert werden. Dateiname und `id` muessen uebereinstimmen, beispielsweise `tokyo.json` und `"id": "tokyo"`. Ausserdem Name, Dienst, Geschwindigkeit und die Proforma-Zeiten anpassen. Erforderlich sind `id`, `name`, `serviceId`, `proformas` und `voyages`; `maxSpeedKnots` sollte explizit gesetzt werden. Ein neuer Dienst wird bei Bedarf aus `serviceId` erkannt. Ein Eintrag im Planmanifest ist fuer das Erkennen neuer Dateien nicht erforderlich. Fehlerhafte JSON-Dateien fuehren zu einer Fehlermeldung; die letzte gueltige Browseransicht bleibt erhalten.

Die Hafenfolge ist in der Oberflaeche noch fest; Excel-Import, echte separate Betriebssystemfenster und Benutzerverwaltung sind nicht enthalten. Der Server ist fuer lokale Einzelnutzung gedacht, nicht fuer produktiven Mehrbenutzerbetrieb. Er bindet nur an `127.0.0.1`.

Schriften, Lucide-Symbole und das Hafenfoto werden online geladen. Die Planung funktioniert auch ohne diese externen Ressourcen; dann nutzt der Browser Ersatzschriften und die beschrifteten Schaltflaechen.

## Tests

```powershell
python -m unittest -v
```