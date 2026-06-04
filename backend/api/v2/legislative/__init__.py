"""
"Legislative data" domain — /api/v2/legislative/*.

One sub-router per source (institution / data provider):
    /eur-lex            EUR-Lex / Publications Office (Cellar) — adopted law
    /oeil               Legislative Observatory — procedures in negotiation
    /legislative-train  Legislative Train — von der Leyen II priority carriages
    /eurovoc            EuroVoc thesaurus + authority tables + subject directory
    /delegated-acts     Commission delegated acts (Article 290 TFEU)
    /implementing-acts  Commission implementing acts (Article 291 TFEU)

This 1:1 mapping (Postman collection "Legislative data" -> sub-folders ->
URL segments) is the template every future institutional domain follows
(parliament/, commission/, council/, ...).
"""

from fastapi import APIRouter

from . import eur_lex as _eur_lex
from . import oeil as _oeil
from . import legislative_train as _legislative_train
from . import eurovoc as _eurovoc
from . import secondary_acts as _secondary_acts

router = APIRouter(prefix="/legislative")
router.include_router(_eur_lex.router)
router.include_router(_oeil.router)
router.include_router(_legislative_train.router)
router.include_router(_eurovoc.router)
router.include_router(_secondary_acts.delegated_router)
router.include_router(_secondary_acts.implementing_router)
