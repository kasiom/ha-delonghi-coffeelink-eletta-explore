# De'Longhi Coffee Link – Eletta Explore pro Home Assistant

Neoficiální samostatná cloudová integrace pro kávovary De'Longhi Eletta Explore
připojené přes Coffee Link a platformu Ayla IoT.

## Stav projektu

| Položka | Stav |
|---|---|
| Kandidát na vydání | 1.2.0 (zatím nezveřejněn) |
| Základ fyzického ověření | [1.1.26](https://github.com/kasiom/ha-delonghi-coffeelink-eletta-explore/releases/tag/v1.1.26) |
| Ověřený kávovar | Eletta Explore ECAM450.65.G (`DL-striker-cb`, oblast EU) |
| Home Assistant | 2026.8.2 nebo novější |
| Jazyky | čeština a angličtina |
| Automatické testy | 311 izolovaných testů se 100% pokrytím + testy ve skutečném HA |
| Repozitář | soukromé ověřování; nyní pouze ruční instalace |

Profil PrimaDonna Soul zůstává v kódu pro zkoušky kompatibility, neprošel však
stejným fyzickým ověřením a je označen jako experimentální.

## Co integrace poskytuje

- stav kávovaru, připojení ke cloudu a údržbové stavy;
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

HACS vyžaduje veřejně dostupný repozitář. Dokud je tento repozitář soukromý:

1. stáhněte jej z GitHub účtu s uděleným přístupem;
2. zkopírujte celou složku
   `custom_components/ha_delonghi_coffeelink_eletta_explore` do
   `/config/custom_components/`;
3. restartujte Home Assistant;
4. v **Nastavení → Zařízení a služby → Přidat integraci** vyhledejte
   **De'Longhi Coffee Link – Eletta Explore**.

Po zveřejnění bude možné repozitář přidat do HACS jako vlastní repozitář typu
**Integrace**. Podrobnosti jsou v [návodu k instalaci](INSTALLATION.md).

## Naučení nápoje

Připravte požadovaný nápoj jednou v oficiální aplikaci Coffee Link, zatímco
Home Assistant běží. Integrace příkaz zkontroluje, bezpečně uloží a vytvoří
odpovídající tlačítko. Nové tlačítko se zpravidla objeví do 30 sekund. Opakované
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
