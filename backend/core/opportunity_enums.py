from enum import Enum


class OpportunityType(str, Enum):
    Hackathon = "Hackathon"


class OpportunityStatus(str, Enum):
    Active = "Active"
    Upcoming = "Upcoming"


_TYPE_ALIASES: dict[str, OpportunityType] = {
    "hackathon": OpportunityType.Hackathon,
    "hackathons": OpportunityType.Hackathon,
}

_STATUS_ALIASES: dict[str, OpportunityStatus] = {
    "active": OpportunityStatus.Active,
    "upcoming": OpportunityStatus.Upcoming,
    # Legacy status value from older scrapers.
    "closed": OpportunityStatus.Active,
}


def parse_opportunity_type(
    value: str | OpportunityType | None,
    default: OpportunityType = OpportunityType.Hackathon,
) -> OpportunityType:
    if isinstance(value, OpportunityType):
        return value
    if value is None:
        return default

    token = value.strip()
    if not token:
        return default

    alias_match = _TYPE_ALIASES.get(token.lower())
    if alias_match is not None:
        return alias_match

    for enum_value in OpportunityType:
        if token == enum_value.value:
            return enum_value

    return default


def parse_opportunity_status(
    value: str | OpportunityStatus | None,
    default: OpportunityStatus = OpportunityStatus.Active,
) -> OpportunityStatus:
    if isinstance(value, OpportunityStatus):
        return value
    if value is None:
        return default

    token = value.strip()
    if not token:
        return default

    alias_match = _STATUS_ALIASES.get(token.lower())
    if alias_match is not None:
        return alias_match

    for enum_value in OpportunityStatus:
        if token == enum_value.value:
            return enum_value

    return default
