# Bozza del post LinkedIn

> Da rifinire insieme. In italiano, perché il pubblico è quello; il repository resta in inglese.
>
> Regola di scrittura seguita: **l'apertura è il risultato, non il progetto.** Nessuno si ferma su
> "ho costruito un modello di previsione". Ci si ferma su un fatto controintuitivo che si capisce in
> due righe.

---

## Versione lunga

> Il miglior predittore della pioggia di domani è la pioggia di oggi.
>
> Espresso come sì/no ottiene uno skill score **negativo**: fa peggio di chi dice la stessa cosa
> tutti i giorni dell'anno.
>
> La stessa identica informazione, espressa come **probabilità calibrata**, diventa skill vero. Fra
> le due versioni ci sono 0,4 punti di Brier Skill Score, e in mezzo non c'è nessun dato in più:
> solo il modo di esprimere la stessa cosa.
>
> È il risultato che mi ha convinto a trasformare un esercizio in un progetto pubblico.
>
> Ho addestrato una regressione logistica a prevedere la pioggia del giorno dopo per cinque città
> venete — Bassano, Conegliano, Vicenza, Padova, Venezia — su dati di rianalisi ERA5. Diciassette
> coefficienti, nove kilobyte, nessuna rete neurale.
>
> Tre cose che mi porto dietro più del modello:
>
> **1. I dati hanno rifiutato la finestra di addestramento che avevo scelto.** Volevo usare tutta la
> serie dal 1996. La frequenza di giorni piovosi però è stabile per vent'anni e poi crolla — ma solo
> in pedemontana. Conegliano perde 10 punti, Padova ne guadagna 1, e distano 60 km. Scomponendo per
> intensità si vede che sono due fenomeni distinti: ovunque i giorni più intensi aumentano, ma solo
> sui rilievi spariscono le piogge deboli. Con una sola località avrei concluso "la serie non è
> stazionaria". Con cinque, la conclusione è molto più specifica.
>
> **2. Il modello ha mancato una soglia che avevo fissato per iscritto prima di misurare.** Non ho
> spostato la soglia. Mancava la fisica: nessuna variabile di pressione. Aggiunte pressione,
> tendenza barica, direzione del vento e nuvolosità, lo skill è salito in modo coerente sia in
> validazione sia in test.
>
> **3. Nessuno ha spiegato la meteorologia al modello, e l'ha ritrovata da solo.** Il coefficiente
> più forte è la pressione, col segno negativo. La pressione in calo pesa negativamente: fronte in
> arrivo. La nuvolosità di oggi pesa positivamente. E il vento da est è positivo in tutte e cinque
> le città — umidità richiamata dall'Adriatico. Niente di questo è stato messo a mano.
>
> **La parte che mi interessava di più, però, è un'altra.**
>
> Una dashboard di backtest, per quanto rigorosa, non può chiudere una domanda: *"come so che non
> hai tarato sul test set?"*.
>
> Così ogni sera una GitHub Action pubblica la previsione del giorno dopo per le cinque città e la
> committa su git — **prima** che il giorno esista. Il giorno dopo la stessa Action ci scrive
> accanto quello che è successo davvero. Non si può tarare un modello su dati che non esistono
> ancora, e il log di git dimostra l'ordine.
>
> Accanto alla mia previsione registro anche quella di Open-Meteo, che gira su previsione numerica
> vera. **Su questo perderò**, ed è scritto nel README dal primo commit: un modello statistico che
> legge le osservazioni di ieri in un punto non può vedere un fronte che non è ancora arrivato. La
> domanda interessante non è chi vince, ma quanto skill si recuperi senza fisica e senza
> supercomputer.
>
> La pagina è statica, gira interamente nel browser e si autoverifica: al caricamento ricalcola il
> modello dai suoi coefficienti e controlla di riprodurre esattamente l'uscita del training Python.
>
> 🔗 [pagina] · [repository]
>
> Dati Open-Meteo (CC BY 4.0), rianalisi ERA5 del Copernicus Climate Change Service presso ECMWF.

---

## Versione corta, se la lunga sembra troppo

> Il miglior predittore della pioggia di domani è la pioggia di oggi.
>
> Espresso come sì/no ottiene uno skill score **negativo** — fa peggio di chi ripete la stessa cosa
> ogni giorno dell'anno. La stessa informazione, espressa come probabilità calibrata, diventa skill
> vero. Zero dati in più: solo il modo di esprimerla.
>
> Ci ho costruito sopra un progetto pubblico. Una regressione logistica da 17 coefficienti prevede
> la pioggia del giorno dopo per cinque città venete, e ogni sera una GitHub Action pubblica la
> previsione **prima** del giorno che prevede, poi ci scrive accanto com'è andata.
>
> Non si può tarare un modello su dati che non esistono ancora — ed è l'unica cosa che un backtest
> non potrà mai dimostrare.
>
> Accanto c'è anche la previsione di Open-Meteo, che gira su modelli numerici veri. Su quella
> perderò, ed è scritto nel README dal primo commit.
>
> 🔗 [pagina] · [repository]

---

## Note per la pubblicazione

- **Sostituire `[pagina]` e `[repository]`** con i link veri dopo aver attivato GitHub Pages.
- **Prima immagine**: il grafico delle baseline, quello con la barra della persistenza secca che
  punta dalla parte sbagliata. È l'unica immagine che spiega il gancio senza didascalia.
- **Non promettere accuratezza.** Il progetto è interessante per il metodo e per il registro
  pubblico, non perché prevede bene. Se il post promette precisione, il primo giorno sbagliato lo
  smentisce; se promette onestà, ogni giorno sbagliato lo conferma.
- **Aspettarsi la domanda "e contro ARPAV / 3B Meteo?"**. La risposta onesta è quella già nel
  README: non è una gara, ed è già registrata contro un riferimento operativo ogni sera.
- **Secondo post fra 60 giorni**, sui risultati accumulati, quando il registro avrà abbastanza
  campioni da dire qualcosa. È lì che il progetto diventa raro: quasi nessuno torna a pubblicare i
  numeri dopo.
