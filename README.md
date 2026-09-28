uesta repository contiene l'implementazione in ambiente cloud di un gestore di tornei automatizzato basato sul sistema Svizzero.

Struttura della repository

├── .github
│ 
└── workflows
│ 
└── deploy.yaml
├── aws-infrastructure
│ 
├── main.tf
│ └── eks.tf
├── k8s-cloud
│ └── apps.yaml
├── frontend
│ ├── Dockerfile
│ └── index.html
├── player-service
│ ├── Dockerfile
│ ├── index.js
│ └── package.json
└── tournament-service
├── Dockerfile
├── app.py
└── requirements.txt
La repository contiene diverse directory principali:

.github/workflows, impiegato per la gestione della pipeline CI/CD;

aws-infrastructure, che contiene i sorgenti Terraform per il provisioning dell'infrastruttura cloud;

k8s-cloud, per i manifest Kubernetes;

Le restanti cartelle (frontend, player-service, tournament-service) contengono i sorgenti da containerizzare per i microservizi dell'applicazione.

Funzionamento del progetto cloud
Il progetto cloud simula il funzionamento di un'infrastruttura distribuita su Amazon Web Services (AWS). La gestione dell'infrastruttura è affidata a Terraform, mentre il deployment dell'applicazione è orchestrato su un cluster Amazon EKS (Elastic Kubernetes Service). L'applicazione è un Gestore di Tornei a microservizi, con front-end web, back-end anagrafico (Node.js) appoggiato su database relazionale PostgreSQL (su AWS RDS) e un back-end per la logica matematica (Python) appoggiato su database NoSQL (Amazon DynamoDB).

Setup delle credenziali (AWS e GitHub)
Le repository e le pipeline sono ospitate su GitHub. Pertanto, è necessario impostare le credenziali AWS per permettere a Terraform e GitHub Actions di interfacciarsi con il cloud provider.
Per fare ciò basta eseguire i seguenti step:

creare un utente IAM dalla console AWS con permessi di amministratore;

generare una nuova Access Key e Secret Access Key per l'utente;

andare su GitHub in Settings > Secrets and variables > Actions e cliccare su New repository secret;

inserire AWS_ACCESS_KEY_ID e AWS_SECRET_ACCESS_KEY con i rispettivi valori recuperati precedentemente.

Una volta registrati i secret, la pipeline GitHub Actions sarà autorizzata a modificare l'infrastruttura ed effettuare il push delle immagini Docker.

Infrastruttura (Terraform)
La cartella aws-infrastructure permette la creazione dell'infrastruttura base e dei database gestiti. La struttura include i file .tf necessari per il provisioning.
La creazione dell'infrastruttura porta alla generazione dei seguenti elementi:

un cluster Kubernetes gestito (Amazon EKS) alla versione specificata (es. 1.30);

un database relazionale Amazon RDS (PostgreSQL) tier db.t3.micro per i giocatori;

una tabella Amazon DynamoDB con PAY_PER_REQUEST per la gestione dinamica dei tornei;

i security group necessari per consentire il traffico.

Repository dell'applicazione e Kubernetes
Le cartelle frontend, player-service e tournament-service contengono i sorgenti e i Dockerfile necessari per la costruzione delle immagini dei microservizi.
La cartella k8s-cloud, invece, contiene i manifest Kubernetes con le specifiche seguenti:

deployment delle applicazioni di front-end e dei due back-end;

specifiche delle replicas per gestire lo scheduling sui nodi limitati di AWS;

il servizio LoadBalancer per il frontend, al fine di definire l'indirizzamento del traffico pubblico verso l'applicazione web.

Il workflow presente in .github/workflows/deploy.yaml permette il deployment automatico dell'applicazione. Nel dettaglio:

effettua il login su AWS e Docker Hub;

costruisce le immagini Docker (es. tournament-service:latest) e le carica sul registry;

applica i manifest Kubernetes usando kubectl apply per aggiornare i pod sul cluster EKS;

il workflow si attiva automaticamente ad ogni push sul branch main.

Costruire l'infrastruttura
Per costruire l'infrastruttura, è sufficiente spostarsi nella cartella aws-infrastructure e inizializzare Terraform:

Bash
cd aws-infrastructure
terraform init
terraform apply -auto-approve
Una volta creata l'infrastruttura (l'operazione richiede circa 15-20 minuti per EKS e RDS), basta pushare le modifiche del codice applicativo su GitHub usando i comandi git (git add, git commit e git push). Affinché i pod siano esposti correttamente, lanciare il seguente comando per recuperare l'indirizzo IP pubblico del sito:

Bash
kubectl get svc frontend-service
Gestione e pulizia del Database
Per azzerare l'applicativo (ad esempio durante le fasi di testing), è possibile svuotare il database PostgreSQL collegandosi direttamente al cloud. È importante specificare il parametro PGSSLMODE=require per rispettare le policy di sicurezza di AWS.

Per effettuare un clean completo della tabella giocatori e resettare gli ID:

Bash
PGPASSWORD="password123" PGSSLMODE=require psql -h <INDIRIZZO_RDS_AWS> -U admin -d playersdb -c "TRUNCATE TABLE players RESTART IDENTITY;"
La tabella dei tornei su DynamoDB, avendo un design NoSQL basato su UUID univoci generati ad ogni nuovo torneo, non necessita di pulizia manuale.

Distruzione del progetto
Per distruggere il progetto ed evitare costi indesiderati su AWS, è sufficiente:

distruggere i servizi Kubernetes esposti (come il Load Balancer) per scollegarli dall'infrastruttura:

Bash
kubectl delete -f k8s-cloud/apps.yaml
distruggere l'intera infrastruttura cloud lanciando il comando nella directory di Terraform:

Bash
cd aws-infrastructure
terraform destroy -auto-approve
