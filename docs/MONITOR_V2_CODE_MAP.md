# MonitorV2 (0x75): mapa kódů a pravidla interpretace

Stav analýzy: 2026-08-19

Stav implementace: opraveno ve verzi 1.1.16, regresně pokryto ve verzi 1.1.26
Cílový model: De'Longhi Eletta Explore (`DL-striker-cb`)
Datový zdroj: `d302_monitor_machine`

## Závěr

Dřívější implementace nesprávně používala bajt `Step` jako globální kód
činnosti. Tím vznikal například chybný stav **„Připravuje mléko“** při přípravě
Cold Brew. Od verze 1.1.16 je stav určován podle níže popsaných pravidel.

Hodnota `Step = 4` je doložena u:

- přípravy mléka pro cappuccino,
- odvápnění,
- spuštění běžné kávy,
- Cold Brew na testované Eletta Explore.

`Step` tedy označuje interní fázi aktuálního procesu, nikoli druh nápoje nebo
jednoznačnou činnost. Druh stavu se smí určit pouze z `Status`. Výjimkou je
`Status = 7`: nulový krok znamená připravený kávovar, nenulový krok obecně
znamená probíhající přípravu nápoje. Konkrétní nápoj z MonitorV2 určit nelze.

## Rozložení obsahu paketu

Obálka paketu a CRC nejsou v tabulce zahrnuté. Offsety se počítají od prvního
bajtu obsahu MonitorV2.

| Offset | Délka | Doporučený název | Význam |
|---:|---:|---|---|
| 0 | 1 | `accessory_code` | Připojené příslušenství |
| 1–2 | 2 | `switches` | 16bitové pole fyzických spínačů, little-endian |
| 3–4 | 2 | `alarms_low` | Alarmové bity 0–15 |
| 5 | 1 | `status_code` | Hlavní stav kávovaru |
| 6 | 1 | `step_code` | Interní krok/fáze procesu; nemá globální slovník |
| 7 | 1 | `progress_percentage` | Průběh aktuální fáze 0–100 % |
| 8–9 | 2 | `alarms_high` | Alarmové bity 16–31 |
| 10–12 | 3 | rezervováno | Na známých modelech obvykle nula |

Současné názvy `action` a `progress` jsou zavádějící. Přesnější jsou `step` a
`progress_percentage`.

## Stavové kódy

Toto je profil používaný protokolem ECAM MonitorV2 a potvrzený také fyzickými
testy Eletta Explore. Čísla neuvedená v tabulce se musí zachovat jako neznámá
spolu se surovým kódem; nesmí se jim domýšlet význam.

| Kód | Interní klíč | English | Česky | Jistota / poznámka |
|---:|---|---|---|---|
| 0 | `standby` | Standby | Pohotovostní režim | potvrzeno |
| 1 | `waking_up` | Waking up | Zapíná se | potvrzeno |
| 2 | `going_to_sleep` | Going to sleep | Přechází do pohotovostního režimu | potvrzeno na testované Eletta Explore |
| 3 | — | Unknown | Neznámý stav | jiná integrace jej nazývá „Brewing“, ale pro tento protokol to není bezpečně doloženo |
| 4 | `descaling` | Descaling | Probíhá odvápnění | potvrzeno |
| 5 | `preparing_steam` | Preparing steam | Připravuje páru | potvrzeno ve více implementacích |
| 6 | `recovering` | Recovering | Obnovuje provoz | knihovna Longshot uvádí Recovery; DlghIoT jej označuje jako pravděpodobný |
| 7 + krok 0 | `ready` | Ready | Připraveno | potvrzeno |
| 7 + krok > 0 | `preparing_beverage` | Preparing beverage | Připravuje nápoj | bezpečný obecný význam; nápoj nelze určit z kódu kroku |
| 8 | `rinsing` | Rinsing | Probíhá proplach | potvrzeno |
| 9 | — | Unknown | Neznámý stav | jiná integrace jej nazývá „Going to sleep“, ale Eletta Explore používá kód 2 |
| 10 | `preparing_milk` | Preparing milk | Připravuje mléko | potvrzeno |
| 11 | `dispensing_hot_water` | Dispensing hot water | Vydává horkou vodu | potvrzeno |
| 12 | `cleaning_milk_system` | Cleaning milk system | Čistí mléčný systém | potvrzeno |
| 16 | `preparing_chocolate` | Preparing chocolate | Připravuje čokoládu | potvrzeno knihovnou protokolu |
| 17 | `preparing_milk_variant` | Preparing milk (variant) | Připravuje mléko (varianta) | pouze DlghIoT; rozdíl proti kódu 10 není znám |
| 29 | `unknown` | Unknown | Neznámý stav | zachovat surový kód 29, význam není znám |
| ostatní 0–255 | `unknown` | Unknown | Neznámý stav | bez spekulace, vždy připojit surový kód |

Poznámka: projekt `sk7n4k3d/delonghi-ha` obsahuje alternativní tabulku 0–9,
která je v rozporu s jeho vlastní dokumentací i se zachycenými pakety ECAM.
Například kód 2 označuje jako `Idle`, zatímco na testované Eletta Explore byl
fyzicky potvrzen jako přechod do pohotovostního režimu. Tuto alternativní
tabulku proto nelze pro tento model převzít.

