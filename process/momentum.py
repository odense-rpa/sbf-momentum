from datetime import datetime
from momentum_client.manager import MomentumClientManager
from odk_tools.tracking import Tracker

proces_navn = "sbf-momentum"


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
            borgers_markeringer = self.momentum.borgere.hent_markeringer(borger)
            sammenhængende_borgerforløb_markering = next(
                (
                    m
                    for m in borgers_markeringer
                    if m["tag"]["title"] == "Sammenhængende borgerforløb"
                    and m["tag"]["end"] is None
                ),
                None,
            )
            if sammenhængende_borgerforløb_markering:
                self.momentum.borgere.afslut_markering(
                    sammenhængende_borgerforløb_markering, datetime.now().date()
                )

    def find_unikke_sagsbehandlere(self, data) -> list:
        """Tæl antal af unikke sagsbehandlere i data."""
        unikke_sagsbehandlere = []
        seen_emails = set()
        børn = data.get("børn", [])
        # lambda til at fjerne alle børn hvor aktiv er False:
        børn = [x for x in børn if x.get("aktiv", True)]

        for barn in børn:
            sagsbehandlere = barn.get("sagsbehandler", [])
            for sagsbehandler in sagsbehandlere:
                email = sagsbehandler.get("email", "")
                if email not in seen_emails:
                    unikke_sagsbehandlere.append(sagsbehandler)
                    seen_emails.add(email)

        print(f"Antal børn: {len(børn)}")
        print(f"Antal unikke sagsbehandlere: {len(unikke_sagsbehandlere)}")

        return unikke_sagsbehandlere

    def fjern_sagsbehandlere_der_ikke_længere_er_i_unikke(self, data: dict):
        unikke_sagsbehandlere = self.find_unikke_sagsbehandlere(data)
        borger = self.momentum.borgere.hent_borger(data["cpr"])
        borgers_sagsbehandlere = self.momentum.borgere.hent_aktive_sagsbehandlere(
            borger
        )

        unikke_emails = [s["email"] for s in unikke_sagsbehandlere]
        for eksisterende_sagsbehandler in borgers_sagsbehandlere["data"]:
            if eksisterende_sagsbehandler[
                "email"
            ] not in unikke_emails and eksisterende_sagsbehandler.get(
                "responsibilityTypeName"
            ) in ["Dubu-sagsbehandler", "Nexus-sagsbehandler"]:
                self.momentum.borgere.fjern_ansvarlig_eller_privat_kontaktperson(
                    borger, eksisterende_sagsbehandler["email"]
                )
                print(eksisterende_sagsbehandler)

    def tilføj_unikke_sagsbehandlere(self, borger: dict, data: dict):
        # Check om unikke_sagsbehandlere allerede er tilknyttet borger
        borgers_sagsbehandlere = self.momentum.borgere.hent_aktive_sagsbehandlere(
            borger
        )  # Henter igen for at få opdateret liste
        borgers_private_kontaktpersoner = (
            self.momentum.borgere.hent_alle_private_kontaktpersoner(borger)
        )

        unikke_sagsbehandlere = self.find_unikke_sagsbehandlere(data)
        for sagsbehandler in unikke_sagsbehandlere:
            if sagsbehandler["email"] not in [
                bsb["email"] for bsb in borgers_sagsbehandlere["data"]
            ]:
                if sagsbehandler["system"] == "Dubu":
                    sagsbehandler["system"] = sagsbehandler["system"].upper()

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
                    print(f"{sagsbehandler['system']}-sagsbehandler")
                    self.momentum.borgere.opdater_borgers_ansvarlige_og_kontaktpersoner(
                        privat_kontaktperson=True,
                        borger=borger,
                        medarbejderid=kontaktperson_id,
                        medarbejderrolle=f"{sagsbehandler['system']}-sagsbehandler",
                    )

    def inaktiver_sagsbehandlere_til_forælder(self, data: dict):
        # 1. Find unikke sagsbehandlere fra input
        unikke_sagsbehandlere = self.find_unikke_sagsbehandlere(data)

        # 2. Hent borger
        borger = self.momentum.borgere.hent_borger(data["cpr"])

        # 3. Hent borgerens aktive sagsbehandlere
        aktive = self.momentum.borgere.hent_aktive_sagsbehandlere(borger)["data"]

        # 4. Set med emails fra momentum (de aktive)
        aktive_emails = {sb["email"] for sb in aktive}

        # 5. Fjern de unikke sagsbehandlere som allerede er aktive
        for sb in unikke_sagsbehandlere:
            email = sb["email"]
            if email in aktive_emails:
                self.momentum.borgere.fjern_ansvarlig_eller_privat_kontaktperson(
                    borger, email
                )
