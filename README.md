# Phoca - Flask-Prototyp

Lokale Liegeplatzplanung fuer die in den JSON-Dateien konfigurierten Schiffe, Haefen und Dienste.

## Anforderungskatalog

Dieser Katalog ist die gemeinsame Grundlage fuer fachliche Abstimmungen, Erweiterungen und spaetere Abnahmetests. Die IDs bleiben bei Aenderungen erhalten; neue Anforderungen erhalten neue IDs. Anforderungen werden nicht allein durch eine Codeaenderung als fachlich abgenommen betrachtet.

**Stand der Bestandsaufnahme: 27.10.2026.** "Vorhanden" beschreibt eine aktuell angebotene Funktion, keine vollstaendige fachliche Freigabe. "Teilweise" bedeutet: Ein Teil ist vorhanden, aber die Anforderung oder ihre Sonderfaelle sind noch nicht vollstaendig abgedeckt. "Offen" bedeutet: Umsetzung oder Entscheidung steht aus. Die Spalte "Abstimmung" haelt offene Regeln fest; Vorschlaege darin sind noch keine beschlossenen Anforderungen. Die folgenden Bedienungs- und Technikabschnitte beschreiben den bisherigen Stand und sind bei Aenderungen mit diesem Katalog abzugleichen.

**Fortschreibung 27.10.2026 (Abgleich mit der Sprachnachricht eines potentiellen Nutzers):** Neue Anforderungen tragen den Zusatz "(neu)" in der Spalte "Stand" und sind noch nicht fachlich abgestimmt. Bestehende IDs und ihr Wortlaut sind unveraendert; Bezuege zu neuen Anforderungen stehen in der Spalte "Abstimmung" als "Ergaenzung 27.10.2026". Die Rueckverfolgung vom Nutzerwunsch zu den IDs steht am Ende des Katalogs.

### Glossar

| Begriff | Bedeutung in diesem Projekt |
| --- | --- |
| Proforma | Dienstvorlage je Dienst, schiffsunabhaengig: je Hafen ein Zeitfenster (von-bis). Wird selten angepasst. |
| LTS (Long Term Schedule) | Excel-Plan, der regelmaessig neu verteilt wird. Enthaelt die vereinbarten Fenster fuer mehrere Regionen (z. B. Asien und Europa) und die Zuordnung Schiff zu Position in der Rotation. |
| Ist / Entwurf | Tatsaechlicher bzw. geplanter Fahrplan eines Schiffes; weicht ggf. vom Soll ab (Verspaetung, Vorlauf). |
| Delta | Abweichung des Ist/Entwurfs vom Soll-Fenster (frueh/spaet) in Stunden. Bezugsbasis siehe SF-017. |
| Umlauf / Voyage-Paar | Eine Reise mit zwei Voyage-Nummern: Westbound (kommt aus Asien nach Europa) und Eastbound (Rueckreise). Dazwischen liegt der Turnport in Europa. |
| Turnport | Hafen in Europa, ab dem die Reise von Westbound auf Eastbound wechselt. |
| Slide | Ein ganzer Dienst rutscht um eine oder mehrere Wochen (eine Woche wird "geblankt"); Schiff A uebernimmt die Position von Schiff B usw. Danach wird in der Regel ein neuer LTS verteilt. |
| Blank Sailing | Bewusst entfallene Runde. Nicht gleichzusetzen mit fehlenden Daten. |
| Change of Rotation | Die Hafenreihenfolge einer Rotation aendert sich. |
| Phase-in / Phase-out | Ein Schiff steigt in einen Dienst ein bzw. aus (z. B. Dock, andere Verwendung, andere Region). Im LTS erscheint meist nur das Phase-in-Schiff offiziell; das Phase-out-Schiff laeuft parallel weiter. |
| Anlauf-Rolle | Rolle eines Schiffes bei einem Anlauf: nur Laden, nur Loeschen, beides oder ausgelassen. Relevant vor allem im Phase-in/out-Paar. |
| Feeder-Verbindung | Ladung wird in einem anderen Hafen gebuendelt und zum Phase-in-Schiff weitergeleitet. |
| Moves | Geplante Containerbewegungen je Liegefenster, aufgeteilt in eigene (Hapag-Lloyd) und Partner. |

### Verantwortungsgrenzen

| Bereich | Verantwortung | Abgrenzung |
| --- | --- | --- |
| Frontend: UI | Navigation, Kalender, Bedienung, Entwurfsanzeige, lokale Ansichten, Darstellung von Plugin-Daten. | Entscheidet keine verbindliche Reiseidentitaet, Importzuordnung oder Wetter-/Tidewarnschwelle. |
| Backend: Fachlogik | Schiffseinsatz, Reiseidentitaet, Proforma-Zuordnung, Wiederholungen, Hafenfolge, Plausibilitaets- und Konfliktregeln. | Soll unabhaengig von Kalenderlayout und Datenanbieter pruefbar sein. |
| Backend: Daten und Schnittstellen | Persistenz, konkurrierende Aenderungen, Importadapter, Datenvalidierung, Anmeldung und Zugriffspruefung. | Anbieterformate werden vor der fachlichen Verarbeitung normalisiert. |
| Backend: Plugins | Datenbeschaffung und Aufbereitung fuer Wind und relative BSH-Tide; Einheiten, Schwellen und kritische Zeitraeume. | Liefern einen definierten Datenvertrag, keine beliebigen UI-Fragmente und keine stillen Fahrplanaenderungen. |
| Frontend: Plugin-Renderer | Zeitposition, Zoomraster, Pfeile, Werte, Warnzeitbaender und Ein-/Ausblenden. | Wertet keine eigenen meteorologischen oder nautischen Grenzwerte aus. |

### Frontend: Oberflaeche und Bedienung

