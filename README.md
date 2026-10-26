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
- Alternativ im selben Dropdown "Hafenuebersicht" waehlen. Links lassen sich mehrere Haefen per Checkbox auswaehlen. Der Kalender zeigt nur diese Haefen untereinander, mit allen Schiffen aller Dienste und ihren Dienstfarben. Die Hafenuebersicht ist eine reine Vergleichsansicht ohne schiffsbezogene Transitzeilen oder Planbearbeitung. Auswahl und Reihenfolge der angewaehlten Haefen werden mit einer benannten Ansicht gespeichert.
- Alle Schiffe desselben Dienstes verwenden dieselbe konfigurierte Farbe, ohne Farbrotation. Angezeigt werden nur die Haefen der ausgewaehlten Hafenfolge, in deren Reihenfolge.
- Einen Aufenthalt ziehen, um ihn stundenweise zu verschieben. Vertikales Ziehen wechselt den Liegeplatz innerhalb desselben Hafens.
- Den rechten Balkenrand ziehen, um die Abfahrt zu aendern.
- Mit "Folgeaufenthalte mitnehmen" werden anschliessende Aufenthalte um denselben Betrag verschoben.
- Einen Balken anklicken: verschiebbares Detailfenster mit Zeiten, Liegeplatz und Transitdauer.
- Die eingetragene Transitdauer ist ein Planungswert. "Ankunft aus Transit neu berechnen" setzt die Ankunft entsprechend und erhaelt die Liegedauer. Die Plausibilitaetspruefung verwendet unabhaengig davon Entfernung / Maximalgeschwindigkeit, nicht den eingetragenen Planungswert.
- Transitzeiten lassen sich auch direkt zwischen den Hafenbloecken bearbeiten. Der Haken berechnet die naechste Ankunft neu und erhaelt die Liegedauer; das Mitnehmen weiterer Aufenthalte folgt dem Schalter oben.
- In der Dienstansicht steht hinter der Liegeplatzzahl "Hafen hinzufuegen". Der Dialog bietet alle registrierten Haefen an und fuegt den gewaehlten Hafen nach dem betreffenden Aufenthalt nur in die aktuelle Reise des ausgewaehlten Schiffs ein. Bei mehreren Besuchen desselben Hafens laesst sich der genaue vorherige Aufenthalt waehlen. Auch ein erneuter Besuch eines bereits enthaltenen Hafens ist moeglich; jeder Besuch hat eine eigene ID, der physische Hafenblock wird nicht dupliziert.
- Der neue Aufenthalt wird mittig zwischen der vorherigen Abfahrt und der folgenden Ankunft positioniert. Seine Liegedauer ist der Durchschnitt der beiden benachbarten Liegedauern, minutengenau gerundet. Bestehende Ankunfts- und Abfahrtszeiten sowie Liegeplaetze bleiben unveraendert. Als Liegeplatz gilt der konfigurierte Dienstdefault, sonst LP 1. Ohne folgenden Aufenthalt ist der Button deaktiviert, weil zwei Nachbarn fuer die Berechnung benoetigt werden.
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
| Beispieldaten und alte Migrationen | Noch im Python-Code enthalten. Als einmalige Demo-Initialisierung bzw. Interpretation alter Dateiformate sinnvoll; fuer ein Produkt spaeter separat ausliefern. Konfigurierte Haefen werden nicht mehr beim Neustart wieder eingefuegt und ein 15-Wochen-Dienst nicht mehr auf 14 umgeschrieben. |
| `repeatWeeks` und `defaultBerths` am Dienst | Derzeit Demo-/Vorlagenmetadaten; vorhandene Reisen verwenden die Werte ihrer Proforma-Stationen und deren `repeatWeeks`. Eine Aenderung am Dienst verschiebt daher keine vorhandenen Proformas. |
| 100 sm / 20 kn | Dokumentierte Ersatzwerte, falls eine Angabe fehlt. Fuer produktive Planung waere eine Pflichtangabe statt stiller Schaetzung sinnvoller. |
| Kollisionspruefung | Prueft derzeit zwei Jahre vor bis zwei Jahre nach den gespeicherten Datumsgrenzen; keine Garantie fuer die unendliche Zukunft. Die Grenze gehoert bei einem groesseren Einsatz in eine Betriebskonfiguration. |
| UI-Vorgaben | Sechs Monate, fuenf Sekunden Aktualisierung, 100 Rueckgaengig-Schritte, Zoom 16 bis 1200 Pixel/Tag und Stundenraster ab 240 Pixel/Tag sind derzeit feste Produktstandards. Bei Bedarf spaeter gemeinsame UI-Konfiguration; nicht jeder Zahlenwert braucht eine JSON-Option. |
| Design und externe Ressourcen | Layoutmasse und Statusfarben koennen zentral im CSS bleiben. Schriften, Symbole und Hafenfoto sind feste Online-Ressourcen; fuer einen Offline-Betrieb lokal bereitstellen. |

