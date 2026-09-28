# Gestore Tornei Svizzero — Cloud

Questa repository contiene l'implementazione in ambiente cloud di un gestore di tornei automatizzato basato sul sistema Svizzero.

## Struttura della repository

```
.github/
  workflows/
    deploy.yaml
aws-infrastructure/
  main.tf
  eks.tf
k8s-cloud/
  apps.yaml
frontend/
  Dockerfile
  index.html
player-service/
  Dockerfile
  index.js
  package.json
tournament-service/
  Dockerfile
  app.py
  requirements.txt
```

La repository contiene diverse directory principali:

- **`.github/workflows`** — gestione della pipeline CI/CD
- **`aws-infrastructure`** — sorgenti Terraform per il provisioning dell'infrastruttura cloud
- **`k8s-cloud`** — manifest Kubernetes
- **`frontend`, `player-service`, `tournament-service`** — sorgenti da containerizzare per i microservizi dell'applicazione

## Funzionamento del progetto cloud

Il progetto simula il funzionamento di un'infrastruttura distribuita su Amazon Web Services (AWS). La gestione dell'infrastruttura è affidata a Terraform, mentre il deployment dell'applicazione è orchestrato su un cluster Amazon EKS (Elastic Kubernetes Service).

L'applicazione è un Gestore di Tornei a microservizi, composto da:

- **Front-end web**
- **Back-end anagrafico** (Node.js), appoggiato su database relazionale PostgreSQL (AWS RDS)
- **Back-end per la logica matematica** (Python), appoggiato su database NoSQL (Amazon DynamoDB)

## Setup delle credenziali (AWS e GitHub)

Le repository e le pipeline sono ospitate su GitHub. È quindi necessario impostare le credenziali AWS per permettere a Terraform e GitHub Actions di interfacciarsi con il cloud provider:

1. Creare un utente IAM dalla console AWS con permessi di amministratore.
2. Generare una nuova Access Key e Secret Access Key per l'utente.
3. Su GitHub, andare in **Settings → Secrets and variables → Actions** e cliccare su **New repository secret**.
4. Inserire `AWS_ACCESS_KEY_ID` e `AWS_SECRET_ACCESS_KEY` con i rispettivi valori recuperati al punto 2.

Una volta registrati i secret, la pipeline GitHub Actions sarà autorizzata a modificare l'infrastruttura ed effettuare il push delle immagini Docker.

## Infrastruttura (Terraform)

La cartella `aws-infrastructure` permette la creazione dell'infrastruttura base e dei database gestiti. La sua applicazione genera:

- Un cluster Kubernetes gestito (Amazon EKS), alla versione specificata (es. 1.30)
- Un database relazionale Amazon RDS (PostgreSQL), tier `db.t3.micro`, per i giocatori
- Una tabella Amazon DynamoDB con `PAY_PER_REQUEST`, per la gestione dinamica dei tornei
- I security group necessari per consentire il traffico

## Repository dell'applicazione e Kubernetes

Le cartelle `frontend`, `player-service` e `tournament-service` contengono i sorgenti e i Dockerfile necessari per la costruzione delle immagini dei microservizi.

La cartella `k8s-cloud` contiene i manifest Kubernetes con le seguenti specifiche:

- Deployment delle applicazioni di front-end e dei due back-end
- Specifiche delle replicas per gestire lo scheduling sui nodi limitati di AWS
- Il Service `LoadBalancer` per il frontend, per l'indirizzamento del traffico pubblico verso l'applicazione web

Il workflow in `.github/workflows/deploy.yaml` gestisce il deployment automatico dell'applicazione:

1. Effettua il login su AWS e Docker Hub.
2. Costruisce le immagini Docker (es. `tournament-service:latest`) e le carica sul registry.
3. Applica i manifest Kubernetes con `kubectl apply` per aggiornare i pod sul cluster EKS.
4. Si attiva automaticamente ad ogni push sul branch `main`.

## Costruire l'infrastruttura

Per costruire l'infrastruttura, spostarsi nella cartella `aws-infrastructure` e inizializzare Terraform:

```bash
cd aws-infrastructure
terraform init
terraform apply -auto-approve
```

L'operazione richiede circa 15-20 minuti per EKS e RDS.

Una volta creata l'infrastruttura, basta pushare le modifiche del codice applicativo su GitHub:

```bash
git add .
git commit -m "..."
git push
```

Affinché i pod siano esposti correttamente, recuperare l'indirizzo IP pubblico del sito con:

```bash
kubectl get svc frontend-service
```

## Gestione e pulizia del database

Per azzerare l'applicativo (ad esempio durante le fasi di testing), è possibile svuotare il database PostgreSQL collegandosi direttamente al cloud. È importante specificare il parametro `PGSSLMODE=require` per rispettare le policy di sicurezza di AWS.

Per effettuare un clean completo della tabella giocatori e resettare gli ID:

```bash
PGPASSWORD="<PASSWORD>" PGSSLMODE=require psql -h <INDIRIZZO_RDS_AWS> -U <UTENTE> -d playersdb -c "TRUNCATE TABLE players RESTART IDENTITY;"
```

> Non salvare credenziali in chiaro in questo file. Recuperare utente e password dal Secret Kubernetes o dai parametri Terraform correnti.

La tabella dei tornei su DynamoDB, avendo un design NoSQL basato su UUID univoci generati ad ogni nuovo torneo, non necessita di pulizia manuale.

## Distruzione del progetto

Per distruggere il progetto ed evitare costi indesiderati su AWS:

1. Distruggere i servizi Kubernetes esposti (come il Load Balancer), per scollegarli dall'infrastruttura:

   ```bash
   kubectl delete -f k8s-cloud/apps.yaml
   ```

2. Distruggere l'intera infrastruttura cloud:

   ```bash
   cd aws-infrastructure
   terraform destroy -auto-approve
   ```