| ID | Anforderung / pruefbares Verhalten | Stand | Abstimmung / Sonderfaelle |
| --- | --- | --- | --- |
| FE-UI-001 | Das Werkzeug ist fuer Desktop-Nutzung ausgelegt; alle Kernablaeufe sind dort bedienbar. | Vorhanden | Mobile Nutzung und mobile Browserpruefungen sind derzeit nicht gefordert. |
| FE-UI-002 | Liegeplatzplanung, Proformas, Datenimport, Flotte und Haefen sind getrennte Arbeitsbereiche. | Vorhanden | Weitere Bereiche nur bei eigenstaendigem Arbeitsablauf ergaenzen. |
| FE-UI-003 | Ein gemeinsamer Kalender stellt Haefen, Liegeplaetze und Transitzeilen mit frei waehlbarem Zeitraum, Zoom und Scrollposition dar und nutzt die verfuegbare Fensterbreite/-hoehe auch beim Browserzoom. Die linke Beschriftungsspalte richtet sich nach dem laengsten angezeigten Hafennamen samt Bedienelementen. | Vorhanden | Keine zentrierte feste Maximalbreite fuer die Planung; genaue Flaechennutzung siehe FE-UI-014. Mindest-/Maximalzeitraum und Leistungsziel fuer grosse Flotten noch festlegen. |
| FE-UI-004 | Auswahl, Dienstfarbe, offener Entwurf, gespeicherter Fahrplan und Proforma sind unterscheidbar; Proformas sind schraffiert. | Vorhanden | Farben und Symbole sollen auch bei Warnbaendern und Dark Mode lesbar bleiben. |
| FE-UI-005 | Ein Aufenthalt laesst sich zeitlich verschieben, verlaengern und auf einen anderen Liegeplatz desselben Terminals setzen. | Vorhanden | Verschiebung zwischen Terminals und Bedienung ueber Tastatur gesondert abstimmen. |
| FE-UI-006 | Das Mitnehmen folgender Aufenthalte ist waehlbar; Vorschau, Rueckgaengig/Wiederholen, Verwerfen und Einzeluebernahme bleiben getrennt. | Vorhanden | Mehrere abhaengige Schiffsentwuerfe und gemeinsame Uebernahme noch abstimmen. |
| FE-UI-007 | Eine Hafenuebersicht zeigt ausgewaehlte Terminals und alle dortigen Schiffe dienstuebergreifend. | Vorhanden | Derzeit Vergleichsansicht, keine dienstuebergreifende Bearbeitung. Ergaenzung 27.10.2026: Fuer Phase-out-Szenarien im Hafen (SF-015) ist ggf. Bearbeitung noetig; siehe FE-UI-017, FE-UI-019, FE-UI-020. |
| FE-UI-008 | Benannte Ansichten speichern lokale Kalenderoptionen einschliesslich einklappbarer Flottenleiste; Liegezeit-Rechtecke lassen sich bei ausgeklappten Haefen optional ausblenden. | Vorhanden | Browserlokal und je Benutzer; keine rechneruebergreifende Synchronisation zugesagt. |
| FE-UI-009 | Beim Wechsel von der Planung zum Datenimport wird das ausgewaehlte Schiff uebernommen; fremde alte Importdaten werden zurueckgesetzt. | Vorhanden | Importziel und offene Entwuerfe muessen eindeutig bleiben. |
| FE-UI-010 | Konfigurierbare Haefen/Terminals, Schiffe und Proforma-Zuordnungen koennen ueber Formulare bearbeitet werden. | Vorhanden | Sichere Loesch-/Stilllegungsablaeufe fehlen als eigene Fachentscheidung. Ergaenzung 27.10.2026: Schiffsdatenfelder siehe BE-DAT-005 und FE-UI-023. |
| FE-UI-011 | Der Proforma-Bereich stellt Dienstvorlage und schiffsspezifischen Versatz getrennt dar. | Teilweise | Der aktuelle Bereich ist fuer Fahrplandetails schreibgeschuetzt; vollstaendigen Editor, Versionsanlage und Freigabe abstimmen. |
| FE-UI-012 | Hell-/Dunkelmodus, klare Trennung der Hafen-/Transitbloecke und angeheftete Hafenbuttons bleiben bei Zoom und Scrollen erhalten. | Vorhanden | Transitzeilen sind oben und unten mit gleich starken, kontrastreichen Linien getrennt. Zwischen Hafenname und "+ Hafen hinzufuegen" steht keine zusaetzliche Liegeplatzanzahl. Ergaenzung 27.10.2026: Pruefen, ob "+ Hafen hinzufuegen" einen Ad-hoc-Anlauf (BE-PLAN-009) oder nur eine Kalenderzeile anlegt; siehe FE-UI-021. |
| FE-UI-013 | Die Flotten-/Hafenauswahlleiste ist ueber einen Schalter links neben "Liegeplatzbelegung" ein- und ausklappbar; eingeklappt erhaelt der Kalender die frei werdende Breite. | Vorhanden | Aktuelles Schiff, offene Entwuerfe und Kalenderoptionen bleiben erhalten. Zustand je Benutzer im Browser und in benannten Ansichten speichern; der Schalter bleibt zum Wiedereinblenden erreichbar. |
| FE-UI-014 | Der Planungs-Hauptbereich nutzt die gesamte Desktopfensterbreite mit schmalen Raendern; der Kalender fuellt den verbleibenden Platz bis zum unteren Fensterrand. | Vorhanden | Verkleinern per Browserzoom darf keine grosse Leerflaeche unten oder seitlich erzeugen. Kalender scrollt innerhalb seiner Flaeche; Formularbereiche bleiben normal scrollbar. Desktoppruefung auch auf grossen Fenstern, keine Mobilpruefung. |
| FE-UI-015 | Je Anlauf wird die Abweichung vom Soll-Fenster (frueh/spaet in Stunden) angezeigt, auch im offenen Entwurf und waehrend des Verschiebens. | Offen (neu) | Darstellung als Badge, Farbe und/oder Fensterrahmen am Balken abstimmen. Berechnung liegt im Backend (BE-PLAN-015). |
| FE-UI-016 | Beim Verschieben zeigt die UI Puffer bis Fensterende und Folgehafen sowie betroffene Schiffe und Dienste (Hervorhebung plus Liste). | Offen (neu) | Nutzt BE-PLAN-016. Frage des Nutzers: "Kann ich das, ohne in Hafen B zu spaet zu sein?" und "Wen beeinflusse ich negativ?". |
| FE-UI-017 | Filter nach Dienst, Region (z. B. nur Europa) und Hafen sind kombinierbar. Die Dienstansicht zeigt die Rotation, die Hafenansicht alle Dienste. | Teilweise (neu) | Hafenansicht ueber FE-UI-007 vorhanden; Dienst- und Regionsfilter in Kombination offen. Bezug BE-PLAN-021. |
| FE-UI-018 | Slide und LTS-/Proforma-Import haben einen Dialog mit Diff-Vorschau (alt zu neu), Mapping der Runden und ausdruecklicher Bestaetigung. | Offen (neu) | Zu BE-PLAN-017 und BE-INT-008. Ergaenzt FE-UI-009. |
| FE-UI-019 | Phase-in/out-Paare sind darstellbar: Begleitspur oder Verknuepfungslinie, Rolle je Anlauf (Laden/Loeschen/beides/ausgelassen) und beide Voyage-Nummern. | Offen (neu) | Eine Zeile oder zwei verknuepfte Zeilen? Erwartete Ueberlappung darf nicht wie ein Fehler aussehen (BE-PLAN-020). SF-015. |
| FE-UI-020 | Freie Fenster je Liegeplatz/Terminal werden in der Hafenansicht hervorgehoben. | Offen (neu) | Zu BE-PLAN-022. Hamburg Eurogate als Referenzfall: Kapazitaetsluecke fuer ein Phase-out-Schiff erkennen. |
| FE-UI-021 | Die Hafenreihenfolge einer Rotation laesst sich im Tool aendern (Change of Rotation) und Haefen koennen hinzugefuegt werden; ein Hafen der Rotation oder ein fremder Hafen. | Teilweise (neu) | Backend-Seite: BE-PLAN-009/010. Dauerhaft oder einmalig siehe SF-005. |
| FE-UI-022 | Terminal-Stammdaten bieten Quicklinks (Terminal Page, Liegeplatzplan) zum Oeffnen in neuem Tab. Es werden keine Zugangsdaten gespeichert. | Offen (neu) | Ersetzt das heutige manuelle Oeffnen vieler einzelner Webseiten. Kein Scraping passwortgeschuetzter Seiten. |
| FE-UI-023 | Schiffsdaten (u. a. E-Mail-Adresse des Schiffes, Laenge, Breite) lassen sich im Formular hinterlegen und per Klick auf ein Schiff einsehen. | Offen (neu) | Zu BE-DAT-005. Anzeige als Seitenpanel oder Tooltip abstimmen; Quicklinks siehe FE-PLG-012. |
| FE-UI-024 | "Standort & Hafen-Plugins" im Hafentab ist ausklappbar und beim Auswaehlen eines Hafens standardmaessig eingeklappt. Wind und Tide haben getrennte Standortlisten mit unabhaengigen Namen, Website-Links, Koordinaten und Aktivierungen; Wind zusaetzlich eigene Warnschwellen. | Vorhanden | Je Plugin unabhaengig null bis 16 Standorte hinzufuegen oder entfernen. Alte gemeinsame Standorte werden beim Speichern getrennt uebernommen. Amtliche Pegelzuordnung und Tidewarnregeln bleiben Teil von BE-PLG-005/006. |

### Frontend: Plugin-Darstellung

| ID | Anforderung / pruefbares Verhalten | Stand | Abstimmung / Sonderfaelle |
| --- | --- | --- | --- |
| FE-PLG-001 | Hafenleisten koennen mehrere Plugin-Spuren aufnehmen, ohne Hafenname, Aktionen oder Planungsbalken zu ueberdecken. | Vorhanden | Platzverteilung bei vielen Plugins oder sehr schmalen Desktopfenstern festlegen. |
| FE-PLG-002 | Plugin-Werte werden anhand ihrer UTC-Zeit im Kalender positioniert; beim Herauszoomen entstehen gleichmaessige feste Zeitraster von 3/6/12/24/48/96 Stunden usw., passend zum verfuegbaren Platz. | Vorhanden | Scrollen verschiebt das Raster nicht. Originalwerte am Rasterzeitpunkt zeigen, nicht den staerksten Wert an einer anderen Uhrzeit. Fehlende Werte nicht erfinden; Warnzeitbaender nach FE-PLG-004 separat erhalten. |
| FE-PLG-003 | Wind wird in kn mit reiner Richtungsspitze aus zwei Strichen angezeigt, ohne Stamm und ohne Kreis. Ueber 10 kn erscheinen ganze Zahlen, bis einschliesslich 10 kn maximal eine Nachkommastelle. | Vorhanden | Die Spitze darf die Zahl in keiner Windrichtung ueberdecken und zeigt die Richtung, in die der Wind weht. Herkunftsrichtung und genauer Wert stehen im Tooltip; siehe FE-PLG-010. |
| FE-PLG-004 | Der gesamte vom Plugin als kritisch gemeldete Zeitraum erscheint als durchgehendes rotes Hintergrundband, auch zwischen ausgeblendeten Zahlenrasterpunkten. | Vorhanden | Nur der Zeitraumshintergrund ist rot; Windfelder und Pfeilhintergruende bleiben transparent, ohne zusaetzliche rote Einzelkaesten. Unkritische Nachbarwerte nicht kuenstlich als kritisch umfaerben. Fachliche Zeitgrenzen liefert das Plugin im verfuegbaren Datenraster; Luecken nicht ueberbruecken. |
| FE-PLG-005 | Ein Wind-Button direkt rechts neben "Heute" in der Kalenderkopfzeile schaltet Windwerte und Warnzeitbaender gemeinsam ein/aus; derselbe Zustand wird im Plugin-Menue angezeigt. | Vorhanden | Button-Zustand erkennbar darstellen und je Benutzer im Browser speichern. Die gemeinsame Hafenaktivierung wird dadurch nicht ueberschrieben; weitere Plugins bleiben getrennt schaltbar. |
| FE-PLG-006 | Ladefehler, fehlende Koordinaten, veraltete Daten und Zeitraeume ohne Daten zerstoeren den Kalender nicht. | Vorhanden | Verhalten bei ausschliesslich teilweise vorhandenen Zeitreihen weiter konkretisieren. |
| FE-PLG-007 | Hoch-/Niedrigwasser erscheinen als Punkte, verbunden durch eine blaue sinusartige Kurve; relevant sind relative Lage und UTC-Zeitpunkt, nicht Meterhoehen. | Teilweise | Relative Kurve aus offiziellen BSH-Ereignissen mit expliziter Pegelwahl vorhanden, auch fuer Hamburg. Datenluecken bleiben offen. Echte Hoehenskalierung, Jahresdateien, getrennte Darstellung astronomischer und wetterbeeinflusster Kurven sowie Tidewarnbaender sind noch offen; manuell vordefinierte Tidenfenster siehe BE-PLG-006. |
| FE-PLG-008 | Windanzeigen werden so dicht wie lesbar dargestellt; beim Herauszoomen wird erst ausgeduennt, wenn Zahl/Pfeil nicht mehr ausreichend Platz haben. Die Abstaende bleiben regelmaessig. | Vorhanden | Aktuelle UI-Referenz: Feld 32 x 34 CSS-Pixel, Mindestabstand fuer Rasterwahl 37 CSS-Pixel. Dies ersetzt die zwischenzeitlichen 64/40/32-Pixel-Abstaende. Schriftgroesse nicht zum Verdichten reduzieren; bei spaeteren Aenderungen Lesbarkeit und alle Richtungen pruefen. |
| FE-PLG-009 | Neue Winddaten werden nach Ablauf der vom Server gemeldeten Cache-Laufzeit automatisch in der bestehenden Website nachgeladen; manuelles Neuladen ist nicht erforderlich. | Vorhanden | Server liefert `refreshAfterSeconds`; kein Keepalive zur Nutzererkennung hinzufuegen. Serverseitigen Abruf, Stundenfrist, Dateicache und Neustartverhalten getrennt in BE-PLG-003 regeln. |
| FE-PLG-010 | Wind-Tooltips zeigen Zeitpunkt in UTC, Einheit, genaueren Windwert, meteorologische Herkunftsrichtung, Datenquelle und Abrufstand; Warnbaender nennen Anfang, Ende und Warnbeschreibung. | Vorhanden | Gerundete Zahl und Richtungsspitze ersetzen nicht den genauen Wert bzw. die Herkunftsrichtung im Tooltip. Veraltete Daten kennzeichnen; die angezeigte Genauigkeit bleibt durch die Anbieterwerte begrenzt. |
| FE-PLG-011 | Die UI stellt nur den vom Anbieter tatsaechlich gelieferten Zeitbereich dar und laesst fehlende Werte offen, auch wenn ein laengerer Horizont angefragt wurde. | Vorhanden | Aktuell bis 16 Kalendertage einschliesslich Heute und zehn Tage Rueckblick angefragt, siehe BE-PLG-002. Ausserhalb des Zeitfensters Hinweis statt erfundener Windwerte; keine Vollstaendigkeit bis zum letzten angefragten Zeitpunkt zusagen. |
| FE-PLG-012 | Ein Klick auf ein Schiff bietet Quicklinks: Live-Position bei MarineTraffic (ueber IMO/MMSI) und Wetter bei Windy (ueber aktuelle Position). | Offen (neu) | Zunaechst nur Links, keine eingebetteten Fremddaten. Eigene AIS-Positionsdaten nur nach Lizenzpruefung als Plugin (BE-PLG-007). Setzt IMO/MMSI in den Schiffsdaten voraus (BE-DAT-005). |
| FE-PLG-013 | Jeder eingeblendete Pluginstandort besitzt eine eigene beschriftete Spur mit eigenen Werten und Warnzeitraeumen. Die erste Pluginspur liegt auf gleicher Hoehe wie der Hafenname; weitere Standorte vergroessern das Hafenband nach unten. | Vorhanden | Beispiel Hamburg/Cuxhaven: verschiedene Windgrenzen duerfen unterschiedliche rote Bereiche ergeben. Sichtbar ist nur der frei benennbare Standortname direkt vor den Werten; Plugin, Einheit und Warnschwelle stehen im Tooltip. Leere Schwelle unterdrueckt nur deren Warnung. |
| FE-PLG-014 | Ein Klick auf eine Windzahl oeffnet den am zugehoerigen Standort gespeicherten HTTPS-Link in einem neuen Tab. | Vorhanden | Windy ist vorbelegt, aber Kartenausschnitt und URL sind bearbeitbar. Keine erzwungene URL-Neuberechnung aus Koordinaten, keine Zugangsdaten und kein Zugriff des Ziel-Tabs auf das Ursprungsfenster. |