## Proforma-Ansicht

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

Neue Schiffe werden aus `data/ships/*.json` erkannt, nicht aus den alten Sicherungs-Unterordnern. Eine bestehende Schiffsdatei kann als Vorlage kopiert werden. Dateiname und `id` muessen uebereinstimmen, beispielsweise `tokyo.json` und `"id": "tokyo"`. Ausserdem Name, Dienst, Geschwindigkeit und die Proforma-Zeiten anpassen. Erforderlich sind `id`, `name`, `serviceId`, `proformas` und `voyages`; `maxSpeedKnots` sollte explizit gesetzt werden. Ein neuer Dienst wird bei Bedarf aus `serviceId` erkannt. Ein zusaetzlicher Registrierungseintrag ist nicht erforderlich. Fehlerhafte JSON-Dateien fuehren zu einer Fehlermeldung; die letzte gueltige Browseransicht bleibt erhalten.

Vorhandene Hafenaufenthalte koennen ueber "Change Rotation" neu geordnet und neue Stationen als Ad-hoc-Aufenthalte in einzelne Reisen eingefuegt werden. Stationen entfernen, Excel-Import, echte separate Betriebssystemfenster und Benutzerverwaltung sind in der Oberflaeche noch nicht enthalten. Der Server ist fuer lokale Einzelnutzung gedacht, nicht fuer produktiven Mehrbenutzerbetrieb. Er bindet nur an `127.0.0.1`.

Schriften, Lucide-Symbole und das Hafenfoto werden online geladen. Die Planung funktioniert auch ohne diese externen Ressourcen; dann nutzt der Browser Ersatzschriften und die beschrifteten Schaltflaechen.

## Flotte und Haefen

Die Reiter "Flotte" und "Haefen" dienen zum Anlegen und Bearbeiten der Stammdaten. Links wird ein vorhandener Datensatz ausgewaehlt; "Schiff anlegen" bzw. "Hafen anlegen" oeffnet ein leeres Formular. "Stammdaten speichern" schreibt direkt die jeweilige Fachdatei. Offene Kalenderentwuerfe muessen vorher uebernommen oder verworfen werden. Ungespeicherte Formulare werden vor einem Wechsel abgefragt.

Bei Schiffen koennen Anzeigename, eindeutiger Importname, Dienst und Maximalgeschwindigkeit geaendert werden. Die technische ID und der Dateiname bleiben bei bestehenden Schiffen stabil. Fuer neue Datensaetze kann eine ID angegeben werden; andernfalls wird sie erzeugt. Der Importname wird normalisiert und muss eindeutig bleiben. Dienstwechsel und Namensaenderung verschieben keine Fahrplaene und veraendern keine Proformas.

Neue Schiffe starten mit leeren `proformas` und `voyages`. Der erste Import erzeugt eine tatsaechliche Reise mit `proformaId: null`; eine Proforma oder Wiederholung wird nicht erfunden. Schiffe ohne Fahrplan bleiben im Kalender auswaehlbar. Spaetere weitere Importe koennen weitere tatsaechliche Reisen hinzufuegen.

Bei Haefen sind Anzeigename, Liegeplatzzahl, Quell-Aliase und nautische Entfernungen bearbeitbar. Aliase werden als JSON-Objekt je Datenquelle eingegeben. Entfernungen gelten fuer beide Richtungen; das Speichern loest doppelte Gegenrichtungswerte auf. Eine Verringerung der Liegeplatzzahl wird abgewiesen, wenn bestehende Proformas oder Reisen dadurch auf ungueltige Liegeplaetze verweisen. Bestehende Aufenthalte werden nicht umnummeriert.