## Kódy kroku (Step)

Pro `Step` neexistuje jednotná převodní tabulka. Pozorované hodnoty jsou pouze
čísla fází a stejná hodnota se opakuje v nesouvisejících procesech.

| Krok | Doložené kontexty | Bezpečný výklad |
|---:|---|---|
| 0 | připraveno, dokončení procesu | žádný aktivní krok |
| 1 | zapínání, vypínání | interní fáze 1 |
| 2 | proplach, začátek mléčného nápoje; na Eletta i klidový rámec pohotovosti | interní fáze 2 |
| 3 | pohotovost, vypínání, čištění mléka, horká voda | interní fáze 3 |
| 4 | káva, Cold Brew, mléko, odvápnění | interní fáze 4 |
| 5 | zapínání, proplach | interní fáze 5 |
| 6 | vypínání | interní fáze 6 |
| 7–9 | zapínání/proplach/odvápnění podle modelu | pouze interní fáze |
| 14 | dokončení nebo zrušení nápoje v jednom zachyceném paketu | pouze interní fáze |
| 17 | odvápnění | interní fáze 17 |
| ostatní | možné, ale nezmapované | zobrazit jen v diagnostice |

Zakázané globální převody, které byly z dřívější implementace odstraněny, jsou:

- `3 → vydává horkou vodu`,
- `4 → připravuje mléko`,
- `5 → zapíná se`,
- `6 → mele kávu`,
- `11 → připravuje kávu`.

Žádný z těchto převodů není obecně platný.

## Příslušenství

| Kód | English | Česky | Jistota |
|---:|---|---|---|
| 0 | None | Bez příslušenství | potvrzeno |
| 1 | Hot water spout | Výpusť horké vody | potvrzeno |
| 2 | LatteCrema Hot | Nádobka LatteCrema Hot | potvrzeno |
| 3 | Chocolate accessory | Nádobka na čokoládu | potvrzeno na podporovaných ECAM modelech |
| 4 | LatteCrema Hot – cleaning position | LatteCrema Hot v poloze čištění | potvrzeno |
| 5 | Unknown, probably descaling-related | Neznámé, pravděpodobně souvisí s odvápněním | nepotvrzeno |
| 6 | LatteCrema Cool | Nádobka LatteCrema Cool | uvedeno v DlghIoT; relevantní pro Eletta Explore |
| 7 | LatteCrema Cool – cleaning position | LatteCrema Cool v poloze čištění | uvedeno v DlghIoT; relevantní pro Eletta Explore |
| 8–255 | Unknown | Neznámé příslušenství | zachovat surový kód |

## Spínačové bity

Hodnota 1 zpravidla znamená aktivní spínač. U bitů 3 a 4 je fyzicky potvrzeno,
že aktivní bit znamená chybějící nádobu.

| Bit | Nejbezpečnější význam | Jistota / konflikt |
|---:|---|---|
| 0 | výpusť vody připojena | potvrzeno |
| 1 | motor v horní poloze | pravděpodobné |
| 2 | motor v dolní poloze | pravděpodobné |
| 3 | zásobník sedliny chybí | potvrzeno z paketů |
| 4 | nádržka na vodu chybí | potvrzeno z paketů |
| 5 | otočný ovladač / neurčeno | modelově závislé |
| 6 | nízká hladina vody | uvedeno ve více zdrojích |
| 7 | neurčeno | DlghIoT: vysoká hladina vody; Longshot: konvice na kávu |
| 8 | nádobka LatteCrema Hot připojena | jiné zdroje: IFD carafe |
| 9 | modelově závislé | DlghIoT: LatteCrema Hot v čištění; Longshot: nádobka na čokoládu |
| 10 | ovladač v poloze Clean | pravděpodobné |
| 11 | LatteCrema Cool připravena | pouze DlghIoT |
| 12 | neznámé | nezmapováno |
| 13 | otevřená servisní dvířka | pravděpodobné |
| 14 | otevřená násypka předemleté kávy | pravděpodobné |
| 15 | LatteCrema Cool v poloze čištění | pouze DlghIoT |

Bit 7 se dříve chybně prezentoval jako jistý atribut `water_level_high`. Od
verze 1.1.16 zůstává bez modelově specifického fyzického ověření pouze v surové
diagnostice.

## Alarmové bity

První čtyři bity jsou aktuální integrací používány a jsou nejlépe doložené.
Vyšší bity se mezi modely a implementacemi částečně rozcházejí.