### Konkretisierte UI-Abnahmebeispiele

Diese Beispiele dokumentieren die zuletzt praezisierten UI-Wuensche. Sie ersetzen keine fachliche Abnahme; insbesondere legt das Plugin die Wettergrenzen fest, nicht der Renderer.

| Anforderungen | Ausgangslage / Aktion | Erwartete Anzeige |
| --- | --- | --- |
| FE-PLG-002/008 | Herauszoomen reduziert ein 3-Stunden-Raster auf 6, 12 oder 24 Stunden; anschliessend horizontal scrollen. | Die vorhandenen Rasterwerte behalten gleichmaessige Zeit-/Pixelabstaende. Kein Springen zu zufaellig staerkeren Werten innerhalb eines Zeitblocks. |
| FE-PLG-003/010 | Windwert 9,6 kn bzw. 10,6 kn; Richtung nacheinander in acht Hauptrichtungen anzeigen. | Zahl 9,6 bzw. 11 mit reiner Pfeilspitze ohne Kreis/Stamm. Spitze und Zahl beruehren sich nicht; der Tooltip erhaelt den genaueren Wert. |
| FE-PLG-004 | Im 6-Stunden-Anzeigeraster sind 00 und 06 Uhr unkritisch, das Plugin meldet 03-06 Uhr als kritisch. | Das Band 03-06 Uhr bleibt rot sichtbar, obwohl um 03 Uhr keine Zahl gezeichnet wird. Keine roten Kaesten hinter 00/06 Uhr; keine kuenstliche Ausdehnung auf 00-06 Uhr. |
| FE-PLG-005 | Wind ueber den Button neben "Heute" ausschalten, dann Plugin-Menue oeffnen und die Seite neu laden. | Zahlen und Warnbaender verschwinden gemeinsam; Menue und Button zeigen "aus". Die gespeicherte Benutzerwahl bleibt erhalten. |
| FE-UI-008/013 | Flottenleiste einklappen, benannte Ansicht speichern, wieder ausklappen und gespeicherte Ansicht laden. | Kalender gewinnt die Seitenleistenbreite; die Ansicht stellt den eingeklappten Zustand wieder her, ohne Auswahl oder offene Planentwuerfe zu verlieren. |
| FE-UI-003/014 | Grosses Desktopfenster nutzen oder per Browserzoom mehr Uebersicht schaffen. | Kalender nutzt die verfuegbare Breite und endet weiterhin am unteren Fensterrand; kein altes 2400-Pixel-Breitenlimit bzw. 1000-Pixel-Hoehenlimit. |

### Backend: Schiffe, Reisen und Proformas

| ID | Anforderung / pruefbares Verhalten | Stand | Abstimmung / Sonderfaelle |
| --- | --- | --- | --- |
| BE-PLAN-001 | Ein Schiff besitzt eine stabile technische Identitaet; der Importname bleibt in seiner Schreibweise erhalten und wird fuer Zuordnung normalisiert verglichen. | Vorhanden | Umgang mit Umbenennung, IMO-Nummer und wiederverwendeten Namen festlegen. Ergaenzung 27.10.2026: IMO/MMSI als Schiffsdatenfelder siehe BE-DAT-005. |
| BE-PLAN-002 | Proformas gehoeren dem Dienst; Schiffe referenzieren sie mit Wirksamkeitsdatum und ganzzahligem Wochenversatz. | Vorhanden | Schiffseinsaetze in mehreren Diensten und unterjaehrige Wechsel gesondert definieren. Ergaenzung 27.10.2026: Der LTS liefert die Schiffsposition in der Rotation; Ableitung des Wochenversatzes aus der Position abstimmen (BE-INT-007/008). |
| BE-PLAN-003 | Solange eine Zuordnung gilt, werden Reisen im Proforma-Zyklus wiederholt; eine spaetere Zuordnung ersetzt die vorherige fuer neue Runden. | Vorhanden | Explizites Gueltigkeitsende ohne Nachfolgezuordnung ist noch offen; siehe SF-002. |
| BE-PLAN-004 | Ein gespeicherter tatsaechlicher Fahrplan ersetzt nur seine nominelle Runde und bleibt bei zeitlicher Verschiebung dieser Runde zugeordnet. | Vorhanden | Die aktuelle Identitaet ist der nominelle Startdatumsschluessel, nicht eine unabhaengige Reise-ID. Ergaenzung 27.10.2026: Ein Slide (BE-PLAN-017) verschiebt die nominellen Runden; die Umlauf-Identitaet ueber das Voyage-Paar (BE-PLAN-018) soll den Schluessel entkoppeln. |
| BE-PLAN-005 | Die Verknuepfung zwischen tatsaechlicher Reise und konkreter Proforma-Runde bleibt bei grosser Verspaetung und erneutem Import erhalten. | Teilweise | Gespeicherte Schluessel bleiben stabil; erneuter Import ohne Reisevorgabe ordnet derzeit zeitbasiert zu. Anbieter-Reisenummern werden noch nicht zur Wiedererkennung genutzt. Ergaenzung 27.10.2026: Voyage-Paar als Vorrangschluessel vor zeitlicher Naehe, siehe BE-PLAN-018. |
| BE-PLAN-006 | Ein gespeicherter Ist-Fahrplan bleibt bei Aenderung einer Dienstvorlage unveraendert. | Vorhanden | Unveraenderliche Referenzversion fuer spaetere Plan-/Ist-Vergleiche ist noch zu definieren. Ergaenzung 27.10.2026: Gilt sinngemaess fuer LTS-Updates (BE-INT-008). |
| BE-PLAN-007 | Proforma-Versionen, Zuordnungswechsel und Wochenversatz liefern eine eindeutige gueltige Runde. | Teilweise | Wechsel waehrend einer laufenden Reise, Luecken, Enddatum und Referenzhistorie abstimmen. |
| BE-PLAN-008 | Wiederholte Anlaeufe desselben Hafens besitzen getrennte Aufenthalts-IDs, auch wenn Terminal und Reise identisch sind. | Vorhanden | Importzuordnung bei mehreren gleichnamigen Besuchen muss gegen Verwechslung abgesichert werden; siehe SF-006. |
| BE-PLAN-009 | Ad-hoc-Anlaeufe aendern nur die betroffene Reise, nicht automatisch die Dienstvorlage oder andere Runden. | Vorhanden | Anlauf nach dem letzten Hafen, ausgelassene Anlaeufe und bewusste Dauerabweichungen abstimmen. Ergaenzung 27.10.2026: Nutzer nennt Hinzufuegen eines Hafens der Rotation oder eines fremden Hafens (FE-UI-021). |
| BE-PLAN-010 | Change of Rotation ordnet die bestehende Runde neu und berechnet Transitwerte zwischen den neuen Nachbarn. | Teilweise | Aktuell chronologische Reparatur ohne Zeitaenderung; bewusste neue Reihenfolge und dauerhafter Rotationswechsel sind gesonderte Anforderungen. Ergaenzung 27.10.2026: Bedienung siehe FE-UI-021. |
| BE-PLAN-011 | Transitpruefung beruecksichtigt Entfernung und Schiffsgeschwindigkeit; Liegeplatz- und Folgereiseueberschneidungen werden erkannt. | Vorhanden | Gleiches Terminal in Folge, fehlende Streckenwerte, Sicherheitsabstaende und tatsaechliche Hafenwechsel abstimmen. |
| BE-PLAN-012 | Die Konfliktbehandlung unterscheidet manuelle Planuebernahme und Import. | Vorhanden | Derzeit blockieren neue manuelle Konflikte die Uebernahme; Importkonflikte werden gewarnt und gespeichert. Verbindliche Ausnahmen/Freigaben festlegen. Ergaenzung 27.10.2026: Erwartete Ueberlappung bei Phase-in/out als eigene Klasse, siehe BE-PLAN-020. |
| BE-PLAN-013 | Phase-in, Phase-out und Ersatzschiffe steuern den Einsatz ohne Loeschen der Vergangenheit. | Offen | Regeln in SF-001 bis SF-004 beschliessen, bevor automatische Runden dafuer erzeugt werden. Ergaenzung 27.10.2026: Paarbildung und Parallellauf siehe BE-PLAN-019 und SF-015. |
| BE-PLAN-014 | Soll-Ebenen sind getrennt: Proforma (Dienstvorlage), LTS (vereinbarte Fenster plus Schiffsposition) und Ist/Entwurf. Die Bezugsbasis fuer das Delta ist eindeutig festgelegt. | Offen (neu) | SF-017. Der LTS-Fensterstand darf die Dienstvorlage nicht still ueberschreiben. |
| BE-PLAN-015 | Das Delta je Anlauf (frueh/pünktlich/spaet, in Stunden gegen das Fenster) wird als reine Funktion berechnet, auch fuer offene Entwuerfe. | Offen (neu) | Ankunft gegen Fensterbeginn, Abfahrt gegen Fensterende? Grenzen inklusive? Verhalten nach Slide siehe SF-016/017. |
| BE-PLAN-016 | Auswirkungsanalyse beim Verschieben: Puffer bis Fensterende und bis Folgehafen, betroffene Schiffe und Dienste samt Verursacher, auch dienstuebergreifend. | Teilweise (neu) | BE-PLAN-011 erkennt Ueberschneidungen und Transit. Offen: Folgeverspaetung (Warten auf belegten Liegeplatz) und Zuordnung Verursacher/Betroffene. |
| BE-PLAN-017 | Slide/Rebaseline: Dienst oder einzelne Schiffe um n Wochen versetzen. Ist-Zeiten bleiben unveraendert, Rundenschluessel und Referenzen werden atomar auf die neue nominelle Runde umgehaengt, mit Vorschau alt zu neu. | Offen (neu) | SF-016. Verhaeltnis zu einem neu importierten LTS (BE-INT-008) und zum Wochenversatz (BE-PLAN-002) klaeren. |
| BE-PLAN-018 | Die Umlauf-Identitaet laeuft ueber das Voyage-Paar (Westbound/Eastbound, Turnport). Bei Phase-out gibt es nur eine Nummer plus Platzhalter. Das Paar hat Vorrang vor zeitlicher Naehe beim Zuordnen. | Teilweise (neu) | BE-PLAN-005 und BE-INT-004 decken Reisenummern erst teilweise. Stuetzt SF-006/008/011. |
| BE-PLAN-019 | Phase-in/out-Paar: zwei Schiffe in einer Position mit Rolle und Verknuepfung. Der Anlauf traegt eine Rolle (Laden/Loeschen/beides/ausgelassen) und optional eine Feeder-Verbindung zum Phase-in-Schiff. | Offen (neu) | Konkretisiert BE-PLAN-013. Das Phase-out-Schiff kann die volle Rotation oder gebuendelte Haefen fahren; Mischformen sind moeglich. SF-015. |
| BE-PLAN-020 | Erwartete Ueberlappung (Parallellauf Phase-in/out) ist eine eigene Konfliktklasse (Hinweis statt Blockade) mit protokollierter Begruendung. Konflikte mit Dritten bleiben Konflikte. | Offen (neu) | Zu BE-PLAN-012 und SF-013. Nutzer will das Phase-out-Schiff durch die Rotation bringen, ohne das bestehende Netzwerk und die regulaeren Proforma-Fenster zu gefaehrden. |
| BE-PLAN-021 | Haefen tragen eine Region. Asien-Anlaeufe sind Kontext der Rotation, aber ausblendbar (z. B. nur Europa). | Offen (neu) | Sollen Asien-Anlaeufe gespeichert oder nur importiert werden? Turnport als Grenze der Europa-Sicht. |
| BE-PLAN-022 | Freie Fenster je Liegeplatz/Terminal ab einer Mindestliegedauer werden berechnet. | Offen (neu) | Liegeplatzattribute (Laenge, Tiefe) nur, wenn das Passen eines Schiffes geprueft werden soll; Schiffslaenge siehe BE-DAT-005. |