Ein Hafeneintrag kann ein einzelnes Terminal darstellen. Zwei Eintraege duerfen denselben Anzeigenamen, etwa "Rotterdam", haben, benoetigen aber unterschiedliche technische IDs, beispielsweise `rotterdam-mv2` und `rotterdam-rwg`. Bei gleichen Anzeigenamen wird die ID in wichtigen Auswahlfeldern ergaenzt. Der spezifische Terminal-Alias einer Datenquelle hat bei der Importzuordnung Vorrang vor dem allgemeinen Stadtnamen; verbleibende Mehrdeutigkeiten werden nicht geraten.

Die technische Hafen-ID ist der Fremdschluessel in `portId` aller Proforma- und Reiseaufenthalte, in Entfernungslisten, Dienst-Standardliegeplaetzen sowie in lokalen Hafen- und Liegeplatzfiltern. Sie kann im Reiter "Haefen" nach einer Bestaetigung umbenannt werden. Vorher wird auf ID-Kollisionen geprueft. Der Server passt die vorhandenen Fahrplanverweise, Entfernungen und Dienstdefaults gemeinsam an; Ankunft, Abfahrt, Liegeplatz, Aufenthalts-ID und Quellenmetadaten bleiben erhalten. Die Ansichten des bearbeitenden Browsers werden ebenfalls angepasst. In anderen Browsern gespeicherte Ansichten muessen gegebenenfalls neu ausgewaehlt werden. Die ID nicht isoliert direkt in der Hafen-JSON umbenennen, da dann die Referenzmigration fehlt.

Beim Anlegen eines Hafens werden die eingegebenen Entfernungen am neuen Eintrag gespeichert, nicht redundant in jedem anderen Hafeneintrag. Die Berechnung liest A nach B oder ersatzweise den Eintrag B nach A; beide Richtungen verwenden daher denselben Wert. Die bereits vorhandenen Hafenobjekte muessen dafuer nicht dupliziert oder gespiegelt ergaenzt werden. Die Oberflaeche bietet alle anderen registrierten Terminals mit 100 sm als Startwert an. Bei einer ID-Aenderung bleiben auch Entfernungen erhalten, die zuvor nur am Gegenhafen definiert waren. Beim Speichern wird jedes betroffene Paar auf einen einzelnen Eintrag zusammengefuehrt.

Die Verwaltungslogik liegt in `master_data.py`, die Oberflaeche in `static/master_data.js`. Es entstehen keine zusaetzlichen Organisationsdateien. Schiffe werden weiterhin einzeln unter `data/ships/` gespeichert; Haefen bleiben in `data/ports.json`.

## Fahrplandaten importieren

Der Reiter "Datenimport" zeigt Fahrplandaten zunaechst ausschliesslich als Pending-Vorschau. Unter "Umfang" kann zwischen "Einzelnes Schiff" und "Ganzer Dienst" gewaehlt werden. Der fruehere Beispiel-Knopf und sein API-Endpunkt wurden entfernt. Gespeicherte Suchausgaben und normalisierte Text-/JSON-Dateien koennen weiterhin importiert werden; die Beispieldatei unter `examples/` bleibt lediglich als Test- und Skriptfixture erhalten.

"Maersk live abrufen" startet das separate Skript ueber den Server und laedt das Ergebnis automatisch in die Vorschau. Bei "Ganzer Dienst" heisst der Knopf "Dienst live abrufen"; alle aktuell registrierten Schiffe dieses Dienstes werden nacheinander mit ihren eindeutigen Schiffsnamen abgefragt. Die Anzeige nennt das aktuelle Schiff und den Fortschritt. "Browserfenster oeffnen" ist standardmaessig aktiviert, da dieser Modus erfolgreich geprueft wurde. Der Abruf speichert keine Fahrplandaten. Immer nur ein Live-Abruf gleichzeitig ist erlaubt; je Schiff gilt ein Zeitlimit von drei Minuten. Ein Dienstabruf kann entsprechend laenger dauern. Direkt am Uebernahmeknopf stehen die noch offenen Bedingungen.

