from backend import chatbot_pipeline
from jomkecek.guards import OUT_OF_SCOPE_MESSAGE
from jomkecek.router import route_query


def check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise AssertionError(f"{name} gagal. {detail}")
    print(f"lulus: {name}")


def main() -> None:
    r = chatbot_pipeline("demo nok gi mano")
    check("dialek ke bm", "Awak nak pergi mana" in r["answer"], r["answer"])
    check("mode dialek", r["route"]["mode"] == "dialect_translation")

    r = chatbot_pipeline("saya nak makan")
    check("bm ke dialek", "ambo nok makey" in r["answer"].lower(), r["answer"])

    r = chatbot_pipeline("Berapa jajahan di Kelantan?")
    check("fakta jajahan", "10 jajahan" in r["answer"], r["answer"])

    r = chatbot_pipeline("Makanan tradisional Kelantan")
    check("makanan", r["kelantan"]["response_type"] == "food", r["kelantan"])

    r = chatbot_pipeline("Tempat menarik di Kota Bharu")
    check("pelancongan", "Pasar Siti Khadijah" in r["answer"], r["answer"])

    r = chatbot_pipeline("Apakah budaya terkenal di Kelantan?")
    check("budaya", r["route"]["intent"] == "culture", str(r["route"]))

    r = chatbot_pipeline("Tempat menarik di Johor")
    check("luar skop negeri", r["answer"] == OUT_OF_SCOPE_MESSAGE, r["answer"])

    r = chatbot_pipeline("Apa teknologi kuantum di Kelantan?")
    check("rag lemah", "Maaf" in r["answer"], r["answer"])

    route = route_query("Mu nok gi mano")
    check("router", route["mode"] == "dialect_translation", str(route))


if __name__ == "__main__":
    main()