### Backend: Datenhaltung und Schnittstellen

| ID | Anforderung / pruefbares Verhalten | Stand | Abstimmung / Sonderfaelle |
| --- | --- | --- | --- |
| BE-DAT-001 | Schiffe, Dienste und Terminals haben getrennte Stammdaten; Hafen-ID-Umbenennungen erhalten Referenzen und Zeiten. | Vorhanden | Terminalzusammenlegung, Loeschen referenzierter Stammdaten und externe Schluessel klaeren. |
| BE-DAT-002 | JSON-Speicherung, Validierung und Datenpruefsumme verhindern unbeabsichtigtes Ueberschreiben neuerer Planungsdaten. | Vorhanden | Mehrdatei-Aenderungen haben Ruecksetzung bei Schreibfehlern, aber keine absturzsichere Datenbanktransaktion. |
| BE-DAT-003 | Mehrbenutzerbetrieb hat definierte Regeln fuer konkurrierende Entwuerfe, Konflikte und gemeinsame Uebernahmen. | Teilweise | Derzeit gemeinsame Fachdaten, lokale Entwuerfe und optimistische Pruefsumme; keine Reservierungen oder verteilten Sperren. |
| BE-DAT-004 | Sicherung, Wiederherstellung, Migration und Aenderungshistorie sind nachvollziehbar spezifiziert. | Offen | Aufbewahrung, Ruecknahme einer Uebernahme, Audit und Datenverlustziel festlegen. |
| BE-DAT-005 | Zu jedem Schiff koennen Stammdaten hinterlegt werden: Name, E-Mail-Adresse des Schiffes, Laenge, Breite; optional IMO, MMSI, Tiefgang, Geschwindigkeit. | Teilweise (neu) | Vorhanden sind laut Katalog mindestens Schiffsname und die fuer die Transitpruefung genutzte Geschwindigkeit. Feldliste, Pflichtfelder und Zugriffsrechte abstimmen; IMO/MMSI nur noetig fuer FE-PLG-012. Schnittstelle zu internen Systemen siehe BE-INT-009. |
| BE-DAT-006 | Benannte Szenarien lassen sich speichern, wieder laden und mit dem Ist vergleichen. | Offen (neu) | Derzeit nur lokale Entwuerfe (FE-UI-008). Lokal oder serverseitig, mit oder ohne Teilen zwischen Benutzern, abstimmen (BE-DAT-003). |
| BE-INT-001 | Anbieteradapter liefern ein gemeinsames Importformat mit Quelle, Schiff, Zeitraum, Hafenanlaeufen und Quellen-Reisenummern. | Vorhanden | Datenvertrag versionieren; neue Anbieter duerfen Fachlogik nicht duplizieren. |
| BE-INT-002 | Einzel- und Dienstimport bieten Vorschau, explizite Hafenzuordnung, Ignorieren und Bestaetigung von Entfernungen und Zeitbasis. | Vorhanden | Fehler einzelner Schiffe erfordern derzeit ausdruecklichen Ausschluss statt stiller Teiluebernahme. |
| BE-INT-003 | Import aktualisiert nur den gewaehlten Reise-/Zeitbereich; Aufenthalte ausserhalb bleiben geschuetzt. | Vorhanden | Grenze ist aktuell die Ankunft; bereits laufende Aufenthalte und Reisen ueber mehrere Fenster siehe SF-010/SF-011. |
| BE-INT-004 | Import erkennt bereits bekannte Reisen und Aufenthalte unabhaengig von geaenderten Ankunftszeiten wieder. | Teilweise | Aktuell Runde zeitbasiert/waehlbar, Besuchsauswahl ueber Terminal und zeitliche Naehe. Stabile Anbieter-IDs und Mehrdeutigkeitsdialog fehlen. Ergaenzung 27.10.2026: Voyage-Paar siehe BE-PLAN-018. |
| BE-INT-005 | Live-Abrufe haben Grenzen, Fehlermeldungen und einen zulaessigen manuellen Ersatzweg. | Teilweise | Maersk-Abruf und Hapag-Adapter vorhanden; Hapag-Sicherheitspruefung kann Automation blockieren. Kopier-/Dateiformate und offizielle APIs separat festlegen. |
| BE-INT-006 | Zeitzonen und Sommerzeit werden beim Import eindeutig in gemeinsame Planzeit ueberfuehrt. | Teilweise | Derzeit ausdrueckliche Uebernahmebestaetigung fuer naive UTC-Planzeit; automatische Anbieter-/Hafenzeitzonen-Konvertierung nicht zugesagt. |
| BE-INT-007 | Excel-Adapter fuer Proforma und LTS liefern das gemeinsame Importformat (BE-INT-001), einschliesslich Region, Schiffsposition, vereinbarten Fenstern und Phase-in/out-Markern. | Offen (neu) | Beispieldateien noetig; Spaltenaufbau und Regionsblock sind unbekannt. Der "Phase out"-Platzhalter ohne ausgehende Voyage ist kein Importfehler (SF-015). |
| BE-INT-008 | Ein Basisdaten-Update (neuer LTS oder Proforma) aendert nie die Ist-Zeiten bestehender Schiffe. Es gibt eine Diff-Vorschau und eine ausdrueckliche Bestaetigung bei geaenderter Schiffsposition. | Offen (neu) | SF-018. Ein verspaetetes Schiff darf nach dem Import nicht als puenktlich gelten. Dialog siehe FE-UI-018. |
| BE-INT-009 | Schnittstelle zu internen Systemen fuer Schiffsdaten und geplante Moves je Liegefenster (eigene und Partner). | Offen (neu) | Nice-to-have; derzeit keine Schnittstelle moeglich. Bis dahin hoechstens optionale manuelle Felder; nichts erzwingen. |

### Backend: Plugins und Betrieb

