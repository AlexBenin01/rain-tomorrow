// Every string on the page, in both languages.
//
// The scaffolding is here from the start rather than retrofitted: moving text
// out of the markup afterwards costs far more than writing it here in the first
// place, and any section added later is born bilingual.
export const STRINGS = {
  en: {
    "lang.other": "Italiano",
    "site.title": "Will it rain tomorrow?",
    "site.tagline":
      "A 17-coefficient statistical model forecasting five towns in the Veneto, " +
      "published every evening and scored against what actually happened.",
    "site.dataNote":
      "Weather data from Open-Meteo (CC BY 4.0), ERA5 reanalysis of the Copernicus " +
      "Climate Change Service at ECMWF.",

    "live.section": "The forecasts on the table",
    "live.heading.tomorrow": "Tomorrow",
    "live.heading.today": "Today",
    "live.heading.past": "Awaiting verification",
    "live.issued": "issued",
    "live.cadence":
      "The model forecasts one day ahead from the last complete day of observations, so a new " +
      "forecast can only exist once a day has ended. It runs every evening around 23:00 " +
      "Italian time — which is when tomorrow appears. Today's forecast stays on the page " +
      "until the day is over and it can be scored.",
    "live.threshold": "of at least 1&nbsp;mm",
    "live.vsNormal": "{ratio}× the {month} normal of {clim}",
    "live.atNormal": "about the {month} normal of {clim}",
    "live.ladder": "how much",
    "live.atLeast": "at least",
    "live.notShipped": "not published here — see below",
    "live.openmeteo": "Open-Meteo forecasts",
    "live.stale":
      "⚠ These forecasts are more than two days old. The daily job may have stopped.",
    "live.empty": "No forecasts published yet.",
    "live.omNote":
      "Open-Meteo's figure is their own daily aggregate, but it answers a different " +
      "question: the chance of rain at <em>some hour</em>, which happens more often " +
      "than a full millimetre over the whole day. Their deterministic forecast, held " +
      "to the same 1&nbsp;mm rule, is the like-for-like comparison.",

    "record.heading": "The public record",
    "record.intro":
      "Every forecast is committed to git before the day it forecasts. You cannot " +
      "tune a model on data that does not exist yet — which is the one thing a " +
      "backtest can never prove.",
    "record.issued": "issued",
    "record.verified": "verified",
    "record.correct": "correct",
    "record.wrong": "wrong",
    "record.brier": "Brier score",
    "record.bss": "skill vs climatology",
    "record.waiting":
      "The record starts empty and fills up one evening at a time. The headline " +
      "numbers below come from 588 held-out days instead.",
    "record.thin":
      "Only {n} forecasts scored so far. Below about 30 the skill score is still " +
      "mostly noise — it is shown anyway, with the sample size next to it.",
    "record.accuracyTrap":
      "The count of correct calls is the easy number to read, and on its own it " +
      "misleads: on an event this rare, “it never rains” would already be right " +
      "about {pct} of the time. That is why the Brier skill score sits beside it.",

    "baseline.heading": "What counts as good",
    "baseline.intro":
      "A forecast is only worth what it adds over the obvious alternatives, so the " +
      "baselines were built first. Skill score against climatology on 588 held-out days:",
    "baseline.constant climatology": "climatology",
    "baseline.monthly climatology": "monthly climatology",
    "baseline.raw persistence (0/1)": "persistence, as yes/no",
    "baseline.calibrated persistence": "persistence, as a probability",
    "baseline.logistic regression": "this model",
    "baseline.gradient boosting": "gradient boosting",
    "baseline.punchline":
      "The bar pointing the wrong way is the finding. “Tomorrow like today” is the " +
      "strongest single predictor there is — but stated as a flat yes or no it scores " +
      "<strong>worse than saying nothing at all</strong>. The same information, " +
      "expressed as a calibrated probability, turns into real skill. Having the right " +
      "predictor is not enough; it has to be expressed as a probability.",

    "cut.heading": "Why there is no yes-or-no here",
    "cut.intro":
      "It is tempting to turn the number into a verdict at 50%. On an event that " +
      "happens about 30% of the time, that is the wrong place to cut — and it is " +
      "how a forecast gets called wrong when it was right.",
    "cut.table":
      "The same model, on the same 588 days, judged at different cut-offs:",
    "cut.threshold": "cut-off",
    "cut.pod": "rain days caught",
    "cut.far": "false alarms",
    "cut.csi": "overall",
    "cut.punchline":
      "At 50% the model catches fewer than half the rainy days. At 30% it catches " +
      "three quarters, and that is where the overall score peaks. Which cut-off is " +
      "right depends on what a miss costs you compared to a false alarm — so the " +
      "page shows the probability and leaves the choice where it belongs.",
    "reliability.heading": "Does 70% mean 70%?",
    "reliability.intro":
      "A probability is only honest if it verifies. Each point compares what the model " +
      "said against how often it then rained; the diagonal is perfect honesty.",
    "reliability.predicted": "forecast",
    "reliability.observed": "observed",
    "reliability.perfect": "perfectly reliable",
    "reliability.samples": "forecasts",

    "stationarity.heading": "Why the model is trained on 8 years, not 29",
    "stationarity.intro":
      "The plan was to use the whole record back to 1996. The data refused. Wet-day " +
      "frequency is steady for two decades and then falls away — but only in the " +
      "foothills. Conegliano and Padova are 60&nbsp;km apart and move in opposite directions.",
    "stationarity.full": "1996–2024",
    "stationarity.recent": "2016–2024",
    "stationarity.change": "change",
    "stationarity.decomposition":
      "Decomposed by intensity, two separate things are happening. Everywhere, the heaviest " +
      "days become more frequent and rain arrives in larger portions. Only in the foothills " +
      "does the number of light rain days collapse. Training on the full record would have " +
      "tuned the model to a climate that no longer exists there.",
    "stationarity.threshold": "at least",
    "stationarity.caveat":
      "Honest caveat: a shift this sharp between neighbouring grid cells deserves caution. " +
      "Part of it may be how the reanalysis resolves that particular cell rather than the " +
      "atmosphere above it. The two cannot be separated from one reanalysis — and the " +
      "decision does not depend on separating them.",

    "physics.heading": "Nobody told it about weather",
    "physics.intro":
      "The model is least squares on a sigmoid. No physical rule was imposed anywhere. " +
      "These are the standardised coefficients it arrived at, ordered by weight:",
    "physics.feature": "predictor",
    "physics.punchline":
      "Pressure comes out strongest and negative — low pressure, unsettled weather. Falling " +
      "pressure means a front is on its way. Cloud today means rain tomorrow. And the " +
      "easterly wind term is positive in all five towns: moisture drawn off the Adriatic. " +
      "None of that was put in by hand.",
    "physics.gradient":
      "The weights also shift along the gradient: pressure and cloud carry steadily more " +
      "of the load from the foothills to the lagoon. Inland, rain that forms over the hills " +
      "adds variance the synoptic picture cannot explain; on the coast it is more purely " +
      "synoptic, so those predictors matter more.",

    "limits.heading": "What this is not",
    "limits.intro":
      "The comparison with Open-Meteo is not a contest, and it is not one this model can " +
      "win. Behind their forecast is numerical weather prediction: atmospheric physics on " +
      "supercomputers, global data assimilation, ensembles. A statistical model reading " +
      "yesterday's observations at one point cannot see a front that has not arrived yet. " +
      "The interesting question is how much skill is recoverable without any of that.",
    "limits.list": [
      "One grid point per town, not a spatial field. At the scale of a town that is a choice, not an oversight.",
      "Consecutive days are far from independent, so the effective sample size is much smaller than the number of rows, and the confidence intervals are wider than they look.",
      "Gradient boosting scores slightly better at four of the five towns. The linear model ships anyway, because it is 17 numbers that run in your browser and its coefficients are the finding above.",
      "The model is trained on reanalysis and served from reanalysis, which removes the product mismatch — but the most recent days of the archive are preliminary, and that residual difference is not yet quantified."
    ],

    "check.running": "verifying the model in your browser…",
    "check.ok":
      "✓ This page recomputed all {m} models from their {n} coefficients each and " +
      "reproduced the Python training output exactly, on {v} reference cases.",
    "check.fail": "✗ The browser model does not match the training output: {err}",
    "footer.repo": "Source and data",
    "footer.report": "Full verification report",
    "footer.method": "Method notes"
  },

  it: {
    "lang.other": "English",
    "site.title": "Domani piove?",
    "site.tagline":
      "Un modello statistico da 17 coefficienti che prevede cinque città venete, " +
      "pubblicato ogni sera e verificato contro quello che è successo davvero.",
    "site.dataNote":
      "Dati meteo Open-Meteo (CC BY 4.0), rianalisi ERA5 del Copernicus Climate " +
      "Change Service presso ECMWF.",

    "live.section": "Le previsioni in corso",
    "live.heading.tomorrow": "Domani",
    "live.heading.today": "Oggi",
    "live.heading.past": "In attesa di verifica",
    "live.issued": "emessa il",
    "live.cadence":
      "Il modello prevede un giorno avanti a partire dall'ultimo giorno completo di " +
      "osservazioni, quindi una previsione nuova può nascere solo quando un giorno è " +
      "finito. Gira ogni sera verso le 23:00, ed è lì che compare domani. Quella di oggi " +
      "resta in pagina finché il giorno non è concluso e si può valutarla.",
    "live.threshold": "di almeno 1&nbsp;mm",
    "live.vsNormal": "{ratio} volte la norma di {month}, che è {clim}",
    "live.atNormal": "in linea con la norma di {month}, che è {clim}",
    "live.ladder": "quanta",
    "live.atLeast": "almeno",
    "live.notShipped": "non pubblicata qui — vedi sotto",
    "live.openmeteo": "Open-Meteo prevede",
    "live.stale":
      "⚠ Queste previsioni hanno più di due giorni. Il processo quotidiano potrebbe essersi fermato.",
    "live.empty": "Nessuna previsione ancora pubblicata.",
    "live.omNote":
      "Il numero di Open-Meteo è la loro aggregazione giornaliera, ma risponde a una " +
      "domanda diversa: la probabilità che piova in <em>qualche ora</em>, che capita più " +
      "spesso di un millimetro sull'intera giornata. Il confronto alla pari è la loro " +
      "previsione deterministica, misurata sulla stessa regola di 1&nbsp;mm.",

    "record.heading": "Il registro pubblico",
    "record.intro":
      "Ogni previsione viene committata su git prima del giorno che prevede. Non si può " +
      "tarare un modello su dati che ancora non esistono — ed è l'unica cosa che un " +
      "backtest non potrà mai dimostrare.",
    "record.issued": "emesse",
    "record.verified": "verificate",
    "record.correct": "azzeccate",
    "record.wrong": "sbagliate",
    "record.brier": "Brier score",
    "record.bss": "skill sulla climatologia",
    "record.waiting":
      "Il registro parte vuoto e si riempie una sera alla volta. I numeri di testa qui " +
      "sotto vengono invece da 588 giorni mai visti dal modello.",
    "record.thin":
      "Finora solo {n} previsioni verificate. Sotto la trentina lo skill score è ancora " +
      "in gran parte rumore — è mostrato lo stesso, con accanto la numerosità.",
    "record.accuracyTrap":
      "Il conteggio delle previsioni azzeccate è il numero facile da leggere, e da solo " +
      "inganna: su un evento così raro, “non piove mai” avrebbe già ragione circa il " +
      "{pct} delle volte. Per questo accanto c'è il Brier skill score.",

    "baseline.heading": "Cosa vuol dire essere bravi",
    "baseline.intro":
      "Una previsione vale solo quello che aggiunge alle alternative ovvie, quindi le " +
      "baseline sono state costruite per prime. Skill score sulla climatologia, su 588 " +
      "giorni mai visti:",
    "baseline.constant climatology": "climatologia",
    "baseline.monthly climatology": "climatologia mensile",
    "baseline.raw persistence (0/1)": "persistenza, come sì/no",
    "baseline.calibrated persistence": "persistenza, come probabilità",
    "baseline.logistic regression": "questo modello",
    "baseline.gradient boosting": "gradient boosting",
    "baseline.punchline":
      "La barra che punta dalla parte sbagliata è il risultato. “Domani come oggi” è il " +
      "predittore singolo più forte che esista — ma espresso come un sì o un no secco " +
      "vale <strong>meno che non dire niente</strong>. La stessa identica informazione, " +
      "espressa come probabilità calibrata, diventa skill vero. Avere il predittore " +
      "giusto non basta: bisogna esprimerlo come probabilità.",

    "cut.heading": "Perché qui non trovi un sì o un no",
    "cut.intro":
      "Viene voglia di trasformare il numero in un verdetto tagliando al 50%. Su un " +
      "evento che capita circa il 30% delle volte, quello è il punto sbagliato dove " +
      "tagliare — ed è così che una previsione giusta viene giudicata sbagliata.",
    "cut.table":
      "Lo stesso modello, sugli stessi 588 giorni, giudicato con tagli diversi:",
    "cut.threshold": "taglio",
    "cut.pod": "piogge intercettate",
    "cut.far": "falsi allarmi",
    "cut.csi": "complessivo",
    "cut.punchline":
      "Al 50% il modello intercetta meno della metà dei giorni di pioggia. Al 30% ne " +
      "prende tre quarti, ed è lì che il punteggio complessivo ha il massimo. Quale " +
      "taglio sia quello giusto dipende da quanto ti costa una pioggia non vista " +
      "rispetto a un allarme a vuoto — quindi la pagina mostra la probabilità e " +
      "lascia la scelta a chi la deve fare.",
    "reliability.heading": "Il 70% è davvero il 70%?",
    "reliability.intro":
      "Una probabilità è onesta solo se si verifica. Ogni punto confronta quello che il " +
      "modello ha detto con quante volte è poi piovuto; la diagonale è l'onestà perfetta.",
    "reliability.predicted": "previsto",
    "reliability.observed": "osservato",
    "reliability.perfect": "affidabilità perfetta",
    "reliability.samples": "previsioni",

    "stationarity.heading": "Perché il modello usa 8 anni e non 29",
    "stationarity.intro":
      "Il piano era usare tutta la serie dal 1996. I dati si sono rifiutati. La frequenza " +
      "dei giorni piovosi resta stabile per vent'anni e poi crolla — ma solo in " +
      "pedemontana. Conegliano e Padova distano 60&nbsp;km e vanno in direzioni opposte.",
    "stationarity.full": "1996–2024",
    "stationarity.recent": "2016–2024",
    "stationarity.change": "variazione",
    "stationarity.decomposition":
      "Scomposto per intensità, stanno succedendo due cose distinte. Ovunque i giorni più " +
      "intensi diventano più frequenti e la pioggia arriva in porzioni più grandi. Solo in " +
      "pedemontana crolla il numero di giorni di pioggia debole. Addestrare sulla serie " +
      "intera avrebbe tarato il modello su un clima che lì non esiste più.",
    "stationarity.threshold": "almeno",
    "stationarity.caveat":
      "Cautela dovuta: uno scarto così netto fra celle di griglia vicine merita prudenza. " +
      "Una parte potrebbe dipendere da come la rianalisi risolve quella cella specifica, " +
      "più che dall'atmosfera sopra di essa. Le due cose non si separano con una sola " +
      "rianalisi — e la decisione non dipende dal separarle.",

    "physics.heading": "Nessuno gli ha spiegato la meteorologia",
    "physics.intro":
      "Il modello è una sigmoide con minimi quadrati. Nessuna regola fisica è stata " +
      "imposta da nessuna parte. Questi sono i coefficienti standardizzati a cui è " +
      "arrivato, in ordine di peso:",
    "physics.feature": "predittore",
    "physics.punchline":
      "La pressione esce come coefficiente più forte, col segno negativo — bassa pressione, " +
      "tempo perturbato. Pressione in calo significa fronte in arrivo. Nuvole oggi " +
      "significano pioggia domani. E il termine del vento da est è positivo in tutte e " +
      "cinque le città: umidità richiamata dall'Adriatico. Niente di tutto questo è stato " +
      "messo a mano.",
    "physics.gradient":
      "I pesi si spostano anche lungo il gradiente: pressione e nuvolosità contano sempre " +
      "di più andando dalla pedemontana alla laguna. All'interno, la pioggia che si forma " +
      "sui rilievi aggiunge variabilità che il quadro sinottico non spiega; sulla costa è " +
      "più puramente sinottica, e quei predittori pesano di più.",

    "limits.heading": "Cosa questo non è",
    "limits.intro":
      "Il confronto con Open-Meteo non è una gara, e non è una gara che questo modello " +
      "possa vincere. Dietro la loro previsione c'è la previsione numerica: fisica " +
      "dell'atmosfera su supercomputer, assimilazione globale di dati, ensemble. Un " +
      "modello statistico che legge le osservazioni di ieri in un punto non può vedere un " +
      "fronte che non è ancora arrivato. La domanda interessante è quanto skill si riesca " +
      "a recuperare senza niente di tutto ciò.",
    "limits.list": [
      "Un punto di griglia per città, non un campo spaziale. A scala di paese è una scelta, non una dimenticanza.",
      "I giorni consecutivi sono tutt'altro che indipendenti, quindi la numerosità effettiva è molto minore del numero di righe e gli intervalli di confidenza sono più larghi di quanto sembrino.",
      "Il gradient boosting va leggermente meglio in quattro città su cinque. Il modello lineare viene spedito lo stesso, perché sono 17 numeri che girano nel tuo browser e i suoi coefficienti sono il risultato raccontato qui sopra.",
      "Il modello è addestrato su rianalisi e servito da rianalisi, il che elimina il disallineamento fra prodotti — ma i giorni più recenti dell'archivio sono preliminari, e quella differenza residua non è ancora quantificata."
    ],

    "check.running": "verifica del modello nel tuo browser…",
    "check.ok":
      "✓ Questa pagina ha ricalcolato tutti i {m} modelli dai loro {n} coefficienti " +
      "ciascuno, riproducendo esattamente l'uscita del training Python su {v} casi di " +
      "riferimento.",
    "check.fail": "✗ Il modello nel browser non coincide con l'uscita del training: {err}",
    "footer.repo": "Codice e dati",
    "footer.report": "Report di verifica completo",
    "footer.method": "Note di metodo"
  }
};

const STORAGE_KEY = "rain-tomorrow-lang";

export function initialLanguage() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === "it" || saved === "en") return saved;
  return (navigator.language || "en").toLowerCase().startsWith("it") ? "it" : "en";
}

export function rememberLanguage(lang) {
  localStorage.setItem(STORAGE_KEY, lang);
}

export function translator(lang) {
  const table = STRINGS[lang] || STRINGS.en;
  return (key, values = {}) => {
    let text = table[key];
    if (text === undefined) return key;
    if (typeof text === "string") {
      for (const [name, value] of Object.entries(values)) {
        text = text.replaceAll(`{${name}}`, value);
      }
    }
    return text;
  };
}
