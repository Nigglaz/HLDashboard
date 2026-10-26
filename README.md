# Harborline - Flask-Prototyp

Lokale Liegeplatzplanung fuer die in den JSON-Dateien konfigurierten Schiffe, Haefen und Dienste.

## Start

Aus diesem Ordner:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Browser: http://127.0.0.1:5055. Ein anderer Port ist ueber die Umgebungsvariable `PORT` einstellbar.

## Anmeldung und Profile

Dashboard, Profil und alle Fach-APIs erfordern eine Anmeldung. Im Profil kann ausschliesslich das eigene Passwort geaendert werden; dazu sind das aktuelle Passwort und zweimal das neue Passwort erforderlich (mindestens acht Zeichen). "Abmelden" beendet die Browsersitzung. Alle Konten haben derzeit dieselben Planungsrechte; es gibt keine Registrierung, Rollen oder Benutzerverwaltung in der UI.

Konten liegen getrennt von den Fachdaten in `instance/users.json` als JSON-Liste. Dieses Verzeichnis ist von Git ausgeschlossen und muss bei Umzuegen gesondert uebernommen werden. Passwoerter sind gesalzene Werkzeug-Hashes, niemals Klartext. Beispielstruktur (den Platzhalter durch einen erzeugten Hash ersetzen):

```json
[
  {
    "email": "person@example.org",
    "passwordHash": "<erzeugter Passwort-Hash>"
  }
]
```

Ein Konto samt Standardpasswort kann auf Linux interaktiv angelegt werden:

```bash
.venv/bin/python -m flask --app app:create_app create-user --email person@example.org
```

Das Passwort wird verdeckt abgefragt und nicht als Kommandozeilenargument benoetigt. Alternativ einen Hash erzeugen und einen weiteren Eintrag in der JSON-Liste ergaenzen:

```bash
.venv/bin/python -m flask --app app:create_app hash-password
```

Unter Windows dieselben Befehle mit `.\.venv\Scripts\python.exe` verwenden. Neue JSON-Eintraege gelten ohne Neustart. E-Mail-Adressen muessen eindeutig sein (Gross-/Kleinschreibung wird ignoriert). Das Standardpasswort kann nach der Anmeldung im Profil geaendert werden; eine Zwangsaenderung ist nicht eingerichtet. Das Speichern aendert nur den Passwort-Hash des angemeldeten Kontos und erhaelt andere Benutzer.

Der zufaellige Sitzungsschluessel liegt in `instance/session-key` und bleibt ueber Serverneustarts erhalten. Beide Dateien vertraulich behandeln und nicht veroeffentlichen oder committen. Sitzungen gelten bis zu zwoelf Stunden; Passwortwechsel oder das Entfernen eines Kontos machen dessen andere Sitzungen ungueltig. Formulare und schreibende API-Anfragen sind mit CSRF-Tokens geschuetzt. Nach zehn Anmeldeversuchen pro IP innerhalb von fuenf Minuten wird bis zum Ablauf dieses Fensters begrenzt (prozesslokal, kein verteilter Schutz).

Lokale Ansichten und Entwuerfe werden jetzt pro E-Mail getrennt gespeichert. Die frueheren, nicht zugeordneten Browserentwuerfe werden nicht automatisch einem Konto zugewiesen. Alle Benutzer arbeiten weiterhin an denselben serverseitigen Fahrplandaten.

Fuer den Heimnetztest bleiben HTTP-Cookies moeglich. Vor einer Internetfreigabe HTTPS und einen Produktionsserver einrichten; bei HTTPS `PHOCA_HTTPS=1` setzen, damit Sitzungscookies nur verschluesselt uebertragen werden. Login allein ersetzt diese Betriebsabsicherung nicht. Die Dateiverwaltung und Anmeldebegrenzung sind weiterhin fuer eine einzelne Serverinstanz ausgelegt.

## Planung

- Transit- und Liegezeiten in Stunden werden in Kalender, Hafenfolge und Detailformular auf maximal zwei Nachkommastellen gerundet angezeigt. Die minutengenauen Ankunfts-/Abfahrtszeiten und Transitminuten bleiben erhalten.
- Ohne gespeicherte Ansicht beginnt das Kalenderfenster beim lokalen heutigen Datum minus zehn Tage und endet einschliesslich des Tages sechs Kalendermonate nach Heute. Der Zeitraum wird nicht aus der ersten Proforma abgeleitet. Manuelle Zeitfenster und gespeicherte Ansichten bleiben moeglich.
- Beim Anklicken eines Aufenthalts werden Schiff und konkrete Reise gemeinsam ausgewaehlt. Fahrplan-/Proforma-Anzeige und "Auf Proforma zuruecksetzen" beziehen sich damit auf denselben Reisebalken. Proforma-Balken sind schraffiert, tatsaechliche Fahrplaene nicht; beide haben einen durchgezogenen Rand.

- Der heutige lokale Kalendertag ist im Zeitkopf und in den Liegeplatz-/Transitspuren blassgruen markiert. "Heute" neben der Liegeplatzbelegung scrollt zu diesem Tag, ohne das Zeitfenster zu veraendern. Liegt Heute ausserhalb des Fensters, erscheint ein Hinweis.
- Die Kalenderdarstellung wird an den Zeitfenstergrenzen abgeschnitten. Aufenthalte, die ueber eine Grenze hinausreichen, behalten ihre vollstaendigen gespeicherten Zeiten, vergroessern aber nicht mehr den horizontalen Scrollbereich.
- In "Proformas" zeigt "Proforma ohne Wochenversatz" die gewaehlte Dienstvorlage. Die Auswahl eines Schiffs zeigt diese Vorlage mit dem Wochenversatz seiner Zuordnung. Ohne Zuordnung zur gewaehlten Vorlage bleibt der Kalender fuer dieses Schiff leer; tatsaechliche Reisen ersetzen hier keine Proforma.