Der Dienstimport zeigt eine eigene Ergebnistabelle je Schiff sowie schiffsbezogene Zuordnungs- und Differenzzeilen. Abruffehler und fehlende Resultate werden nicht unterschlagen. Solange ein eingeschlossenes Schiff fehlt oder fehlerhaft ist, wird die gemeinsame Uebernahme blockiert. Ein Schiff kann in der Ergebnistabelle ausdruecklich ausgeschlossen werden. Ohne solchen Ausschluss sind alle Schiffe des gewaehlten Dienstes erforderlich. Hafenzuordnungen und "Ignorieren" gelten nur fuer die betreffende Zeile des jeweiligen Schiffs.

Vor "Import fuer Dienst ... uebernehmen" werden alle eingeschlossenen Kandidaten und ihre gemeinsamen Konflikte geprueft. Erst danach werden die betreffenden Schiffsdateien geschrieben. Proformas, ausgeschlossene Schiffe und Schiffe anderer Dienste bleiben unveraendert. Jede Datei wird atomar ersetzt; bei einem gemeldeten Schreibfehler wird eine Wiederherstellung bereits geschriebener Dateien versucht. Das ist keine transaktionale Datenbank mit garantierter Wiederherstellung nach einem Prozess- oder Rechnerabsturz.

Die Vorschau zeigt alle Quellaufenthalte, ihre Hafenzuordnung sowie neue, geaenderte, unveraenderte und entfernte Aufenthalte der betroffenen Reise. Nicht zugeordnete Zeilen blockieren die Uebernahme, solange sie eingeschlossen sind. Sie muessen manuell einem vorhandenen Hafen zugeordnet oder explizit ausgeschlossen werden. Im Beispiel sind beide Suez-Aufenthalte ungeklärt, da dieser Hafen noch nicht in den Fachdaten vorhanden ist. Es werden keine unbekannten Haefen automatisch angelegt oder stillschweigend verworfen.

Die Uebernahme betrifft nur die gewaehlte Runde des gefundenen Schiffs, nie die Proforma. Sie verlangt die Bestaetigung der Zeitbasis sowie bei entfernten Aufenthalten eine gesonderte Bestaetigung. Bereits offene Kalenderentwuerfe desselben Schiffs blockieren die Uebernahme; andere Schiffsentwuerfe bleiben erhalten. Eine geaenderte Datenpruefsumme erzwingt eine neue Vorschau. Der Zeitraum bzw. die Zeilenauswahl muss auf eine Runde begrenzt werden; mehrere Runden werden nicht automatisch zusammengefuehrt.

**Importgrenze:** Bei jeder Quelle werden nur Aufenthalte mit einer Ankunft innerhalb des ausgewaehlten Fensters "Ab" bis "Bis" geaendert oder als entfernt vorgeschlagen. Beide Tage sind inklusive. Frueher begonnene Aufenthalte bleiben vollstaendig erhalten, auch wenn ihre Abfahrt erst nach dem Startdatum liegt. Auch Aufenthalte nach dem Enddatum bleiben unveraendert. Dies gilt ebenfalls fuer Dienstimporte. Der in der Oberflaeche gewaehlte Zeitraum hat Vorrang vor dem Zeitraum in einer geladenen Importdatei. Zeilen ausserhalb des Fensters werden als geschuetzt markiert; nur neue bzw. geaenderte Aufenthalte erhalten neu berechnete Transitwerte. Andere Runden bleiben unangetastet.

Fehlt im gelieferten Ausschnitt ein vergangener Aufenthalt, wird er daher nicht mehr entfernt. Bei einem neuen Schiff ohne Plan wird nur der aktuelle Importzeitraum als tatsaechliche Reise angelegt. Es werden keine historischen Aufenthalte oder Proformas rekonstruiert.

### Schiff und Hafen-Aliase

`vesselName` ist der datenquellenuebergreifend eindeutige Schiffsname. Er wird fuer die Zuordnung grossgeschrieben und bezueglich Leerzeichen normalisiert; doppelte Namen werden abgewiesen. Fuer Mathilde lautet er `MATHILDE MAERSK`. Die interne `id` und der bestehende Dateiname bleiben als technische Referenzen erhalten. Fehlt `vesselName` bei aelteren Schiffen, wird der bisherige Anzeigename verwendet.

