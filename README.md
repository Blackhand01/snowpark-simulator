# Snowpark Simulator

Genera uno snowpark 3D in Blender e immagini sintetiche con condizioni note e ripetibili. Serve a studiare acquisizione da più camere e ricostruzione **Gaussian Splatting**: una rappresentazione 3D basata su primitive gaussiane.

Il progetto comprende terreno innevato, rail, atleta articolato e movimento sugli sci. È una scena procedurale per esperimenti visivi: il movimento è definito dalle rotazioni delle ossa, senza una simulazione fisica calibrata.

![Vista sintetica dello snowpark con atleta e rail](docs/images/snowpark-overview.png)

## Avvio rapido

Richiede **Python ≥ 3.11** e **Blender**. Non occorrono pacchetti Python aggiuntivi per generare l'ambiente statico.

```sh
git clone https://github.com/Blackhand01/snowpark-simulator.git
cd snowpark-simulator
python3 -B -m snowpark_simulator scene --without-reference
```

Il comando costruisce l'ambiente statico iniziale, salva `snowpark.blend`, produce quattro render e riapre il file in un processo Blender separato per verificarlo. L'atleta e il movimento dell'immagine dimostrativa richiedono i workflow successivi.

Blender viene cercato tramite `--blender`, la variabile `SNOWPARK_BLENDER`, il `PATH`, quindi l'app macOS:

```sh
python3 -B -m snowpark_simulator scene --without-reference --blender /percorso/a/blender
python3 -B -m snowpark_simulator --help
python3 -B -m snowpark_simulator motion --help
```

Per un controllo veloce dell'installazione:

```sh
python3 -B -m snowpark_simulator scene --without-reference --config configs/scene/smoke.toml
```

Ogni costruzione crea una nuova directory `outputs/<fase>-<UTC>/`, con scena, render, configurazione congelata, sorgenti, log e verifiche. I vecchi output non vengono sovrascritti. La navigazione interattiva in Blender è una verifica distinta da quella automatica.

## Movimento dimostrativo

![Anteprima del boardslide: ingresso, rotazione sul rail e uscita](docs/images/boardslide-preview.gif)

Anteprima Workbench con materiali semplificati, esportata a 20 fotogrammi al secondo; il movimento dura circa cinque secondi. Mostra l'articolazione e la sequenza, non la qualità di un render finale. La scena animata e i dataset non sono inclusi nel clone.

## Comandi e configurazioni

| Comando | Responsabilità |
| --- | --- |
| `scene` | Ambiente statico e verifica indipendente |
| `terrain` | Morfologia della pista e contatto con il terreno |
| `athlete` | Confronto neve e atleta statico riggato |
| `appearance`, `presentation` | Abbigliamento, accessori e leggibilità della neve |
| `motion` | Costruzione, controllo e anteprima del movimento |
| `capture` | Immagini da camere calibrate, posa congelata e verifica |
| `conditions` | Varianti controllate di luce, neve, foschia e occlusione |
| `brush` | Backend opzionale di Gaussian Splatting |

Le configurazioni sono raggruppate in `configs/scene/`, `motion/`, `capture/`, `conditions/` e `tricks/`. **Quelle avanzate contengono percorsi e hash di esecuzioni storiche**: occorre fornire gli input e aggiornare i profili prima di usarle. Il clone riproduce direttamente solo la demo statica, non l'intera catena mostrata nelle immagini.

## Struttura e sviluppo

```text
snowpark_simulator/   CLI, workflow e gestione delle esecuzioni
scripts/             Generatori, librerie e verificatori eseguiti da Blender
tools/               Analisi, valutazione e composizione delle evidenze
configs/             Parametri della scena e degli esperimenti
tests/               Test automatici senza Blender
assets/              Texture e manifest di provenienza
docs/                Architettura, guida di sviluppo e due anteprime
outputs/             Risultati locali, esclusi da Git
```

[Architettura e responsabilità](docs/architecture.md) · [Sviluppo, workflow e test](docs/development.md) · [Asset e licenze](ASSET_CREDITS.md)

```sh
python3 -B -m unittest discover -s tests -v
ruff check .
ruff format --check .
```

## Limiti e dipendenze opzionali

Verificato nello sviluppo con Blender 5.2.2 LTS su macOS Apple Silicon; altre piattaforme richiedono una verifica specifica. Geometria, abiti, neve e movimento sono approssimazioni artistiche, senza calibrazione di forze, attrito o biomeccanica. Il personaggio resta visibilmente sintetico.

Gli strumenti in `tools/` possono richiedere NumPy, Pillow, Matplotlib e scikit-image; video e confronto temporale richiedono FFmpeg/FFprobe. Brush v0.3.0 è opzionale, separato e non scaricato automaticamente. Nessun add-on Blender è obbligatorio.

Geometria e personaggio sono procedurali. Le texture **Snow 01**, Rob Tuytel / Poly Haven, sono CC0: [fonte e manifest](ASSET_CREDITS.md). Nessuna fotografia personale è distribuita come texture.
