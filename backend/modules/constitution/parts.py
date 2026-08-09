"""The Parts of the Constitution, as a static list.

Static for the same reason core/geography.py is: the Parts change through
constitutional amendment, not through an editor's afternoon, and they are the
navigation spine of the library. Part VII is present and flagged repealed rather
than omitted -- a library that silently renumbers around a repeal misleads
anyone cross-referencing an older commentary.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Part:
    number: str
    title: str
    title_hi: str
    articles: str  # human-readable range, for the index page
    repealed: bool = False


PARTS: list[Part] = [
    Part("I", "The Union and its Territory", "संघ और उसका राज्यक्षेत्र", "1-4"),
    Part("II", "Citizenship", "नागरिकता", "5-11"),
    Part("III", "Fundamental Rights", "मूल अधिकार", "12-35"),
    Part("IV", "Directive Principles of State Policy", "राज्य की नीति के निदेशक तत्व", "36-51"),
    Part("IVA", "Fundamental Duties", "मूल कर्तव्य", "51A"),
    Part("V", "The Union", "संघ", "52-151"),
    Part("VI", "The States", "राज्य", "152-237"),
    Part("VII", "The States in Part B of the First Schedule", "पहली अनुसूची के भाग ख के राज्य", "238", repealed=True),
    Part("VIII", "The Union Territories", "संघ राज्यक्षेत्र", "239-242"),
    Part("IX", "The Panchayats", "पंचायत", "243-243O"),
    Part("IXA", "The Municipalities", "नगरपालिकाएं", "243P-243ZG"),
    Part("IXB", "The Co-operative Societies", "सहकारी सोसाइटियां", "243ZH-243ZT"),
    Part("X", "The Scheduled and Tribal Areas", "अनुसूचित और जनजाति क्षेत्र", "244-244A"),
    Part("XI", "Relations between the Union and the States", "संघ और राज्यों के बीच संबंध", "245-263"),
    Part("XII", "Finance, Property, Contracts and Suits", "वित्त, संपत्ति, संविदाएं और वाद", "264-300A"),
    Part("XIII", "Trade, Commerce and Intercourse within the Territory of India", "भारत के राज्यक्षेत्र के भीतर व्यापार, वाणिज्य और समागम", "301-307"),
    Part("XIV", "Services under the Union and the States", "संघ और राज्यों के अधीन सेवाएं", "308-323"),
    Part("XIVA", "Tribunals", "अधिकरण", "323A-323B"),
    Part("XV", "Elections", "निर्वाचन", "324-329A"),
    Part("XVI", "Special Provisions relating to certain Classes", "कुछ वर्गों के संबंध में विशेष उपबंध", "330-342A"),
    Part("XVII", "Official Language", "राजभाषा", "343-351"),
    Part("XVIII", "Emergency Provisions", "आपात उपबंध", "352-360"),
    Part("XIX", "Miscellaneous", "प्रकीर्ण", "361-367"),
    Part("XX", "Amendment of the Constitution", "संविधान का संशोधन", "368"),
    Part("XXI", "Temporary, Transitional and Special Provisions", "अस्थायी, संक्रमणकालीन और विशेष उपबंध", "369-392"),
    Part("XXII", "Short Title, Commencement, Authoritative Text in Hindi and Repeals", "संक्षिप्त नाम, प्रारंभ, हिंदी में प्राधिकृत पाठ और निरसन", "393-395"),
]

PARTS_BY_NUMBER: dict[str, Part] = {p.number: p for p in PARTS}

# The Parts a first-time reader of this platform actually needs. Surfaced as
# "Start here" on the library index, because handing someone 22 Parts and 395
# articles is the same as handing them nothing.
CORE_PARTS: tuple[str, ...] = ("III", "IV", "IVA", "IX", "XV", "XX")


def as_dicts() -> list[dict]:
    return [
        {
            "number": p.number,
            "title": p.title,
            "titleHi": p.title_hi,
            "articles": p.articles,
            "repealed": p.repealed,
            "isCore": p.number in CORE_PARTS,
        }
        for p in PARTS
    ]
