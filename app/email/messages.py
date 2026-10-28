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
    "student_invite": {
        "en": (
            "Your SST Virtual Tutor login",
            "Hi {first_name},\n\nYour parent has set up an SST Virtual Tutor account for you. "
            "Open this link within 7 days to choose your password:\n\n{link}\n\n"
            "The tutor is an AI. Use it only as your school allows.",
        ),
        "de": (
            "Dein Login für den SST Virtual Tutor",
            "Hallo {first_name},\n\nDeine Eltern haben ein Konto beim SST Virtual Tutor für dich "
            "eingerichtet. Öffne diesen Link innerhalb von 7 Tagen, um dein Passwort zu wählen:\n\n"
            "{link}\n\nDer Tutor ist eine KI. Nutze ihn nur so, wie es deine Schule erlaubt.",
        ),
        "fr": (
            "Ton accès au SST Virtual Tutor",
            "Salut {first_name},\n\nTes parents ont créé un compte SST Virtual Tutor pour toi. "
            "Ouvre ce lien dans les 7 jours pour choisir ton mot de passe :\n\n{link}\n\n"
            "Le tuteur est une IA. Utilise-le uniquement comme ton école l'autorise.",
        ),
    },
    "staff_invite": {
        "en": (
            "Your SST Virtual Tutor staff account",
            "Hello {first_name},\n\nAn SST Virtual Tutor account has been created for you as "
            "{role}. Open this link within 7 days to choose your password. You will then be "
            "asked to set up an authenticator app, which is required for staff:\n\n{link}",
        ),
        "de": (
            "Ihr Mitarbeiterkonto beim SST Virtual Tutor",
            "Guten Tag {first_name},\n\nFür Sie wurde ein Konto beim SST Virtual Tutor als "
            "{role} erstellt. Öffnen Sie diesen Link innerhalb von 7 Tagen, um Ihr Passwort zu "
            "wählen. Anschliessend richten Sie eine Authenticator-App ein, die für Mitarbeitende "
            "Pflicht ist:\n\n{link}",
        ),
        "fr": (
            "Votre compte collaborateur SST Virtual Tutor",
            "Bonjour {first_name},\n\nUn compte SST Virtual Tutor a été créé pour vous en tant "
            "que {role}. Ouvrez ce lien dans les 7 jours pour choisir votre mot de passe. Vous "
            "devrez ensuite configurer une application d'authentification, obligatoire pour le "
            "personnel :\n\n{link}",
        ),
    },
    "trial_ending": {
        "en": (
            "Your free trial ends in three days",
            "Hello,\n\nYour SST Virtual Tutor trial ends in three days. After that your "
            "subscription starts and the payment method you saved will be charged. "
            "To change or cancel, open Billing in the app:\n\n{link}",
        ),
        "de": (
            "Ihre kostenlose Testphase endet in drei Tagen",
            "Guten Tag,\n\nIhre Testphase beim SST Virtual Tutor endet in drei Tagen. Danach "
            "beginnt Ihr Abonnement und die hinterlegte Zahlungsmethode wird belastet. "
            "Zum Ändern oder Kündigen öffnen Sie in der App den Bereich Abrechnung:\n\n{link}",
        ),
        "fr": (
            "Votre essai gratuit se termine dans trois jours",
            "Bonjour,\n\nVotre essai SST Virtual Tutor se termine dans trois jours. Ensuite, "
            "votre abonnement commence et le moyen de paiement enregistré sera débité. "
            "Pour modifier ou annuler, ouvrez Facturation dans l'application :\n\n{link}",
        ),
    },
    "payment_failed": {
        "en": (
            "We could not take your payment",
            "Hello,\n\nYour latest SST Virtual Tutor payment did not go through. Access continues "
            "for 7 days while you update your payment method:\n\n{link}",
        ),
        "de": (
            "Ihre Zahlung konnte nicht ausgeführt werden",
            "Guten Tag,\n\nIhre letzte Zahlung für den SST Virtual Tutor ist fehlgeschlagen. "
            "Der Zugang bleibt 7 Tage bestehen, während Sie Ihre Zahlungsmethode aktualisieren:"
            "\n\n{link}",
        ),
        "fr": (
            "Votre paiement n'a pas abouti",
            "Bonjour,\n\nVotre dernier paiement SST Virtual Tutor a échoué. L'accès reste ouvert "
            "pendant 7 jours le temps de mettre à jour votre moyen de paiement :\n\n{link}",
        ),
    },
}


def build(kind: str, locale: str, to: str, **params: str) -> OutgoingEmail:
    locale = locale if locale in ("en", "de", "fr") else "en"
    subject, body = TEXTS[kind][locale]
    text = body.format(**params) + SIGNATURE[locale]
    return OutgoingEmail(to=to, subject=subject, text=text)


def app_link(path: str) -> str:
    return get_settings().app_base_url.rstrip("/") + path
