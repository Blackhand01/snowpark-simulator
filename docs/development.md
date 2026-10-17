# Sviluppo e workflow

Eseguire i comandi dalla radice del repository. Python ≥ 3.11; nessuna dipendenza Python aggiuntiva per i workflow host. Blender rimane un eseguibile esterno.

## Configurazioni

| Directory | Contenuto |
| --- | --- |
| `configs/scene/` | `static` e `smoke` per un clone nuovo; `athlete`, `terrain`, `appearance`, `presentation` per gli stadi successivi |
| `configs/motion/` | Salto, rail slide, boardslide, sincronizzazione video e relativi timestamp |
| `configs/capture/` | Posa e acquisizioni boardslide a 8 o 32 camere |
| `configs/conditions/` | Matrice delle variazioni grafiche |
| `configs/tricks/` | Catalogo e profili sperimentali di rotazione |

Le distanze sono in metri, i tempi in secondi; i campi `*_degrees` sono in gradi. Nei profili raffinati Z è verticale e la discesa segue −Y. Le impostazioni complete dipendono dal profilo: non attribuire alla configurazione iniziale le dimensioni dei refinement successivi.

I profili avanzati sono esempi storici collegati a file locali non distribuiti. Prima di costruire una variante: fornire il `.blend`, impostare il percorso relativo al repository e il suo SHA-256, aggiornare eventuali manifest e input video. Non rimuovere il controllo dell'hash per far passare un input diverso.

## Comandi

Il solo punto d'ingresso è `python3 -B -m snowpark_simulator`. I precedenti `run_*.py` sono sostituiti dai comandi seguenti; non sono mantenute copie parallele della stessa implementazione.

```sh
python3 -B -m snowpark_simulator scene --without-reference
python3 -B -m snowpark_simulator motion build --config configs/motion/boardslide-synced.toml
python3 -B -m snowpark_simulator motion verify --output outputs/NOME_RUN
python3 -B -m snowpark_simulator capture capture --config configs/capture/boardslide-32.toml
python3 -B -m snowpark_simulator capture freeze --output outputs/NOME_RUN
python3 -B -m snowpark_simulator capture verify --output outputs/NOME_RUN
```

Questi sono esempi di invocazione: non eseguono automaticamente tutta la pipeline. Consultare `COMMAND --help` prima di ogni workflow. Il confronto neve richiede una scelta esplicita con `--snow` e `--reason`; il termine di un render non seleziona da solo un materiale.

Gli strumenti di analisi restano comandi autonomi, ad esempio:

```sh
python3 -B tools/check_catalog.py --output .local/catalog-check.json
python3 -B tools/encode_preview.py --help
python3 -B tools/prepare_brush_dataset.py --help
```

Le composizioni PNG in `tools/*_evidence.py` usano render reali e dichiarano ridimensionamenti o ritagli. Non devono trasformarsi in ritocco delle evidenze. I preset cork storici esterni al catalogo e i controlli ad hoc superati non fanno più parte del codice attivo.

## Test e stile

```sh
python3 -B -m unittest discover -s tests -v
ruff check .
ruff format --check .
```

L’integrazione continua (CI) è configurata per i controlli host con Python 3.11 e 3.13, senza Blender, asset privati o backend. Le azioni sono fissate a commit ufficiali; definire il workflow non equivale a eseguirlo su GitHub. Ruff è uno strumento di sviluppo, non una dipendenza della scena. Per un controllo reale di Blender usare il profilo `smoke.toml`: quattro piccoli render e verifica indipendente del `.blend` riaperto. `tests/blender_imports.py`, eseguito esplicitamente tramite Blender, controlla inoltre gli import delle librerie riordinate senza creare oggetti. Queste non sono prove di navigazione GUI o qualità estetica.

Mantenere i calcoli in funzioni prive di accesso al filesystem quando possibile. Aggiungere test per invarianti osservabili: continuità, direzione della pendenza, isolamento degli output e propagazione degli errori. Evitare test che copiano semplicemente le formule dell'implementazione.

Non importare `bpy` nei workflow host. Non avviare processi all'importazione. Per nuove operazioni usare `blender_command`, `run_logged`, `within` e `new_run`; per i controlli degli input usare eccezioni esplicite, non `assert`, che Python può disattivare con `-O`.

I generatori Blender storici mantengono alcuni assert interni, import di compatibilità e assegnazioni con effetti di creazione oggetti. Il refactor ne conserva il comportamento; le eccezioni di lint sono circoscritte a questi file. Una modifica algoritmica richiede una verifica specifica della scena, oltre ai test host.

## File locali e immagini pubbliche

`outputs/`, `.tools/`, riferimenti personali e `.local/` sono esclusi da Git. I report cronologici, tre preset storici e due vecchie immagini del README sono conservati localmente sotto `.local/refactor-archive/`, con mappa degli spostamenti. Le scene validate non vengono eliminate dalla pulizia del codice.

Il README pubblica due immagini: panoramica della scena e anteprima del movimento. Il mosaico dei risultati e la sequenza statica di pose non vengono duplicati nella presentazione del progetto. Nessuna cancellazione riscrive la storia Git: alleggerire i commit già pubblicati richiederebbe un'operazione separata.
