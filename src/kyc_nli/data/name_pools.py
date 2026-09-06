"""Embedded synthetic name pools, one per supported language.

These are high-frequency given names and surnames for each language, combined at
random by the generator. No entry is a real person's record; a randomly paired
given name and surname carries no identifying information. This pool exists so
that ``kyc-nli generate`` runs on a clean checkout with zero downloads.

For anything that goes in the paper, replace this with a real corpus:
  hi  Dakshina (CC BY-SA 4.0) romanised/native lexicons
  ru  MIDV-2020 Russian passport field annotations (mock identities)
  ar / zh  Wikidata person labels (CC0), filtered to public figures

Loaders for those live in ``kyc_nli.data.corpora`` and write to data/external/,
which is gitignored. See CLAUDE.md: never commit anything under data/.
"""

from __future__ import annotations

from dataclasses import dataclass

from kyc_nli.schema import Script


@dataclass(frozen=True)
class NamePool:
    language: str
    script: Script
    given: tuple[str, ...]
    surnames: tuple[str, ...]
    places: tuple[str, ...]
    authorities: tuple[str, ...]


POOLS: dict[str, NamePool] = {
    "en": NamePool(
        language="en",
        script=Script.LATIN,
        given=(
            "JAMES", "MARY", "ROBERT", "PATRICIA", "JOHN", "JENNIFER", "MICHAEL",
            "LINDA", "DAVID", "ELIZABETH", "WILLIAM", "BARBARA", "RICHARD",
            "SUSAN", "JOSEPH", "JESSICA", "THOMAS", "SARAH", "CHARLES", "KAREN",
        ),
        surnames=(
            "SMITH", "JOHNSON", "WILLIAMS", "BROWN", "JONES", "GARCIA", "MILLER",
            "DAVIS", "RODRIGUEZ", "MARTINEZ", "HERNANDEZ", "LOPEZ", "GONZALEZ",
            "WILSON", "ANDERSON", "THOMAS", "TAYLOR", "MOORE", "JACKSON", "MARTIN",
        ),
        places=("LONDON", "MANCHESTER", "BIRMINGHAM", "LEEDS", "GLASGOW", "BRISTOL"),
        authorities=("HMPO", "IPS LONDON", "HOME OFFICE"),
    ),
    "ru": NamePool(
        language="ru",
        script=Script.CYRILLIC,
        given=(
            "АЛЕКСАНДР", "ЕЛЕНА", "ДМИТРИЙ", "ОЛЬГА", "СЕРГЕЙ", "НАТАЛЬЯ",
            "АНДРЕЙ", "ТАТЬЯНА", "АЛЕКСЕЙ", "ИРИНА", "МАКСИМ", "СВЕТЛАНА",
            "ЕВГЕНИЙ", "ЮЛИЯ", "МИХАИЛ", "АНАСТАСИЯ", "ВЛАДИМИР", "МАРИЯ",
            "ЮРИЙ", "ЕКАТЕРИНА",
        ),
        surnames=(
            "ИВАНОВ", "СМИРНОВ", "КУЗНЕЦОВ", "ПОПОВ", "ВАСИЛЬЕВ", "ПЕТРОВ",
            "СОКОЛОВ", "МИХАЙЛОВ", "НОВИКОВ", "ФЁДОРОВ", "МОРОЗОВ", "ВОЛКОВ",
            "АЛЕКСЕЕВ", "ЛЕБЕДЕВ", "СЕМЁНОВ", "ЕГОРОВ", "ПАВЛОВ", "КОЗЛОВ",
            "СТЕПАНОВ", "НИКОЛАЕВ",
        ),
        places=("МОСКВА", "САНКТ-ПЕТЕРБУРГ", "НОВОСИБИРСК", "ЕКАТЕРИНБУРГ", "КАЗАНЬ"),
        authorities=("ФМС 770-001", "УФМС РОССИИ", "ГУ МВД РОССИИ"),
    ),
    "ar": NamePool(
        language="ar",
        script=Script.ARABIC,
        given=(
            "محمد", "أحمد", "علي", "حسن", "حسين", "خالد", "عمر", "يوسف",
            "إبراهيم", "مصطفى", "فاطمة", "مريم", "زينب", "سارة", "نور",
            "ليلى", "عائشة", "خديجة", "أمينة", "هدى",
        ),
        surnames=(
            "الأنصاري", "الحسيني", "المصري", "البغدادي", "الشامي", "الخالدي",
            "النجار", "الحداد", "السيد", "العلي", "الرشيد", "القاسمي",
            "الزهراني", "العتيبي", "الدوسري", "الشمري", "المطيري", "الحربي",
            "الغامدي", "القحطاني",
        ),
        places=("القاهرة", "دمشق", "بغداد", "الرياض", "بيروت", "عمان"),
        authorities=("وزارة الداخلية", "مصلحة الجوازات"),
    ),
    "hi": NamePool(
        language="hi",
        script=Script.DEVANAGARI,
        given=(
            "राहुल", "प्रिया", "अमित", "पूजा", "विकास", "नेहा", "संजय", "अंजलि",
            "राजेश", "सुनीता", "मनोज", "कविता", "दीपक", "रेखा", "अनिल",
            "ममता", "विजय", "गीता", "सुरेश", "शालिनी",
        ),
        surnames=(
            "शर्मा", "वर्मा", "गुप्ता", "सिंह", "कुमार", "यादव", "मिश्रा",
            "पांडे", "तिवारी", "अग्रवाल", "जोशी", "मेहता", "चौहान", "राठौर",
            "देसाई", "पटेल", "नायर", "रेड्डी", "बनर्जी", "चटर्जी",
        ),
        places=("दिल्ली", "मुंबई", "जयपुर", "लखनऊ", "पटना", "भोपाल"),
        authorities=("भारत सरकार", "पासपोर्ट कार्यालय"),
    ),
    "zh": NamePool(
        language="zh",
        script=Script.HAN,
        given=(
            "伟", "芳", "娜", "敏", "静", "秀英", "华", "慧", "军", "洋",
            "勇", "艳", "杰", "涛", "明", "超", "霞", "平", "刚", "文丽",
        ),
        surnames=(
            "王", "李", "张", "刘", "陈", "杨", "黄", "赵", "吴", "周",
            "徐", "孙", "马", "朱", "胡", "郭", "何", "林", "高", "罗",
        ),
        places=("北京", "上海", "广州", "深圳", "成都", "杭州"),
        authorities=("公安部", "出入境管理局"),
    ),
}


def pool_for(language: str) -> NamePool:
    try:
        return POOLS[language]
    except KeyError as exc:  # pragma: no cover - guarded by the language registry
        raise KeyError(
            f"No name pool for language {language!r}. "
            f"Add one to kyc_nli.data.name_pools.POOLS."
        ) from exc