- Oben einen Dienst auswaehlen; links erscheinen ausschliesslich dessen Schiffe. Das ausgewaehlte Schiff ist rot, andere Schiffe bleiben zum Vergleich im Kalender sichtbar.
- Alternativ im selben Dropdown "Hafenuebersicht" waehlen. Links lassen sich mehrere Haefen per Checkbox auswaehlen. Der Kalender zeigt nur diese Haefen untereinander, mit allen Schiffen aller Dienste und ihren Dienstfarben. Die Hafenuebersicht ist eine reine Vergleichsansicht ohne schiffsbezogene Transitzeilen oder Planbearbeitung. Auswahl und Reihenfolge der angewaehlten Haefen werden mit einer benannten Ansicht gespeichert.
- Alle Schiffe desselben Dienstes verwenden dieselbe konfigurierte Farbe, ohne Farbrotation. Angezeigt werden nur die Haefen der ausgewaehlten Hafenfolge, in deren Reihenfolge.
- Einen Aufenthalt ziehen, um ihn stundenweise zu verschieben. Vertikales Ziehen wechselt den Liegeplatz innerhalb desselben Hafens.
- Den rechten Balkenrand ziehen, um die Abfahrt zu aendern.
- Mit "Folgeaufenthalte mitnehmen" werden anschliessende Aufenthalte um denselben Betrag verschoben.
- Einen Balken anklicken: verschiebbares Detailfenster mit Zeiten, Liegeplatz und Transitdauer.
- Die eingetragene Transitdauer ist ein Planungswert. "Ankunft aus Transit neu berechnen" setzt die Ankunft entsprechend und erhaelt die Liegedauer. Die Plausibilitaetspruefung verwendet unabhaengig davon Entfernung / Maximalgeschwindigkeit, nicht den eingetragenen Planungswert.
- Transitzeiten lassen sich auch direkt zwischen den Hafenbloecken bearbeiten. Der Haken berechnet die naechste Ankunft neu und erhaelt die Liegedauer; das Mitnehmen weiterer Aufenthalte folgt dem Schalter oben.
- In der Dienstansicht steht hinter der Liegeplatzzahl "Hafen hinzufuegen". Hafenname, Liegeplatzzahl und Button bleiben beim horizontalen Scrollen gemeinsam links sichtbar. Der Dialog bietet alle registrierten Haefen an und fuegt den gewaehlten Hafen vor dem betreffenden Aufenthalt nur in die aktuelle Reise des ausgewaehlten Schiffs ein. Bei mehreren Besuchen desselben Hafens laesst sich unter "Vor Aufenthalt" der genaue folgende Aufenthalt waehlen. Auch ein erneuter Besuch eines bereits enthaltenen Hafens ist moeglich; jeder Besuch hat eine eigene ID, der physische Hafenblock wird nicht dupliziert.
- Der neue Aufenthalt wird mittig zwischen der vorherigen Abfahrt und der folgenden Ankunft positioniert. Seine Liegedauer ist der Durchschnitt der beiden benachbarten Liegedauern, minutengenau gerundet. Vor dem ersten Aufenthalt wird dessen Liegedauer uebernommen und der neue Aufenthalt direkt davor gesetzt; die zunaechst fehlende Transitzeit muss vor dem Speichern passend eingeplant werden. Bestehende Ankunfts- und Abfahrtszeiten sowie Liegeplaetze bleiben unveraendert. Als Liegeplatz gilt der konfigurierte Dienstdefault, sonst LP 1.
- Ad-hoc-Aufenthalte bleiben zunaechst gelbe Pending-Aenderungen und lassen sich bearbeiten oder rueckgaengig machen. Reicht die Luecke nicht aus, wird trotzdem der berechnete Entwurf angezeigt; vor dem Speichern muessen Ueberlappungen und zu kurze Transitzeiten behoben werden. Proforma und andere Runden erhalten keinen zusaetzlichen Aufenthalt. Im Proforma-Vergleich bekommt eine Ad-hoc-Station keinen erfundenen Planrahmen.
- Bei negativen Zeitfenstern zwischen zwei Haefen oder explizit negativen Transitwerten einer tatsaechlichen Reise erscheint "Change Rotation". Der Button sortiert die Aufenthalte dieser Runde nach Ankunft und berechnet die Transitminuten zwischen den neuen Nachbarn. Das funktioniert auch fuer mehr als zwei vertauschte Haefen. Ankunft, Abfahrt und Liegeplatz bleiben unveraendert. Die neue Hafenfolge wird als Pending-Entwurf angezeigt und kann rueckgaengig gemacht werden; erst "Plan fuer dieses Schiff uebernehmen" speichert sie.
- "Change Rotation" prueft die neue Reihenfolge gegen die Mindestfahrzeiten aus Entfernung und Maximalgeschwindigkeit. Ueberlappende Aufenthalte und zu kurze Streckenzeiten werden mit einer Fehlermeldung abgewiesen; die Zeiten werden nicht automatisch passend verschoben. Weitere Liegeplatz- oder Reise-Konflikte werden wie gewohnt vor dem Speichern geprueft. Proformas und andere Runden des Schiffs bleiben unveraendert. Bereits falsch geordnete tatsaechliche JSON-Reisen bleiben fuer diese gezielte Reparatur ladbar.
- Hafenueberschriften klappen die Liegeplaetze ein und aus. In der Transitzeile steht vor dem Transit ein grauer Kasten mit Schiffsname und Liegezeit. Er bleibt auch bei eingeklappten Haefen sichtbar; es gibt keine gesonderten Liegezeitzeilen pro Hafen. Unter "Liegeplaetze & Ansicht" lassen sich alle Haefen einklappen oder einzelne Liegeplaetze ausblenden. Eine benannte Ansicht speichert diese Einstellungen, Schiff, Reisedatum, Anfang, Ende, Zoom und Scrollposition lokal im Browser. Die zuletzt gewaehlte Ansicht wird im selben Browser wieder geladen.
- Mausrad: horizontal durch die Zeit scrollen. Strg/Mac-Command + Mausrad: am Mauszeiger zoomen. Umschalt + Mausrad: vertikal scrollen. Der Zoomregler funktioniert ebenfalls.
- "Reise ab" waehlt eine Reise anhand ihres nominellen Startdatums; zwischen zwei Starts wird die vorherige Runde gewaehlt. Vor dem ersten Start einer neuen Proforma wird deren erste gueltige Runde angeboten. Ohne tatsaechlichen Reiseabschnitt wird die datumsabhaengig gueltige Proforma verwendet. Der Standardzyklus ist 14 Wochen: Busan startet erneut am 24.04.2027. Der Kalender umfasst standardmaessig sechs Kalendermonate und zeigt darin auch die weiteren Runden. "Ab" und "Bis" lassen sich unabhaengig anpassen; "Bis" ist inklusive. Der Zoom reicht bis 1200 Pixel pro Tag; ab 240 Pixeln erscheinen Uhrzeiten im 3-Stunden-Abstand.
- Gelb: ungespeicherter Entwurf. Gestrichelter Umriss: bisherige Belegung, stets mit Schiffsname im Balken.
- "Proforma vergleichen" blendet fuer alle Schiffe des ausgewaehlten Dienstes die Proforma-Positionen als gestrichelte Rahmen ein. Rahmen und gestrichelte Verbindungslinien tragen die jeweilige Schiffsfarbe; das ausgewaehlte Schiff ist rot. Ueber der Linie steht die Abweichung der Ankunft gegenueber der fuer das Reisedatum gueltigen Proforma, z. B. "+24 h Verzoegerung", "6 h frueher" oder "0 h Abweichung". Bestehende Reisen bleiben unveraendert. Der Vergleichsschalter wird mit benannten Ansichten gespeichert.
- Es gibt nur den aktuellen Plan und offene Aenderungen (Pending). "Plan fuer dieses Schiff uebernehmen" speichert ausschliesslich das ausgewaehlte Schiff. Andere offene Schiffsentwuerfe bleiben erhalten. Die Einzeluebernahme wird gegen die gespeicherten Plaene der anderen Schiffe geprueft, nicht gegen deren ungespeicherte Aenderungen. Dadurch kann eine abhaengige Verschiebung erfordern, zuerst das andere Schiff zu uebernehmen.
- Rueckgaengig/Wiederholen, Verwerfen und JSON-Export stehen zur Verfuegung. "Verwerfen" betrifft nur das ausgewaehlte Schiff. Lokale Entwuerfe bleiben im selben Browser nach Neuladen erhalten.

