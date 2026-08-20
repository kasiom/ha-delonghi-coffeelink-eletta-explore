# De'Longhi Coffee Link – Eletta Explore pro Home Assistant

Neoficiální samostatná cloudová integrace pro kávovary De'Longhi Eletta Explore
připojené přes Coffee Link a platformu Ayla IoT.

## Stav projektu

| Položka | Stav |
|---|---|
| Aktuální vydání | 1.2.1 – nainstalováno přes HACS a ověřeno načtení v cílovém Home Assistantu |
| Lokální beta | 1.3.0-beta.2 – hybridní DSS push/polling, nezveřejněno na GitHubu |
| Fyzické ověření příkazů | 1.2.0 – probuzení, Cold Brew Start/Stop a pohotovostní režim; 1.2.1 tyto části běhu nemění |
| Ověřený kávovar | Eletta Explore ECAM450.65.G (`DL-striker-cb`, oblast EU) |
| Home Assistant | 2026.8.2 nebo novější |
| Jazyky | čeština a angličtina |
| Automatické testy | 334 izolovaných testů se 100% pokrytím + testy ve skutečném HA |
| Distribuce | vlastní repozitář HACS nebo ruční instalace z vydání na GitHubu; zařazení do výchozího katalogu se posuzuje |

Profil PrimaDonna Soul zůstává v kódu pro zkoušky kompatibility, neprošel však
stejným fyzickým ověřením a je označen jako experimentální.

## Co integrace poskytuje

- stav kávovaru, připojení ke cloudu a údržbové stavy;
- téměř okamžité cloudové aktualizace DSS a přesná potvrzení příkazů s
  automatickým návratem k 30sekundovému dotazování při výpadku streamu;
- počitadla nápojů, vody, filtru, odvápnění a zásobníku sedliny;
- dynamická tlačítka nápojů naučená z oficiální aplikace Coffee Link;
- automatické načtení přidaného kávovaru a odstranění záznamů odebraného
  kávovaru;
- zapnutí, pohotovostní režim, synchronizaci dat a bezpečné zastavení;
- rozpoznání kolize relace Coffee Link a stav posledního příkazu Home Assistantu;
- kontrolu připravenosti, nádržky na vodu a zásobníku sedliny před přípravou;
- ověření kontrolního součtu, typu příkazu, nápoje a podpisu zařízení;
- diagnostiku bez přihlašovacích údajů, identifikátorů zařízení a surových příkazů;
- přeložené položky Opravy, které upozorní na poškozený uložený příkaz a po
  opětovném naučení samy zmizí.

## Instalace

[![Otevřít tento repozitář v HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kasiom&repository=ha-delonghi-coffeelink-eletta-explore&category=integration)

Dokud integrace nebude součástí výchozího katalogu HACS, přidejte ji jednou jako
vlastní repozitář:

[Žádost o zařazení](https://github.com/hacs/default/pull/10136) je nyní ve frontě
na kontrolu HACS.

1. v HACS otevřete **Vlastní repozitáře**;
2. přidejte
   `https://github.com/kasiom/ha-delonghi-coffeelink-eletta-explore`
   jako **Integraci**;
3. nainstalujte **De'Longhi Coffee Link – Eletta Explore** a restartujte Home
   Assistant;
4. v **Nastavení → Zařízení a služby → Přidat integraci** vyhledejte
   **De'Longhi Coffee Link – Eletta Explore**.

Při ruční instalaci stáhněte nejnovější vydání, zkopírujte celou složku
`custom_components/ha_delonghi_coffeelink_eletta_explore` do
`/config/custom_components/` a restartujte Home Assistant. Nemíchejte soubory z
různých vydání. Podrobnosti jsou v [návodu k instalaci](INSTALLATION.md).

## Naučení nápoje

Připravte požadovaný nápoj jednou v oficiální aplikaci Coffee Link, zatímco
Home Assistant běží. Integrace příkaz zkontroluje, bezpečně uloží a vytvoří
odpovídající tlačítko. Přes DSS se nové tlačítko zpravidla objeví ihned; při
náhradním dotazování nejpozději přibližně do 30 sekund. Opakované
naučení stejného receptu nahradí jeho starší příkaz.

Tlačítko **Zastavit přípravu nápoje** je dostupné jen tehdy, když integrace zná
právě připravovaný nápoj i jeho platný příkaz pro zastavení.

## Bezpečnost

Vzdálený příkaz může spustit výdej horké vody, kávy, mléka nebo páry. Vždy
zkontrolujte správný šálek, připojené příslušenství a prostor kolem kávovaru.
Integraci nepoužívejte k bezobslužnému vzdálenému výdeji.

Další informace: [použití a bezpečnost](USAGE.md),
[kompatibilita](COMPATIBILITY.md), [řešení potíží](TROUBLESHOOTING.md) a
[ochrana soukromí](PRIVACY.md).
