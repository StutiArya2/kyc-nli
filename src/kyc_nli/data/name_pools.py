"""Embedded synthetic name pools, one per supported language.

Entries are ``(native_script, attested_latin)`` PAIRS, not bare native strings.
This mirrors the shape of the real corpus that will replace them: the Dakshina
dataset (Google Research, CC BY-SA 4.0) ships paired native and romanised
lexicons, and it covers **all four** non-English languages in the active set —
Bengali, Hindi, Tamil and Urdu. One licence, one download, four languages of
real romanisation variation. That is the strongest single reason the active set
is what it is.

Pairing also fixes a correctness problem. An Indian passport prints the holder's
*attested* Latin spelling in its English zone and MRZ — SHARMA, SUBRAMANIYAN,
BANDYOPADHYAY — not whatever a rule-based romaniser happens to emit. Deriving
the document's own Latin from the transliterator would have printed SARM,
CHUBRAMANIYAN and BANDJOPAADHJAAJ. The transliterator's job is to *recognise*
the variants at match time, not to decide what the document says.

No entry is a real person's record; given names and surnames are paired at
random by the generator, and a randomly paired name carries no identifying
information. This pool exists so ``kyc-nli generate`` runs on a clean checkout
with zero downloads.

Loaders for the real corpora live in ``kyc_nli.data.corpora`` and write to
data/external/, which is gitignored. See CLAUDE.md: never commit under data/.
"""

from __future__ import annotations

from dataclasses import dataclass

from kyc_nli.schema import Script

#: (native script form, attested Latin form)
NamePair = tuple[str, str]


@dataclass(frozen=True)
class NamePool:
    language: str
    script: Script
    given: tuple[NamePair, ...]
    surnames: tuple[NamePair, ...]
    places: tuple[NamePair, ...]
    authorities: tuple[NamePair, ...]