## Daten

Die Anwendung benoetigt nur Fachdaten, keine zusaetzlichen Organisationsdateien:

```text
data/
	ports.json          Haefen, Liegeplaetze und Entfernungen
	services.json       Dienstkonfiguration und Dienstfarben
	ships/
		busan.json        Schiff, Geschwindigkeit, Proformas und Reisen
		berlin.json
		...
```

Die JSON-Dateien sind die einzige Quelle fuer Fachdaten. `ports.json` und `services.json` muessen vor dem Start vorhanden sein; fehlende Dateien fuehren zu einem ausdruecklichen Ladefehler. Fuer eine leere Konfiguration jeweils `[]` hinterlegen. Ein fehlendes oder leeres `ships/`-Verzeichnis bedeutet eine leere Flotte. Es werden weder Demohaefen noch Dienste oder Beispielschiffe erzeugt. Testdaten liegen getrennt unter `tests/fixtures/plan.json` und werden von der Anwendung nicht geladen.

Beim Uebernehmen wird ausschliesslich die aktuelle Datei des ausgewaehlten Schiffs atomar ersetzt. Die Schiffe werden direkt aus dem Verzeichnis ermittelt. Weder ein Manifest noch eine Legacy-Sicherung oder eine serverseitige Ansichtsdatei werden angelegt oder benoetigt. Die entsprechenden frueheren Dateien wurden entfernt. Vorhandene aeltere Schiffssicherungen in Unterordnern sind keine aktiven Daten und werden nicht eingelesen. Die Anwendung ist fuer eine einzelne lokale Serverinstanz ausgelegt.

Der Schutz gegen gleichzeitiges Ueberschreiben verwendet ausschliesslich `dataSignature`, eine aus den aktuellen Fachdaten berechnete Pruefsumme. Ein zusaetzlicher Speicherzaehler oder eine Metadatendatei ist nicht erforderlich. Pending und benannte Ansichten bleiben getrennt im lokalen Browser (`localStorage`). Ansichten werden nicht zwischen verschiedenen Browsern oder Rechnern synchronisiert; das Loeschen der Websitedaten entfernt diese lokalen Einstellungen und Entwuerfe.

Eine Schiffsdatei enthaelt `id`, `name`, `serviceId`, `proformas` und `voyages`. Jede Proforma hat `id`, `name`, `validFrom`, `repeatWeeks` und `stops`. Das Startdatum einer Reise entscheidet, welche Proforma-Version verwendet wird; die jeweils neueste Version mit passendem Geltungsbeginn gewinnt. Die erste Ankunft der Vorlage ist der Anker ihres Zyklus. Unterschiedliche Jahres- oder Saisonproformas koennen dadurch unterschiedliche Anker und Intervalle haben.

`voyages` enthaelt nur explizit gespeicherte tatsaechliche Reisen, indiziert nach dem nominellen Startdatum. Jede Reise speichert die vollstaendige Hafenfolge und ihre `proformaId`. Fehlt ein Eintrag, berechnet die Anwendung die Reise aus der Vorlage. Erst eine Aenderung in der Liegeplatzplanung legt einen Reiseabschnitt an. Proforma-Aenderungen wirken auf den Fallback, aber nicht auf vorhandene tatsaechliche Reisen. "Auf Proforma zuruecksetzen" entfernt einen tatsaechlichen Reiseabschnitt als Entwurf; erst "Plan fuer dieses Schiff uebernehmen" speichert das Entfernen.

Bereits frueher uebernommene tatsaechliche Reisen und alte 15-Wochen-Ausnahmen bleiben in den Schiffsdateien erhalten; sie koennen daher vom 14-Wochen-Fallback abweichen. Beim Start werden keine historischen Sammeldateien mehr verwendet. Ein absichtlich geleertes Schiffsverzeichnis wird beim Neustart nicht erneut mit Beispieldaten gefuellt.

## Dienstfarben und feste Werte

Die Dienstfarbe steht in `data/services.json` als `color`, zum Beispiel als Ausschnitt eines Dienstes:

```json
{
	"id": "NE2",
	"color": "#347cd0"
}
```

Erlaubt ist eine Hexfarbe im Format `#RRGGBB`. Alle Schiffe eines Dienstes verwenden exakt diese Farbe; es gibt keine Rotation oder Abstufung nach Schiffsreihenfolge. Legende, Balken und Proforma-Vergleich verwenden dieselbe Konfiguration. Neue Dienste brauchen keinen eigenen Fall im JavaScript. Ohne Farbangabe gilt als technischer Ersatzwert `#278ba9`. Die bestehende automatische JSON-Aktualisierung uebernimmt Farbaenderungen ebenfalls, sofern keine Bearbeitung offen ist.

Rot fuer das ausgewaehlte Schiff und Gelb fuer Pending sind bewusst unabhaengige Statusfarben aus den CSS-Variablen `--red` und `--yellow`, keine Dienstfarben.

