# SBF Momentum - Sammenhængende Borgerforløb

En automatiseringsproces til synkronisering af sagsbehandlere og markeringer i Momentum-systemet for sammenhængende borgerforløb (SBF).

## 📋 Beskrivelse

Dette projekt automatiserer håndtering af sammenhængende borgerforløb i Momentum ved at:
- Synkronisere sagsbehandlere fra DUBU og Nexus systemer til borgere i Momentum
- Oprette og afslutte markeringen "Sammenhængende borgerforløb" baseret på borgerens aktive børn og tilknyttede sagsbehandlere
- Holde borgernes sagsbehandlere opdateret når børnenes status ændrer sig

## 🚀 Funktionalitet

### Hovedprocesser

**Aktive forældreforløb:**
- Tilføjer unikke sagsbehandlere fra børnenes sager til forælderen
- Fjerner sagsbehandlere der ikke længere er relevante
- Opretter/vedligeholder markeringen "Sammenhængende borgerforløb"

**Inaktive forældreforløb:**
- Fjerner eksterne sagsbehandlere (DUBU/Nexus) fra forælderen
- Afslutter markeringen "Sammenhængende borgerforløb" hvis ingen relevante eksterne sagsbehandlere er tilbage

### Sagsbehandler-håndtering

Processen håndterer sagsbehandlere fra:
- **DUBU** - DUBU-sagsbehandler
- **Nexus** - Nexus-sagsbehandler

Sagsbehandlere oprettes som private kontaktpersoner i Momentum og tilknyttes derefter som ansvarlige med passende roller.

## 🛠️ Installation

### Forudsætninger
- Python 3.13+
- UV package manager
- Adgang til Automation Server
- Momentum API credentials
- Odense SQL Server credentials (til tracking)

### Setup

1. **Klon repository:**
```bash
git clone https://github.com/odense-rpa/sbf-momentum.git
cd sbf-momentum
```

2. **Installer dependencies:**
```bash
uv sync
```

3. **Konfigurer credentials i Automation Server:**
   - `Momentum - produktion`: API credentials til Momentum
   - `Odense SQL Server`: Tracking database credentials

## 📊 Datastruktur

### Work Item Format

Work items skal indeholde følgende struktur:

```json
{
  "cpr": "1234567890",
  "aktiv": true,
  "børn": [
    {
      "aktiv": true,
      "sagsbehandler": [
        {
          "navn": "Sagsbehandler Navn",
          "email": "email@example.com",
          "telefon": "12345678",
          "system": "Dubu"
        }
      ]
    }
  ]
}
```

### Felter

- `cpr`: Borgerens CPR-nummer
- `aktiv`: Om forældreforløbet er aktivt
- `børn`: Array af børneobjekter
  - `aktiv`: Om barnet er aktivt i forløbet
  - `sagsbehandler`: Array af sagsbehandlere tilknyttet barnet


## 🏗️ Arkitektur

### Projektstruktur

```
sbf-momentum/
├── main.py                 # Entry point og workqueue håndtering
├── process/
│   └── momentum.py         # MomentumService med forretningslogik
├── pyproject.toml          # Dependencies og projekt konfiguration
└── README.md
```

### Afhængigheder

- **automation-server-client**: Integration med Automation Server workqueue
- **momentum-client**: API klient til Momentum-systemet
- **odk-tools**: Tracking og logging funktionalitet

## 📝 Forretningslogik

### Beslutningsflow

```
Er forælder aktiv OG har aktive børn?
├─ JA:
│  ├─ Fjern sagsbehandlere der ikke længere er i børnenes sager
│  ├─ Tilføj nye unikke sagsbehandlere fra børnenes sager
│  └─ Sikr "Sammenhængende borgerforløb" markering er aktiv
│
└─ NEJ:
   ├─ Fjern alle DUBU/Nexus sagsbehandlere
   └─ Afslut "Sammenhængende borgerforløb" markering (hvis ingen relevante eksterne sagsbehandlere)
```

## ⚙️ Udvikling

### Code Quality

Projektet bruger Ruff til linting og formatting:

```bash
uv run ruff check .
uv run ruff format .
```

## 👥 Kontakt

For spørgsmål eller support, kontakt RPA-teamet i Odense Kommune.

