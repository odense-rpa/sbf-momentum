import asyncio
import logging
import sys
from datetime import datetime

from automation_server_client import AutomationServer, Workqueue, WorkItemError, Credential
from momentum_client.manager import MomentumClientManager
from odk_tools.tracking import Tracker

tracker: Tracker
momentum: MomentumClientManager
proces_navn = "sbf-momentum"

def tilføj_sagsbehandlere_til_forælder(data):
    unikke_sagsbehandlere = find_unikke_sagsbehandlere(data)
    borger = momentum.borgere.hent_borger(data["cpr"])
    borgers_sagsbehandlere = momentum.borgere.hent_aktive_sagsbehandlere(borger)
    borgers_private_kontaktpersoner = momentum.borgere.hent_alle_private_kontaktpersoner(borger)
    borgers_markeringer = momentum.borgere.hent_markeringer(borger)

    # Check om borger har markering "Sammenhængende borgerforløb"
    sammenhængende_borgerforløb_markering = next(
        (m for m in borgers_markeringer if m["tag"]["title"] == "Sammenhængende borgerforløb" and m["tag"]["end"] is None),
        None
    )
    if sammenhængende_borgerforløb_markering is None:
        momentum.borgere.opret_markering(
            borger=borger,
            markeringsnavn="Sammenhængende borgerforløb",
            start_dato=datetime.now().date(),
        )

    # Check om unikke_sagsbehandlere allerede er tilknyttet borger
    for sagsbehandler in unikke_sagsbehandlere:
        if sagsbehandler["email"] not in [bsb["email"] for bsb in borgers_sagsbehandlere["data"]]:
            if sagsbehandler["system"] == "Dubu": 
                sagsbehandler["system"] = sagsbehandler["system"].upper()

            # Check om sagsbehandler allerede er oprettet som privat kontaktperson
            if sagsbehandler["email"] not in [bpk["email"]["address"] for bpk in borgers_private_kontaktpersoner["data"]]:
                # opretter privat kontaktperson hvis ikke eksisterende
                kontaktperson = momentum.borgere.opret_privat_kontaktperson(
                    borger,
                    navn=sagsbehandler["navn"],
                    email=sagsbehandler["email"],
                    telefon=sagsbehandler.get("telefon", ""),
                )
                # tilføjer denne som sagsbehandler:
                momentum.borgere.opdater_borgers_ansvarlige_og_kontaktpersoner(
                    privat_kontaktperson=True,
                    borger=borger,
                    kontaktperson=kontaktperson["id"],
                    medarbejderrolle=f"{sagsbehandler["system"]}-sagsbehandler",
                )
            # Sagsbehandler eksisterer som privat kontaktperson, så vi tilføjer som sagsbehandler direkte
            else:
                # find sagsbehandler id fra borgers_private_kontaktpersoner
                kontaktperson_id = next(
                    bpk["id"]
                    for bpk in borgers_private_kontaktpersoner["data"]
                    if bpk["email"]["address"] == sagsbehandler["email"]
                )
                print(f"{sagsbehandler["system"]}-sagsbehandler")
                momentum.borgere.opdater_borgers_ansvarlige_og_kontaktpersoner(
                    privat_kontaktperson=True,
                    borger=borger,
                    medarbejderid=kontaktperson_id,
                    medarbejderrolle=f"{sagsbehandler["system"]}-sagsbehandler",
                )



    return unikke_sagsbehandlere

def inaktiver_sagsbehandlere_til_forælder(data):
    # 1. Find unikke sagsbehandlere fra input
    unikke_sagsbehandlere = find_unikke_sagsbehandlere(data)

    # 2. Hent borger
    borger = momentum.borgere.hent_borger(data["cpr"])

    # 3. Hent borgerens aktive sagsbehandlere
    aktive = momentum.borgere.hent_aktive_sagsbehandlere(borger)["data"]

    # 4. Set med emails fra momentum (de aktive)
    aktive_emails = { sb["email"] for sb in aktive }

    # 5. Fjern de unikke sagsbehandlere som allerede er aktive
    for sb in unikke_sagsbehandlere:
        email = sb["email"]
        if email in aktive_emails:
            momentum.borgere.fjern_ansvarlig_eller_privat_kontaktperson(
                borger,
                email
            )
    
    aktive = momentum.borgere.hent_aktive_sagsbehandlere(borger)["data"]
    # kig aktive igennem. Hvis der ikke er nogle med responsibilityTypeName "DUBU-sagsbehandler" eller 
    # "Nexus-sagsbehandler", så fjern markering
    ekstern_sagsbehandler_typer = {"DUBU-sagsbehandler", "Nexus-sagsbehandler"}

    har_relevant_ekstern_sagsbehandler = any(
        sb.get("responsibilityTypeName") in ekstern_sagsbehandler_typer
        for sb in aktive
    )

    if not har_relevant_ekstern_sagsbehandler:
        borgers_markeringer = momentum.borgere.hent_markeringer(borger)
        sammenhængende_borgerforløb_markering = next((m for m in borgers_markeringer if m['tag']['title'] == "Sammenhængende borgerforløb" and m['tag']['end'] is None), None)
        if sammenhængende_borgerforløb_markering:
            momentum.borgere.afslut_markering(
                sammenhængende_borgerforløb_markering, datetime.datetime.today()
            )
        pass

    print("hej")

def find_unikke_sagsbehandlere(data) -> list:
    """Tæl antal af unikke sagsbehandlere i data."""
    unikke_sagsbehandlere = []
    seen_emails = set()
    børn = data.get("børn", [])
    #lambda til at fjerne alle børn hvor aktiv er False:
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


async def populate_queue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)

    logger.info("Hello from populate workqueue!")


async def process_workqueue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)

    logger.info("Hello from process workqueue!")

    for item in workqueue:
        with item:
            data = item.data  # Item data deserialized from json as dict


            try:
                # Kald den relevante funktion baseret på om data er aktiv
                if data["aktiv"]:
                    tilføj_sagsbehandlere_til_forælder(data)
                else:
                    inaktiver_sagsbehandlere_til_forælder(data)
                    
                # hent borger i momentum via cpr:
                borger = momentum.borgere.hent_borger(data["cpr"])
                borgers_sagsbehandlere = momentum.borgere.hent_aktive_sagsbehandlere(borger)
                print(borgers_sagsbehandlere)
            except WorkItemError as e:
                # A WorkItemError represents a soft error that indicates the item should be passed to manual processing or a business logic fault
                logger.error(f"Error processing item: {data}. Error: {e}")
                item.fail(str(e))






if __name__ == "__main__":
    ats = AutomationServer.from_environment()

    workqueue = ats.workqueue()

    # Initialize external systems for automation here..
    tracking_credential = Credential.get_credential("Odense SQL Server")
    tracker = Tracker(
        username=tracking_credential.username, password=tracking_credential.password
    )
    momentum_credential = Credential.get_credential("Momentum - produktion")
    momentum = MomentumClientManager(
        base_url=momentum_credential.data["base_url"],
        client_id=momentum_credential.username,
        client_secret=momentum_credential.password,
        api_key=momentum_credential.data["api_key"],
        resource=momentum_credential.data["resource"],
    )

    # Queue management
    if "--queue" in sys.argv:
        workqueue.clear_workqueue("new")
        asyncio.run(populate_queue(workqueue))
        exit(0)

    # Process workqueue
    asyncio.run(process_workqueue(workqueue))