Die Durchsicht hat folgende Unterscheidung ergeben:

| Bereich | Bewertung |
| --- | --- |
| Schiffe, Haefen, Liegeplaetze, Distanzen, Geschwindigkeit, Proformas | Fachdaten in JSON; nicht in der Laufzeitlogik festlegen. |
| Dienstfarben | Jetzt pro Dienst konfigurierbar, einschliesslich Legende und Proforma-Vergleich. |
| Startauswahl und Kalenderdatum | Werden aus dem ersten geladenen Schiff und seiner ersten Proforma abgeleitet; kein Busan-/NE2-/Januar-2027-Zwang mehr. Gespeicherte Ansichten haben Vorrang. |
| Beispieldaten und alte Migrationen | Keine Demo-Initialisierung oder schiffsbezogenen Datumskorrekturen im Laufzeitcode. Die verbleibenden Migrationen uebernehmen ausschliesslich vorhandene JSON-Daten, etwa schiffseigene Proformas in gemeinsame Dienstvorlagen oder Geschwindigkeiten aus einer alten Navigations-JSON. |
| `repeatWeeks` und `defaultBerths` am Dienst | Derzeit Demo-/Vorlagenmetadaten; vorhandene Reisen verwenden die Werte ihrer Proforma-Stationen und deren `repeatWeeks`. Eine Aenderung am Dienst verschiebt daher keine vorhandenen Proformas. |
| Entfernungen und Geschwindigkeit | Pflichtangaben aus JSON, keine stillen Ersatzwerte. Fehlende Streckenentfernungen oder Schiffsgeschwindigkeiten werden ausdruecklich gemeldet. |
| Importname und Importzeitraum | Keine fest eingetragenen Beispielwerte. Die Oberflaeche startet mit dem geladenen Schiff; der Importzeitraum reicht standardmaessig vom heutigen lokalen Browserdatum bis zwei Kalendermonate spaeter. Beide Datumsfelder bleiben manuell editierbar. Bei Monatsenden wird auf den letzten vorhandenen Tag des Zielmonats begrenzt. Textimport und Skript verlangen explizite Angaben. |
| Kollisionspruefung | Prueft derzeit zwei Jahre vor bis zwei Jahre nach den gespeicherten Datumsgrenzen; keine Garantie fuer die unendliche Zukunft. Die Grenze gehoert bei einem groesseren Einsatz in eine Betriebskonfiguration. |
| UI-Vorgaben | Sechs Monate, fuenf Sekunden Aktualisierung, 100 Rueckgaengig-Schritte, Zoom 16 bis 1200 Pixel/Tag und Stundenraster ab 240 Pixel/Tag sind derzeit feste Produktstandards. Bei Bedarf spaeter gemeinsame UI-Konfiguration; nicht jeder Zahlenwert braucht eine JSON-Option. |
| Design und externe Ressourcen | Layoutmasse und Statusfarben koennen zentral im CSS bleiben. Schriften, Symbole und Hafenfoto sind feste Online-Ressourcen; fuer einen Offline-Betrieb lokal bereitstellen. |

## Proforma-Ansicht

Der Reiter "Proformas" ist ausschliesslich eine schreibgeschuetzte Ansicht. Dienst, Schiff und vorhandene Vorlage lassen sich auswaehlen; Name, Geltungsbeginn, Zyklus, Liegeplaetze und Transitzeiten koennen nicht bearbeitet werden. Auch die API weist Proforma-Aenderungen ab. Der spaetere Excel-Import ist noch nicht implementiert. Zwischen der Planungs- und Proforma-Ansicht kann gewechselt werden, ohne offene Schiffsentwuerfe zu verwerfen.

## Nautische Transitpruefung

Entfernungen stehen direkt an den Haefen in `data/ports.json`, Geschwindigkeiten als `maxSpeedKnots` in der jeweiligen Schiffsdatei. Die Mindestfahrzeit ergibt sich ausschliesslich aus diesen Angaben. Die mitgelieferten JSONs enthalten teilweise Platzhalter von **100 sm** und **20 kn**; diese Werte werden vom Programm weder erzeugt noch als Ersatz fuer fehlende Angaben verwendet. Fuer eine reale Planung sind die JSON-Werte fachlich zu pflegen.

Beim Hafeneintrag mit `id: "rotterdam"` aendert `distancesNm.hamburg` die Entfernung nach Hamburg. Jedes Paar steht nur einmal und gilt in beiden Richtungen. Fuer benachbarte Aufenthalte in unterschiedlichen Haefen muss eine Entfernung konfiguriert sein; innerhalb desselben Hafens gilt eine Strecke von null. Fehlende oder ungueltige Entfernungen und Geschwindigkeiten fuehren zu einer Fehlermeldung statt einer geschaetzten Mindestfahrzeit. Eine Geschwindigkeit aus einer noch vorhandenen alten Navigations-JSON wird nur uebernommen, wenn dort tatsaechlich ein Wert hinterlegt ist.

Die verfuegbare Zeit wird aus Abfahrt des vorherigen Hafens und Ankunft im naechsten Hafen berechnet. Hinweise enthalten die verfuegbaren Stunden, die erforderlichen Stunden und die Rechnung in sm / kn. `transitMinutes` bleibt ein Planungswert. Neue bzw. verschaerfte Unterschreitungen werden beim Uebernehmen abgewiesen; bekannte Unterschreitungen blockieren keine unabhaengigen Aenderungen. Vorhandene Fahrplanzeiten werden bei einer Aenderung der Entfernung oder Geschwindigkeit nicht automatisch verschoben.

Alle Zeitangaben sind gemeinsame **UTC-Planzeit**, ohne saisonale oder lokale Umrechnung. Die gelieferten Uhrzeiten werden unveraendert als Planzeit verwendet. Busan Express startet am 16.01.2027; Berlin, Gdansk, Rotterdam, Hamburg und Genova Express folgen jeweils sieben Tage spaeter.

Schiffsspezifische Zeiten, auch fuer Mathilde Maersk, stehen ausschliesslich in den JSON-Vorlagen und Reisen. Es gibt keine automatische Sonderkorrektur bestimmter Schiffsnamen oder Datumswerte im Programm.

