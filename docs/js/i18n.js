// Every string on the page, in both languages.
//
// House style, checked by scripts/check_prose.py: no em dash as a rhetorical
// pause, no paragraph closing with a moral, headings are labels rather than
// lessons, impersonal constructions, numbers before adjectives.
export const STRINGS = {
  en: {
    "lang.other": "Italiano",
    "site.title": "Will it rain tomorrow?",
    "site.tagline":
      "Rain forecast for five towns in the Veneto. 25 coefficients, four intensity " +
      "thresholds, published every evening and scored against what was observed.",
    "site.dataNote":
      "Weather data from Open-Meteo (CC BY 4.0), ERA5 reanalysis of the Copernicus " +
      "Climate Change Service at ECMWF.",

    "live.section": "Current forecasts",
    "live.heading.tomorrow": "Tomorrow",
    "live.heading.today": "Today",
    "live.heading.past": "Awaiting verification",
    "live.issued": "issued",
    "live.cadence":
      "The model looks one day ahead from the last complete day of observations, so a " +
      "new forecast exists only once a day has ended. The job runs every evening around " +
      "23:00 Italian time. Today's forecast stays up until the day is over and can be " +
      "scored.",
    "live.threshold": "of at least 1&nbsp;mm",
    "live.vsNormal": "{ratio}× the {month} normal of {clim}",
    "live.atNormal": "about the {month} normal of {clim}",
    "live.ladder": "how much",
    "live.atLeast": "at least",
    "live.notShipped": "not published",
    "live.notShippedWhy":
      "A missing row means that threshold failed its acceptance test during training and " +
      "is not published for that town. At 20&nbsp;mm there are 106 to 165 events in nine " +
      "years of training data, which is too few at Vicenza and Padova.",
    "live.openmeteo": "Open-Meteo forecasts",
    "live.stale":
      "⚠ These forecasts are more than two days old. The daily job may have stopped.",
    "live.empty": "No forecasts published yet.",
    "live.omNote":
      "The Open-Meteo figure is their own daily aggregate. It answers a different " +
      "question: the chance of rain at <em>some hour</em>, which happens more often than " +
      "a full millimetre across the whole day. Their deterministic forecast, held to the " +
      "same 1&nbsp;mm rule, is the like-for-like comparison.",

    "record.heading": "The record",
    "record.intro":
      "Every evening a GitHub Action commits the next day's forecast. The commit is " +
      "dated, so anyone can check the forecast existed before the outcome. A backtest " +
      "cannot show that.",
    "record.issued": "issued",
    "record.verified": "verified",
    "record.correct": "correct",
    "record.wrong": "wrong",
    "record.brier": "Brier score",
    "record.bss": "skill vs climatology",
    "record.them": "Open-Meteo, same days",
    "record.rained": "of those days rained",
    "record.pending": "nothing scored yet",
    "record.modelNote":
      "Scores are kept separate per model version. The record spans a model change, and " +
      "averaging two models into one number would hide what the record is for.",
    "record.waiting":
      "The record starts empty and fills one evening at a time. The figures below come " +
      "from 589 held-out days instead.",
    "record.thin":
      "{n} verified forecasts. Below about 30 the skill score is mostly noise. It is " +
      "shown anyway, with the sample size next to it.",
    "record.accuracyTrap":
      "The count of correct calls is the easy number to read and it misleads on its own. " +
      "On an event this rare, “it never rains” would already be right about {pct} of the " +
      "time.",

    "baseline.heading": "Baselines",
    "baseline.intro":
      "The obvious alternatives were measured before the model. Skill score against " +
      "climatology, on 589 held-out days:",
    "baseline.constant climatology": "climatology",
    "baseline.monthly climatology": "monthly climatology",
    "baseline.raw persistence (0/1)": "persistence, as yes/no",
    "baseline.calibrated persistence": "persistence, as a probability",
    "baseline.logistic regression": "this model",
    "baseline.gradient boosting": "gradient boosting",
    "baseline.punchline":
      "The bar pointing the wrong way is worth a second look. “Tomorrow like today” is " +
      "the strongest single predictor available. Stated as a flat yes or no it scores " +
      "between −0.21 and −0.39, worse than saying the same thing every day. The identical " +
      "information, expressed as a calibrated probability, scores +0.09 to +0.15.",

    "cut.heading": "The cut-off",
    "cut.intro":
      "Turning the number into a verdict at 50% is tempting. On an event that happens " +
      "about 30% of the time, 50% is the wrong place to cut.",
    "cut.table": "The same model, on the same 589 days, judged at different cut-offs:",
    "cut.threshold": "cut-off",
    "cut.pod": "rain days caught",
    "cut.far": "false alarms",
    "cut.csi": "overall",
    "cut.punchline":
      "At 50% the model catches about half the rainy days. At 30% it catches three " +
      "quarters, at the cost of more false alarms. Which cut-off is right depends on what " +
      "a miss costs compared to a false alarm, so the page shows the probability and " +
      "leaves the choice open.",

    "reliability.heading": "Reliability",
    "reliability.intro":
      "A probability is only useful if it verifies. Each point compares what the model " +
      "said against how often it then rained. The diagonal is perfect reliability.",
    "reliability.predicted": "forecast",
    "reliability.observed": "observed",
    "reliability.perfect": "perfectly reliable",
    "reliability.samples": "forecasts",

    "wrong.heading": "When it fails",
    "wrong.intro":
      "The forecast correlates 0.68 with the rain that has already fallen and 0.51 with " +
      "the rain being predicted. It tracks today more closely than tomorrow.",
    "wrong.table":
      "Splitting the test set by whether the weather changed makes the consequence " +
      "concrete. A day is a transition when tomorrow differs from today: rain starting, " +
      "or rain stopping.",
    "wrong.kind": "day",
    "wrong.persist": "weather unchanged",
    "wrong.change": "weather changed",
    "wrong.share": "share of days",
    "wrong.punchline":
      "Transitions are 28% of days. On them the Brier score is about four times worse " +
      "than on days that stay put, and the skill score against climatology is −0.27. On " +
      "the days when the weather actually changes, the seasonal average does better than " +
      "this model.",
    "wrong.fair":
      "Calibrated persistence scores 0.470 on those same days against the model's 0.366, " +
      "so the model recovers 0.104 of Brier that pure persistence loses. It carries real " +
      "information about change, and not enough of it. The headline skill of about +0.26 " +
      "comes mostly from being right on the 72% of days when nothing changes.",

    "stationarity.heading": "The training window",
    "stationarity.intro":
      "The plan was to use the whole record back to 1996. Wet-day frequency is steady for " +
      "two decades and then falls away, but only in the foothills. Conegliano and Padova " +
      "are 60&nbsp;km apart and move in opposite directions.",
    "stationarity.full": "1996–2024",
    "stationarity.recent": "2016–2024",
    "stationarity.change": "change",
    "stationarity.decomposition":
      "Decomposed by intensity, two things are happening at once. Everywhere the heaviest " +
      "days become more frequent and rain arrives in larger portions. Only in the " +
      "foothills does the count of light rain days collapse. Training on the full record " +
      "would tune the model to a climate that no longer exists there.",
    "stationarity.threshold": "at least",
    "stationarity.caveat":
      "A shift this sharp between neighbouring grid cells deserves caution. Part of it " +
      "may be how the reanalysis resolves that particular cell rather than the atmosphere " +
      "above it. One reanalysis cannot separate the two, and the decision does not need " +
      "them separated.",

    "physics.heading": "Coefficients",
    "physics.intro":
      "The model is least squares on a sigmoid and no physical rule was imposed. These " +
      "are the standardised coefficients it arrived at, ordered by weight:",
    "physics.feature": "predictor",
    "physics.punchline":
      "Pressure comes out strongest and negative: low pressure, unsettled weather. The " +
      "pressure at 18:00 minus the pressure at 06:00 is second, also negative, so a fall " +
      "within the day matters more than the difference between two daily means. Cloud " +
      "today is positive. The easterly wind term is positive in all five towns, which is " +
      "moisture drawn off the Adriatic.",
    "physics.gradient":
      "The weights shift along the gradient: pressure and cloud carry more of the load " +
      "from the foothills to the lagoon. Inland, rain forming over the hills adds " +
      "variance the synoptic picture does not explain. On the coast the rain is more " +
      "purely synoptic.",

    "limits.heading": "Limitations",
    "limits.intro":
      "The comparison with Open-Meteo is a reference, not a contest, and not one this " +
      "model can win. Behind their forecast is numerical weather prediction: atmospheric " +
      "physics on supercomputers, global data assimilation, ensembles. A statistical " +
      "model reading yesterday's observations at one point cannot see a front that has " +
      "not arrived. The question worth asking is how much skill is recoverable without " +
      "any of that.",
    "limits.list": [
      "One grid point per town, not a spatial field. At the scale of a town that is a deliberate choice.",
      "Consecutive days are far from independent, so the effective sample size is much smaller than the row count and the confidence intervals are wider than they look.",
      "The 20 mm threshold is not published at Vicenza or Padova. It fires on 3 to 5% of days and failed its acceptance test there.",
      "Gradient boosting scores slightly better at four of the five towns. The linear model ships because it is 25 numbers per threshold that run in a browser, and because its coefficients can be read.",
      "The intra-day predictors raised resolution by about a quarter and cost some reliability, from 0.003 to 0.006. The net is positive and it is a trade.",
      "Training and serving both use the reanalysis, which removes the product mismatch, but the most recent days of the archive are preliminary and that difference is not quantified."
    ],

    "check.running": "verifying the models in your browser…",
    "check.ok":
      "✓ This page recomputed all {m} models from their {n} coefficients each and " +
      "reproduced the Python training output exactly, on {v} reference cases.",
    "check.fail": "✗ The browser models do not match the training output: {err}",
    "footer.repo": "Source and data",
    "footer.report": "Verification report",
    "footer.method": "Method notes"
  },

  it: {
    "lang.other": "English",
    "site.title": "Domani piove?",
    "site.tagline":
      "Previsione di pioggia per cinque città venete. 25 coefficienti, quattro soglie di " +
      "intensità, pubblicata ogni sera e verificata contro l'osservato.",
    "site.dataNote":
      "Dati meteo Open-Meteo (CC BY 4.0), rianalisi ERA5 del Copernicus Climate Change " +
      "Service presso ECMWF.",

    "live.section": "Previsioni in corso",
    "live.heading.tomorrow": "Domani",
    "live.heading.today": "Oggi",
    "live.heading.past": "In attesa di verifica",
    "live.issued": "emessa il",
    "live.cadence":
      "Il modello guarda un giorno avanti a partire dall'ultimo giorno completo di " +
      "osservazioni, quindi una previsione nuova esiste solo quando un giorno è finito. " +
      "Il processo gira ogni sera verso le 23:00. La previsione di oggi resta in pagina " +
      "finché il giorno non è concluso e si può valutare.",
    "live.threshold": "di almeno 1&nbsp;mm",
    "live.vsNormal": "{ratio} volte la norma di {month}, che è {clim}",
    "live.atNormal": "in linea con la norma di {month}, che è {clim}",
    "live.ladder": "quanta",
    "live.atLeast": "almeno",
    "live.notShipped": "non pubblicata",
    "live.notShippedWhy":
      "Dove manca una riga, quella soglia non ha superato il test di accettazione in " +
      "addestramento e non viene pubblicata per quella città. A 20&nbsp;mm ci sono da 106 " +
      "a 165 eventi in nove anni di dati, troppo pochi a Vicenza e Padova.",
    "live.openmeteo": "Open-Meteo prevede",
    "live.stale":
      "⚠ Queste previsioni hanno più di due giorni. Il processo quotidiano potrebbe " +
      "essersi fermato.",
    "live.empty": "Nessuna previsione ancora pubblicata.",
    "live.omNote":
      "Il numero di Open-Meteo è la loro aggregazione giornaliera. Risponde a una domanda " +
      "diversa: la probabilità che piova in <em>qualche ora</em>, che capita più spesso " +
      "di un millimetro sull'intera giornata. Il confronto alla pari è la loro previsione " +
      "deterministica, misurata sulla stessa regola di 1&nbsp;mm.",

    "record.heading": "Il registro",
    "record.intro":
      "Ogni sera una GitHub Action committa la previsione del giorno dopo. Il commit è " +
      "datato: la previsione esiste prima dell'esito e chiunque può controllarlo. Un " +
      "backtest non lo consente.",
    "record.issued": "emesse",
    "record.verified": "verificate",
    "record.correct": "azzeccate",
    "record.wrong": "sbagliate",
    "record.brier": "Brier score",
    "record.bss": "skill sulla climatologia",
    "record.them": "Open-Meteo, stessi giorni",
    "record.rained": "di quei giorni ha piovuto",
    "record.pending": "ancora nessuna valutata",
    "record.modelNote":
      "I punteggi restano separati per versione del modello. Il registro attraversa un " +
      "cambio di modello, e mediare due modelli in un numero solo nasconderebbe proprio " +
      "quello per cui il registro esiste.",
    "record.waiting":
      "Il registro parte vuoto e si riempie una sera alla volta. I numeri qui sotto " +
      "vengono invece da 589 giorni mai visti dal modello.",
    "record.thin":
      "{n} previsioni verificate. Sotto la trentina lo skill score è in gran parte " +
      "rumore. È mostrato lo stesso, con accanto la numerosità.",
    "record.accuracyTrap":
      "Il conteggio delle previsioni azzeccate è il numero facile da leggere e da solo " +
      "inganna. Su un evento così raro, “non piove mai” avrebbe già ragione circa il " +
      "{pct} delle volte.",

    "baseline.heading": "Le baseline",
    "baseline.intro":
      "Le alternative ovvie sono state misurate prima del modello. Skill score sulla " +
      "climatologia, su 589 giorni mai visti:",
    "baseline.constant climatology": "climatologia",
    "baseline.monthly climatology": "climatologia mensile",
    "baseline.raw persistence (0/1)": "persistenza, come sì/no",
    "baseline.calibrated persistence": "persistenza, come probabilità",
    "baseline.logistic regression": "questo modello",
    "baseline.gradient boosting": "gradient boosting",
    "baseline.punchline":
      "La barra che punta dalla parte sbagliata merita una seconda occhiata. “Domani come " +
      "oggi” è il predittore singolo più forte disponibile. Detto come un sì o un no " +
      "secco vale fra −0,21 e −0,39, peggio che ripetere la stessa cosa ogni giorno. La " +
      "stessa informazione, espressa come probabilità calibrata, vale da +0,09 a +0,15.",

    "cut.heading": "La soglia",
    "cut.intro":
      "Viene voglia di trasformare il numero in un verdetto tagliando al 50%. Su un " +
      "evento che capita circa il 30% delle volte, il 50% è il punto sbagliato dove " +
      "tagliare.",
    "cut.table": "Lo stesso modello, sugli stessi 589 giorni, giudicato con tagli diversi:",
    "cut.threshold": "taglio",
    "cut.pod": "piogge intercettate",
    "cut.far": "falsi allarmi",
    "cut.csi": "complessivo",
    "cut.punchline":
      "Al 50% il modello intercetta circa metà dei giorni di pioggia. Al 30% ne prende " +
      "tre quarti, al prezzo di più falsi allarmi. Quale taglio sia quello giusto dipende " +
      "da quanto costa una pioggia non vista rispetto a un allarme a vuoto, quindi la " +
      "pagina mostra la probabilità e lascia la scelta aperta.",

    "reliability.heading": "Affidabilità",
    "reliability.intro":
      "Una probabilità serve solo se si verifica. Ogni punto confronta quello che il " +
      "modello ha detto con quante volte è poi piovuto. La diagonale è l'affidabilità " +
      "perfetta.",
    "reliability.predicted": "previsto",
    "reliability.observed": "osservato",
    "reliability.perfect": "affidabilità perfetta",
    "reliability.samples": "previsioni",

    "wrong.heading": "Quando sbaglia",
    "wrong.intro":
      "La previsione correla 0,68 con la pioggia già caduta e 0,51 con quella da " +
      "prevedere. Segue oggi più di quanto anticipi domani.",
    "wrong.table":
      "Dividere il test set a seconda che il tempo sia cambiato rende la conseguenza " +
      "concreta. Un giorno è di transizione quando domani è diverso da oggi: la pioggia " +
      "che comincia, o che finisce.",
    "wrong.kind": "giorno",
    "wrong.persist": "tempo invariato",
    "wrong.change": "tempo cambiato",
    "wrong.share": "quota dei giorni",
    "wrong.punchline":
      "Le transizioni sono il 28% dei giorni. Lì il Brier è circa quattro volte peggiore " +
      "che nei giorni in cui non cambia niente, e lo skill sulla climatologia è −0,27. " +
      "Nei giorni in cui il tempo cambia davvero, la media stagionale fa meglio di questo " +
      "modello.",
    "wrong.fair":
      "Negli stessi giorni la persistenza calibrata vale 0,470 contro lo 0,366 del " +
      "modello, quindi il modello recupera 0,104 di Brier che la sola persistenza perde. " +
      "Porta informazione vera sul cambiamento, e non abbastanza. Il +0,26 complessivo " +
      "viene soprattutto dall'avere ragione sul 72% di giorni in cui non cambia nulla.",

    "stationarity.heading": "La finestra di addestramento",
    "stationarity.intro":
      "Il piano era usare tutta la serie dal 1996. La frequenza dei giorni piovosi resta " +
      "stabile per vent'anni e poi crolla, ma solo in pedemontana. Conegliano e Padova " +
      "distano 60&nbsp;km e vanno in direzioni opposte.",
    "stationarity.full": "1996–2024",
    "stationarity.recent": "2016–2024",
    "stationarity.change": "variazione",
    "stationarity.decomposition":
      "Scomposto per intensità, stanno succedendo due cose insieme. Ovunque i giorni più " +
      "intensi diventano più frequenti e la pioggia arriva in porzioni più grandi. Solo " +
      "in pedemontana crolla il numero di giorni di pioggia debole. Addestrare sulla " +
      "serie intera tarerebbe il modello su un clima che lì non esiste più.",
    "stationarity.threshold": "almeno",
    "stationarity.caveat":
      "Uno scarto così netto fra celle di griglia vicine richiede prudenza. Una parte " +
      "potrebbe dipendere da come la rianalisi risolve quella cella specifica, più che " +
      "dall'atmosfera sopra di essa. Una sola rianalisi non separa le due cose, e la " +
      "decisione non ha bisogno che siano separate.",

    "physics.heading": "I coefficienti",
    "physics.intro":
      "Il modello è una sigmoide con minimi quadrati e nessuna regola fisica è stata " +
      "imposta. Questi sono i coefficienti standardizzati a cui è arrivato, in ordine di " +
      "peso:",
    "physics.feature": "predittore",
    "physics.punchline":
      "La pressione esce come coefficiente più forte, col segno negativo: bassa " +
      "pressione, tempo perturbato. La pressione delle 18 meno quella delle 6 è seconda, " +
      "anch'essa negativa, quindi una caduta dentro la giornata conta più della " +
      "differenza fra due medie giornaliere. La nuvolosità di oggi è positiva. Il termine " +
      "del vento da est è positivo in tutte e cinque le città, ed è umidità richiamata " +
      "dall'Adriatico.",
    "physics.gradient":
      "I pesi si spostano lungo il gradiente: pressione e nuvolosità contano di più " +
      "andando dalla pedemontana alla laguna. All'interno, la pioggia che si forma sui " +
      "rilievi aggiunge variabilità che il quadro sinottico non spiega. Sulla costa è più " +
      "puramente sinottica.",

    "limits.heading": "Limiti",
    "limits.intro":
      "Il confronto con Open-Meteo è un riferimento, non una gara, e non è una gara che " +
      "questo modello possa vincere. Dietro la loro previsione c'è la previsione " +
      "numerica: fisica dell'atmosfera su supercomputer, assimilazione globale di dati, " +
      "ensemble. Un modello statistico che legge le osservazioni di ieri in un punto non " +
      "può vedere un fronte che non è ancora arrivato. La domanda che vale la pena porsi " +
      "è quanto skill si recuperi senza niente di tutto ciò.",
    "limits.list": [
      "Un punto di griglia per città, non un campo spaziale. A scala di paese è una scelta deliberata.",
      "I giorni consecutivi sono tutt'altro che indipendenti, quindi la numerosità effettiva è molto minore del numero di righe e gli intervalli di confidenza sono più larghi di quanto sembrino.",
      "La soglia da 20 mm non è pubblicata a Vicenza e Padova. Scatta sul 3-5% dei giorni e lì non ha superato il test di accettazione.",
      "Il gradient boosting va leggermente meglio in quattro città su cinque. Il modello lineare viene spedito perché sono 25 numeri per soglia che girano nel browser, e perché i suoi coefficienti si leggono.",
      "I predittori infragiornalieri hanno alzato la risoluzione di circa un quarto e sono costati un po' di affidabilità, da 0,003 a 0,006. Il saldo è positivo ed è uno scambio.",
      "Addestramento e servizio usano entrambi la rianalisi, il che elimina il disallineamento fra prodotti, ma i giorni più recenti dell'archivio sono preliminari e quella differenza non è quantificata."
    ],

    "check.running": "verifica dei modelli nel tuo browser…",
    "check.ok":
      "✓ Questa pagina ha ricalcolato tutti i {m} modelli dai loro {n} coefficienti " +
      "ciascuno, riproducendo esattamente l'uscita del training Python su {v} casi di " +
      "riferimento.",
    "check.fail": "✗ I modelli nel browser non coincidono con l'uscita del training: {err}",
    "footer.repo": "Codice e dati",
    "footer.report": "Report di verifica",
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
