# Bozza del post LinkedIn

> In italiano, perché il pubblico è quello. Il repository resta in inglese.
>
> Prima persona qui, a differenza della pagina: un post social scritto in forma impersonale suona
> falso. Resta però la stessa regola sul resto, niente massime finali e nessun numero che non venga
> dai dati.
>
> Apre il risultato, non il progetto. Nessuno si ferma su "ho costruito un modello di previsione".

---

## Versione lunga

> Il miglior predittore della pioggia di domani è la pioggia di oggi.
>
> Detto come sì o no, ottiene uno skill score **negativo**: fa peggio di chi ripete la stessa cosa
> tutti i giorni dell'anno. La stessa identica informazione, espressa come probabilità calibrata,
> diventa skill vero. Fra le due versioni ci sono circa 0,4 punti di Brier Skill Score, e in mezzo
> non c'è nessun dato in più.
>
> Da lì è nato un progetto pubblico. Una regressione logistica prevede la pioggia del giorno dopo per
> cinque città venete, con quattro soglie di intensità: 25 coefficienti per soglia, venti modelli in
> tutto, nove kilobyte l'uno. Girano nel browser di chi apre la pagina, che li ricalcola e verifica
> di riprodurre esattamente l'uscita del training.
>
> Tre cose che mi porto dietro più del modello.
>
> **1. I dati hanno rifiutato la finestra di addestramento che avevo scelto.** Volevo usare tutta la
> serie dal 1996. La frequenza dei giorni piovosi è però stabile per vent'anni e poi crolla, ma solo
> in pedemontana: Conegliano perde 10 punti, Padova ne guadagna 1, e distano 60 km. Scomponendo per
> intensità si vede che sono due fenomeni distinti. Con una sola località avrei concluso "la serie
> non è stazionaria". Con cinque, la conclusione è molto più precisa.
>
> **2. Conta la forma della giornata, non la giornata.** Ogni variabile era una media giornaliera, e
> una media non distingue "coperto tutto il giorno" da "schiarita, poi si copre". Ho aggiunto otto
> predittori ricavati dai dati orari: lo skill è salito in tutte e cinque le città, +0,05 in media.
> Il più forte è la pressione delle 18 meno quella delle 6, secondo solo alla pressione stessa.
>
> **3. Ho scoperto che il modello insegue ieri invece di anticipare domani.** Correla 0,68 con la
> pioggia già caduta e 0,51 con quella da prevedere. Diviso fra giorni in cui il tempo resta com'è e
> giorni in cui cambia, il Brier passa da 0,076 a 0,366. Sul 28% di giorni in cui il tempo cambia
> davvero, la media stagionale fa meglio del mio modello.
>
> Quel terzo punto è sulla pagina, in una sezione intitolata "Quando sbaglia".
>
> **La parte che mi interessava di più è però un'altra.**
>
> Un backtest, per quanto rigoroso, non chiude la domanda: come so che non hai tarato sul test set?
>
> Così ogni sera una GitHub Action pubblica la previsione del giorno dopo e la committa su git,
> prima che il giorno esista. Il giorno dopo la stessa Action ci scrive accanto cosa è successo
> davvero. Non si può tarare un modello su dati che non esistono ancora, e il log di git dimostra
> l'ordine.
>
> Nella prima settimana il registro ha fatto esattamente il suo lavoro: ha riprodotto in diretta il
> modo di sbagliare che avevo diagnosticato nel backtest. Ha mancato l'inizio di un evento piovoso,
> ha azzeccato il giorno centrale, ha mancato la fine.
>
> Accanto alla mia previsione registro anche quella di Open-Meteo, che gira su previsione numerica
> vera. Su quella perdo, ed è scritto nel README dal primo commit: un modello statistico che legge le
> osservazioni di ieri in un punto non può vedere un fronte che non è ancora arrivato.
>
> 🔗 [pagina] · [repository]
>
> Dati Open-Meteo (CC BY 4.0), rianalisi ERA5 del Copernicus Climate Change Service presso ECMWF.

---

## Versione corta

> Il miglior predittore della pioggia di domani è la pioggia di oggi.
>
> Detto come sì o no ottiene uno skill score **negativo**, peggio di chi ripete la stessa cosa ogni
> giorno. La stessa informazione, espressa come probabilità calibrata, diventa skill vero. Zero dati
> in più.
>
> Ci ho costruito sopra un progetto pubblico: venti piccoli modelli prevedono pioggia e intensità per
> cinque città venete, e ogni sera una GitHub Action pubblica la previsione **prima** del giorno che
> prevede, poi ci scrive accanto com'è andata.
>
> Nella prima settimana il registro ha già mostrato il limite del modello: insegue ieri invece di
> anticipare domani, e sul 28% di giorni in cui il tempo cambia fa peggio della media stagionale.
> Sta scritto sulla pagina.
>
> 🔗 [pagina] · [repository]

---

## Note per la pubblicazione

- Sostituire `[pagina]` e `[repository]` con i link veri.
- **Prima immagine**: il grafico delle baseline, quello con la barra della persistenza secca che
  punta dalla parte sbagliata. È l'unica immagine che spiega il gancio senza didascalia.
- **Non promettere accuratezza.** Il progetto è interessante per il metodo e per il registro
  pubblico. Se il post promette precisione, il primo giorno sbagliato lo smentisce; se promette
  onestà, ogni giorno sbagliato lo conferma.
- Aspettarsi la domanda "e contro ARPAV o 3B Meteo?". La risposta è già nel README: non è una gara,
  ed è comunque registrata ogni sera contro un riferimento operativo.
- **Secondo post a 60 giorni**, sui numeri accumulati. È lì che il progetto diventa raro: quasi
  nessuno torna a pubblicare i risultati dopo.