Der Server prueft Transitzeiten, Liegeplaetze, neue Doppelbelegungen und sich ueberlappende Reisen. Die Kollisionspruefung generiert alle Runden vom fruehesten gespeicherten Datum minus zwei Jahren bis zum spaetesten Datum plus zwei Jahren. Sie ist keine Zusage, dass sich beliebige Dienstzyklen in unendlicher Zukunft nie ueberschneiden.

Die eingetragenen Transitzeiten der Beispieldaten sind aus den gelieferten Abfahrts- und Ankunftszeiten abgeleitet. Sie bleiben als Planungswerte erhalten und werden nicht automatisch aus einer Verschiebung zurueckgerechnet. Die nautische Mindestfahrzeit wird dagegen stets aus der separaten Entfernungs- und Geschwindigkeitskonfiguration berechnet.

## Dynamisches Laden

Der Server liest Hafen-, Dienst- und Schiffsdateien bei jeder Anfrage neu ein. Der Browser fragt alle fuenf Sekunden und bei Rueckkehr zum Fenster nach Aenderungen. Ohne offenen Entwurf oder aktive Eingabe wird die Ansicht automatisch aktualisiert; Zoom, Zeitraum und Scrollposition bleiben erhalten. Ein Neustart ist fuer gueltige Datenaenderungen nicht erforderlich.

Bei offenen Entwuerfen, einem geoeffneten Aufenthaltsfenster oder aktiven Eingaben wird die automatische Uebernahme zurueckgehalten. Bei erkannten externen Aenderungen erscheint ein Hinweis. Entwuerfe werden nicht stillschweigend ueberschrieben; sie koennen exportiert oder verworfen werden. Eine Datenpruefsumme verhindert, dass ein alter Entwurf inzwischen manuell geaenderte JSON-Dateien ueberschreibt. Nach dem Verwerfen werden die aktuellen Dateien wieder automatisch geladen.

Neue Schiffe werden aus `data/ships/*.json` erkannt, nicht aus den alten Sicherungs-Unterordnern. Eine bestehende Schiffsdatei kann als Vorlage kopiert werden. Dateiname und `id` muessen uebereinstimmen, beispielsweise `tokyo.json` und `"id": "tokyo"`. Ausserdem Name, Dienst, Geschwindigkeit und die Proforma-Zeiten anpassen. Erforderlich sind `id`, `name`, `serviceId`, `proformas` und `voyages`; `maxSpeedKnots` sollte explizit gesetzt werden. Ein neuer Dienst wird bei Bedarf aus `serviceId` erkannt. Ein zusaetzlicher Registrierungseintrag ist nicht erforderlich. Fehlerhafte JSON-Dateien fuehren zu einer Fehlermeldung; die letzte gueltige Browseransicht bleibt erhalten.

Vorhandene Hafenaufenthalte koennen ueber "Change Rotation" neu geordnet und neue Stationen als Ad-hoc-Aufenthalte in einzelne Reisen eingefuegt werden. Stationen entfernen, Excel-Import, echte separate Betriebssystemfenster und die Administration weiterer Benutzer sind in der Oberflaeche noch nicht enthalten. Anmeldung und eigenes Passwortaendern sind vorhanden. Der Server ist fuer lokale Tests mit einer einzelnen Serverinstanz gedacht, nicht fuer produktiven Mehrbenutzerbetrieb. `python app.py` bindet nur an `127.0.0.1`; fuer Heimnetztests kann der Flask-CLI-Start mit `--host=0.0.0.0` verwendet werden.

Schriften, Lucide-Symbole und das Hafenfoto werden online geladen. Die Planung funktioniert auch ohne diese externen Ressourcen; dann nutzt der Browser Ersatzschriften und die beschrifteten Schaltflaechen.

## Flotte und Haefen

Die Reiter "Flotte" und "Haefen" dienen zum Anlegen und Bearbeiten der Stammdaten. Links wird ein vorhandener Datensatz ausgewaehlt; "Schiff anlegen" bzw. "Hafen anlegen" oeffnet ein leeres Formular. "Stammdaten speichern" schreibt direkt die jeweilige Fachdatei. Offene Kalenderentwuerfe muessen vorher uebernommen oder verworfen werden. Ungespeicherte Formulare werden vor einem Wechsel abgefragt.

Bei Schiffen koennen Anzeigename, eindeutiger Importname, Dienst und Maximalgeschwindigkeit geaendert werden. Die technische ID und der Dateiname bleiben bei bestehenden Schiffen stabil. Fuer neue Datensaetze kann eine ID angegeben werden; andernfalls wird sie erzeugt. Der Importname wird normalisiert und muss eindeutig bleiben. Dienstwechsel und Namensaenderung verschieben keine Fahrplaene und veraendern keine Proformas.

Neue Schiffe starten mit leeren `proformas` und `voyages`. Der erste Import erzeugt eine tatsaechliche Reise mit `proformaId: null`; eine Proforma oder Wiederholung wird nicht erfunden. Schiffe ohne Fahrplan bleiben im Kalender auswaehlbar. Spaetere weitere Importe koennen weitere tatsaechliche Reisen hinzufuegen.

Bei Schiffen ohne Proforma bleibt eine gespeicherte Reise waehrend ihrer gesamten Laufzeit einschliesslich Transitluecken auswaehlbar. Passt das aktuelle Reisedatum beim Schiffwechsel zu keiner Reise, waehlt der Kalender eine gespeicherte Reise im sichtbaren Zeitraum, ersatzweise die erste gespeicherte Reise. Es wird dabei kein Fahrplan erzeugt. Kollisionshinweise pruefen alle Reisen im Kalenderzeitraum, nicht nur die aktuell ausgewaehlte Runde; "Bestand" bezeichnet bereits gespeicherte Konflikte. Balken am selben Liegeplatz koennen sich bei einer Kollision ueberdecken.

Bei Haefen sind Anzeigename, Liegeplatzzahl, Quell-Aliase und nautische Entfernungen bearbeitbar. Aliase werden als JSON-Objekt je Datenquelle eingegeben. Entfernungen gelten fuer beide Richtungen; das Speichern loest doppelte Gegenrichtungswerte auf. Eine Verringerung der Liegeplatzzahl wird abgewiesen, wenn bestehende Proformas oder Reisen dadurch auf ungueltige Liegeplaetze verweisen. Bestehende Aufenthalte werden nicht umnummeriert.