| ID | Anforderung / pruefbares Verhalten | Stand | Abstimmung / Sonderfaelle |
| --- | --- | --- | --- |
| BE-PLG-001 | Lokale Plugin-Pakete werden beim Serverstart ueber versionierte Manifeste automatisch geladen. Backend, Validierung, Renderer, Einstellungs-HTML/-JavaScript und Styles gehoeren dem jeweiligen Paket. | Vorhanden | Neue Pakete ohne Aenderung am PHOCA-Kern hinzufuegen oder entfernen; Serverneustart und Browser-Neuladen erforderlich. Schnittstelle: `plugins/README.md`. Keine Plugin-Downloads oder Uploads ueber die UI. |
| BE-PLG-002 | Wetter wird standortbezogen in kn/Richtung mit 3-Stunden-Werten, zehn Tagen Rueckblick und maximalem Anbieter-Vorschauhorizont geliefert (aktuell 16 Kalendertage einschliesslich Heute). | Vorhanden | Modell-/API-Verfuegbarkeit begrenzt den Horizont; keine Messdatenzusage. |
| BE-PLG-003 | Bedarfsgesteuerter Datenabruf, neustartfester Stunden-Cache, Warnschwelle und Zusammenfassung kritischer Windabschnitte liegen im Plugin. | Vorhanden | Ohne Zugriffe kein externer Hintergrundabruf und kein Keepalive; 3-Stunden-Aufloesung, stale Daten und Schwellenwerte sind keine sicherheitsverbindliche Betriebsfreigabe. |
| BE-PLG-004 | Fehlende, fehlerhafte oder deaktivierte Pakete veraendern keine Fahrplaene und blockieren deren Bedienung nicht. Unbekannte bzw. nicht verfuegbare Konfigurationen bleiben gespeichert. | Vorhanden | Leeres Verzeichnis, nur Wind, nur Tide, Backend-/Metadaten-/Validatorfehler sowie defekte Frontend-Formulare/-Renderer geprueft. Lokale Plugins bleiben vertrauenswuerdiger Code, keine Sandbox; Rate Limits und produktive Verfuegbarkeitsziele weiterhin klaeren. |
| BE-PLG-005 | Tide wird aus einer geeigneten Quelle mit Stationszuordnung, Hoehenbezug, Einheit und Warnregeln geliefert. | Teilweise | Offizielle BSH-Water-Level-Forecast-API unter CC BY 4.0 mit expliziter Pegelkennung und UTC-Umrechnung angebunden. Genutzt werden die gelieferten HW-/NW-Ereignisse, nicht selbst aus Modellhoehen abgeleitete Zeiten. Hoehenbezug/-darstellung, Jahresdateien, Wetter-/Astronomie-Uebergang und UKC-/Warnregeln sind weiterhin offen. |
| BE-PLG-006 | Tidenfenster sind je Terminal manuell vordefinierbar und wirken als Warnregel (nicht als Blockade); spaeter mit Datenquelle aus BE-PLG-005. | Offen (neu) | Zwei Stufen: erst manuelle Fenster (z. B. Hamburg), dann Plugin-Quelle. Tiefgangsabhaengigkeit und Warnung bei Ein-/Auslaufzeit abstimmen; SF-014. |
| BE-PLG-007 | Optionales Plugin fuer eigene AIS-Positionsdaten. | Offen (neu) | Nur nach Lizenz- und Kostenpruefung; bis dahin genuegen die Quicklinks aus FE-PLG-012. |
| BE-PLG-008 | Ein Hafen speichert getrennte, unterschiedlich lange Wind- und Tide-Standortlisten mit bis zu 16 Eintraegen je Plugin. Zuordnung, Links, Koordinaten und Windwarnschwellen werden pro Standort validiert und unabhaengig ausgewertet. | Vorhanden | In `pluginLocations` markiert `plugin: "weather"` bzw. `"tide"` die exklusive Zuordnung auch deaktivierter Eintraege. Alte gemeinsame Eintraege bleiben lesbar. Wetter-Rohdaten bleiben nach Koordinaten gemeinsam cachebar; geaenderte Warnschwellen brauchen keinen neuen Anbieterabruf. |
| BE-OPS-001 | Anmeldung, Passwort-Hashes, Sitzungen und CSRF-Schutz sichern UI und Fach-APIs. | Vorhanden | Benutzeranlage erfolgt derzeit per CLI; Rollen, Leserechte und Freigaberechte sind offen. |
| BE-OPS-002 | Produktiver Betrieb hat passende API-Lizenzen, HTTPS, Datensicherung und einen geeigneten Server. | Offen | Der aktuelle lokale Prototyp ist keine Produktionsfreigabe; Open-Meteo-Vertragsmodell beachten. |

### Sonderfaelle zur fachlichen Abstimmung

Diese Faelle sind ein eigener Diskussionskatalog, keine pauschale Zusage bereits implementierter Regeln. Nach einer Entscheidung werden die betroffenen Anforderungen und ein konkreter Abnahmetest ergaenzt.

| Fall-ID | Fall / betroffene Anforderungen | Zu entscheidende Regel und Abnahmebeispiel |
| --- | --- | --- |
| SF-001 | Phase-in; BE-PLAN-002/003/013 | Einstieg ab Datum oder konkretem Anlauf? Beginnt das Schiff mitten in einer Runde, duerfen davor keine erfundenen Aufenthalte entstehen. Wer bestimmt erste Runde, Hafen und Versatz? |
| SF-002 | Phase-out; BE-PLAN-003/007/013 | Gilt das Ende nach nominellem Rundenstart, letzter Abfahrt oder letztem erlaubten Anlauf? Beispiel: Ausstieg am 15.06. waehrend einer laufenden Runde; Vergangenheit erhalten, spaetere Fallback-Runden nicht weiter erzeugen. |
| SF-003 | Ersatzschiff / Dienstwechsel; BE-PLAN-002/013, BE-DAT-003 | Werden Runden uebertragen, abgebrochen oder neu angelegt? Beispiel: Schiff B uebernimmt die noch offenen Anlaeufe von A; keine Doppelbelegung durch zwei aktive Fallbacks. |
| SF-004 | Einsatzluecke / temporaere Aussetzung; BE-PLAN-003/007/013 | Unterschied zwischen unbesetzter Runde, Pause und fehlenden Daten festlegen. Nach Wiederaufnahme denselben Versatz fortsetzen oder neu verankern? |
| SF-005 | Change of Rotation; BE-PLAN-009/010 | Einmalig fuer eine Ist-Reise oder dauerhaft als neue Dienstvorlage? Beispiel A-B-C wird A-C-B; welche Zeiten bleiben, welche Transitstrecken werden neu berechnet? |
| SF-006 | Doppelter Hafenanlauf; BE-PLAN-008, BE-INT-004 | A-B-A muss zwei getrennte Aufenthalte behalten. Welche Quellen-ID/Reisenummer identifiziert beim erneuten Import den ersten bzw. zweiten A-Anlauf trotz Verspaetung? |
| SF-007 | Mehrere Terminals derselben Stadt; BE-DAT-001, BE-INT-002/004 | Rotterdam MV2 und RWG sind unterschiedliche Ziele. Wann genuegt ein Alias, wann ist eine manuelle Auswahl erforderlich? Terminalwechsel darf andere Besuche nicht still umhaengen. |
| SF-008 | Starke Verspaetung; BE-PLAN-004/005, BE-INT-004 | Runde A wird ins nominelle Fenster von B verschoben. Erneuter Import muss A zugeordnet oder zur Auswahl gestellt werden; B darf nicht wegen zeitlicher Naehe ueberschrieben werden. |
| SF-009 | Proforma-Wechsel in laufender Reise; BE-PLAN-006/007 | Neue Jahresversion gilt ab 01.01., die alte Runde endet erst am 10.01. Welche Vorlage bleibt Referenz? Beispiel: Mathilde ab 2026 NE4/2026 +3 Wochen, ab 2027 NE4/2027 +4 Wochen. |
| SF-010 | Import einer Teilrunde / eines laufenden Aufenthalts; BE-INT-003 | Aufenthalt beginnt vor dem Importfenster und endet darin. Ganze Station schuetzen, Abfahrt aktualisieren oder ausdruecklich nachfragen? Fehlende Quellzeile darf nicht automatisch "ausgefallen" bedeuten. |
| SF-011 | Mehrere Runden / Split oder Merge; BE-PLAN-005, BE-INT-003/004 | Quelle enthaelt mehrere Umlaeufe oder abweichende Ankunfts-/Abfahrts-Reisenummern. Wie werden sie getrennt, verknuepft und bestaetigt? Aktuell keine automatische Mehr-Runden-Uebernahme. |
| SF-012 | Auslassen / Hinzufuegen / Abbruch; BE-PLAN-008/009, BE-INT-002 | Bewusster ausgelassener Hafen vs. fehlende Daten, neuer Anlauf vor/nach der Route und Teilabbruch unterscheiden. Gilt die Aenderung nur fuer diese Reise oder fuer kuenftige Runden? |
| SF-013 | Konflikte und Freigaben; BE-PLAN-011/012 | Was ist Hinweis, Warnung oder harter Fehler? Beispiel: Import mit zu kurzer Transitzeit wird gespeichert; darf dieselbe Situation manuell bestaetigt werden, und muss eine Begruendung protokolliert werden? |
| SF-014 | Wetter-/Tidegrenze; BE-PLG-002/003/005 | Vergleich ab Grenzwert inklusive? Was passiert bei Datenluecken, Stationswechsel oder veralteten Daten? Warnung an einem Termin von Warnung innerhalb eines Zeitbereichs unterscheiden. |
| SF-015 | Phase-out im Parallellauf; BE-PLAN-013/018/019/020, BE-INT-007 | Das Phase-out-Schiff steht im LTS nur als "Phase out" ohne ausgehende Voyage, das Phase-in-Schiff laeuft in derselben Position. Varianten: gleiche Rotation (einer laedt, einer loescht), gebuendelte Haefen mit Feeder, Mischformen. Wie wird das Paar erkannt, dargestellt und gegen Dritte geprueft? |
| SF-016 | Slide mit Blank Sailing; BE-PLAN-004/015/017, FE-UI-018 | Eine Woche entfaellt, A rueckt auf B, B auf C. Gilt der Slide fuer den ganzen Dienst oder einzelne Schiffe? Ist-Zeiten bleiben, Delta nach dem Slide wieder gegen die neue Position. Was passiert mit Vergangenheit und mit bereits gespeicherten Runden? |
| SF-017 | Bezugsbasis des Delta; BE-PLAN-014/015 | Proforma oder LTS-vereinbart? Nach einem Slide gegen die neue oder die historische Baseline? Wie wird die Abweichung bei Fenstern (von-bis) gemessen? |
| SF-018 | LTS-Reimport bei geaenderter Schiffsposition; BE-INT-008 | Welche Position gilt, wenn Ist-Daten schon abweichen? Was passiert mit Schiffen, die im neuen LTS fehlen, und mit neuen Schiffen? Aenderung nur nach ausdruecklicher Bestaetigung? |

### Entwurf: Abnahmebeispiele Fachlogik (noch nicht abgestimmt)

