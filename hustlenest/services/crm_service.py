from __future__ import annotations

from datetime import date
from typing import List, Optional, Tuple

from ..data import crm_repository, order_repository
from ..models.order_models import CRMContact, CRMInteraction, NotificationMessage


def list_pending_followups(*, limit: int = 25, days_ahead: int = 14) -> List[CRMContact]:
    today = date.today()
    horizon = today.toordinal() + days_ahead
    contacts: List[CRMContact] = []
    for contact in crm_repository.list_contacts():
        if contact.next_follow_up is None:
            continue
        ordinal = contact.next_follow_up.toordinal()
        if ordinal < today.toordinal():
            contacts.append(contact)
        elif ordinal <= horizon:
            contacts.append(contact)
    contacts.sort(key=lambda contact: (contact.next_follow_up or date.max))
    return contacts[:limit]


def build_followup_notifications(*, limit: int = 10) -> List[NotificationMessage]:
    today = date.today()
    notifications: List[NotificationMessage] = []
    for contact in list_pending_followups(limit=limit):
        if contact.next_follow_up is None:
            continue
        days_delta = (contact.next_follow_up - today).days
        if days_delta < 0:
            severity = "critical"
            status = f"overdue by {-days_delta} day(s)"
        elif days_delta == 0:
            severity = "warning"
            status = "due today"
        else:
            severity = "info"
            status = f"due in {days_delta} day(s)"
        notifications.append(
            NotificationMessage(
                "CRM",
                f"Follow-up with {contact.customer_name} ({contact.company}) {status}.",
                severity,
            )
        )
    return notifications


def list_contacts(*, tags: Optional[List[str]] = None) -> List[CRMContact]:
    return crm_repository.list_contacts(tags=tags)


def get_contact(contact_id: int) -> Optional[CRMContact]:
    return crm_repository.get_contact(contact_id)


def save_contact(contact: CRMContact) -> int:
    return crm_repository.save_contact(contact)


def delete_contact(contact_id: int) -> None:
    crm_repository.delete_contact(contact_id)


def list_interactions(contact_id: int, *, limit: Optional[int] = None) -> List[CRMInteraction]:
    return crm_repository.list_interactions(contact_id, limit=limit)


def save_interaction(interaction: CRMInteraction) -> int:
    return crm_repository.save_interaction(interaction)


def delete_interaction(interaction_id: int) -> None:
    crm_repository.delete_interaction(interaction_id)


def import_contacts_from_orders(
    *,
    tag: Optional[str] = "Orders",
    update_missing_addresses: bool = True,
) -> Tuple[int, int]:
    existing_contacts = crm_repository.list_contacts()
    exact_lookup: dict[tuple[str, str], CRMContact] = {}
    name_lookup: dict[str, CRMContact] = {}

    def _normalize(value: str) -> str:
        return value.strip().casefold()

    for contact in existing_contacts:
        name_key = _normalize(contact.customer_name)
        addr_key = _normalize(contact.address)
        if name_key:
            exact_lookup[(name_key, addr_key)] = contact
            if name_key not in name_lookup:
                name_lookup[name_key] = contact

    created = 0
    updated = 0
    candidates = order_repository.fetch_distinct_customers()
    for raw_name, raw_address in candidates:
        name = (raw_name or "").strip()
        if not name:
            continue
        address = (raw_address or "").strip()
        key = (_normalize(name), _normalize(address))

        existing = exact_lookup.get(key)
        if existing is not None:
            continue

        existing_by_name = name_lookup.get(_normalize(name))
        if existing_by_name is not None:
            if (
                update_missing_addresses
                and address
                and not existing_by_name.address.strip()
            ):
                existing_by_name.address = address
                crm_repository.save_contact(existing_by_name)
                updated += 1
                exact_lookup[(key[0], _normalize(existing_by_name.address))] = existing_by_name
            continue

        tags = [tag] if tag else []
        contact = CRMContact(
            id=None,
            customer_name=name,
            company="",
            email="",
            phone="",
            address=address,
            tags=tags,
            created_at=None,
            last_contacted=None,
            next_follow_up=None,
            preferred_channel="",
            notes="Imported from order history",
        )
        crm_repository.save_contact(contact)
        created += 1
        exact_lookup[key] = contact
        name_lookup.setdefault(key[0], contact)

    return created, updated