POOLS: dict[str, NamePool] = {
    # ------------------------------------------------------------------
    # English / Latin. The control condition.
    #
    # Drawn from the same population as the other pools rather than from an
    # unrelated Anglophone list: an English control sharing no names with the
    # other languages would measure the wrong thing, because the comparison we
    # want is "same names, different script", not "different names entirely".
    # ------------------------------------------------------------------
    "en": NamePool(
        language="en",
        script=Script.LATIN,
        given=tuple(
            (n, n)
            for n in (
                "RAHUL", "PRIYA", "AMIT", "POOJA", "VIKAS", "NEHA", "SANJAY",
                "ANJALI", "RAJESH", "SUNITA", "ARJUN", "KAVITA", "DEEPAK",
                "REKHA", "ANIL", "MEENA", "VIJAY", "GEETA", "SURESH", "SHALINI",
            )
        ),
        surnames=tuple(
            (n, n)
            for n in (
                "SHARMA", "VERMA", "GUPTA", "SINGH", "KUMAR", "YADAV", "MISHRA",
                "PANDEY", "TIWARI", "AGARWAL", "JOSHI", "MEHTA", "CHAUHAN",
                "RATHORE", "DESAI", "PATEL", "NAIR", "REDDY", "IYER", "MENON",
            )
        ),
        places=tuple(
            (n, n)
            for n in ("DELHI", "MUMBAI", "CHENNAI", "KOLKATA", "LUCKNOW", "BHOPAL")
        ),
        authorities=tuple(
            (n, n)
            for n in (
                "PASSPORT OFFICE DELHI",
                "PASSPORT OFFICE CHENNAI",
                "REGIONAL PASSPORT OFFICE",
            )
        ),
    ),
    # ------------------------------------------------------------------
    # Hindi / Devanagari. Non-normative romanisation.
    # ------------------------------------------------------------------
    "hi": NamePool(
        language="hi",
        script=Script.DEVANAGARI,
        given=(
            ("राहुल", "RAHUL"), ("प्रिया", "PRIYA"), ("अमित", "AMIT"),
            ("पूजा", "POOJA"), ("विकास", "VIKAS"), ("नेहा", "NEHA"),
            ("संजय", "SANJAY"), ("अंजलि", "ANJALI"), ("राजेश", "RAJESH"),
            ("सुनीता", "SUNITA"), ("मनोज", "MANOJ"), ("कविता", "KAVITA"),
            ("दीपक", "DEEPAK"), ("रेखा", "REKHA"), ("अनिल", "ANIL"),
            ("ममता", "MAMTA"), ("विजय", "VIJAY"), ("गीता", "GEETA"),
            ("सुरेश", "SURESH"), ("शालिनी", "SHALINI"),
        ),
        surnames=(
            ("शर्मा", "SHARMA"), ("वर्मा", "VERMA"), ("गुप्ता", "GUPTA"),
            ("सिंह", "SINGH"), ("कुमार", "KUMAR"), ("यादव", "YADAV"),
            ("मिश्रा", "MISHRA"), ("पांडे", "PANDEY"), ("तिवारी", "TIWARI"),
            ("अग्रवाल", "AGARWAL"), ("जोशी", "JOSHI"), ("मेहता", "MEHTA"),
            ("चौहान", "CHAUHAN"), ("राठौर", "RATHORE"), ("देसाई", "DESAI"),
            ("पटेल", "PATEL"), ("नायर", "NAIR"), ("रेड्डी", "REDDY"),
            ("बनर्जी", "BANERJEE"), ("चटर्जी", "CHATTERJEE"),
        ),
        places=(
            ("दिल्ली", "DELHI"), ("मुंबई", "MUMBAI"), ("जयपुर", "JAIPUR"),
            ("लखनऊ", "LUCKNOW"), ("पटना", "PATNA"), ("भोपाल", "BHOPAL"),
        ),
        authorities=(
            ("पासपोर्ट कार्यालय दिल्ली", "PASSPORT OFFICE DELHI"),
            ("पासपोर्ट कार्यालय लखनऊ", "PASSPORT OFFICE LUCKNOW"),
        ),
    ),
    # ------------------------------------------------------------------
    # Tamil. Systematically ambiguous romanisation: the script does not mark
    # voicing, so K/G, CH/S, T/D, TH/DH and P/B are not recoverable from it.
    # ------------------------------------------------------------------
    "ta": NamePool(
        language="ta",
        script=Script.TAMIL,
        given=(
            ("கண்ணன்", "KANNAN"), ("முருகன்", "MURUGAN"), ("செல்வம்", "SELVAM"),
            ("அருள்", "ARUL"), ("மாலதி", "MALATHI"), ("கமலா", "KAMALA"),
            ("வளர்மதி", "VALARMATHI"), ("சரவணன்", "SARAVANAN"), ("பாலு", "BALU"),
            ("ரமேஷ்", "RAMESH"), ("லட்சுமி", "LAKSHMI"), ("மீனா", "MEENA"),
            ("கவிதா", "KAVITHA"), ("தமிழ்", "TAMIZH"), ("வேலு", "VELU"),
            ("பாண்டியன்", "PANDIYAN"), ("நிர்மலா", "NIRMALA"), ("சுதா", "SUDHA"),
            ("ராஜா", "RAJA"), ("இளங்கோ", "ILANGO"),
        ),
        surnames=(
            ("சுப்ரமணியன்", "SUBRAMANIYAN"), ("கோபால்", "GOPAL"),
            ("நடராஜன்", "NATARAJAN"), ("ராமன்", "RAMAN"),
            ("கிருஷ்ணன்", "KRISHNAN"), ("வெங்கடேசன்", "VENKATESAN"),
            ("சுந்தரம்", "SUNDARAM"), ("பழனி", "PALANI"), ("மணி", "MANI"),
            ("சிவா", "SIVA"), ("ரங்கன்", "RANGAN"),
            ("தியாகராஜன்", "THIYAGARAJAN"), ("அண்ணாமலை", "ANNAMALAI"),
            ("பெருமாள்", "PERUMAL"), ("செல்வராஜ்", "SELVARAJ"),
            ("முத்து", "MUTHU"), ("வடிவேலு", "VADIVELU"),
            ("கார்த்திகேயன்", "KARTHIKEYAN"), ("ஜெயராமன்", "JEYARAMAN"),
            ("சண்முகம்", "SHANMUGAM"),
        ),
        places=(
            ("சென்னை", "CHENNAI"), ("மதுரை", "MADURAI"),
            ("கோயம்புத்தூர்", "COIMBATORE"), ("திருச்சி", "TIRUCHY"),
            ("சேலம்", "SALEM"),
        ),
        authorities=(
            ("பாஸ்போர்ட் அலுவலகம் சென்னை", "PASSPORT OFFICE CHENNAI"),
            ("மண்டல பாஸ்போர்ட் அலுவலகம்", "REGIONAL PASSPORT OFFICE"),
        ),
    ),
    # ------------------------------------------------------------------
    # Bengali. Inherent vowel nearer /o/ than /a/; no /v/; the ya-phala is
    # written with the same letter as /dʒ/.
    # ------------------------------------------------------------------
    "bn": NamePool(
        language="bn",
        script=Script.BENGALI,
        given=(
            ("রাহুল", "RAHUL"), ("প্রিয়া", "PRIYA"), ("অমিত", "AMIT"),
            ("সুমিতা", "SUMITA"), ("দেবাশিস", "DEBASHIS"), ("মৌসুমী", "MOUSUMI"),
            ("সঞ্জয়", "SANJAY"), ("অঞ্জলি", "ANJALI"), ("রাজীব", "RAJIB"),
            ("কল্পনা", "KALPANA"), ("শুভ", "SHUBHO"), ("রিনা", "RINA"),
            ("তাপস", "TAPAS"), ("মিতা", "MITA"), ("প্রদীপ", "PRADIP"),
            ("শিপ্রা", "SHIPRA"), ("বিকাশ", "BIKASH"), ("গীতা", "GITA"),
            ("সুব্রত", "SUBRATA"), ("নন্দিতা", "NANDITA"),
        ),
        surnames=(
            ("বন্দ্যোপাধ্যায়", "BANDYOPADHYAY"),
            ("চট্টোপাধ্যায়", "CHATTOPADHYAY"),
            ("মুখোপাধ্যায়", "MUKHOPADHYAY"), ("ঘোষ", "GHOSH"),
            ("বসু", "BASU"), ("দত্ত", "DUTTA"), ("সেন", "SEN"),
            ("রায়", "ROY"), ("সরকার", "SARKAR"), ("দাস", "DAS"),
            ("পাল", "PAL"), ("মিত্র", "MITRA"), ("চক্রবর্তী", "CHAKRABORTY"),
            ("ভট্টাচার্য", "BHATTACHARYA"), ("গঙ্গোপাধ্যায়", "GANGOPADHYAY"),
            ("নন্দী", "NANDI"), ("সাহা", "SAHA"), ("বিশ্বাস", "BISWAS"),
            ("হালদার", "HALDAR"), ("মজুমদার", "MAJUMDAR"),
        ),
        places=(
            ("কলকাতা", "KOLKATA"), ("হাওড়া", "HOWRAH"),
            ("শিলিগুড়ি", "SILIGURI"), ("দুর্গাপুর", "DURGAPUR"),
            ("আসানসোল", "ASANSOL"),
        ),
        authorities=(
            ("পাসপোর্ট অফিস কলকাতা", "PASSPORT OFFICE KOLKATA"),
            ("আঞ্চলিক পাসপোর্ট অফিস", "REGIONAL PASSPORT OFFICE"),
        ),
    ),
    # ------------------------------------------------------------------
    # Urdu / Perso-Arabic. RTL, no short vowels written, dropped diacritics.
    # ------------------------------------------------------------------
    "ur": NamePool(
        language="ur",
        script=Script.ARABIC,
        given=(
            ("محمد", "MOHAMMAD"), ("عبداللہ", "ABDULLAH"), ("اسلم", "ASLAM"),
            ("ریحانہ", "REHANA"), ("فاطمہ", "FATIMA"), ("عائشہ", "AYESHA"),
            ("عمران", "IMRAN"), ("سلیم", "SALEEM"), ("رشید", "RASHEED"),
            ("نسرین", "NASREEN"), ("زبیدہ", "ZUBAIDA"), ("یوسف", "YUSUF"),
            ("ابراہیم", "IBRAHIM"), ("رضوان", "RIZWAN"), ("شبانہ", "SHABANA"),
            ("نازیہ", "NAZIA"), ("فیروز", "FEROZ"), ("جاوید", "JAVED"),
            ("شکیل", "SHAKEEL"), ("تبسم", "TABASSUM"),
        ),
        surnames=(
            ("خان", "KHAN"), ("صدیقی", "SIDDIQUI"), ("انصاری", "ANSARI"),
            ("شیخ", "SHEIKH"), ("سید", "SYED"), ("قریشی", "QURESHI"),
            ("پٹھان", "PATHAN"), ("ملک", "MALIK"), ("رضوی", "RIZVI"),
            ("نقوی", "NAQVI"), ("حسین", "HUSSAIN"), ("احمد", "AHMAD"),
            ("رحمان", "RAHMAN"), ("ہاشمی", "HASHMI"), ("فاروقی", "FAROOQUI"),
            ("عثمانی", "USMANI"), ("چشتی", "CHISHTI"), ("بیگ", "BAIG"),
            ("مرزا", "MIRZA"), ("خٹک", "KHATTAK"),
        ),
        places=(
            ("لکھنؤ", "LUCKNOW"), ("حیدرآباد", "HYDERABAD"), ("دہلی", "DELHI"),
            ("بھوپال", "BHOPAL"), ("علی گڑھ", "ALIGARH"),
        ),
        authorities=(
            ("پاسپورٹ آفس لکھنؤ", "PASSPORT OFFICE LUCKNOW"),
            ("علاقائی پاسپورٹ آفس", "REGIONAL PASSPORT OFFICE"),
        ),
    ),
}