| Bit | Známý / navržený význam | Jistota / konflikt |
|---:|---|---|
| 0 | prázdná nádržka na vodu | vysoká |
| 1 | plný zásobník sedliny | vysoká |
| 2 | nutné odvápnění | vysoká |
| 3 | nutná výměna vodního filtru | vysoká |
| 4 | káva namleta příliš jemně | střední |
| 5 | došla kávová zrna | střední |
| 6 | nutný servis kávovaru | střední |
| 7 | porucha teplotního čidla kávového ohřevu | střední |
| 8 | příliš mnoho kávy | střední |
| 9 | porucha motoru spařovací jednotky | střední |
| 10 | porucha teplotního čidla páry | střední |
| 11 | problém s odkapávací miskou | zdroje se liší: prázdná vs. chybějící |
| 12 | problém hydraulického okruhu | střední |
| 13 | poloha nádržky na vodu | polarita a použití se mezi zdroji liší; pro chybějící nádržku je spolehlivější spínač 4 |
| 14 | vyčistit mléčný ovladač | střední |
| 15 | došla zrna – druhý zásobník / varianta | modelově závislé |
| 16 | neurčeno | DlghIoT: nízká hladina; Longshot: nádržka příliš plná; jiná integrace: nutné čištění |
| 17 | chybí zásobník zrn | modelově závislé |
| 18 | přítomnost mřížky / mřížka chybí | nejistá polarita |
| 19 | čidlo spařovací jednotky | pouze protokolová knihovna |
| 20 | nedostatek kávy | pouze protokolová knihovna |
| 21 | chyba komunikace rozšiřujícího modulu | pouze protokolová knihovna |
| 22 | chyba komunikace dílčích modulů | pouze protokolová knihovna |
| 23 | porucha mlecí jednotky 1 | pouze protokolová knihovna |
| 24 | porucha mlecí jednotky 2 | pouze protokolová knihovna |
| 25 | porucha kondenzačního ventilátoru | pouze protokolová knihovna |
| 26 | chyba komunikace hodin/Bluetooth | pouze protokolová knihovna |
| 27 | chyba komunikace SPI | pouze protokolová knihovna |
| 28–31 | neznámé | nezmapováno |

Alarmy 4–27 se nemají automaticky vytvářet jako produkční senzory bez ověření
polarity a významu na konkrétním modelu. Bezpečné je uchovat celé pole v
diagnostice a neznámé aktivní bity zalogovat.

## Doporučená rozhodovací logika

1. Dekódovat `Status`, `Step` a `Progress` odděleně.
2. Nikdy nepřepisovat hlavní stav podle samotného `Step`.
3. Pro `Status = 7`:
   - `Step = 0` → `ready`,
   - `Step > 0` → `preparing_beverage`.
4. Pro ostatní známé statusy použít přímo tabulku stavů.
5. Neznámý status zobrazit jako `unknown` a připojit `status_code`.
6. `Step`, procenta, příslušenství a hexadecimální bitová pole ponechat v
   diagnostických atributech.
7. Před spuštěním receptu považovat za připravený pouze stav `7 / krok 0`;
   nepoužívat seznam domnělých „aktivních akcí“.
8. Druh připravovaného nápoje lze spolehlivě uvést pouze tehdy, když jej zná
   integrace ze svého právě potvrzeného příkazu. MonitorV2 jej sám neobsahuje.

## Stav implementace

Ve verzi 1.1.16 byly provedeny všechny změny vyplývající z analýzy:

- odstraněna globální interpretace kroku jako činnosti;
- doplněn obecný stav `preparing_beverage` v angličtině i češtině;
- parser a předstartovní kontrola používají kombinaci `Status 7 / Step 0` jako
  jediný potvrzený stav připravenosti;
- diagnostika používá názvy `step` a `progress_percentage` a zachovává
  kompatibilní aliasy pouze uvnitř parseru;
- odstraněn nedoložený výklad `water_level_high`;
- neznámé surové kódy zůstávají dostupné v diagnostice;
- regresní testy ověřují známé i neznámé stavy a zejména to, že
  `Status 7 + Step 4` není interpretován jako příprava mléka.

Ve verzi 1.1.26 jsou všechny větve parseru a navazující logiky pokryty
automatickými testy. Nový význam kódu se přesto nesmí přidat bez zachyceného
paketu a fyzického ověření na konkrétním modelu.

## Použité zdroje

- actabi/delonghi_coffeelink – původní parser používá pro stav pouze `Status` a
  `Step` pouze předává jako surový atribut:
  https://github.com/actabi/delonghi_coffeelink/blob/main/custom_components/delonghi_coffeelink/monitor.py
- Longshot – typy, stavové kódy a zachycené pakety:
  https://github.com/mmastrac/longshot/blob/main/src/protocol/hardware_enums.rs
  https://github.com/mmastrac/longshot/blob/main/src/protocol/request/monitor.rs
  https://github.com/mmastrac/longshot/blob/main/src/protocol/mod.rs
- DlghIoT – dokumentace rozložení MonitorV2, příslušenství a stavů:
  https://framagit.org/mattgk/dlghiot
- Arbuzov/home_assistant_delonghi_primadonna – fyzicky zachycené pakety; bajt
  fáze je popsán jako `cooking progress stage`:
  https://github.com/Arbuzov/home_assistant_delonghi_primadonna/blob/master/DEBUG_NOTES.md
- sk7n4k3d/delonghi-ha – srovnávací zdroj pro cloudovou Eletta Explore; jeho
  alternativní stavová tabulka nebyla převzata kvůli popsaným rozporům:
  https://github.com/sk7n4k3d/delonghi-ha
