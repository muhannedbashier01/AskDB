"""Domain constants for the insurance policies schema.

This module owns the business-level definition of which tables belong to
the policies domain. Keeping it here (not in config) ensures that:
- Configuration (config.py) stays infrastructure-only.
- Domain rules are co-located and easy to extend without touching settings.
"""

# Tables that form the policies domain schema.
# Only these tables are loaded into the LLM context for SQL generation.
POLICIES_TABLES: list[str] = [
    # Core Aggregate
    "PurchasedPolicyDetail",
    # Related Tables
    "PurchasedPolicyInfo",
    "PurchasedPolicyVehicleInformation",
    "LeasingPurchaseTracking",
    "LeasingContract",
    # Lookup Tables
    "VehiclePlateTypeMaster",
    "VehicleColorMaster",
    "VehicleMakeMaster",
    "VehicleModelMaster",
    "InsuranceCompany",
]