Am jeweiligen Hafen in `data/ports.json` werden alternative Namen je Datenquelle gespeichert, beispielsweise:

```json
"aliases": {
	"maersk": ["Hamburg", "Eurogate Container Terminal Hamburg"]
}
```

Andere Quellen koennen eigene Listen unter ihrem Quellenbezeichner erhalten. Mehrdeutige Treffer werden nicht automatisch ausgewaehlt. Manuelle Zuordnungen in der Vorschau gelten nur fuer diesen Import; dauerhafte Aliase werden in der Hafen-JSON gepflegt.

### Separates Maersk-Skript

Das eigenstaendige `import_maersk.py` erzeugt nur ein normalisiertes Import-JSON und schreibt nie direkt in Schiffsdateien. Der dateibasierte Modus ist getestet:

```powershell
.\.venv\Scripts\python.exe import_maersk.py --input examples/maersk_mathilde_2027.txt --vessel "MATHILDE MAERSK" --from 2027-01-01 --to 2027-03-01 --output maersk_pending.json
```

Die erzeugte Datei kann im Import-Reiter geoeffnet werden. Ohne `--output` wird das JSON auf stdout geschrieben. Das gemeinsame Format besitzt `schemaVersion: 1`, `source`, `vesselName`, `fromDate`, `toDate`, `fetchedAt`, `timeBasis` und `calls`; jede Zeile enthaelt eine eindeutige `id`, `portName`, `terminalName`, `arrival`, `departure` sowie optional die Quell-Voyagenummern. Weitere Skripte koennen dasselbe Format mit einem anderen `source` erzeugen.

Fuer einen Dienstimport werden diese Einzelpakete in einem Objekt mit `schemaVersion: 1`, `source`, `serviceId`, `packets` (Liste der Einzelpakete) und `errors` (Liste aus `vesselName` und `error`) gebuendelt. Der Live-Dienstabruf erzeugt dieses Objekt automatisch. Doppelte Schiffsergebnisse oder Schiffe aus einem anderen Dienst werden zurueckgewiesen. Ein Importpaket benoetigt keine zusaetzlichen Organisationsdateien im Datenverzeichnis.

Der Live-Modus mit sichtbarem Browser ist erfolgreich verifiziert:

```powershell
.\.venv\Scripts\python.exe import_maersk.py --vessel "MATHILDE MAERSK" --from 2027-01-01 --to 2027-03-01 --headed
```

Die fruehere Ursache war eine nicht uebernommene Auswahl im Maersk-Web-Component: Der sichtbare Text enthielt den Schiffsnamen, aber der interne Schiffsdatensatz war leer. Die Such-URL enthielt deshalb nur `fromDate`, nicht `vesselCode`. Das Skript oeffnet nun nach der Eingabe das Dropdown, klickt die exakt passende `mc-option`, kontrolliert `selecteddata` und wartet auf eine Such-URL mit Vessel-Code. Der sichtbare lokale Lauf fuer MATHILDE MAERSK lieferte erfolgreich alle sieben Aufenthalte mit `vesselCode=2BM`.

Der Headless-Modus ist weiterhin nicht zuverlaessig: In der geprueften Umgebung lieferte er bereits beim Laden der Schiffsliste "No suggestions found". Die Ursache dafuer ist nicht belegt; es wird keine Zugriffssperre behauptet oder umgangen. Fuer den bestaetigten Ablauf `--headed` bzw. das aktivierte Browserfenster im Import-Reiter verwenden. Windows verwendet standardmaessig den installierten Edge-Browser; `--browser chrome` oder `--browser chromium` waehlen andere installierte Browser. Fuer Chromium kann `python -m playwright install chromium` erforderlich sein.

Die Zeitzone der angezeigten Maersk-Zeiten ist nicht eindeutig belegt. Daher traegt der Import `timeBasis: "unconfirmed"`; es erfolgt keine stille Zeitzonenumrechnung. Vor der Uebernahme muss bestaetigt werden, dass die Zeiten als gemeinsame UTC-Planzeit verwendet werden sollen. Die Quelldaten und Voyage-Nummern bleiben in der Importvorschau sichtbar; die gespeicherte Reise erhaelt Quellenmetadaten.

## Tests ausfuehren

```powershell
python -m unittest -v
```