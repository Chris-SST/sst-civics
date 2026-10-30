"""Email texts in British English, German and French. Other languages fall back to English.

Each message is a function of (locale, **params) returning (subject, text).
Keep these short and plain; the app address comes from settings."""

from __future__ import annotations

from app.config import get_settings
from app.email.backend import OutgoingEmail

SIGNATURE = {
    "en": "\n\nCivics Trainer",
    "de": "\n\nCivics Trainer",
    "fr": "\n\nCivics Trainer",
}

TEXTS: dict[str, dict[str, tuple[str, str]]] = {
    "verify_email": {
        "en": (
            "Confirm your email address",
            "Hello,\n\nThanks for creating a Civics Trainer account. "
            "Please confirm your email address by opening this link within 24 hours:\n\n"
            "{link}\n\nIf you did not create an account, you can ignore this email.",
        ),
        "de": (
            "Bestätigen Sie Ihre E-Mail-Adresse",
            "Guten Tag,\n\nVielen Dank, dass Sie ein Konto bei Civics Trainer erstellt haben. "
            "Bitte bestätigen Sie Ihre E-Mail-Adresse innerhalb von 24 Stunden über diesen "
            "Link:\n\n{link}\n\n"
            "Falls Sie kein Konto erstellt haben, können Sie diese E-Mail ignorieren.",
        ),
        "fr": (
            "Confirmez votre adresse e-mail",
            "Bonjour,\n\nMerci d'avoir créé un compte Civics Trainer. "
            "Veuillez confirmer votre adresse e-mail en ouvrant ce lien dans les 24 heures :\n\n"
            "{link}\n\nSi vous n'avez pas créé de compte, vous pouvez ignorer cet e-mail.",
        ),
    },
    "reset_password": {
        "en": (
            "Reset your password",
            "Hello,\n\nSomeone asked to reset the password for this Civics Trainer account. "
            "Open this link within 30 minutes to choose a new password:\n\n{link}\n\n"
            "If this was not you, you can ignore this email and your password stays the same.",
        ),
        "de": (
            "Passwort zurücksetzen",
            "Guten Tag,\n\nJemand hat das Zurücksetzen des Passworts für dieses "
            "Civics-Trainer-Konto angefordert. Öffnen Sie diesen Link innerhalb von 30 Minuten, "
            "um ein neues Passwort zu wählen:\n\n{link}\n\n"
            "Falls Sie das nicht waren, ignorieren Sie diese E-Mail; Ihr Passwort bleibt "
            "unverändert.",
        ),
        "fr": (
            "Réinitialiser votre mot de passe",
            "Bonjour,\n\nQuelqu'un a demandé la réinitialisation du mot de passe de ce compte "
            "Civics Trainer. Ouvrez ce lien dans les 30 minutes pour choisir un nouveau "
            "mot de passe :\n\n{link}\n\n"
            "Si ce n'était pas vous, ignorez cet e-mail ; votre mot de passe reste inchangé.",
        ),
    },
    "sign_in_link": {
        "en": (
            "Your sign-in link",
            "Hello,\n\nOpen this link within 15 minutes to sign in. It works once:\n\n{link}\n\n"
            "If you did not ask for it, you can ignore this email. Nobody can sign in without "
            "the link.",
        ),
        "de": (
            "Ihr Anmeldelink",
            "Guten Tag,\n\nÖffnen Sie diesen Link innerhalb von 15 Minuten, um sich anzumelden. "
            "Er funktioniert einmal:\n\n{link}\n\n"
            "Falls Sie ihn nicht angefordert haben, können Sie diese E-Mail ignorieren. Ohne den "
            "Link kann sich niemand anmelden.",
        ),
        "fr": (
            "Votre lien de connexion",
            "Bonjour,\n\nOuvrez ce lien dans les 15 minutes pour vous connecter. Il ne fonctionne "
            "qu'une fois :\n\n{link}\n\n"
            "Si vous ne l'avez pas demandé, vous pouvez ignorer cet e-mail. Personne ne peut se "
            "connecter sans ce lien.",
        ),
    },
    "account_deleted": {
        "en": (
            "Your account is being deleted",
            "Hello,\n\nAs you asked, we are deleting your account and your learning data: "
            "progress, answers, conversations with the AI assistant and question reports.\n\n"
            "Billing records of payments you made are kept for as long as the law requires, "
            "without your email address.\n\n"
            "If you did not ask for this, please reply to this email at once.",
        ),
        "de": (
            "Ihr Konto wird gelöscht",
            "Guten Tag,\n\nWie von Ihnen gewünscht, löschen wir Ihr Konto und Ihre Lerndaten: "
            "Fortschritt, Antworten, Gespräche mit dem KI-Assistenten und Fragemeldungen.\n\n"
            "Buchhaltungsbelege zu Ihren Zahlungen bewahren wir so lange auf, wie es das Gesetz "
            "verlangt, ohne Ihre E-Mail-Adresse.\n\n"
            "Falls Sie dies nicht veranlasst haben, antworten Sie bitte umgehend auf diese "
            "E-Mail.",
        ),
        "fr": (
            "Votre compte est en cours de suppression",
            "Bonjour,\n\nComme vous l'avez demandé, nous supprimons votre compte et vos données "
            "d'apprentissage : progression, réponses, conversations avec l'assistant IA et "
            "signalements de questions.\n\n"
            "Les pièces comptables de vos paiements sont conservées aussi longtemps que la loi "
            "l'exige, sans votre adresse e-mail.\n\n"
            "Si vous n'êtes pas à l'origine de cette demande, répondez immédiatement à cet "
            "e-mail.",
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
