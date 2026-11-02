# Statistics and counter semantics

## English

### What issue #15 does and does not establish

| Requested property | Handling |
|---|---|
| `d701_tot_bev_b` as a lifetime beverage total | Not accepted under that name. On the verified Eletta it contributes to the black-coffee summary, not every beverage. |
| `d580_service_parameters` | Add optional **Descale threshold usage** and **Descale status code** when their fields can be parsed. Both are diagnostics, disabled by default. |
| `d733_tot_bev_counters` | Already used for selected official black/iced-milk summaries. Do not sum the whole object: recipe groups can overlap. |
| `d734_tot_bev_usage`, `d740_water_qty_bev` | No new sensor until field meaning, units and non-overlap are verified. They are not universal lifetime totals. |
| Initial old cloud snapshot and missing signature | Show an actionable Repair explaining first-time learning; retain the signature safety guard. |

On the verified Striker Cold Brew profile, Coffee Link's black-coffee summary is
`d701_tot_bev_b` plus `tot_bev_b_iced` from d733. Hot-milk beverages come from
selected d702 fields; cold-milk beverages from selected d733 fields. Mug to Go
is assembled from the hot and cold mug counters. Do not add all visible recipe,
mug and group counters to invent a lifetime total. Legacy Soul properties have
different names and meanings; a shared numeric prefix is not a shared contract.

The optional d580 progress is
`last_4_water_calc_qty / last_4_calc_threshold * 100`, capped at 100%. Both fields
must be present, non-negative integers and the threshold must be greater than
zero. Missing, malformed, boolean and fractional fields remain unknown, not
zero. It is a service-threshold ratio, **not litres** and not a replacement for
**Remaining until descale**, which comes from d512. The separate status entity
shows the numeric `descale_status` code without guessing its meaning and has no
statistics state class. New service entities appear only when valid fields are
available during integration setup; reload after the cloud first supplies them.

### First-time learning versus recurring synchronization

If no validated device-specific frame has been learned, an Eletta cloud-session
statistics request cannot safely be built. Cloud property reads still work, but
may return an older appliance snapshot. A Repair explains the prerequisite
without claiming to know the age of every counter. With HA running, use Coffee
Link once to wake the machine or prepare a supervised beverage with a suitable
container. Close Coffee Link afterwards. The notice clears when a valid frame is
learned; the learned data survives HA restarts. Reopening the official app for
each later refresh is not required.

PR #16, included since beta.1, uses Coffee Link's statistics request (`0xe8 0xf0`),
not the old session-refresh request. It also requests statistics eight seconds
after an accepted DSS preparing-to-ready transition; an hourly cooperative
request remains the fallback. No fresh publication is reported as unverified,
not a guarantee that every unchanged counter is current. Busy, offline and
foreign-session guards remain in place.

### Filter volume correction and preserved history

Beta.2 changes d555 from `/1000` to `/2000` on known `DL-striker-cb` models only.
Twelve paired intervals on ECAM450.65.G showed a cumulative 37.990 L increase
in verified total water versus 75.980 L in the former filter conversion. The
independent d513 filter percentage is passed through unchanged. Other profiles
retain the previous filter conversion until independently verified.

Create a backup **including the Recorder database** before upgrading. Existing
old-scale filter history is moved, unchanged, to a uniquely named legacy archive
through HA's registry/Recorder rename handling. The archive is hidden and
disabled and is not updated. The corrected active entity retains its old entity
ID, unique ID, custom name, area, aliases, labels, visibility, enabled/disabled
choice and entity options; its new statistical series starts cleanly. No history
is deleted and unrelated entities are not changed. The archive retains the old
factor-of-two error deliberately; it is historical evidence, not corrected
consumption. Detailed histories follow HA's normal retention policy.

The migration journals its intended move before renaming and resumes safely if
interrupted. It refuses an archive-ID collision or incomplete Recorder rename
instead of publishing corrected values into the old series. To roll back the
scale transition, restore the pre-upgrade backup rather than only downgrading
the integration. Beta.2 is not a stable-release promotion or a universal model
compatibility claim.

## Česky

### Výsledky prověření #15

- `d701_tot_bev_b` není celkový počet všech nápojů. U ověřené Eletta tvoří část
  souhrnu černých káv; aplikace k němu přidává vybrané ledové kávy z d733.
  Součtem všech viditelných čítačů bychom některé nápoje započítali opakovaně.
- d733 se již používá ve vybraných souhrnech. d734 a d740 nemají automaticky
  stejný význam na všech modelech; bez ověřené definice je nesčítáme ani jim
  nepřiřazujeme odhadnuté jednotky.
- Z platných polí d580 mohou vzniknout dva volitelné diagnostické senzory:
  **Využití limitu odvápnění** a **Kód stavu odvápnění**. Po instalaci jsou
  deaktivované. První je poměr servisní hodnoty a limitu, nikoli litry vody.
  Druhý zobrazuje pouze číselný kód bez odhadovaného slovního významu a nemá
  dlouhodobé statistiky. Chybějící nebo neplatná data se nemění na nulu.
  Dosavadní **Do odvápnění zbývá** zůstává beze změny.
- Při chybějícím naučeném podpisu se zobrazí srozumitelné upozornění v Opravách.
  Při běžícím HA jednou použijte Coffee Link k zapnutí kávovaru nebo bezpečné
  přípravě nápoje pod dohledem a pak aplikaci zavřete. Podpis zůstává uložený
  po restartu; kvůli každé aktualizaci není třeba aplikaci znovu otevírat.

### Voda přes filtr a aktualizace beta.2

U ověřeného profilu `DL-striker-cb` opravujeme převod objemu přes filtr na
`/2000`. Dvanáct porovnaných intervalů prokázalo dlouhodobý dvojnásobný přírůstek
při původním převodu. Procento využití filtru čteme samostatně z kávovaru a
neměníme je. U jiných modelů neprovádíme neověřenou změnu měřítka.

Před aktualizací vytvořte zálohu **včetně databáze Recorderu**. Historii původního
chybného přepočtu uchováme v označeném, skrytém a deaktivovaném archivu; nadále
se do něj nezapisuje. Aktivní položka si zachová ID, vlastní název, oblast,
aliasy, štítky, viditelnost, aktivaci/deaktivaci i uživatelské volby. Správně
přepočtené hodnoty začnou novou statistickou řadu. Žádnou historii nemažeme a
ostatních senzorů se změna netýká. Archiv ponechává původní chybné měřítko jako
doklad; není vydáván za opravenou spotřebu. Platí běžná retenční pravidla HA.

Tím zabráníme tomu, aby HA pokles po opravě přepočtu považoval za výměnu filtru
a přičetl falešnou spotřebu. Přechod lze bezpečně opakovat po přerušení. Návrat
na starý přepočet vyžaduje obnovu předchozí zálohy, ne jen instalaci starší verze.
Beta.1 již ověřila automatické načtení statistik po jednom Espressu připraveném
na displeji se zavřenou Coffee Link. To není potvrzení všech receptů a modelů;
beta.2 má vlastní navazující ověřování a není zatím stabilním vydáním.
