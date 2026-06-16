"""One-off i18n inserter for the Phase B 'api.billing.*' strings."""
import json
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parent.parent / "src" / "i18n" / "locales"

TRANSLATIONS = {
    "en": {
        "titlePre": "API",
        "titleAccent": "billing",
        "lede": "Top up your euro balance, watch every call you make against it, and configure auto-top-up so your integration never runs dry.",
        "loading": "Loading your balance…",
        "backToApi": "Back to /api",
        "signedOut": {
            "title": "Sign in to view your API balance",
            "body": "API billing is tied to your Brubru account. Sign in to top up, check usage and set auto-top-up.",
        },
        "balance": {
            "title": "Balance",
            "empty": "Your balance is empty — top up to start calling /api/v1/*.",
            "calls": "~{{count}} lightweight calls remaining",
        },
        "banner": {
            "success": "Thanks — your top-up is processing. Your balance updates as soon as Stripe confirms the payment (usually a few seconds).",
            "cancelled": "Top-up cancelled. No charge was made.",
        },
        "topup": {
            "cta": "Top up",
            "title": "Top up with euros",
            "lede": "Pick a preset or enter a custom amount. Minimum 1 EUR. You'll be redirected to Stripe to pay.",
            "customLabel": "Custom amount (EUR)",
            "customPlaceholder": "e.g. 25",
            "checkout": "Continue to checkout",
            "submitting": "Redirecting…",
            "minHint": "Minimum 1 EUR. We don't issue free signup credit — but our public sandbox (in /api/docs) covers evaluation.",
            "callsApprox": "~{{count}} calls",
            "errors": {
                "topup_below_minimum": "Minimum top-up is 1 EUR.",
                "topup_above_maximum": "For amounts above 5,000 EUR, contact hello@beresol.eu.",
                "stripe_error": "Could not start checkout. Please try again or contact hello@beresol.eu.",
                "unknown": "Could not start checkout. Please try again.",
            },
        },
        "autoTopup": {
            "title": "Automatic top-up",
            "lede": "When your balance drops below the threshold, Brubru charges your default Stripe payment method to top up. Disabled by default.",
            "enableLabel": "Auto-top-up enabled",
            "thresholdLabel": "When balance drops below (EUR)",
            "thresholdHint": "We trigger a top-up the next time you fall below this.",
            "amountLabel": "Top-up amount (EUR)",
            "amountHint": "Minimum 1 EUR. The amount added each cycle.",
            "save": "Save",
            "saving": "Saving…",
            "saved": "Saved",
        },
        "usage": {
            "title": "Recent usage",
            "empty": "No paid calls yet. Calls against /api/v1/* will appear here as soon as they land.",
            "when": "When",
            "endpoint": "Endpoint",
            "method": "Method",
            "cost": "Cost",
            "status": "Status",
            "refunded": "Refunded",
        },
        "history": {
            "title": "Top-up history",
            "status": {
                "pending": "Pending",
                "succeeded": "Succeeded",
                "failed": "Failed",
                "refunded": "Refunded",
            },
        },
    },

    "es": {
        "titlePre": "Facturación",
        "titleAccent": "de la API",
        "lede": "Recarga tu saldo en euros, supervisa cada llamada y configura la recarga automática para que tu integración nunca se quede sin saldo.",
        "loading": "Cargando tu saldo…",
        "backToApi": "Volver a /api",
        "signedOut": {
            "title": "Inicia sesión para ver tu saldo API",
            "body": "La facturación API está ligada a tu cuenta de Brubru. Inicia sesión para recargar, consultar el uso y configurar la recarga automática.",
        },
        "balance": {
            "title": "Saldo",
            "empty": "Tu saldo está vacío — recarga para empezar a llamar /api/v1/*.",
            "calls": "~{{count}} llamadas ligeras restantes",
        },
        "banner": {
            "success": "Gracias — tu recarga se está procesando. Tu saldo se actualizará en cuanto Stripe confirme el pago (segundos normalmente).",
            "cancelled": "Recarga cancelada. No se ha cargado nada.",
        },
        "topup": {
            "cta": "Recargar",
            "title": "Recargar con euros",
            "lede": "Elige un preset o introduce un importe personalizado. Mínimo 1 EUR. Te llevaremos a Stripe para pagar.",
            "customLabel": "Importe personalizado (EUR)",
            "customPlaceholder": "p. ej. 25",
            "checkout": "Continuar al pago",
            "submitting": "Redirigiendo…",
            "minHint": "Mínimo 1 EUR. No damos crédito gratuito al registrarse — pero el sandbox público (en /api/docs) cubre la evaluación.",
            "callsApprox": "~{{count}} llamadas",
            "errors": {
                "topup_below_minimum": "La recarga mínima es 1 EUR.",
                "topup_above_maximum": "Para importes superiores a 5.000 EUR, contacta hello@beresol.eu.",
                "stripe_error": "No se pudo iniciar el pago. Inténtalo de nuevo o contacta hello@beresol.eu.",
                "unknown": "No se pudo iniciar el pago. Inténtalo de nuevo.",
            },
        },
        "autoTopup": {
            "title": "Recarga automática",
            "lede": "Cuando tu saldo cae por debajo del umbral, Brubru cobra tu método de pago de Stripe para recargar. Desactivada por defecto.",
            "enableLabel": "Recarga automática activada",
            "thresholdLabel": "Cuando el saldo cae por debajo de (EUR)",
            "thresholdHint": "Disparamos una recarga la próxima vez que caigas por debajo de este valor.",
            "amountLabel": "Importe de recarga (EUR)",
            "amountHint": "Mínimo 1 EUR. El importe añadido cada ciclo.",
            "save": "Guardar",
            "saving": "Guardando…",
            "saved": "Guardado",
        },
        "usage": {
            "title": "Uso reciente",
            "empty": "Aún no hay llamadas de pago. Las llamadas contra /api/v1/* aparecerán aquí en cuanto se realicen.",
            "when": "Cuándo",
            "endpoint": "Endpoint",
            "method": "Método",
            "cost": "Coste",
            "status": "Estado",
            "refunded": "Reembolsado",
        },
        "history": {
            "title": "Historial de recargas",
            "status": {
                "pending": "Pendiente",
                "succeeded": "Completada",
                "failed": "Fallida",
                "refunded": "Reembolsada",
            },
        },
    },

    "ca": {
        "titlePre": "Facturació",
        "titleAccent": "de l'API",
        "lede": "Recarrega el teu saldo en euros, segueix cada trucada i configura la recàrrega automàtica perquè la teva integració mai es quedi sense saldo.",
        "loading": "Carregant el teu saldo…",
        "backToApi": "Tornar a /api",
        "signedOut": {
            "title": "Inicia sessió per veure el teu saldo API",
            "body": "La facturació API està lligada al teu compte de Brubru. Inicia sessió per recarregar, consultar l'ús i configurar la recàrrega automàtica.",
        },
        "balance": {
            "title": "Saldo",
            "empty": "El teu saldo està buit — recarrega per començar a cridar /api/v1/*.",
            "calls": "~{{count}} trucades lleugeres restants",
        },
        "banner": {
            "success": "Gràcies — la recàrrega s'està processant. El teu saldo s'actualitzarà tan aviat com Stripe confirmi el pagament (normalment segons).",
            "cancelled": "Recàrrega cancel·lada. No s'ha carregat res.",
        },
        "topup": {
            "cta": "Recarregar",
            "title": "Recarregar amb euros",
            "lede": "Tria un preset o introdueix un import personalitzat. Mínim 1 EUR. Et portarem a Stripe per pagar.",
            "customLabel": "Import personalitzat (EUR)",
            "customPlaceholder": "p. ex. 25",
            "checkout": "Continuar al pagament",
            "submitting": "Redirigint…",
            "minHint": "Mínim 1 EUR. No donem crèdit gratuït en registrar-se — però el sandbox públic (a /api/docs) cobreix l'avaluació.",
            "callsApprox": "~{{count}} trucades",
            "errors": {
                "topup_below_minimum": "La recàrrega mínima és 1 EUR.",
                "topup_above_maximum": "Per imports superiors a 5.000 EUR, contacta hello@beresol.eu.",
                "stripe_error": "No s'ha pogut iniciar el pagament. Torna-ho a provar o contacta hello@beresol.eu.",
                "unknown": "No s'ha pogut iniciar el pagament. Torna-ho a provar.",
            },
        },
        "autoTopup": {
            "title": "Recàrrega automàtica",
            "lede": "Quan el teu saldo cau per sota del llindar, Brubru cobra el teu mètode de pagament de Stripe per recarregar. Desactivada per defecte.",
            "enableLabel": "Recàrrega automàtica activada",
            "thresholdLabel": "Quan el saldo cau per sota de (EUR)",
            "thresholdHint": "Disparem una recàrrega la pròxima vegada que caiguis per sota d'aquest valor.",
            "amountLabel": "Import de recàrrega (EUR)",
            "amountHint": "Mínim 1 EUR. L'import afegit a cada cicle.",
            "save": "Desar",
            "saving": "Desant…",
            "saved": "Desat",
        },
        "usage": {
            "title": "Ús recent",
            "empty": "Encara no hi ha trucades de pagament. Les trucades contra /api/v1/* apareixeran aquí tan bon punt es facin.",
            "when": "Quan",
            "endpoint": "Endpoint",
            "method": "Mètode",
            "cost": "Cost",
            "status": "Estat",
            "refunded": "Reemborsat",
        },
        "history": {
            "title": "Històric de recàrregues",
            "status": {
                "pending": "Pendent",
                "succeeded": "Completada",
                "failed": "Fallida",
                "refunded": "Reemborsada",
            },
        },
    },

    "fr": {
        "titlePre": "Facturation",
        "titleAccent": "de l'API",
        "lede": "Rechargez votre solde en euros, suivez chaque appel et configurez la recharge automatique pour que votre intégration ne tombe jamais à court.",
        "loading": "Chargement de votre solde…",
        "backToApi": "Retour vers /api",
        "signedOut": {
            "title": "Connectez-vous pour voir votre solde API",
            "body": "La facturation API est liée à votre compte Brubru. Connectez-vous pour recharger, consulter l'utilisation et configurer la recharge automatique.",
        },
        "balance": {
            "title": "Solde",
            "empty": "Votre solde est vide — rechargez pour commencer à appeler /api/v1/*.",
            "calls": "~{{count}} appels légers restants",
        },
        "banner": {
            "success": "Merci — votre recharge est en cours. Votre solde se met à jour dès que Stripe confirme le paiement (quelques secondes en général).",
            "cancelled": "Recharge annulée. Aucun débit n'a été effectué.",
        },
        "topup": {
            "cta": "Recharger",
            "title": "Recharger en euros",
            "lede": "Choisissez un montant prédéfini ou saisissez un montant personnalisé. Minimum 1 EUR. Vous serez redirigé vers Stripe pour payer.",
            "customLabel": "Montant personnalisé (EUR)",
            "customPlaceholder": "ex. 25",
            "checkout": "Continuer vers le paiement",
            "submitting": "Redirection…",
            "minHint": "Minimum 1 EUR. Aucun crédit gratuit à l'inscription — le sandbox public (dans /api/docs) couvre l'évaluation.",
            "callsApprox": "~{{count}} appels",
            "errors": {
                "topup_below_minimum": "La recharge minimum est de 1 EUR.",
                "topup_above_maximum": "Pour des montants au-delà de 5 000 EUR, contactez hello@beresol.eu.",
                "stripe_error": "Impossible de démarrer le paiement. Réessayez ou contactez hello@beresol.eu.",
                "unknown": "Impossible de démarrer le paiement. Réessayez.",
            },
        },
        "autoTopup": {
            "title": "Recharge automatique",
            "lede": "Lorsque votre solde passe sous le seuil, Brubru débite votre moyen de paiement Stripe par défaut pour recharger. Désactivée par défaut.",
            "enableLabel": "Recharge automatique activée",
            "thresholdLabel": "Lorsque le solde passe sous (EUR)",
            "thresholdHint": "Une recharge se déclenche la prochaine fois que vous passez sous ce seuil.",
            "amountLabel": "Montant de recharge (EUR)",
            "amountHint": "Minimum 1 EUR. Le montant ajouté à chaque cycle.",
            "save": "Enregistrer",
            "saving": "Enregistrement…",
            "saved": "Enregistré",
        },
        "usage": {
            "title": "Utilisation récente",
            "empty": "Aucun appel payant pour l'instant. Les appels vers /api/v1/* apparaîtront ici dès qu'ils seront effectués.",
            "when": "Quand",
            "endpoint": "Endpoint",
            "method": "Méthode",
            "cost": "Coût",
            "status": "Statut",
            "refunded": "Remboursé",
        },
        "history": {
            "title": "Historique des recharges",
            "status": {
                "pending": "En attente",
                "succeeded": "Réussie",
                "failed": "Échouée",
                "refunded": "Remboursée",
            },
        },
    },

    "it": {
        "titlePre": "Fatturazione",
        "titleAccent": "API",
        "lede": "Ricarica il tuo saldo in euro, controlla ogni chiamata e configura la ricarica automatica perché la tua integrazione non rimanga mai senza credito.",
        "loading": "Caricamento del saldo…",
        "backToApi": "Torna a /api",
        "signedOut": {
            "title": "Accedi per vedere il tuo saldo API",
            "body": "La fatturazione API è legata al tuo account Brubru. Accedi per ricaricare, consultare l'uso e configurare la ricarica automatica.",
        },
        "balance": {
            "title": "Saldo",
            "empty": "Il saldo è vuoto — ricarica per iniziare a chiamare /api/v1/*.",
            "calls": "~{{count}} chiamate leggere rimanenti",
        },
        "banner": {
            "success": "Grazie — la ricarica è in elaborazione. Il saldo si aggiorna non appena Stripe conferma il pagamento (di solito pochi secondi).",
            "cancelled": "Ricarica annullata. Nessun addebito.",
        },
        "topup": {
            "cta": "Ricarica",
            "title": "Ricarica in euro",
            "lede": "Scegli un importo predefinito o inseriscine uno personalizzato. Minimo 1 EUR. Verrai reindirizzato su Stripe per pagare.",
            "customLabel": "Importo personalizzato (EUR)",
            "customPlaceholder": "es. 25",
            "checkout": "Vai al pagamento",
            "submitting": "Reindirizzamento…",
            "minHint": "Minimo 1 EUR. Nessun credito gratuito alla registrazione — il sandbox pubblico (in /api/docs) copre la valutazione.",
            "callsApprox": "~{{count}} chiamate",
            "errors": {
                "topup_below_minimum": "La ricarica minima è 1 EUR.",
                "topup_above_maximum": "Per importi sopra i 5.000 EUR, contatta hello@beresol.eu.",
                "stripe_error": "Impossibile avviare il pagamento. Riprova o contatta hello@beresol.eu.",
                "unknown": "Impossibile avviare il pagamento. Riprova.",
            },
        },
        "autoTopup": {
            "title": "Ricarica automatica",
            "lede": "Quando il saldo scende sotto la soglia, Brubru addebita il tuo metodo di pagamento Stripe predefinito. Disattivata per impostazione predefinita.",
            "enableLabel": "Ricarica automatica attiva",
            "thresholdLabel": "Quando il saldo scende sotto (EUR)",
            "thresholdHint": "Una ricarica si attiva la prossima volta che scendi sotto questo valore.",
            "amountLabel": "Importo di ricarica (EUR)",
            "amountHint": "Minimo 1 EUR. L'importo aggiunto ogni ciclo.",
            "save": "Salva",
            "saving": "Salvataggio…",
            "saved": "Salvato",
        },
        "usage": {
            "title": "Uso recente",
            "empty": "Nessuna chiamata a pagamento ancora. Le chiamate verso /api/v1/* compariranno qui non appena effettuate.",
            "when": "Quando",
            "endpoint": "Endpoint",
            "method": "Metodo",
            "cost": "Costo",
            "status": "Stato",
            "refunded": "Rimborsato",
        },
        "history": {
            "title": "Cronologia ricariche",
            "status": {
                "pending": "In sospeso",
                "succeeded": "Completata",
                "failed": "Fallita",
                "refunded": "Rimborsata",
            },
        },
    },

    "nl": {
        "titlePre": "API-",
        "titleAccent": "facturatie",
        "lede": "Vul je euro-saldo aan, volg elke API-call die je doet en stel automatisch bijvullen in zodat je integratie nooit zonder krediet komt.",
        "loading": "Saldo wordt geladen…",
        "backToApi": "Terug naar /api",
        "signedOut": {
            "title": "Log in om je API-saldo te zien",
            "body": "API-facturatie is gekoppeld aan je Brubru-account. Log in om bij te vullen, gebruik te bekijken en automatisch bijvullen in te stellen.",
        },
        "balance": {
            "title": "Saldo",
            "empty": "Je saldo is leeg — vul bij om /api/v1/* te kunnen aanroepen.",
            "calls": "~{{count}} lichte calls over",
        },
        "banner": {
            "success": "Bedankt — je bijvulling wordt verwerkt. Je saldo wordt bijgewerkt zodra Stripe de betaling bevestigt (meestal binnen seconden).",
            "cancelled": "Bijvulling geannuleerd. Er is niets afgeschreven.",
        },
        "topup": {
            "cta": "Bijvullen",
            "title": "Bijvullen met euro's",
            "lede": "Kies een preset of voer een aangepast bedrag in. Minimaal 1 EUR. Je wordt doorgestuurd naar Stripe om te betalen.",
            "customLabel": "Aangepast bedrag (EUR)",
            "customPlaceholder": "bv. 25",
            "checkout": "Naar de betaling",
            "submitting": "Doorsturen…",
            "minHint": "Minimaal 1 EUR. We geven geen gratis krediet bij registratie — de publieke sandbox (in /api/docs) dekt de evaluatie.",
            "callsApprox": "~{{count}} calls",
            "errors": {
                "topup_below_minimum": "Minimum bijvullen is 1 EUR.",
                "topup_above_maximum": "Voor bedragen boven 5.000 EUR, neem contact op via hello@beresol.eu.",
                "stripe_error": "Kon de betaling niet starten. Probeer opnieuw of mail hello@beresol.eu.",
                "unknown": "Kon de betaling niet starten. Probeer opnieuw.",
            },
        },
        "autoTopup": {
            "title": "Automatisch bijvullen",
            "lede": "Wanneer je saldo onder de drempel zakt, schrijft Brubru je standaard Stripe-betaalmethode af om bij te vullen. Standaard uitgeschakeld.",
            "enableLabel": "Automatisch bijvullen aan",
            "thresholdLabel": "Wanneer saldo onder (EUR)",
            "thresholdHint": "We starten een bijvulling de volgende keer dat je onder deze waarde komt.",
            "amountLabel": "Bijvulbedrag (EUR)",
            "amountHint": "Minimaal 1 EUR. Het bedrag dat elke ronde wordt toegevoegd.",
            "save": "Opslaan",
            "saving": "Bezig met opslaan…",
            "saved": "Opgeslagen",
        },
        "usage": {
            "title": "Recent gebruik",
            "empty": "Nog geen betaalde calls. Aanroepen naar /api/v1/* verschijnen hier zodra ze plaatsvinden.",
            "when": "Wanneer",
            "endpoint": "Endpoint",
            "method": "Methode",
            "cost": "Kosten",
            "status": "Status",
            "refunded": "Gerestitueerd",
        },
        "history": {
            "title": "Bijvulgeschiedenis",
            "status": {
                "pending": "In behandeling",
                "succeeded": "Geslaagd",
                "failed": "Mislukt",
                "refunded": "Gerestitueerd",
            },
        },
    },
}


def main() -> int:
    for locale, billing_block in TRANSLATIONS.items():
        path = LOCALES_DIR / f"{locale}.json"
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if "api" not in data:
            data["api"] = {}
        data["api"]["billing"] = billing_block
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"  {locale}: wrote {len(billing_block)} api.billing.* subkeys")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