Die Beispiele nutzen Platzhalterwerte und stehen unter dem Vorbehalt der offenen Entscheidungen (insbesondere SF-016 bis SF-018). Sie sollen als Vorlage fuer automatisierte Tests dienen.

| Anforderungen | Gegeben / Wenn | Dann |
| --- | --- | --- |
| BE-PLAN-015 | Das Fenster in Hafen B endet am 10.03. um 18:00; die Abfahrt des Entwurfs liegt am 10.03. um 22:00. | Delta der Abfahrt: +4 h (spaet). Unter Vorbehalt von SF-017 (Messregel fuer Fenster). |
| BE-PLAN-017, SF-016 | Schiff A hat gespeicherte Ist-Zeiten mit +7 Tagen gegen die alte nominelle Runde. Der Dienst wird um +1 Woche geslidet. | Ist-Zeiten bleiben unveraendert; die Referenz haengt an der neuen nominellen Runde; Delta nahe 0; Vergangenheit unveraendert; die Vorschau zeigt das Mapping alt zu neu vor der Uebernahme. |
| BE-INT-008, SF-018 | Schiff A hat gespeicherte Ist-Zeiten mit +2 Tagen. Ein neuer LTS ohne Aenderung fuer A wird importiert. | Ist-Zeiten bleiben; Delta weiter +2 Tage; nur Soll-Fenster und Position werden aktualisiert; eine geaenderte Position wird erst nach Bestaetigung uebernommen. |
| BE-PLAN-019/020, SF-015 | Im LTS steht Schiff X als "Phase out" ohne ausgehende Voyage, Schiff Y als Phase-in in derselben Position. | Kein Importfehler; das Paar ist erkennbar; die Ueberlappung zwischen X und Y gilt als erwartet; Konflikte nur bei Kollision mit Dritten. |

### Rueckverfolgung: Nutzerwunsch zu Anforderungen

| Nutzerwunsch (Sprachnachricht) | Anforderungen |
| --- | --- |
| Zentrales Tool statt vieler einzelner Quellen und Webseiten | FE-UI-022, FE-PLG-012, BE-INT-007, BE-INT-009 |
| Grafische Rotation je Dienst, nur Region Europa | FE-UI-003, FE-UI-017, BE-PLAN-021 |
| Overlap- und Zeitprueung zwischen Liegeplaetzen | BE-PLAN-011 |
| Szenarien durch Verschieben ("Kann ich das, ohne in Hafen B zu spaet zu sein?") | FE-UI-005/006/016, BE-PLAN-016, BE-DAT-006 |
| Versatz zum Proforma sehen (zu frueh/spaet) | FE-UI-015, BE-PLAN-014/015, SF-017 |
| Proforma und LTS aus Excel, Update ohne Ueberschreiben bestehender Verspaetungen | BE-INT-007/008, BE-PLAN-006, SF-018 |
| Change of Rotation, Haefen hinzufuegen | BE-PLAN-009/010, FE-UI-021, SF-005 |
| Slide eines ganzen Dienstes | BE-PLAN-017, FE-UI-018, SF-016 |
| Phase-in/out, Parallellauf, Feeder, Mischformen | BE-PLAN-013/019/020, FE-UI-019, SF-001 bis SF-004, SF-015 |
| Voyage-Nummern (Westbound/Eastbound, Turnport) | BE-PLAN-018, BE-INT-004, SF-006/008/011 |
| Hafenfilter und freie Kapazitaet (z. B. Hamburg Eurogate) | FE-UI-007/017/020, BE-PLAN-022 |
| Wen beeinflusse ich negativ? | BE-PLAN-016, FE-UI-016 |
| Tidenfenster | FE-PLG-007, BE-PLG-005/006 |
| Live-Position und Windy-Link | FE-PLG-012, BE-PLG-007 |
| Schiffsdaten (E-Mail-Adresse, Breite, Laenge) hinterlegen | BE-DAT-005, FE-UI-023 |
| Moves je Liegefenster, interne Systeme (Nice-to-have) | BE-INT-009 |

### Entscheidungen und Abnahmekriterien pflegen

Zu einer abgestimmten Anforderung werden die folgenden Felder ergaenzt, beispielsweise direkt unter der betroffenen Tabelle. Einfache UI-Wuensche muessen dabei nicht zu einem eigenen Dokument werden.

| Feld | Inhalt |
| --- | --- |
| Referenz | Anforderungs-ID und gegebenenfalls SF-ID. |
| Entscheidung | Beschlossene Regel, ausdrueckliche Ausnahmen und Umfang (ein Aufenthalt, eine Reise, ein Schiff oder ganzer Dienst). |
| Datenbezug | Verwendete Identitaeten, nominelle Runde, Wirksamkeitsbeginn/-ende und relevante Zeitbasis. |
| Abnahmekriterium | Gegeben konkrete Ausgangsdaten; wenn eine Aktion erfolgt; dann konkrete erwartete Daten und Anzeige, inklusive unveraenderter Daten. |
| Nachweis | Testfall oder manuelle Desktoppruefung; umgesetzt, geprueft und fachlich abgenommen getrennt vermerken. |
| Aenderung | Datum und Bezug zur vorherigen Entscheidung; IDs nicht still umdeuten. |

**Empfohlener Beginn der Abstimmung:** SF-017 (Bezugsbasis des Delta), BE-PLAN-018 (Voyage-Paar als Identitaet), SF-016 (Slide), danach die Excel-Importe BE-INT-007/008 mit Beispieldateien. Parallel bleiben SF-001/SF-002 (Einsatzgrenzen), SF-008 (Reiseidentitaet trotz Verspaetung) und SF-009 (Proforma-Wechsel) wichtig, weil sie Datenmodell und Importe beeinflussen. Erst danach Delta/Impact (BE-PLAN-015/016), Phase-in/out (SF-015) sowie Region, freie Fenster, Tide und Quicklinks angehen.

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

## Hafen-Plugins, Wind und Tide

Unter "Haefen" ist "Standort & Hafen-Plugins" ausklappbar und beim Wechsel zu einem Hafen zunaechst geschlossen. Darin haben Wind und Tide eigene Standortlisten mit unabhaengigen Hinzufuegen-/Entfernen-Aktionen und jeweils null bis 16 Eintraegen. Jeder Eintrag hat einen eigenen Namen, HTTPS-Website-Link, WGS84-Koordinaten und eine Aktivierung fuer sein Plugin. Wind hat zusaetzlich die optionale "Windwarnung ab (kn)"; Tide-Hoehenwarnregeln sind noch nicht implementiert. Die globale Hafenoption "Wind-Plugin aktiv" bleibt ein Hauptschalter ausschliesslich fuer Wind. Eine leere Windwarnschwelle deaktiviert nur die Warnfarben des betreffenden Windstandorts. Fuer die bisherigen Haefen sind ungefaehre Positionen vorbelegt; vor betrieblicher Nutzung pruefen und gegebenenfalls korrigieren. Technisch liegen beide Listen weiterhin in `pluginLocations` am Hafeneintrag in `data/ports.json`, bei neuen Eintraegen mit exklusiver `plugin`-Zuordnung. Alte gemeinsame Standorte und deren Tide-Links bleiben lesbar und werden erst beim Speichern in unabhaengige Eintraege aufgeteilt. Beispiel eines bisherigen gemeinsamen Formats:

```json
{
	"plugins": {"weather": {"enabled": true}},
	"pluginLocations": [
		{
			"id": "terminal", "name": "Hamburg",
			"coordinates": {"latitude": 53.5264, "longitude": 9.9175},
			"url": "https://www.windy.com/?53.777,9.181,10",
			"plugins": {"weather": {"enabled": true, "warningWindKnots": 20}, "tide": {"enabled": false}}
		},
		{
			"id": "cuxhaven", "name": "Cuxhaven",
			"coordinates": {"latitude": 53.873, "longitude": 8.709},
			"url": "https://www.windy.com/?53.873,8.709,10",
			"plugins": {"weather": {"enabled": true, "warningWindKnots": 30}, "tide": {"enabled": false}}
		}
	]
}
```

Die verschiedenen Grenzen im Beispiel sind frei waehlbar. Bei 25 kn wird nur Hamburg rot markiert, Cuxhaven noch nicht. Jede Standort-/Plugin-Kombination erhaelt eine eigene 38-Pixel-Spur; die erste liegt direkt neben dem Hafennamen und weitere darunter. Werte und rote Zeitbaender verschiedener Standorte werden nicht vermischt. Direkt vor den Werten steht ausschliesslich der kompakte Standortname, der im Hafentab auch abgekuerzt werden kann. Einheit, Pluginname und Warnschwelle bleiben im Tooltip. Ein Klick auf eine Zahl oeffnet den jeweiligen gespeicherten Website-Link als normalen Link in einem neuen Tab (`noopener noreferrer`). Leerer Link bedeutet: keine Weiterleitung. Alte Hafenkoordinaten bleiben als Fallback fuer Konfigurationen ohne `pluginLocations` lesbar. Alte gemeinsame Warnschwellen werden beim Bearbeiten in die einzelnen Standorte uebernommen; explizit leere Standortschwellen bleiben ohne Warnung.

Der Button "Wind" neben "Heute" schaltet Windwerte und Warnzeitbaender gemeinsam um. Dieselbe Auswahl ist unter "Liegeplaetze & Ansicht" -> "Hafen-Plugins" verfuegbar und wird je Benutzer lokal gespeichert. Das Deaktivieren am Hafen ist dagegen eine gemeinsame Stammdateneinstellung und verhindert dort Wetterabrufe. Die Anzeige nutzt nur den sichtbaren horizontalen Kalenderausschnitt. Hafenname, quadratischer Plus-Button, Standortname und erste Pluginspur bleiben in derselben Zeile; es gibt keine zusaetzliche Kopfzeile oberhalb des Plugins.

Das erste Plugin fragt Open-Meteo serverseitig nach 10-m-Windgeschwindigkeit und Windrichtung ab: zehn vergangene Tage und den maximalen Forecast-API-Horizont von 16 Kalendertagen einschliesslich Heute, also bis zu 15 folgende Kalendertage in UTC. Je nach Modell und Standort koennen die letzten gueltigen Werte frueher enden; es werden nur tatsaechlich gelieferte Werte angezeigt. Aus den stuendlichen Modellwerten werden die Zeitpunkte 00/03/06/09/12/15/18/21 Uhr geliefert. Das sind Wettermodellwerte, keine Terminalmessung und keine sicherheitsverbindliche Freigabe. Fehlen einzelne API-Werte, werden sie nicht erfunden. Vergangenheitswerte stammen aus dem vom Anbieter gelieferten Modellverlauf, nicht aus einer lokalen Messhistorie.

