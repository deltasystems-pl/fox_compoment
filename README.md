# F&F Fox devices (Home Assistant)

Integracja dla urządzeń F&F Fox z obsługą rolet (STR1S2), świateł i przekaźników. Komponent korzysta z biblioteki `foxrestapiclient` (release `0.1.17`).

## Najważniejsze funkcje
- Konfiguracja z automatycznym wykrywaniem urządzeń w sieci LAN.
- Ręczne dodawanie urządzeń po adresie IP (pojedynczo lub wiele urządzeń naraz).
- Obsługa rolet z pozycją, pozycją lameli i przyciskiem Stop.
- Zdalne sterowanie światłem i przełącznikami.
- Odczyt wybranych parametrów (R1S1).

## Wymagania
- Home Assistant (Core/Supervised/OS).
- Dostęp do urządzeń F&F Fox w tej samej sieci lokalnej.
- Włączony REST API w urządzeniu F&F Fox.

## Instalacja (HACS)
1. Otwórz HACS w Home Assistant.
2. Dodaj to repozytorium jako Custom Repository (Integration).
3. Zainstaluj integrację.
4. Zrestartuj Home Assistant.

Repozytorium komponentu:
`https://github.com/deltasystems-pl/fox_compoment`

## Instalacja ręczna
1. Skopiuj katalog `custom_components/fandffox` do `config/custom_components/`.
2. Zrestartuj Home Assistant.

## Konfiguracja
1. W Home Assistant przejdź do Integracje.
2. Wyszukaj `F&F Fox devices`.
3. Uruchom konfigurację.
4. Jeśli automatyczne wykrywanie nie znajdzie urządzeń, wybierz opcję ręczną.

W trybie ręcznym podaj:
- adres IP urządzenia,
- typ urządzenia,
- klucz REST API,
- opcjonalnie MAC.

## Obsługiwane urządzenia
- STR1S2 (rolety / żaluzje).
- R1S1, R2S2 (przekaźniki).
- LED2S2, DIM1S2, RGBW (oświetlenie).

## Funkcje rolet (STR1S2)
- Otwieranie i zamykanie.
- Stop ruchu.
- Ustawianie pozycji rolety (0-100%).
- Ustawianie pozycji lameli (0-100%).
- Jednoczesne ustawienie pozycji rolety i lameli.
- Ustawienie pozycji rolety z blokadą czasową.

## Usługi
- `fandffox.set_cover_and_tilt_positions`
- `fandffox.set_cover_position_with_blocking`

## Dashboard (przykłady kart)

### Enhanced Shutter Card
```yaml
type: custom:enhanced-shutter-card
title: Rolety
entities:
  - entity: cover.salon_roleta
    name: Salon
    shutter_preset: shutter
  - entity: cover.sypialnia_roleta
    name: Sypialnia
    shutter_preset: shutter
```

### Tile (wbudowana karta HA)
```yaml
type: tile
entity: cover.salon_roleta
features:
  - type: cover-open-close
  - type: cover-position
  - type: cover-tilt-position
```

### Przykładowy dashboard (pełny widok)
```yaml
title: Dom
views:
  - title: Rolety
    path: rolety
    cards:
      - type: custom:enhanced-shutter-card
        title: Rolety
        entities:
          - entity: cover.salon_roleta
            name: Salon
      - type: tile
        entity: cover.sypialnia_roleta
        name: Sypialnia
        features:
          - type: cover-open-close
          - type: cover-position
          - type: cover-tilt-position
```

## Najczęstsze problemy
- Nie widzisz urządzeń: sprawdź, czy urządzenie jest w tej samej sieci, a REST API jest włączone.
- Błąd klucza: upewnij się, że podany klucz REST API jest prawidłowy.
- Brak odświeżania: sprawdź ustawienia czasu odświeżania w opcjach integracji.

## Wsparcie
- Repozytorium: `https://github.com/deltasystems-pl/fox_compoment`
- Biblioteka: `https://github.com/deltasystems-pl/foxrestapiclient`
