import * as React from "react";
import styles from './index.css';

export default function EmailCoordination() {
  return (
    <div className={styles.container}>
      <header className={styles.header}>
        Evento para Aprovação
      </header>
      <main className={styles.content}>
        <div>Olá Coordenação</div>
        <div className={styles.description}>
          O evento com os dados abaixo:
        </div>
        <img
          loading="lazy"
          src="https://cdn.builder.io/api/v1/image/assets/TEMP/646e3d9e8d552b88b0f729cf05ce4d8f52fcce5f5abc0aecde491eb356f1f922?placeholderIfAbsent=true&apiKey=ae36e2726dea4582bb6ce927bc59ba75"
          className={styles.eventImage}
          alt="Detalhes do evento para aprovação"
        />
        <button 
          className={styles.actionButton}
          onClick={() => {}}
          tabIndex={0}
        >
          Request Changes
        </button>
        <div className={styles.imageContainer} />
      </main>
    </div>
  );
}