Ein Hafeneintrag kann ein einzelnes Terminal darstellen. Zwei Eintraege duerfen denselben Anzeigenamen, etwa "Rotterdam", haben, benoetigen aber unterschiedliche technische IDs, beispielsweise `rotterdam-mv2` und `rotterdam-rwg`. Bei gleichen Anzeigenamen wird die ID in wichtigen Auswahlfeldern ergaenzt. Der spezifische Terminal-Alias einer Datenquelle hat bei der Importzuordnung Vorrang vor dem allgemeinen Stadtnamen; verbleibende Mehrdeutigkeiten werden nicht geraten.

Die technische Hafen-ID ist der Fremdschluessel in `portId` aller Proforma- und Reiseaufenthalte, in Entfernungslisten, Dienst-Standardliegeplaetzen sowie in lokalen Hafen- und Liegeplatzfiltern. Sie kann im Reiter "Haefen" nach einer Bestaetigung umbenannt werden. Vorher wird auf ID-Kollisionen geprueft. Der Server passt die vorhandenen Fahrplanverweise, Entfernungen und Dienstdefaults gemeinsam an; Ankunft, Abfahrt, Liegeplatz, Aufenthalts-ID und Quellenmetadaten bleiben erhalten. Die Ansichten des bearbeitenden Browsers werden ebenfalls angepasst. In anderen Browsern gespeicherte Ansichten muessen gegebenenfalls neu ausgewaehlt werden. Die ID nicht isoliert direkt in der Hafen-JSON umbenennen, da dann die Referenzmigration fehlt.

Beim Anlegen eines Hafens werden die eingegebenen Entfernungen am neuen Eintrag gespeichert, nicht redundant in jedem anderen Hafeneintrag. Die Berechnung liest A nach B oder ersatzweise den Eintrag B nach A; beide Richtungen verwenden daher denselben Wert. Die bereits vorhandenen Hafenobjekte muessen dafuer nicht dupliziert oder gespiegelt ergaenzt werden. Nicht konfigurierte Entfernungen bleiben im Formular leer und muessen eingegeben werden; auch neue Schiffsgeschwindigkeiten und Liegeplatzzahlen werden nicht vorbelegt. Bei einer ID-Aenderung bleiben auch Entfernungen erhalten, die zuvor nur am Gegenhafen definiert waren. Beim Speichern wird jedes betroffene Paar auf einen einzelnen Eintrag zusammengefuehrt.

Die Verwaltungslogik liegt in `master_data.py`, die Oberflaeche in `static/master_data.js`. Es entstehen keine zusaetzlichen Organisationsdateien. Schiffe werden weiterhin einzeln unter `data/ships/` gespeichert; Haefen bleiben in `data/ports.json`.

## Fahrplandaten importieren

Der Reiter "Datenimport" zeigt Fahrplandaten zunaechst ausschliesslich als Pending-Vorschau. Unter "Umfang" kann zwischen "Einzelnes Schiff" und "Ganzer Dienst" gewaehlt werden. Der fruehere Beispiel-Knopf und sein API-Endpunkt wurden entfernt. Gespeicherte Suchausgaben und normalisierte Text-/JSON-Dateien koennen weiterhin importiert werden; die Beispieldatei unter `examples/` bleibt lediglich als Test- und Skriptfixture erhalten.

Unter "Datenquelle" stehen Maersk und Hapag-Lloyd zur Wahl. Der jeweilige Live-Knopf startet das separate Quellskript ueber den Server und laedt das Ergebnis automatisch in die Vorschau. Bei "Ganzer Dienst" werden alle aktuell registrierten Schiffe dieses Dienstes nacheinander mit ihren eindeutigen Schiffsnamen bei der ausgewaehlten Quelle abgefragt. Die Anzeige nennt das aktuelle Schiff und den Fortschritt. Dashboard-Abrufe laufen immer im Fenstermodus; die bisherige Browserauswahl und der Headless-Hinweis wurden entfernt. Der Abruf speichert keine Fahrplandaten. Immer nur ein Live-Abruf gleichzeitig ist erlaubt; je Schiff gilt ein Zeitlimit von drei Minuten. Ein Dienstabruf kann entsprechend laenger dauern. Direkt am Uebernahmeknopf stehen die noch offenen Bedingungen.

Der Dienstimport zeigt eine eigene Ergebnistabelle je Schiff sowie schiffsbezogene Zuordnungs- und Differenzzeilen. Abruffehler und fehlende Resultate werden nicht unterschlagen. Solange ein eingeschlossenes Schiff fehlt oder fehlerhaft ist, wird die gemeinsame Uebernahme blockiert. Ein Schiff kann in der Ergebnistabelle ausdruecklich ausgeschlossen werden. Ohne solchen Ausschluss sind alle Schiffe des gewaehlten Dienstes erforderlich. Hafenzuordnungen und "Ignorieren" gelten nur fuer die betreffende Zeile des jeweiligen Schiffs.

Vor "Import fuer Dienst ... uebernehmen" werden alle eingeschlossenen Kandidaten und ihre gemeinsamen Konflikte geprueft. Erst danach werden die betreffenden Schiffsdateien geschrieben. Proformas, ausgeschlossene Schiffe und Schiffe anderer Dienste bleiben unveraendert. Jede Datei wird atomar ersetzt; bei einem gemeldeten Schreibfehler wird eine Wiederherstellung bereits geschriebener Dateien versucht. Das ist keine transaktionale Datenbank mit garantierter Wiederherstellung nach einem Prozess- oder Rechnerabsturz.

Die Vorschau zeigt alle Quellaufenthalte, ihre Hafenzuordnung sowie neue, geaenderte, unveraenderte und entfernte Aufenthalte der betroffenen Reise. Nicht zugeordnete Zeilen blockieren die Uebernahme, solange sie eingeschlossen sind. Sie muessen manuell einem vorhandenen Hafen zugeordnet oder explizit ausgeschlossen werden. Im Beispiel sind beide Suez-Aufenthalte ungeklärt, da dieser Hafen noch nicht in den Fachdaten vorhanden ist. Es werden keine unbekannten Haefen automatisch angelegt oder stillschweigend verworfen.

Die Uebernahme betrifft nur die gewaehlte Runde des gefundenen Schiffs, nie die Proforma. Sie verlangt die Bestaetigung der Zeitbasis sowie bei entfernten Aufenthalten eine gesonderte Bestaetigung. Bereits offene Kalenderentwuerfe desselben Schiffs blockieren die Uebernahme; andere Schiffsentwuerfe bleiben erhalten. Eine geaenderte Datenpruefsumme erzwingt eine neue Vorschau. Der Zeitraum bzw. die Zeilenauswahl muss auf eine Runde begrenzt werden; mehrere Runden werden nicht automatisch zusammengefuehrt.