Die Zahl ist Wind in kn, mit einer reinen Pfeilspitze ohne Stamm oder Kreis. Windwerte ueber 10 kn erscheinen als ganze Zahlen; kleinere Werte mit maximal einer Nachkommastelle. Der Pfeil zeigt, wohin der Wind weht; im Tooltip steht die meteorologische Herkunftsrichtung (z. B. "Wind aus 270 Grad" = aus Westen, Pfeil nach Osten), der UTC-Zeitpunkt und Abrufstand. Beim Herauszoomen wird nicht jeder 3-Stunden-Wert gezeichnet. Die UI verwendet feste, UTC-verankerte Raster von 3/6/12/24/48/96 Stunden usw., passend zum Zoom und mit gleichmaessigem Abstand. Gezeigt wird der jeweilige Originalwert am Rasterzeitpunkt, nicht der Maximalwert eines Zeitblocks. Fehlende Werte werden nicht interpoliert.

Kritische Windzeitraeume erscheinen zusaetzlich als rote Baender hinter den Werten, unabhaengig vom Zoom und Zahlenraster. Die Zahlen an unkritischen Nachbarzeitpunkten werden nicht kuenstlich als kritisch umgefaerbt. Das Plugin bewertet jeden verfuegbaren 3-Stunden-Wert fuer den folgenden 3-Stunden-Abschnitt und fuehrt direkt benachbarte kritische Abschnitte zusammen. Ein kritischer Wert um 03 Uhr mit unkritischem Folgewert um 06 Uhr markiert also 03-06 Uhr. Das ist eine Darstellung im Datenraster, keine minutengenaue Aussage ueber den Schwellenuebertritt. Datenluecken werden nicht ueberbrueckt; im Tooltip stehen Zeitraum und maximaler Windwert. Der Renderer schneidet Baender am sichtbaren Ausschnitt ab, ohne ihre fachlichen Start-/Endzeiten zu veraendern.

Der Server puffert Wetterdaten im Normalfall eine Stunde je Standort im Arbeitsspeicher und atomar in `instance/plugin-cache/weather/`. Alte `weather-*.json` aus `instance/weather-cache/` werden beim Start kopiert, ohne vorhandene private Dateien zu ueberschreiben; Daten und Ablaufzeiten bleiben unveraendert. Cache-Dateien enthalten Datenversion, Standort-/Abfragekennung, aufbereitete Windwerte, `fetchedAt` und `expiresAt`; keine API-Schluessel oder Warnschwellen. Die Schwellen werden aus den aktuellen Hafeneinstellungen auf die gespeicherten Werte angewendet. Gleichzeitige Anfragen teilen sich denselben externen Abruf. Nach einem Serverneustart wird beim ersten Bedarf zuerst die Cache-Datei gelesen: Ist sie noch gueltig, bleibt ihre urspruengliche Ablaufzeit bestehen und es gibt keinen neuen Anbieterabruf. Ein Tageswechsel allein verwirft den Cache nicht. Fehlende, beschaedigte, unpassende oder abgelaufene Dateien fuehren bei Bedarf zu einem neuen Abruf. Kann die Datei nicht geschrieben werden, funktioniert der RAM-Cache weiter und der Server protokolliert einen Hinweis. Das gesamte `instance/`-Verzeichnis bleibt von Git ausgeschlossen.

Es gibt keinen stuendlichen Serverjob und keinen Keepalive zur Nutzererkennung. Ohne Wetteranfragen wird nichts extern abgefragt. Die geoeffnete Website verwendet einen normalen Timer fuer den Ablauf der Winddaten und aktualisiert die Werte per API im bestehenden Kalender; die Seite muss dafuer nicht neu geladen werden. Die UI speichert Daten bis zum Cache-Ablauf. Der Server liefert die verbleibende Laufzeit als `refreshAfterSeconds`, damit spaeter geoeffnete Browser alte Daten nicht eine weitere volle Stunde festhalten. Scrollen, Zoom, mehrere Benutzer und ein Browser-Neuladen erzwingen keinen neuen Wetteranbieter-Abruf, solange der Servercache gueltig ist. Die unabhaengige automatische Aktualisierung von Fahrplandaten ist kein externer Wetterabruf.

Bei Abruffehlern werden vorhandene Werte, auch aus einer abgelaufenen Cache-Datei nach Neustart, als veraltet markiert; andernfalls erscheint ein Hinweis statt eines kaputten Kalenders. Nach einem Fehler wird fruehestens nach fuenf Minuten erneut extern abgefragt. Plugin-Daten und Cache-Zeitstempel fliessen nicht in Fahrplan-JSONs, Planentwuerfe oder deren Signaturen ein. Die Abrufbuendelung gilt fuer die vorgesehene einzelne Serverinstanz; mehrere unabhaengige Prozesse haben keine verteilte Abrufsperre.

Die freie Open-Meteo-API ist laut Anbieter nur fuer nichtkommerzielle Nutzung und weniger als 10.000 Abrufe pro Tag gedacht. Fuer kommerziellen Betrieb einen passenden Open-Meteo-Vertrag und `OPEN_METEO_API_KEY` in der Serverumgebung hinterlegen; dann wird automatisch `customer-api.open-meteo.com` verwendet. Den Schluessel nicht in Hafen-JSONs oder Git speichern. Quellenattribution ist im Plugin-Menue verlinkt. Bedingungen: https://open-meteo.com/en/terms ; API-Dokumentation: https://open-meteo.com/en/docs .

### Relative Tide

Das Plugin "Tide (BSH)" verwendet ausschliesslich die offizielle BSH-Water-Level-Forecast-API. Unter "Haefen" im getrennten Tide-Bereich einen Standort anlegen, "Tide anzeigen" aktivieren und dessen "BSH-Pegelkennung" waehlen oder eintragen. Verifizierte Beispiele sind `hamburg_st-pauli`, `hamburg_seemannshoeft`, `hamburg_blankenese`, `cuxhaven_steubenhoeft` und `bremerhaven_alter_leuchtturm`. Der frei waehlbare Standortname und die Koordinaten bestimmen den Pegel nicht automatisch. Die lokale Plugin-Auswahl unter "Liegeplaetze & Ansicht" muss Tide ebenfalls erlauben. Bestehende Standorte ohne Pegelkennung bleiben erhalten und zeigen bis zur Zuordnung einen Konfigurationshinweis. Es gibt keine automatische Zuordnung zum naechstgelegenen Pegel und keinen Open-Meteo-Rueckfall. Wind verwendet unveraendert Open-Meteo.

Der optionale HTTPS-"Website-Link" eines Tide-Standorts gehoert ausschliesslich diesem Tide-Eintrag, unabhaengig von allen Wind-Links. Er wird als `url` gespeichert, zusammen mit `plugin: "tide"` und eigener `plugins.tide`-Konfiguration. Alte gemeinsame Eintraege mit `plugins.tide.url` werden weiterhin gelesen; das Formular uebernimmt diesen Link beim Aufteilen in den neuen Tide-Eintrag. Ein leerer Website-Link bedeutet keine Weiterleitung. Punkte und Kurvenbereich oeffnen den gespeicherten Link in einem neuen Tab; der Link wird nicht zur Datenbeschaffung verwendet.

Die Quelle ist `https://gdi.bsh.de/ldproxy/rest/services/WaterLevelForecast/collections/waterlevelforecastdata/items/<Pegelkennung>?f=json`. Die Ereignisse aus `properties.high_water_low_water` liefern `event` (HW/NW) und `event_timestamp` mit Zeitzonenoffset. Zeitpunkte werden nach UTC umgerechnet und nicht aus einer groben Modellkurve geschaetzt. Die Antwort muss zum gewaehlten Pegel gehoeren. Hoehen- oder Wetterkorrekturen werden nicht auf Ereigniszeiten addiert; meteorologisch verschobene Extremzeiten werden nicht eigenstaendig berechnet.

Die bestehende Kurvenansicht bleibt relativ: Hochwasser oben, Niedrigwasser unten, ohne Meterhoehen. Die blaue geglaettete Verbindung illustriert lediglich den Wechsel zwischen den gelieferten Ereignissen, nicht den Verlauf der realen Zwischenpegel. Fehlende Ereignisse bzw. groessere Luecken werden nicht ueberbrueckt. Tooltips nennen UTC-Zeitpunkt, BSH-Pegelkennung, Attribution und Abrufstand. Echte Hoehen mit sichtbereichsabhaengiger Skalierung, astronomische Jahresdateien, ein farblich getrennter Wetter-/Astronomie-Uebergang und Tidewarnregeln sind noch nicht umgesetzt. Auch amtliche Quelldaten machen diese Planungsdarstellung nicht zu einer Navigations-/UKC-Freigabe.

Die API liefert einen rollierenden, stationsabhaengigen Ereigniszeitraum; nur gelieferte Ereignisse werden angezeigt. Der Renderer erlaubt einen Abfrageausschnitt von zehn Tagen Rueckblick bis acht Kalendertagen einschliesslich Heute, ohne fuer dieses ganze Fenster Daten zu versprechen. Beim Live-Test am 28.10.2026 lieferten Hamburg und Cuxhaven je 22 Ereignisse bis zum 03.11.2026. Langfristige Jahresdaten und eine Rueckblickhistorie werden nicht zusaetzlich beschafft. Eine Stunde RAM-/Dateicache, neustartfeste Ablaufzeit, Abrufbuendelung, fuenf Minuten Fehlerpause und gekennzeichnete veraltete Werte funktionieren bedarfsgesteuert wie beim Wind. Cache-Schluessel verwenden BSH-Pegelkennung und Datenversion; alte Marine-Caches koennen deshalb nicht als BSH-Daten erscheinen. Tide speichert `tide-*.json`-Dateien unter `instance/plugin-cache/tide/`, ohne Fahrplaene zu veraendern. Alte Dateien aus `instance/weather-cache/` werden beim Start ohne Ueberschreiben uebernommen. Die Windows-Abhaengigkeit wird bei Bedarf mit `python -m pip install -r plugins/tide/requirements.txt` installiert.

