from asyncio.log import logger
from datetime import datetime
from momentum_client.manager import MomentumClientManager
from odk_tools.tracking import Tracker

proces_navn = "SBF Momentum"


class MomentumService:
    """Service klasse til at håndtere sbf-Momentum"""

    def __init__(self, tracker: Tracker, momentum: MomentumClientManager):
        """Initialiserer MomentumService med tracker og momentum klient.

        Args:
            momentum (MomentumClientManager): Instans af MomentumClientManager.
            tracker (Tracker): Instans af logging af procesaktiviteter.
        """
        self.tracker = tracker
        self.momentum = momentum

    def synkroniser_markering(self, borger: dict):
        borgers_markeringer = self.momentum.borgere.hent_markeringer(borger)
        # Check om borger har markering "Sammenhængende borgerforløb"
        sammenhængende_borgerforløb_markering = next(
            (
                m
                for m in borgers_markeringer
                if m["tag"]["title"] == "Sammenhængende borgerforløb"
                and m["tag"]["end"] is None
            ),
            None,
        )
        if sammenhængende_borgerforløb_markering is None:
            self.momentum.borgere.opret_markering(
                borger=borger,
                markeringsnavn="Sammenhængende borgerforløb",
                start_dato=datetime.now().date(),
            )

    def afslut_markering(self, borger: dict):
        aktive = self.momentum.borgere.hent_aktive_sagsbehandlere(borger)["data"]
        # kig aktive igennem. Hvis der ikke er nogle med responsibilityTypeName "DUBU-sagsbehandler" eller
        # "Nexus-sagsbehandler", så fjern markering
        ekstern_sagsbehandler_typer = {"DUBU-sagsbehandler", "Nexus-sagsbehandler"}

        har_relevant_ekstern_sagsbehandler = any(
            sb.get("responsibilityTypeName") in ekstern_sagsbehandler_typer
            for sb in aktive
        )

        if not har_relevant_ekstern_sagsbehandler:
            markering_navne = {
                "Sammenhængende borgerforløb",
                "Sammenhængende Borgerforløb - Udsatte familier",
                "Sammenhængende borgerforløb - afventer samtykke",
                "Sammenhængende borgerforløb - deltager IKKE",
                "Sammenhængende borgerforløb - deltager",
            }
            
            borgers_markeringer = self.momentum.borgere.hent_markeringer(borger)
            aktive_relevante_markeringer = [
                m for m in borgers_markeringer
                if m["tag"]["title"] in markering_navne and m["tag"]["end"] is None
            ]
            
            for markering in aktive_relevante_markeringer:
                try:
                    self.momentum.borgere.afslut_markering(
                        markering, datetime.now().date()
                    )
                except Exception as e:
                    logger.error(f"Fejl ved afslutning af markering: {e}")
                    continue

    def find_unikke_sagsbehandlere(self, data) -> list:
        """Find unikke sagsbehandlere blandt aktive børn."""
        unikke_sagsbehandlere = []
        seen_emails = set()
        børn = data.get("børn", [])
        # Filtrer kun aktive børn
        børn = [x for x in børn if x.get("aktiv", True)]

        for barn in børn:
            sagsbehandlere = barn.get("sagsbehandler", [])
            for sagsbehandler in sagsbehandlere:

                if not sagsbehandler.get("telefon"): # Hvis telefonnummer ikke er angivet, sæt til "00000000"
                    sagsbehandler["telefon"] = "00000000"

                email = sagsbehandler.get("email", "")
                if email not in seen_emails:
                    unikke_sagsbehandlere.append(sagsbehandler)
                    seen_emails.add(email)

        return unikke_sagsbehandlere

    def fjern_sagsbehandlere_der_ikke_længere_er_i_unikke(self, data: dict):
        unikke_sagsbehandlere = self.find_unikke_sagsbehandlere(data)
        borger = self.momentum.borgere.hent_borger(data["cpr"])
        borgers_sagsbehandlere = self.momentum.borgere.hent_aktive_sagsbehandlere(
            borger
        )

        unikke_emails = [s["email"] for s in unikke_sagsbehandlere]
        for eksisterende_sagsbehandler in borgers_sagsbehandlere["data"]:
            responsibility = (eksisterende_sagsbehandler.get("responsibilityTypeName") or "").lower()
            if eksisterende_sagsbehandler[
                "email"
            ] not in unikke_emails and responsibility in ["dubu-sagsbehandler", "nexus-sagsbehandler"]:
                self.momentum.borgere.fjern_ansvarlig_eller_privat_kontaktperson(
                    borger, eksisterende_sagsbehandler["email"]
                )

    def tilføj_unikke_sagsbehandlere(self, borger: dict, data: dict):
        # Check om unikke_sagsbehandlere allerede er tilknyttet borger
        borgers_sagsbehandlere = self.momentum.borgere.hent_aktive_sagsbehandlere(
            borger
        )  # Henter igen for at få opdateret liste
        borgers_private_kontaktpersoner = (
            self.momentum.borgere.hent_alle_private_kontaktpersoner(borger)
        )

        unikke_sagsbehandlere = self.find_unikke_sagsbehandlere(data)
        afregn_opgave = False
        for sagsbehandler in unikke_sagsbehandlere:
            if sagsbehandler["email"] not in [
                bsb["email"] for bsb in borgers_sagsbehandlere["data"]
            ]:
                if sagsbehandler["system"] == "Dubu":
                    sagsbehandler["system"] = sagsbehandler["system"].upper()

                # Sæt afregn_opgave til True hvis der tilføjes en sagsbehandler
                afregn_opgave = True

                # Check om sagsbehandler allerede er oprettet som privat kontaktperson
                if sagsbehandler["email"] not in [
                    bpk["email"]["address"]
                    for bpk in borgers_private_kontaktpersoner["data"]
                ]:
                    # opretter privat kontaktperson hvis ikke eksisterende
                    kontaktperson = self.momentum.borgere.opret_privat_kontaktperson(
                        borger,
                        navn=sagsbehandler["navn"],
                        email=sagsbehandler["email"],
                        telefon=sagsbehandler.get("telefon", ""),
                    )
                    # tilføjer denne som sagsbehandler:
                    self.momentum.borgere.opdater_borgers_ansvarlige_og_kontaktpersoner(
                        privat_kontaktperson=True,
                        borger=borger,
                        medarbejderid=kontaktperson["id"],
                        medarbejderrolle=f"{sagsbehandler['system']}-sagsbehandler",
                    )
                # Sagsbehandler eksisterer som privat kontaktperson, så vi tilføjer som sagsbehandler direkte
                else:
                    # find sagsbehandler id fra borgers_private_kontaktpersoner
                    kontaktperson_id = next(
                        bpk["id"]
                        for bpk in borgers_private_kontaktpersoner["data"]
                        if bpk["email"]["address"] == sagsbehandler["email"]
                    )
                    self.momentum.borgere.opdater_borgers_ansvarlige_og_kontaktpersoner(
                        privat_kontaktperson=True,
                        borger=borger,
                        medarbejderid=kontaktperson_id,
                        medarbejderrolle=f"{sagsbehandler['system']}-sagsbehandler",
                    )

        if afregn_opgave:
            self.tracker.track_task(process_name=proces_navn)

    def inaktiver_sagsbehandlere_til_forælder(self, data: dict):
        # 1. Find unikke sagsbehandlere fra input
        unikke_sagsbehandlere = self.find_unikke_sagsbehandlere(data)

        # 2. Hent borger
        borger = self.momentum.borgere.hent_borger(data["cpr"])
        myndighedstilknytning = self.momentum.momentum_client.get(f"citizens/{borger['id']}/jobcenterAffiliations").json()
        if myndighedstilknytning and myndighedstilknytning[0]["jobcenterId"] != "46101":
            return  # Skip only if the citizen has an affiliation and it's not the specified job center

        # 3. Hent borgerens aktive sagsbehandlere
        aktive = self.momentum.borgere.hent_aktive_sagsbehandlere(borger)["data"]

        # 4. Set med emails fra momentum (de aktive)
        aktive_emails = {sb["email"] for sb in aktive}

        # 5. Fjern de unikke sagsbehandlere som allerede er aktive
        afregn_opgave = False
        for sb in unikke_sagsbehandlere:
            email = sb["email"]
            if email in aktive_emails:
                self.momentum.borgere.fjern_ansvarlig_eller_privat_kontaktperson(
                    borger, email
                )
                afregn_opgave = True

        # 6. Log processen
        if afregn_opgave:
            self.tracker.track_task(process_name=proces_navn)