**Importgrenze:** Bei jeder Quelle werden nur Aufenthalte mit einer Ankunft innerhalb des ausgewaehlten Fensters "Ab" bis "Bis" geaendert oder als entfernt vorgeschlagen. Beide Tage sind inklusive. Frueher begonnene Aufenthalte bleiben vollstaendig erhalten, auch wenn ihre Abfahrt erst nach dem Startdatum liegt. Auch Aufenthalte nach dem Enddatum bleiben unveraendert. Dies gilt ebenfalls fuer Dienstimporte. Der in der Oberflaeche gewaehlte Zeitraum hat Vorrang vor dem Zeitraum in einer geladenen Importdatei. Zeilen ausserhalb des Fensters werden als geschuetzt markiert; nur neue bzw. geaenderte Aufenthalte erhalten neu berechnete Transitwerte. Andere Runden bleiben unangetastet.

Bei einer bisher nur aus der Proforma berechneten Reise kann ein importierter Aufenthalt die passende Vorlagenstation auch dann ersetzen, wenn deren urspruengliche Ankunft ausserhalb des Importfensters lag. So erzeugt eine Verschiebung ueber die Importgrenze keinen zusaetzlichen alten Proforma-Halt. Dieser Abgleich veraendert keine Dienstvorlage. Bei bereits gespeicherten tatsaechlichen Reisen bleiben historische Aufenthalte ausserhalb des Fensters weiterhin geschuetzt; bestehende fehlerhafte Doppelaufenthalte werden nicht automatisch geloescht.

Fehlt im gelieferten Ausschnitt ein vergangener Aufenthalt, wird er daher nicht mehr entfernt. Bei einem neuen Schiff ohne Plan wird nur der aktuelle Importzeitraum als tatsaechliche Reise angelegt. Es werden keine historischen Aufenthalte oder Proformas rekonstruiert.

### Schiff und Hafen-Aliase

`vesselName` ist der datenquellenuebergreifend eindeutige Schiffsname. Er wird fuer die Zuordnung grossgeschrieben und bezueglich Leerzeichen normalisiert; doppelte Namen werden abgewiesen. Fuer Mathilde lautet er `MATHILDE MAERSK`. Die interne `id` und der bestehende Dateiname bleiben als technische Referenzen erhalten. Fehlt `vesselName` bei aelteren Schiffen, wird der bisherige Anzeigename verwendet.

Am jeweiligen Hafen in `data/ports.json` werden alternative Namen je Datenquelle gespeichert, beispielsweise:

```json
"aliases": {
	"maersk": ["Hamburg", "Eurogate Container Terminal Hamburg"],
	"hapag": ["HAMBURG"]
}
```

Andere Quellen koennen eigene Listen unter ihrem Quellenbezeichner erhalten. Mehrdeutige Treffer werden nicht automatisch ausgewaehlt. Manuelle Zuordnungen in der Vorschau gelten nur fuer diesen Import; dauerhafte Aliase werden in der Hafen-JSON gepflegt.

### Hapag-Lloyd Vessel Tracker

`import_hapag.py` liest den oeffentlichen Vessel Tracker ueber Playwright aus. Es waehlt das Schiff exakt aus der Mainline-Liste oder, falls dort nicht vorhanden, aus der Feeder-Liste. Das Skript liest die verfuegbare Reiseliste und Hafenaufenthalte, filtert nach Ankunft im ausgewaehlten Zeitraum und erzeugt dasselbe Importformat mit `source: "hapag"`.

Identische Aufenthalte (Hafen, Ankunft und Abfahrt) koennen im Tracker unter mehreren Quellreisen stehen. Sie werden einmal importiert; die erste bzw. letzte zugehoerige Quellreise wird als Ankunfts-/Abfahrtsreise hinterlegt. Erneute Besuche mit anderen Zeiten bleiben getrennt. Als "Omit" markierte Aufenthalte werden nicht importiert. Fehlende oder ungueltige Zeiten und unbekannte Tabellenformate fuehren zu einer ausdruecklichen Fehlermeldung.

Die ausgelesene Uebersicht liefert Hafennamen, aber keine Terminalnamen. Daher bleibt `terminalName` leer; es wird kein Terminal geraten. Bei mehreren Terminals desselben Hafens die Zuordnung in der Vorschau manuell pruefen. Dauerhafte Quellnamen koennen unter `aliases.hapag` in der Hafen-JSON gepflegt werden. Die Zeitbasis ist wie beim Maersk-Import unbestaetigt und muss vor der Uebernahme bestaetigt werden.

Auf einem headless Raspberry mit installiertem Xvfb:

```bash
xvfb-run -a .venv/bin/python import_hapag.py --vessel "GDANSK EXPRESS" --from 2026-10-26 --to 2026-11-26 --headed --output hapag_pending.json
```

Unter Windows kann das Skript mit `.venv\Scripts\python.exe` gestartet werden; ohne `--browser` verwendet es dort wie der Maersk-Importer Edge, unter Linux Chromium. Das Dashboard selbst weiterhin unter `xvfb-run` starten; beide Quellen teilen sich dieselbe Playwright-Installation. Eine gespeicherte normalisierte Hapag-JSON kann im Datenimport geladen werden; kopierter Hapag-Webseitentext wird nicht als Maersk-Text interpretiert.

Hapag-Lloyd kann den automatisierten Zugriff mit einer Browser-Sicherheitspruefung blockieren. Das Skript meldet dies ausdruecklich und umgeht weder CAPTCHA noch Zugriffsschutz. Bei der Entwicklung waren die echten Gdansk-Tabellen im integrierten Browser abrufbar; der direkte Chromium-Abruf auf dem Raspberry wurde durch eine Sicherheitspruefung blockiert. Ein erfolgreicher unbeaufsichtigter Liveabruf auf dem Raspberry ist daher noch nicht bestaetigt.

### Separates Maersk-Skript

Das eigenstaendige `import_maersk.py` erzeugt nur ein normalisiertes Import-JSON und schreibt nie direkt in Schiffsdateien. Der dateibasierte Modus ist getestet:

```powershell
.\.venv\Scripts\python.exe import_maersk.py --input examples/maersk_mathilde_2027.txt --vessel "MATHILDE MAERSK" --from 2027-01-01 --to 2027-03-01 --output maersk_pending.json
```

