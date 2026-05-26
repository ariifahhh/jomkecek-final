from .preprocessing import tokenize


def detect_intent(query: str, selected_mode: str = "Auto") -> str:
    if selected_mode == "Terjemahan Dialek":
        return "translation"
    if selected_mode == "Info Kelantan":
        return "kelantan"

    tokens = set(tokenize(query))
    kelantan_terms = {
        "kelantan",
        "kelate",
        "kota",
        "bharu",
        "tempat",
        "menarik",
        "pantai",
        "pasar",
        "muzium",
        "makanan",
        "budaya",
        "tradisional",
        "jajahan",
        "sultan",
        "mb",
        "menteri",
        "besar",
        "cuaca",
        "dialek",
    }
    dialect_terms = {"mu", "demo", "kawe", "ambo", "nok", "gapo", "mano", "makey", "gi", "ko"}

    if tokens & kelantan_terms and not (tokens & dialect_terms and len(tokens) <= 6):
        return "kelantan"
    return "translation"

