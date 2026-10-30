"""Email texts in British English, German and French.

Each message is a function of (locale, **params) returning (subject, text).
Keep these short and plain; the app address comes from settings."""

from __future__ import annotations

from app.config import get_settings
from app.email.backend import OutgoingEmail

SIGNATURE = {
    "en": "\n\nSwiss Science Tutors\nhttps://swisssciencetutors.ch",
    "de": "\n\nSwiss Science Tutors\nhttps://swisssciencetutors.ch",
    "fr": "\n\nSwiss Science Tutors\nhttps://swisssciencetutors.ch",
}

TEXTS: dict[str, dict[str, tuple[str, str]]] = {
    "verify_email": {
        "en": (
            "Confirm your email address",
            "Hello,\n\nThanks for creating an SST Virtual Tutor account. "
            "Please confirm your email address by opening this link within 24 hours:\n\n"
            "{link}\n\nIf you did not create an account, you can ignore this email.",
        ),
        "de": (
            "Bestätigen Sie Ihre E-Mail-Adresse",
            "Guten Tag,\n\nVielen Dank, dass Sie ein Konto beim SST Virtual Tutor erstellt haben. "
            "Bitte bestätigen Sie Ihre E-Mail-Adresse innerhalb von 24 Stunden über diesen "
            "Link:\n\n{link}\n\n"
            "Falls Sie kein Konto erstellt haben, können Sie diese E-Mail ignorieren.",
        ),
        "fr": (
            "Confirmez votre adresse e-mail",
            "Bonjour,\n\nMerci d'avoir créé un compte SST Virtual Tutor. "
            "Veuillez confirmer votre adresse e-mail en ouvrant ce lien dans les 24 heures :\n\n"
            "{link}\n\nSi vous n'avez pas créé de compte, vous pouvez ignorer cet e-mail.",
        ),
    },
    "reset_password": {
        "en": (
            "Reset your password",
            "Hello,\n\nSomeone asked to reset the password for this SST Virtual Tutor account. "
            "Open this link within 30 minutes to choose a new password:\n\n{link}\n\n"
            "If this was not you, you can ignore this email and your password stays the same.",
        ),
        "de": (
            "Passwort zurücksetzen",
            "Guten Tag,\n\nJemand hat das Zurücksetzen des Passworts für dieses "
            "SST-Virtual-Tutor-Konto angefordert. Öffnen Sie diesen Link innerhalb von 30 Minuten, "
            "um ein neues Passwort zu wählen:\n\n{link}\n\n"
            "Falls Sie das nicht waren, ignorieren Sie diese E-Mail; Ihr Passwort bleibt "
            "unverändert.",
        ),
        "fr": (
            "Réinitialiser votre mot de passe",
            "Bonjour,\n\nQuelqu'un a demandé la réinitialisation du mot de passe de ce compte "
            "SST Virtual Tutor. Ouvrez ce lien dans les 30 minutes pour choisir un nouveau "
            "mot de passe :\n\n{link}\n\n"
            "Si ce n'était pas vous, ignorez cet e-mail ; votre mot de passe reste inchangé.",
        ),
    },
    "cost_alert": {
        "en": (
            "AI cost alert ({period})",
            "Hello,\n\nAn AI spending threshold was crossed this month ({period}).\n\n"
            "Scope: {scope}\nSpent so far: CHF {amount}\nThreshold: CHF {threshold}\n\n"
            "The breakdown is in the admin area:\n\n{link}\n\nYou get one email per threshold "
            "and month.",
        ),
        "de": (
            "Hinweis zu KI-Kosten ({period})",
            "Guten Tag,\n\nIn diesem Monat ({period}) wurde eine Kostenschwelle für KI-Aufrufe "
            "überschritten.\n\nBereich: {scope}\nBisher ausgegeben: CHF {amount}\n"
            "Schwelle: CHF {threshold}\n\nDie Aufschlüsselung finden Sie im Admin-Bereich:\n\n"
            "{link}\n\nSie erhalten eine E-Mail pro Schwelle und Monat.",
        ),
        "fr": (
            "Alerte de coûts IA ({period})",
            "Bonjour,\n\nUn seuil de dépenses IA a été dépassé ce mois-ci ({period}).\n\n"
            "Périmètre : {scope}\nDépensé à ce jour : CHF {amount}\nSeuil : CHF {threshold}\n\n"
            "Le détail se trouve dans l'espace admin :\n\n{link}\n\nVous recevez un e-mail par "
            "seuil et par mois.",
        ),
    },
}


def build(kind: str, locale: str, to: str, **params: str) -> OutgoingEmail:
    locale = locale if locale in ("en", "de", "fr") else "en"
    subject, body = TEXTS[kind][locale]
    text = body.format(**params) + SIGNATURE[locale]
    return OutgoingEmail(to=to, subject=subject.format(**params), text=text)


def app_link(path: str) -> str:
    return get_settings().app_base_url.rstrip("/") + path
