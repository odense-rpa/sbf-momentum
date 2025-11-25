import asyncio
import logging
import sys

from automation_server_client import (
    AutomationServer,
    Workqueue,
    WorkItemError,
    Credential,
)
from momentum_client.manager import MomentumClientManager
from odk_tools.tracking import Tracker
from process.momentum import MomentumService

tracker: Tracker
momentum: MomentumClientManager
momentum_service: MomentumService
proces_navn = "sbf-momentum"


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
                # tæl antal aktive børn
                aktive_børn_antal = sum(
                    1 for item in data.get("børn", []) if item.get("aktiv")
                )
                borger = momentum.borgere.hent_borger(data["cpr"])

                if data["aktiv"] and aktive_børn_antal > 0:
                    # synkroniser_sagsbehandlere
                    momentum_service.fjern_sagsbehandlere_der_ikke_længere_er_i_unikke(
                        data
                    )
                    momentum_service.tilføj_unikke_sagsbehandlere(borger, data)
                    # ensure_tag
                    momentum_service.synkroniser_markering(borger=borger)
                else:
                    momentum_service.inaktiver_sagsbehandlere_til_forælder(data)
                    # afslut_markering
                    momentum_service.afslut_markering(borger=borger)

                # hent borger i momentum via cpr:
                borgers_sagsbehandlere = momentum.borgere.hent_aktive_sagsbehandlere(
                    borger
                )
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
    momentum_service = MomentumService(tracker=tracker, momentum=momentum)

    # Queue management
    if "--queue" in sys.argv:
        workqueue.clear_workqueue("new")
        asyncio.run(populate_queue(workqueue))
        exit(0)

    # Process workqueue
    asyncio.run(process_workqueue(workqueue))