#: Retained but not in the active language set; see decision 0005. Kept so that
#: "does this generalise beyond the Indian document context?" stays a cheap
#: experiment rather than a rewrite.
RETAINED_POOLS: dict[str, NamePool] = {
    "ru": NamePool(
        language="ru",
        script=Script.CYRILLIC,
        given=(
            ("АЛЕКСАНДР", "ALEKSANDR"), ("ЕЛЕНА", "ELENA"),
            ("ДМИТРИЙ", "DMITRII"), ("ОЛЬГА", "OLGA"), ("СЕРГЕЙ", "SERGEI"),
            ("НАТАЛЬЯ", "NATALIA"), ("АНДРЕЙ", "ANDREI"),
            ("ТАТЬЯНА", "TATIANA"), ("ЮРИЙ", "IURII"), ("МАРИЯ", "MARIIA"),
        ),
        surnames=(
            ("ИВАНОВ", "IVANOV"), ("СМИРНОВ", "SMIRNOV"),
            ("КУЗНЕЦОВ", "KUZNETSOV"), ("ПОПОВ", "POPOV"),
            ("ПЕТРОВ", "PETROV"), ("ВОЛКОВ", "VOLKOV"),
            ("МОРОЗОВ", "MOROZOV"), ("ЛЕБЕДЕВ", "LEBEDEV"),
            ("КОЗЛОВ", "KOZLOV"), ("НИКОЛАЕВ", "NIKOLAEV"),
        ),
        places=(("МОСКВА", "MOSKVA"), ("КАЗАНЬ", "KAZAN")),
        authorities=(("ФМС 770-001", "FMS 770-001"),),
    ),
    "zh": NamePool(
        language="zh",
        script=Script.HAN,
        given=(("伟", "WEI"), ("芳", "FANG"), ("娜", "NA"), ("敏", "MIN")),
        surnames=(
            ("王", "WANG"), ("李", "LI"), ("张", "ZHANG"),
            ("刘", "LIU"), ("陈", "CHEN"),
        ),
        places=(("北京", "BEIJING"), ("上海", "SHANGHAI")),
        authorities=(("公安部", "MINISTRY OF PUBLIC SECURITY"),),
    ),
}


def pool_for(language: str) -> NamePool:
    pool = POOLS.get(language) or RETAINED_POOLS.get(language)
    if pool is None:
        raise KeyError(
            f"No name pool for language {language!r}. "
            f"Add one to kyc_nli.data.name_pools.POOLS."
        )
    return pool
