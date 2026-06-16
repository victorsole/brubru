"""
One-off i18n inserter for the Phase A "api.keys.*" strings.
Adds a `keys` block to the `api` block in each of the 6 locale files.

British English in en. Catalan with diacritics (sóc, perquè, Brussel·les).
"""
import json
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parent.parent / "src" / "i18n" / "locales"

TRANSLATIONS = {
    "en": {
        "title": "Your API keys",
        "lede": "Mint, list and revoke the keys your applications use to call the Brubru Data Provider API.",
        "activeCount": "{{active}} of {{max}} active",
        "createCta": "Create key",
        "loading": "Loading your keys…",
        "empty": {
            "title": "No keys yet",
            "body": "Create your first API key to start calling /api/v1/* from your application, command line or notebook.",
            "cta": "Create your first API key",
        },
        "cap": {
            "reached": "You have reached the maximum of 3 active API keys. Revoke an unused key to create a new one.",
        },
        "signedOut": {
            "title": "Sign in to mint an API key",
            "body": "Self-serve API keys are minted from your Brubru account. Sign in or create one to get started.",
            "cta": "Sign in",
            "signup": "Create an account",
        },
        "list": {
            "name": "Name",
            "prefix": "Key prefix",
            "scopes": "Scopes",
            "lastUsed": "Last used",
            "expires": "Expires",
            "status": "Status",
            "revoke": "Revoke",
            "never": "Never",
            "statusLabels": {
                "active": "Active",
                "revoked": "Revoked",
                "expired": "Expired",
            },
        },
        "create": {
            "title": "Create API key",
            "subtitle": "Pick the scopes this key needs and choose an expiry window.",
            "nameLabel": "Name",
            "namePlaceholder": "Production, Local dev, GovClipping integration…",
            "nameHint": "3–100 characters. Visible only to you.",
            "scopesLabel": "What can this key do?",
            "scopesHint": "Each scope unlocks a related group of /api/v1/* endpoints. Tick what you need; leave the rest off.",
            "loadingScopes": "Loading the scope catalogue…",
            "expiryLabel": "Expires after",
            "expiryHint": "After this window the key stops working. You can rotate to a new one at any time.",
            "expiryOptions": {
                "30": "30 days",
                "90": "90 days",
                "180": "180 days (recommended)",
                "365": "365 days",
            },
            "submit": "Create key",
            "submitting": "Creating…",
            "cancel": "Cancel",
            "errors": {
                "nameLength": "Name must be between 3 and 100 characters.",
                "scopesRequired": "Pick at least one scope.",
                "invalid_scopes": "One of the chosen scopes is not allowed. Pick only scopes from the list.",
                "invalid_expiry": "Pick a valid expiry window from the dropdown.",
                "key_cap_reached": "You already have 3 active keys. Revoke an unused one to create a new one.",
                "mint_rate_limited": "Too many keys minted in the last hour. Try again later.",
                "validation_error": "One of the fields is invalid. Please review and try again.",
                "unknown": "We could not create the key. Please try again or contact hello@beresol.eu.",
            },
        },
        "reveal": {
            "title": "Save this key now",
            "warning": "This is the only time we will show this key. Copy it and store it somewhere safe — a password manager, a CI secret store, an env file. If you lose it, revoke and mint a new one.",
            "copy": "Copy to clipboard",
            "copied": "Copied",
            "done": "I've saved it",
        },
        "revoke": {
            "title": "Revoke this key?",
            "body": "Any application using \"{{name}}\" will stop working immediately. This cannot be undone.",
            "cancel": "Cancel",
            "confirm": "Revoke",
            "working": "Revoking…",
        },
    },

    # ---- Spanish -------------------------------------------------------------
    "es": {
        "title": "Tus claves API",
        "lede": "Crea, lista y revoca las claves que tus aplicaciones usan para llamar a la API de datos de Brubru.",
        "activeCount": "{{active}} de {{max}} activas",
        "createCta": "Crear clave",
        "loading": "Cargando tus claves…",
        "empty": {
            "title": "Aún no tienes claves",
            "body": "Crea tu primera clave API para empezar a llamar /api/v1/* desde tu aplicación, terminal o notebook.",
            "cta": "Crea tu primera clave API",
        },
        "cap": {
            "reached": "Has alcanzado el máximo de 3 claves API activas. Revoca una sin usar para crear otra.",
        },
        "signedOut": {
            "title": "Inicia sesión para crear una clave API",
            "body": "Las claves API se crean desde tu cuenta de Brubru. Inicia sesión o crea una para empezar.",
            "cta": "Iniciar sesión",
            "signup": "Crear cuenta",
        },
        "list": {
            "name": "Nombre",
            "prefix": "Prefijo",
            "scopes": "Ámbitos",
            "lastUsed": "Último uso",
            "expires": "Caduca",
            "status": "Estado",
            "revoke": "Revocar",
            "never": "Nunca",
            "statusLabels": {
                "active": "Activa",
                "revoked": "Revocada",
                "expired": "Caducada",
            },
        },
        "create": {
            "title": "Crear clave API",
            "subtitle": "Elige los ámbitos que esta clave necesita y la ventana de caducidad.",
            "nameLabel": "Nombre",
            "namePlaceholder": "Producción, Local, Integración GovClipping…",
            "nameHint": "Entre 3 y 100 caracteres. Solo lo ves tú.",
            "scopesLabel": "¿Qué puede hacer esta clave?",
            "scopesHint": "Cada ámbito desbloquea un grupo de endpoints /api/v1/*. Marca lo que necesites; deja el resto sin marcar.",
            "loadingScopes": "Cargando catálogo de ámbitos…",
            "expiryLabel": "Caduca tras",
            "expiryHint": "Pasada esta ventana la clave deja de funcionar. Puedes rotar a una nueva cuando quieras.",
            "expiryOptions": {
                "30": "30 días",
                "90": "90 días",
                "180": "180 días (recomendado)",
                "365": "365 días",
            },
            "submit": "Crear clave",
            "submitting": "Creando…",
            "cancel": "Cancelar",
            "errors": {
                "nameLength": "El nombre debe tener entre 3 y 100 caracteres.",
                "scopesRequired": "Elige al menos un ámbito.",
                "invalid_scopes": "Alguno de los ámbitos elegidos no está permitido. Elige solo de la lista.",
                "invalid_expiry": "Elige una ventana de caducidad válida.",
                "key_cap_reached": "Ya tienes 3 claves activas. Revoca una sin usar para crear otra.",
                "mint_rate_limited": "Demasiadas claves creadas en la última hora. Inténtalo más tarde.",
                "validation_error": "Algún campo no es válido. Revísalo e inténtalo de nuevo.",
                "unknown": "No hemos podido crear la clave. Inténtalo de nuevo o escribe a hello@beresol.eu.",
            },
        },
        "reveal": {
            "title": "Guarda esta clave ahora",
            "warning": "Es la única vez que mostraremos esta clave. Cópiala y guárdala en un sitio seguro: gestor de contraseñas, secreto de CI o archivo .env. Si la pierdes, revoca y crea una nueva.",
            "copy": "Copiar al portapapeles",
            "copied": "Copiada",
            "done": "Ya la he guardado",
        },
        "revoke": {
            "title": "¿Revocar esta clave?",
            "body": "Cualquier aplicación que use «{{name}}» dejará de funcionar al instante. No se puede deshacer.",
            "cancel": "Cancelar",
            "confirm": "Revocar",
            "working": "Revocando…",
        },
    },

    # ---- Catalan (accent-correct: sóc, perquè, Brussel·les, política) -------
    "ca": {
        "title": "Les teves claus API",
        "lede": "Crea, llista i revoca les claus que les teves aplicacions fan servir per cridar l'API de dades de Brubru.",
        "activeCount": "{{active}} de {{max}} actives",
        "createCta": "Crear clau",
        "loading": "Carregant les teves claus…",
        "empty": {
            "title": "Encara no tens claus",
            "body": "Crea la teva primera clau API per començar a cridar /api/v1/* des de l'aplicació, terminal o notebook.",
            "cta": "Crea la primera clau API",
        },
        "cap": {
            "reached": "Has arribat al màxim de 3 claus API actives. Revoca una clau no utilitzada per crear-ne una de nova.",
        },
        "signedOut": {
            "title": "Inicia sessió per crear una clau API",
            "body": "Les claus API es creen des del teu compte de Brubru. Inicia sessió o crea'n un per començar.",
            "cta": "Iniciar sessió",
            "signup": "Crear compte",
        },
        "list": {
            "name": "Nom",
            "prefix": "Prefix",
            "scopes": "Àmbits",
            "lastUsed": "Últim ús",
            "expires": "Caduca",
            "status": "Estat",
            "revoke": "Revocar",
            "never": "Mai",
            "statusLabels": {
                "active": "Activa",
                "revoked": "Revocada",
                "expired": "Caducada",
            },
        },
        "create": {
            "title": "Crear clau API",
            "subtitle": "Tria els àmbits que aquesta clau necessita i la finestra de caducitat.",
            "nameLabel": "Nom",
            "namePlaceholder": "Producció, Local, Integració GovClipping…",
            "nameHint": "Entre 3 i 100 caràcters. Només la veus tu.",
            "scopesLabel": "Què pot fer aquesta clau?",
            "scopesHint": "Cada àmbit desbloqueja un grup d'endpoints /api/v1/*. Marca el que necessitis; deixa la resta sense marcar.",
            "loadingScopes": "Carregant el catàleg d'àmbits…",
            "expiryLabel": "Caduca al cap de",
            "expiryHint": "Passada aquesta finestra la clau deixa de funcionar. Pots rotar-la quan vulguis.",
            "expiryOptions": {
                "30": "30 dies",
                "90": "90 dies",
                "180": "180 dies (recomanat)",
                "365": "365 dies",
            },
            "submit": "Crear clau",
            "submitting": "Creant…",
            "cancel": "Cancel·lar",
            "errors": {
                "nameLength": "El nom ha de tenir entre 3 i 100 caràcters.",
                "scopesRequired": "Tria almenys un àmbit.",
                "invalid_scopes": "Algun dels àmbits triats no és permès. Tria només els de la llista.",
                "invalid_expiry": "Tria una finestra de caducitat vàlida.",
                "key_cap_reached": "Ja tens 3 claus actives. Revoca'n una de no utilitzada per crear-ne una de nova.",
                "mint_rate_limited": "Massa claus creades a l'última hora. Torna-ho a provar més tard.",
                "validation_error": "Algun camp no és vàlid. Revisa'l i torna-ho a provar.",
                "unknown": "No hem pogut crear la clau. Torna-ho a provar o escriu a hello@beresol.eu.",
            },
        },
        "reveal": {
            "title": "Desa aquesta clau ara",
            "warning": "És l'única vegada que et mostrarem aquesta clau. Copia-la i desa-la en un lloc segur: gestor de contrasenyes, secret de CI o fitxer .env. Si la perds, revoca-la i crea'n una de nova.",
            "copy": "Copiar al porta-retalls",
            "copied": "Copiada",
            "done": "Ja l'he desada",
        },
        "revoke": {
            "title": "Revocar aquesta clau?",
            "body": "Qualsevol aplicació que faci servir «{{name}}» deixarà de funcionar a l'instant. No es pot desfer.",
            "cancel": "Cancel·lar",
            "confirm": "Revocar",
            "working": "Revocant…",
        },
    },

    # ---- French --------------------------------------------------------------
    "fr": {
        "title": "Vos clés API",
        "lede": "Créez, listez et révoquez les clés que vos applications utilisent pour appeler l'API de données Brubru.",
        "activeCount": "{{active}} sur {{max}} actives",
        "createCta": "Créer une clé",
        "loading": "Chargement de vos clés…",
        "empty": {
            "title": "Pas encore de clé",
            "body": "Créez votre première clé API pour commencer à appeler /api/v1/* depuis votre application, terminal ou notebook.",
            "cta": "Créer ma première clé API",
        },
        "cap": {
            "reached": "Vous avez atteint le maximum de 3 clés API actives. Révoquez une clé inutilisée pour en créer une autre.",
        },
        "signedOut": {
            "title": "Connectez-vous pour créer une clé API",
            "body": "Les clés API se créent depuis votre compte Brubru. Connectez-vous ou créez-en un pour commencer.",
            "cta": "Se connecter",
            "signup": "Créer un compte",
        },
        "list": {
            "name": "Nom",
            "prefix": "Préfixe",
            "scopes": "Périmètres",
            "lastUsed": "Dernière utilisation",
            "expires": "Expire",
            "status": "Statut",
            "revoke": "Révoquer",
            "never": "Jamais",
            "statusLabels": {
                "active": "Active",
                "revoked": "Révoquée",
                "expired": "Expirée",
            },
        },
        "create": {
            "title": "Créer une clé API",
            "subtitle": "Choisissez les périmètres dont cette clé a besoin et la fenêtre d'expiration.",
            "nameLabel": "Nom",
            "namePlaceholder": "Production, Local, Intégration GovClipping…",
            "nameHint": "Entre 3 et 100 caractères. Visible uniquement par vous.",
            "scopesLabel": "Que peut faire cette clé ?",
            "scopesHint": "Chaque périmètre débloque un groupe d'endpoints /api/v1/*. Cochez ce dont vous avez besoin ; laissez le reste décoché.",
            "loadingScopes": "Chargement du catalogue de périmètres…",
            "expiryLabel": "Expire après",
            "expiryHint": "Passée cette fenêtre, la clé ne fonctionne plus. Vous pouvez en générer une nouvelle à tout moment.",
            "expiryOptions": {
                "30": "30 jours",
                "90": "90 jours",
                "180": "180 jours (recommandé)",
                "365": "365 jours",
            },
            "submit": "Créer la clé",
            "submitting": "Création…",
            "cancel": "Annuler",
            "errors": {
                "nameLength": "Le nom doit contenir entre 3 et 100 caractères.",
                "scopesRequired": "Choisissez au moins un périmètre.",
                "invalid_scopes": "L'un des périmètres choisis n'est pas autorisé. Choisissez uniquement dans la liste.",
                "invalid_expiry": "Choisissez une fenêtre d'expiration valide.",
                "key_cap_reached": "Vous avez déjà 3 clés actives. Révoquez-en une inutilisée pour en créer une nouvelle.",
                "mint_rate_limited": "Trop de clés créées dans la dernière heure. Réessayez plus tard.",
                "validation_error": "Un des champs est invalide. Vérifiez et réessayez.",
                "unknown": "Nous n'avons pas pu créer la clé. Réessayez ou contactez hello@beresol.eu.",
            },
        },
        "reveal": {
            "title": "Enregistrez cette clé maintenant",
            "warning": "C'est la seule fois où nous afficherons cette clé. Copiez-la et stockez-la en lieu sûr : gestionnaire de mots de passe, secret CI, fichier .env. Si vous la perdez, révoquez-la et créez-en une autre.",
            "copy": "Copier dans le presse-papiers",
            "copied": "Copiée",
            "done": "C'est enregistré",
        },
        "revoke": {
            "title": "Révoquer cette clé ?",
            "body": "Toute application utilisant « {{name}} » cessera immédiatement de fonctionner. C'est irréversible.",
            "cancel": "Annuler",
            "confirm": "Révoquer",
            "working": "Révocation…",
        },
    },

    # ---- Italian -------------------------------------------------------------
    "it": {
        "title": "Le tue chiavi API",
        "lede": "Crea, elenca e revoca le chiavi che le tue applicazioni usano per chiamare l'API dati di Brubru.",
        "activeCount": "{{active}} di {{max}} attive",
        "createCta": "Crea chiave",
        "loading": "Caricamento delle chiavi…",
        "empty": {
            "title": "Nessuna chiave ancora",
            "body": "Crea la tua prima chiave API per iniziare a chiamare /api/v1/* dalla tua applicazione, terminale o notebook.",
            "cta": "Crea la prima chiave API",
        },
        "cap": {
            "reached": "Hai raggiunto il limite di 3 chiavi API attive. Revoca una chiave inutilizzata per crearne una nuova.",
        },
        "signedOut": {
            "title": "Accedi per creare una chiave API",
            "body": "Le chiavi API si creano dal tuo account Brubru. Accedi o creane uno per iniziare.",
            "cta": "Accedi",
            "signup": "Crea un account",
        },
        "list": {
            "name": "Nome",
            "prefix": "Prefisso",
            "scopes": "Ambiti",
            "lastUsed": "Ultimo uso",
            "expires": "Scade",
            "status": "Stato",
            "revoke": "Revoca",
            "never": "Mai",
            "statusLabels": {
                "active": "Attiva",
                "revoked": "Revocata",
                "expired": "Scaduta",
            },
        },
        "create": {
            "title": "Crea chiave API",
            "subtitle": "Scegli gli ambiti necessari e la finestra di scadenza.",
            "nameLabel": "Nome",
            "namePlaceholder": "Produzione, Locale, Integrazione GovClipping…",
            "nameHint": "Tra 3 e 100 caratteri. Visibile solo a te.",
            "scopesLabel": "Cosa può fare questa chiave?",
            "scopesHint": "Ogni ambito sblocca un gruppo di endpoint /api/v1/*. Spunta ciò che ti serve; lascia il resto.",
            "loadingScopes": "Caricamento del catalogo degli ambiti…",
            "expiryLabel": "Scade dopo",
            "expiryHint": "Trascorsa questa finestra la chiave smette di funzionare. Puoi crearne una nuova in qualsiasi momento.",
            "expiryOptions": {
                "30": "30 giorni",
                "90": "90 giorni",
                "180": "180 giorni (consigliato)",
                "365": "365 giorni",
            },
            "submit": "Crea chiave",
            "submitting": "Creazione…",
            "cancel": "Annulla",
            "errors": {
                "nameLength": "Il nome deve essere tra 3 e 100 caratteri.",
                "scopesRequired": "Scegli almeno un ambito.",
                "invalid_scopes": "Uno degli ambiti scelti non è ammesso. Scegli solo dalla lista.",
                "invalid_expiry": "Scegli una finestra di scadenza valida.",
                "key_cap_reached": "Hai già 3 chiavi attive. Revoca una chiave inutilizzata per crearne una nuova.",
                "mint_rate_limited": "Troppe chiavi create nell'ultima ora. Riprova più tardi.",
                "validation_error": "Uno dei campi non è valido. Verifica e riprova.",
                "unknown": "Non siamo riusciti a creare la chiave. Riprova o scrivi a hello@beresol.eu.",
            },
        },
        "reveal": {
            "title": "Salva questa chiave ora",
            "warning": "Questa è l'unica volta in cui mostreremo questa chiave. Copiala e archiviala in un posto sicuro: gestore di password, secret CI, file .env. Se la perdi, revocala e creane una nuova.",
            "copy": "Copia negli appunti",
            "copied": "Copiata",
            "done": "L'ho salvata",
        },
        "revoke": {
            "title": "Revocare questa chiave?",
            "body": "Qualsiasi applicazione che usa «{{name}}» smetterà di funzionare immediatamente. Non si può annullare.",
            "cancel": "Annulla",
            "confirm": "Revoca",
            "working": "Revoca in corso…",
        },
    },

    # ---- Dutch ---------------------------------------------------------------
    "nl": {
        "title": "Jouw API-sleutels",
        "lede": "Maak, bekijk en trek API-sleutels in die je applicaties gebruiken om de Brubru-data-API aan te roepen.",
        "activeCount": "{{active}} van {{max}} actief",
        "createCta": "Sleutel aanmaken",
        "loading": "Sleutels worden geladen…",
        "empty": {
            "title": "Nog geen sleutels",
            "body": "Maak je eerste API-sleutel aan om /api/v1/* aan te roepen vanuit je applicatie, terminal of notebook.",
            "cta": "Maak je eerste API-sleutel",
        },
        "cap": {
            "reached": "Je hebt het maximum van 3 actieve API-sleutels bereikt. Trek een ongebruikte sleutel in om een nieuwe te maken.",
        },
        "signedOut": {
            "title": "Log in om een API-sleutel aan te maken",
            "body": "API-sleutels worden vanuit je Brubru-account aangemaakt. Log in of maak er een om te beginnen.",
            "cta": "Inloggen",
            "signup": "Account aanmaken",
        },
        "list": {
            "name": "Naam",
            "prefix": "Prefix",
            "scopes": "Scopes",
            "lastUsed": "Laatst gebruikt",
            "expires": "Verloopt",
            "status": "Status",
            "revoke": "Intrekken",
            "never": "Nooit",
            "statusLabels": {
                "active": "Actief",
                "revoked": "Ingetrokken",
                "expired": "Verlopen",
            },
        },
        "create": {
            "title": "API-sleutel aanmaken",
            "subtitle": "Kies de scopes die deze sleutel nodig heeft en de geldigheidsperiode.",
            "nameLabel": "Naam",
            "namePlaceholder": "Productie, Lokaal, GovClipping-integratie…",
            "nameHint": "3–100 tekens. Alleen jij ziet dit.",
            "scopesLabel": "Wat mag deze sleutel doen?",
            "scopesHint": "Elke scope geeft toegang tot een groep /api/v1/*-endpoints. Vink aan wat je nodig hebt; laat de rest staan.",
            "loadingScopes": "Scope-catalogus wordt geladen…",
            "expiryLabel": "Verloopt na",
            "expiryHint": "Na deze periode werkt de sleutel niet meer. Je kunt altijd een nieuwe aanmaken.",
            "expiryOptions": {
                "30": "30 dagen",
                "90": "90 dagen",
                "180": "180 dagen (aanbevolen)",
                "365": "365 dagen",
            },
            "submit": "Sleutel aanmaken",
            "submitting": "Bezig met aanmaken…",
            "cancel": "Annuleren",
            "errors": {
                "nameLength": "Naam moet tussen 3 en 100 tekens zijn.",
                "scopesRequired": "Kies minstens één scope.",
                "invalid_scopes": "Een van de gekozen scopes is niet toegestaan. Kies alleen uit de lijst.",
                "invalid_expiry": "Kies een geldige geldigheidsperiode.",
                "key_cap_reached": "Je hebt al 3 actieve sleutels. Trek er een ongebruikte in om een nieuwe te maken.",
                "mint_rate_limited": "Te veel sleutels aangemaakt in het afgelopen uur. Probeer het later opnieuw.",
                "validation_error": "Een van de velden is ongeldig. Controleer en probeer opnieuw.",
                "unknown": "We konden de sleutel niet aanmaken. Probeer het opnieuw of mail hello@beresol.eu.",
            },
        },
        "reveal": {
            "title": "Bewaar deze sleutel nu",
            "warning": "Dit is de enige keer dat we deze sleutel laten zien. Kopieer hem en bewaar hem veilig: wachtwoordkluis, CI-geheim of .env-bestand. Raak je hem kwijt, trek hem in en maak een nieuwe.",
            "copy": "Kopieer naar klembord",
            "copied": "Gekopieerd",
            "done": "Opgeslagen",
        },
        "revoke": {
            "title": "Deze sleutel intrekken?",
            "body": "Elke applicatie die '{{name}}' gebruikt stopt direct met werken. Dit kan niet ongedaan worden gemaakt.",
            "cancel": "Annuleren",
            "confirm": "Intrekken",
            "working": "Bezig met intrekken…",
        },
    },
}


def main() -> int:
    for locale, keys_block in TRANSLATIONS.items():
        path = LOCALES_DIR / f"{locale}.json"
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if "api" not in data:
            data["api"] = {}
        # Idempotent: replace any existing api.keys block in-place.
        data["api"]["keys"] = keys_block

        # Preserve order: api block goes back where it was.
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"  {locale}: wrote {len(keys_block)} top-level api.keys subkeys")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
