import re
from typing import Final

# Indian States & UTs GST State Code mapping
GST_STATE_CODES: Final[dict[str, str]] = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "25": "Daman and Diu",
    "26": "Dadra and Nagar Haveli",
    "27": "Maharashtra",
    "28": "Andhra Pradesh (Old)",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
    "97": "Other Territory",
    "99": "Centre Jurisdiction"
}

# Standard GST Slabs in India
STANDARD_GST_RATES: Final[list[float]] = [0.0, 0.25, 3.0, 5.0, 12.0, 18.0, 28.0]

# Standard 15-character GSTIN regex: 2 digits + 5 alpha + 4 digits + 1 alpha + 1 alpha/digit + Z + 1 alpha/digit
GSTIN_REGEX: Final[re.Pattern] = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")


def is_valid_gstin_format(gstin: str | None) -> bool:
    if not gstin:
        return False
    gstin = gstin.strip().upper()
    return bool(GSTIN_REGEX.match(gstin))


def get_gstin_state_code(gstin: str | None) -> str | None:
    if not gstin or len(gstin) < 2:
        return None
    code = gstin[:2]
    return code if code in GST_STATE_CODES else None


def is_valid_state_code(state_code: str | None) -> bool:
    return bool(state_code and state_code in GST_STATE_CODES)
