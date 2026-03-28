import requests
import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

NYC_OPEN_DATA_TOKEN = os.getenv("NYC_OPEN_DATA_TOKEN")

HPD_ENDPOINT = "https://data.cityofnewyork.us/resource/wvxf-dwi5.json"
AEP_ENDPOINT = "https://data.cityofnewyork.us/resource/muaj-atjc.json"


def _as_socrata_rows(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def query_hpd(address: str, borough: str) -> list[dict]:
    house_number = address.split()[0]
    street_name = " ".join(address.split()[1:])

    params = {
        "housenumber": house_number,
        "streetname": street_name.upper(),
        "boroid": get_boro_id(borough),
        "violationstatus": "Open",
        "$limit": 50,
    }

    if NYC_OPEN_DATA_TOKEN:
        params["$$app_token"] = NYC_OPEN_DATA_TOKEN

    response = requests.get(HPD_ENDPOINT, params=params)
    return _as_socrata_rows(response.json())


def get_boro_id(borough: str) -> str:
    mapping = {
        "MANHATTAN": "1",
        "BRONX": "2",
        "BROOKLYN": "3",
        "QUEENS": "4",
        "STATEN ISLAND": "5"
    }
    return mapping.get(borough.upper(), "3")


def check_aep(building_id: str) -> bool:
    if not building_id:
        return False
    params = {"buildingid": building_id}
    if NYC_OPEN_DATA_TOKEN:
        params["$$app_token"] = NYC_OPEN_DATA_TOKEN
    response = requests.get(AEP_ENDPOINT, params=params)
    return len(_as_socrata_rows(response.json())) > 0


def calculate_days_open(date_str: str) -> int:
    if not date_str:
        return 0
    try:
        clean = date_str.split("T")[0]
        opened = datetime.strptime(clean, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - opened).days
    except:
        return 0


def determine_breach(violations: list) -> bool:
    for v in violations:
        days = calculate_days_open(v.get("approveddate", ""))
        class_type = v.get("class", "").upper()
        if class_type == "C" and days > 0:
            return True
        if class_type == "B" and days > 30:
            return True
    return False


def build_tenant_rights(violations: list) -> list:
    classes = set(v.get("class", "").upper() for v in violations)
    rights = []

    if "C" in classes:
        rights.append("Landlord must correct Class C violations within 24 hours under NYC HMC §27-2017")
    if "B" in classes:
        rights.append("Landlord must correct Class B violations within 30 days under NYC HMC §27-2017")
    if classes:
        rights.append("Landlord cannot retaliate or evict within 6 months of a complaint")
        rights.append("As-is lease clauses do not override NYC Housing Maintenance Code")
    if "B" in classes or "C" in classes:
        rights.append("Tenant may be eligible for rent reduction if violations go uncorrected")

    return rights


def build_form_payload(
    violation_type: str,
    address: str,
    borough: str,
    class_c: int,
    class_b: int,
    oldest_days: int
) -> dict:
    descriptor_map = {
        "mold": "MOLD",
        "pest infestation": "MICE/RATS",
        "water damage": "WATER SUPPLY",
        "broken heat": "HEAT",
        "broken fixture": "PLUMBING",
    }

    return {
        "complaint_type": "UNSANITARY CONDITION",
        "descriptor": descriptor_map.get(violation_type.lower(), "UNSANITARY CONDITION"),
        "address": address,
        "borough": borough.upper(),
        "description": (
            f"Tenant reports {violation_type}. "
            f"Building has {class_c} open Class C and {class_b} open Class B violations. "
            f"Oldest open violation is {oldest_days} days old. "
            f"Landlord has not corrected conditions within legally required timeframe."
        )
    }


def run_agent(
    violation_type: str,
    address: str,
    borough: str,
    preferred_language: str = "en"
) -> dict:
    violations = query_hpd(address, borough)

    if not violations:
        return {
            "address": address,
            "violation_type": violation_type,
            "open_violations": 0,
            "class_c_open": 0,
            "class_b_open": 0,
            "oldest_open_days": 0,
            "aep_listed": False,
            "last_inspection": None,
            "landlord_in_breach": False,
            "tenant_rights": [
                "Landlord cannot retaliate or evict within 6 months of a complaint",
                "As-is lease clauses do not override NYC Housing Maintenance Code"
            ],
            "form_payload": build_form_payload(violation_type, address, borough, 0, 0, 0),
            "preferred_language": preferred_language
        }

    class_c = [v for v in violations if v.get("class", "").upper() == "C"]
    class_b = [v for v in violations if v.get("class", "").upper() == "B"]
    days_open = [calculate_days_open(v.get("approveddate", "")) for v in violations]

    return {
        "address": address,
        "violation_type": violation_type,
        "open_violations": len(violations),
        "class_c_open": len(class_c),
        "class_b_open": len(class_b),
        "oldest_open_days": max(days_open) if days_open else 0,
        "aep_listed": check_aep(violations[0].get("buildingid", "")),
        "last_inspection": violations[0].get("inspectiondate", None),
        "landlord_in_breach": determine_breach(violations),
        "tenant_rights": build_tenant_rights(violations),
        "form_payload": build_form_payload(
            violation_type, address, borough,
            len(class_c), len(class_b),
            max(days_open) if days_open else 0
        ),
        "preferred_language": preferred_language
    }


if __name__ == "__main__":
    result = run_agent(
        violation_type="mold",
        address="2386 VALENTINE AVENUE",
        borough="Bronx",
        preferred_language="en"
    )
    print(json.dumps(result, indent=2))