`--vessel`, `--from` und `--to` sind sowohl im dateibasierten als auch im Live-Modus Pflichtangaben. Die erzeugte Datei kann im Import-Reiter geoeffnet werden. Ohne `--output` wird das JSON auf stdout geschrieben. Das gemeinsame Format besitzt `schemaVersion: 1`, `source`, `vesselName`, `fromDate`, `toDate`, `fetchedAt`, `timeBasis` und `calls`; jede Zeile enthaelt eine eindeutige `id`, `portName`, `terminalName`, `arrival`, `departure` sowie optional die Quell-Voyagenummern. Weitere Skripte koennen dasselbe Format mit einem anderen `source` erzeugen.

Fuer einen Dienstimport werden diese Einzelpakete in einem Objekt mit `schemaVersion: 1`, `source`, `serviceId`, `packets` (Liste der Einzelpakete) und `errors` (Liste aus `vesselName` und `error`) gebuendelt. Der Live-Dienstabruf erzeugt dieses Objekt automatisch. Doppelte Schiffsergebnisse oder Schiffe aus einem anderen Dienst werden zurueckgewiesen. Ein Importpaket benoetigt keine zusaetzlichen Organisationsdateien im Datenverzeichnis.

Der Live-Modus mit sichtbarem Browser ist erfolgreich verifiziert:

```powershell
.\.venv\Scripts\python.exe import_maersk.py --vessel "MATHILDE MAERSK" --from 2027-01-01 --to 2027-03-01 --headed
```

Die fruehere Ursache war eine nicht uebernommene Auswahl im Maersk-Web-Component: Der sichtbare Text enthielt den Schiffsnamen, aber der interne Schiffsdatensatz war leer. Die Such-URL enthielt deshalb nur `fromDate`, nicht `vesselCode`. Das Skript oeffnet nun nach der Eingabe das Dropdown, klickt die exakt passende `mc-option`, kontrolliert `selecteddata` und wartet auf eine Such-URL mit Vessel-Code. Der sichtbare lokale Lauf fuer MATHILDE MAERSK lieferte erfolgreich alle sieben Aufenthalte mit `vesselCode=2BM`.

Die Schiffsauswahl wartet nicht auf eine allgemeine ARIA-Meldung zur noch leeren Schiffsliste. Das Skript gibt zuerst den Schiffsnamen ein, oeffnet das Dropdown und wartet direkt auf die exakt passende sichtbare Option. ARIA-Statusmeldungen dienen nur zur Fehlerdiagnose. Browserstart, Seitenladen und einzelne UI-Warteschritte haben jeweils maximal 20 Sekunden Wartezeit (einige Schritte sind kuerzer); das ist kein Gesamtlimit fuer den Import. Das serverseitige Gesamtlimit bleibt drei Minuten.

Beim Seitenaufruf wird zunaechst auf die HTTP-Antwort und danach gezielt auf das sichtbare Schiffseingabefeld gewartet, nicht auf `DOMContentLoaded` fuer die gesamte Seite. HTTP-Fehler, fehlende Navigationsantworten und ein nicht geladenes Suchformular werden getrennt gemeldet. HTTP 200 allein bedeutet nicht, dass die JavaScript-Anwendung bereit ist. Im Headless-Modus auf dem Raspberry blieben unter anderem Skripte fuer die Fahrplansuche ausstehend und das Formular leer. Unter Xvfb mit `--headed` wurde dagegen ein vollstaendiger Live-Abruf fuer GDANSK EXPRESS vom 27.10.2026 bis 27.11.2026 erfolgreich geprueft; er lieferte vier Aufenthalte.

Das Ab-Datum des Live-Imports muss innerhalb des von Maersk angebotenen Suchzeitraums liegen. Die Grenzen werden bei jedem Abruf direkt aus dem Datumsfeld der Quellseite gelesen, nicht fest im Programm hinterlegt. Ein Datum ausserhalb dieses Bereichs wird vor dem Suchklick mit einer Fehlermeldung inklusive erlaubtem Zeitraum abgewiesen und nicht automatisch ersetzt. Historische Daten ausserhalb des Live-Suchfensters lassen sich weiterhin aus gespeicherten Text- oder JSON-Dateien importieren.

Der Headless-Modus ist weiterhin nicht durchgehend live verifiziert: "No suggestions found" nach der Namenseingabe kann auch auf nicht geladene Quelldaten hinweisen. In diesem Fall wird der Import mit Statusmeldung abgebrochen; es wird weder ein Vessel-Code erfunden noch eine Zugriffssperre umgangen. Windows verwendet standardmaessig den installierten Edge-Browser, Linux Playwright-Chromium; `--browser chrome` oder `--browser chromium` waehlen andere installierte Browser.

Auf dem Raspberry/Linux werden Browser und Systembibliotheken separat installiert:

```bash
cd ~/HLDashboard
.venv/bin/python -m playwright install chromium
sudo .venv/bin/python -m playwright install-deps chromium
```

Dashboard-Liveimporte benoetigen eine grafische Sitzung oder ein virtuelles Display auf dem Server. Der Importbrowser laeuft auf dem Server, nicht auf dem Geraet, das das Dashboard aufruft. Nur das separate CLI-Skript bietet weiterhin einen Headless-Modus zu Diagnosezwecken.

Alternativ kann auf einem Raspberry ohne Desktop ein virtuelles Display verwendet werden:

```bash
sudo apt install xvfb xauth
xvfb-run -a .venv/bin/python -m flask --app app:create_app run --host=0.0.0.0 --port=5055
```

Der Importprozess verwendet automatisch den Fenstermodus und erbt das virtuelle Display des Servers; ein physischer Bildschirm ist nicht erforderlich.

Die Zeitzone der angezeigten Maersk-Zeiten ist nicht eindeutig belegt. Daher traegt der Import `timeBasis: "unconfirmed"`; es erfolgt keine stille Zeitzonenumrechnung. Vor der Uebernahme muss bestaetigt werden, dass die Zeiten als gemeinsame UTC-Planzeit verwendet werden sollen. Die Quelldaten und Voyage-Nummern bleiben in der Importvorschau sichtbar; die gespeicherte Reise erhaelt Quellenmetadaten.

## Tests ausfuehren

```powershell
python -m unittest -v
```

Gezielte JavaScript-Regressionstests fuer die Reiseauswahl (falls Node.js installiert ist):

```bash
node --test tests/calendar.test.js
```