BSH verlangt hier weder Registrierung noch API-Schluessel und bietet die Daten unter CC BY 4.0 an; Quelle und Lizenz stehen in den Plugin-Metadaten. Die relative Aufbereitung wird als Darstellung durch PHOCA gekennzeichnet. Unter Windows verwendet der HTTPS-Abruf `truststore`, damit der Windows-Zertifikatsspeicher genutzt wird; Zertifikats- und Hostnamenpruefung bleiben aktiv. Auf Linux bleibt die System-CA-Pruefung aktiv. `OPEN_METEO_API_KEY` betrifft nur noch Wind. Quelle: https://gdi.bsh.de/ldproxy/rest/services/WaterLevelForecast ; Lizenz: https://creativecommons.org/licenses/by/4.0/ .

### Schnittstelle fuer weitere Plugins

Die kompakte, versionierte Schnittstellenbeschreibung steht in [plugins/README.md](plugins/README.md). Wind liegt vollstaendig unter `plugins/weather/`, Tide unter `plugins/tide/`: jeweils Manifest, Backend, Frontend-ES-Modul, Einstellungs-HTML, scoped CSS und eigene Backendtests. `plugin_runtime.py`, `port_plugins.py`, `plugin_api.py` und `static/plugin_host.js` bilden den generischen PHOCA-Host, ohne feste Wind-/Tide-Felder oder Renderer. PHOCA stellt Serverzeit, Konfiguration, UTC-Zeitfenster, Zeilen und geschuetzte APIs bereit; der Zeileninhalt und die Formulare kommen vom lokal installierten Paket. Metadaten mit `locationOptIn: true` verlangen eine ausdrueckliche Aktivierung je Standort.

Pakete lokal hinzufuegen oder entfernen, Abhaengigkeiten bei Bedarf installieren, Server neu starten und Browser neu laden. Keine manuelle Registrierung und kein Hot-Reload. Fehlerhafte Pakete bzw. Frontend-Module werden isoliert; nicht verfuegbare Einstellungen bleiben erhalten. Alte gemeinsame Standortdaten werden beim Bearbeiten paketweise uebernommen, ohne Konfigurationen entfernter Pakete zu loeschen. Lokal geladene Python-/JS-/HTML-Dateien sind bewusst vertrauenswuerdiger Code. Paketdateien werden nur angemeldet ausgeliefert; Backend und Manifest sind nicht ueber die Asset-Route abrufbar.

- `GET /api/port-plugins`: `schemaVersion: 1`, installierte Plugin-Metadaten mit `assets` fuer Frontend/HTML/CSS und `diagnostics` fuer Startfehler. Fachliche Metadaten duerfen Plugins selbst erweitern.
- `GET /api/ports/<id>/plugins?start=<UTC-Planzeit>&end=<UTC-Planzeit>&plugins=weather,tide`: `schemaVersion: 1`, `portId`, `timeBasis: "UTC"` und `tracks`. Beide Endpunkte verlangen Anmeldung.
- Ein Track enthaelt Metadaten, `locationId`, `locationName`, den Standort-Link `url`, `status` (`ready`, `stale`, `error`, `empty`, `unconfigured`, `disabled`, `out-of-range`), optionalen Hinweis/Abrufstand, `samples` und optionale `periods`. Mehrere Tracks koennen dieselbe Plugin-ID, aber verschiedene Standort-IDs haben. Der Windtrack liefert die geltende Standortschwelle als `warningWindKnots`. Jeder Zeitraum hat `start`/`end` (UTC, Ende exklusiv), `state` (`warning`/`danger`) und optional `label`. Er wird unabhaengig von der Ausduennung der Samples als durchgehendes Zeitband gezeichnet.
- Die mitgelieferten Pakete verwenden Samples mit naiver UTC-ISO-Zeit `time`, numerischem `value` und eigenen Zusatzfeldern. Andere Pakete koennen eigene Sample-/Periodenformate zwischen ihrem Backend und Frontend vereinbaren; der Host interpretiert diese nicht. Der Windrenderer nutzt `rotationDegrees` (0 = Pfeil nach Norden) und das feste Zahlenraster, ohne Prioritaetsauswahl.
- `presentation: "tide"` verwendet `relative: true`, eine leere Einheit und Ereignisse mit `kind` (`high`/`low`), relativem `value` (+1/-1) und `segmentId`. Nur abwechselnde Ereignisse innerhalb desselben Segments werden verbunden. `accuracyNote` erlaeutert die Grenzen der Extremzeiten; Meterhoehen und Tidewarnbaender sind nicht Teil dieses Datenvertrags.
- Der Host stellt getrennte, abgeschnittene 38-Pixel-Spuren und Zeit-/Pixelhilfen bereit; Positionierung und Inhalt innerhalb der Spur uebernimmt das Paket. Fehler werden pro Plugin abgefangen; der Fahrplan bleibt bedienbar.

## Planung

- Der Hauptbereich hat keine feste maximale Breite; die Planungsansicht nutzt die Desktopfensterbreite mit schmalen Seitenraendern. Kalender und eigene Scrollflaeche fuellen den unter Navigation/Werkzeugen verbleibenden Platz bis zum unteren Fensterrand, auch bei verkleinerter Browserdarstellung. Formularbereiche bleiben normal seitenweise scrollbar.
- Die gemeinsame Spalte "HAFEN / LIEGEPLATZ" wird aus dem laengsten aktuell angezeigten Hafennamen mit der verwendeten Schrift berechnet, einschliesslich Aufklapppfeil und gegebenenfalls Plus-Button. Beim Wechsel der angezeigten Haefen passt sie sich an; eine Mindestbreite haelt die Ueberschrift lesbar. Liegeplatz-/Transitbeschriftungen und Pluginpositionierung nutzen dieselbe Breite.
- Der Seitenleisten-Schalter links neben "Liegeplatzbelegung" blendet die Flotten-/Hafenauswahlleiste aus und wieder ein. Ausgeblendet steht dem Kalender die gesamte Arbeitsbreite zur Verfuegung. Auswahl und Entwuerfe bleiben erhalten; die Einstellung wird je Benutzer im Browser sowie in benannten Ansichten gespeichert.
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
- In der Dienstansicht steht direkt rechts neben dem Hafennamen ein quadratischer Plus-Button fuer "Hafen hinzufuegen"; die Funktion ist per Tooltip benannt. Hafenname und Button bleiben beim horizontalen Scrollen gemeinsam links neben der ersten Pluginspur sichtbar; die Liegeplatzanzahl wird dort nicht zusaetzlich angezeigt. Der Dialog bietet alle registrierten Haefen an und fuegt den gewaehlten Hafen vor dem betreffenden Aufenthalt nur in die aktuelle Reise des ausgewaehlten Schiffs ein. Bei mehreren Besuchen desselben Hafens laesst sich unter "Vor Aufenthalt" der genaue folgende Aufenthalt waehlen. Auch ein erneuter Besuch eines bereits enthaltenen Hafens ist moeglich; jeder Besuch hat eine eigene ID, der physische Hafenblock wird nicht dupliziert.
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
	services.json       Dienstkonfiguration, Dienstfarben und gemeinsame Proformas
	ships/
		busan.json        Schiff, Geschwindigkeit, Proforma-Zuordnungen und Reisen
		berlin.json
		...
```

Die JSON-Dateien sind die einzige Quelle fuer Fachdaten. `ports.json` und `services.json` muessen vor dem Start vorhanden sein; fehlende Dateien fuehren zu einem ausdruecklichen Ladefehler. Fuer eine leere Konfiguration jeweils `[]` hinterlegen. Ein fehlendes oder leeres `ships/`-Verzeichnis bedeutet eine leere Flotte. Es werden weder Demohaefen noch Dienste oder Beispielschiffe erzeugt. Testdaten liegen getrennt unter `tests/fixtures/plan.json` und werden von der Anwendung nicht geladen.

Beim Uebernehmen wird ausschliesslich die aktuelle Datei des ausgewaehlten Schiffs atomar ersetzt. Die Schiffe werden direkt aus dem Verzeichnis ermittelt. Weder ein Manifest noch eine Legacy-Sicherung oder eine serverseitige Ansichtsdatei werden angelegt oder benoetigt. Die entsprechenden frueheren Dateien wurden entfernt. Vorhandene aeltere Schiffssicherungen in Unterordnern sind keine aktiven Daten und werden nicht eingelesen. Die Anwendung ist fuer eine einzelne lokale Serverinstanz ausgelegt.

Der Schutz gegen gleichzeitiges Ueberschreiben verwendet ausschliesslich `dataSignature`, eine aus den aktuellen Fachdaten berechnete Pruefsumme. Ein zusaetzlicher Speicherzaehler oder eine Metadatendatei ist nicht erforderlich. Pending und benannte Ansichten bleiben getrennt im lokalen Browser (`localStorage`). Ansichten werden nicht zwischen verschiedenen Browsern oder Rechnern synchronisiert; das Loeschen der Websitedaten entfernt diese lokalen Einstellungen und Entwuerfe.

Eine Schiffsdatei enthaelt `id`, `name`, `serviceId`, `proformaAssignments` und `voyages` sowie Importname und Geschwindigkeit. Jede Zuordnung hat `proformaId`, `validFrom` und `offsetWeeks`. Die gemeinsame Vorlage liegt unter `proformas` des Dienstes in `services.json` und hat `id`, `name`, `validFrom`, `repeatWeeks` und `stops`. Fuer die Rundenerzeugung wird die zeitlich gueltige Schiffszuordnung verwendet; die erste Ankunft der referenzierten Vorlage plus Wochenversatz ist der Zyklusanker. Unterschiedliche Jahres- oder Saisonproformas koennen unterschiedliche Anker und Intervalle haben. Regeln fuer einen Wechsel waehrend einer laufenden Reise sind unter SF-009 noch abzustimmen.

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

Neue Schiffe starten mit leeren `proformaAssignments` und `voyages`. Der erste Import erzeugt eine tatsaechliche Reise mit `proformaId: null`; eine Proforma oder Wiederholung wird nicht erfunden. Schiffe ohne Fahrplan bleiben im Kalender auswaehlbar. Spaetere weitere Importe koennen weitere tatsaechliche Reisen hinzufuegen.

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